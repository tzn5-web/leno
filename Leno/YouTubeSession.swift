import Foundation
import AVFoundation
import Combine
import MediaPlayer
import WebKit

final class YouTubeSession: NSObject, ObservableObject, WKScriptMessageHandler {
    enum State: Equatable {
        case idle
        case loading
        case ready
        case recovering(Int)
        case failed(String)
    }

    @Published private(set) var state: State = .idle
    @Published private(set) var title = "YouTube"
    @Published private(set) var isPlaying = false
    @Published private(set) var hasMedia = false
    @Published private(set) var currentTime: Double = 0
    @Published private(set) var duration: Double = 0
    @Published private(set) var canGoBack = false
    @Published private(set) var canGoForward = false
    @Published private(set) var currentURL: URL?
    @Published private(set) var progress: Double = 0
    @Published private(set) var isLoading = false
    @Published private(set) var isPlayerPresented = false
    @Published private(set) var playerAvailable = false

    weak var webView: WKWebView?
    weak var browserWebView: WKWebView?

    private var playerWebViewReady = false
    private var pendingPlayerURL: URL?
    private var currentPlayerURL: URL?
    private var retryCount = 0
    private let maxRetries = 3
    private var remoteTargets: [(MPRemoteCommand, Any)] = []
    private var notificationTokens: [NSObjectProtocol] = []
    private var wasPlayingBeforeInterruption = false
    private var wantsPlayback = false
    private var desiredPlayback = false
    private var explicitPauseActive = false
    private var systemInterruptionActive = false
    private var hasPlaybackContext = false
    private var appIsBackground = false
    private var isReallyHidden = false
    private var transitionArmed = false
    private var presentationMode = "inline"
    private var bridgeVideoID = ""
    private var mediaReadyState = 0
    private var mediaNetworkState = 0
    private var mediaElementInDOM = false
    private var lastMediaHealthSignature = ""
    private var lastStablePlaybackTime: Double = 0
    private var frozenRepairWorkItem: DispatchWorkItem?
    private var lastFrozenRepairDate = Date.distantPast
    private var pendingRepairResumeTime: Double?
    private var pendingRepairShouldPlay = false
    private var foregroundRepairWindowUntil = Date.distantPast
    private var nativeMediaPlaybackState: WKMediaPlaybackState = .none
    private var pendingWebProcessRecovery = false
    private var transitionRecoveryGeneration = 0
    private var transitionRecoveryDeadline = Date.distantPast
    private var transitionRecoveryWorkItems: [DispatchWorkItem] = []
    private var lastTransitionReason = ""

    private static let homeURL = URL(string: "https://m.youtube.com/")!

    override init() {
        super.init()
        configureAudioSession()
        configureRemoteCommands()
        observeAudioSession()
    }

    deinit {
        for (command, token) in remoteTargets {
            command.removeTarget(token)
        }

        notificationTokens.forEach {
            NotificationCenter.default.removeObserver($0)
        }

        MPNowPlayingInfoCenter.default().nowPlayingInfo = nil
    }

    func attach(webView: WKWebView) {
        self.webView = webView
    }

    func attachBrowser(webView: WKWebView) {
        self.browserWebView = webView
    }

    func playerDidBecomeReady() {
        playerWebViewReady = true

        if let pendingPlayerURL {
            self.pendingPlayerURL = nil
            loadPlayer(
                pendingPlayerURL
            )
        }
    }

    func openVideo(_ url: URL) {
        guard isPlaybackURL(url) else {
            showBrowser(url)
            return
        }

        currentPlayerURL = url
        pendingPlayerURL = nil
        playerAvailable = true
        isPlayerPresented = true
        explicitPauseActive = false
        desiredPlayback = true
        wantsPlayback = true
        cancelTransitionRecovery()

        if playerWebViewReady {
            loadPlayer(url)
        } else {
            pendingPlayerURL = url
        }
    }

    func showBrowser(_ url: URL? = nil) {
        isPlayerPresented = false

        guard let browserWebView else {
            return
        }

        if let url {
            browserWebView.load(
                URLRequest(
                    url: url
                )
            )
        } else if browserWebView.url == nil {
            browserWebView.load(
                URLRequest(
                    url: Self.homeURL
                )
            )
        }
    }

    func showPlayer() {
        guard playerAvailable else {
            return
        }

        isPlayerPresented = true
    }

    func loadBrowserHome() {
        showBrowser(
            Self.homeURL
        )
    }

    func loadHome() {
        loadBrowserHome()
    }

    func reloadFromHome() {
        retryCount = 0
        loadBrowserHome()
    }

    func shouldOpenInPlayer(
        _ url: URL
    ) -> Bool {
        isPlaybackURL(url)
    }

    func shouldRoutePlayerNavigationToBrowser(
        _ url: URL
    ) -> Bool {
        guard currentPlayerURL != nil else {
            return false
        }

        let scheme =
            url.scheme?
                .lowercased() ?? ""

        guard scheme == "http" ||
              scheme == "https" else {
            return false
        }

        return !isPlaybackURL(url)
    }

    func routePlayerNavigationToBrowser(
        _ url: URL
    ) {
        showBrowser(url)
    }

    func goBack() {
        if isPlayerPresented {
            showBrowser()
            return
        }

        guard let browserWebView,
              browserWebView.canGoBack else {
            return
        }

        browserWebView.goBack()
    }

    func goForward() {
        guard !isPlayerPresented,
              let browserWebView,
              browserWebView.canGoForward else {
            return
        }

        browserWebView.goForward()
    }

    func reload() {
        if isPlayerPresented {
            guard let webView else {
                return
            }

            if webView.url == nil ||
               webView.url?.scheme == "about" {
                if let currentPlayerURL {
                    loadPlayer(
                        currentPlayerURL
                    )
                }
            } else {
                markLoading()
                webView.reload()
            }

            return
        }

        guard let browserWebView else {
            return
        }

        if browserWebView.url == nil {
            loadBrowserHome()
        } else {
            browserWebView.reload()
        }
    }

    func updateNavigationState(
        canGoBack: Bool,
        canGoForward: Bool,
        url: URL?,
        progress: Double,
        isLoading: Bool
    ) {
        DispatchQueue.main.async {
            self.canGoBack = canGoBack
            self.canGoForward = canGoForward
            self.currentURL = url

            if let url,
               self.isPlaybackURL(
                    url
               ) {
                self.currentPlayerURL =
                    url
                self.playerAvailable =
                    true
            }
            self.progress = min(max(progress, 0), 1)
            self.isLoading = isLoading
        }
    }

    func markLoading() {
        DispatchQueue.main.async {
            self.state = .loading
            self.isLoading = true
        }
    }

    func markReady() {
        DispatchQueue.main.async {
            self.retryCount = 0
            self.state = .ready
            self.isLoading = false
            self.progress = 1
            self.resumeAfterFrozenMediaRepairIfNeeded()
        }
    }

    func recover(after error: Error? = nil) {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }

            if self.appIsBackground {
                self.pendingWebProcessRecovery = true
                return
            }

            guard self.retryCount < self.maxRetries else {
                self.isLoading = false
                self.state = .failed(
                    error?.localizedDescription ??
                    "YouTube could not be loaded."
                )
                return
            }

            self.retryCount += 1
            let attempt = self.retryCount
            self.state = .recovering(attempt)

            let delay = min(1.2 * Double(attempt), 3.6)

            DispatchQueue.main.asyncAfter(
                deadline: .now() + delay
            ) { [weak self] in
                guard let self else { return }

                if self.webView?.url == nil ||
                   self.webView?.url?.scheme == "about" {
                    if let currentPlayerURL =
                            self.currentPlayerURL {
                        self.loadPlayer(
                            currentPlayerURL
                        )
                    }
                } else {
                    self.webView?.reload()
                }
            }
        }
    }

    func applicationWillResignActive() {
        activateAudioSession()

        if (
            isPlaying ||
            wantsPlayback
        ) &&
           !explicitPauseActive {
            desiredPlayback = true
            wantsPlayback = true
        }

        if shouldRecoverDesiredPlayback {
            evaluate(
                PlaybackBridgeScript.prepareBackgroundCall
            )

            beginTransitionRecovery(
                reason: "inactive"
            )
        }

        updateNowPlaying()
    }

    func applicationDidEnterBackground() {
        appIsBackground = true
        foregroundRepairWindowUntil =
            .distantPast
        frozenRepairWorkItem?.cancel()
        frozenRepairWorkItem = nil
        activateAudioSession()

        if (
            isPlaying ||
            wantsPlayback
        ) &&
           !explicitPauseActive {
            desiredPlayback = true
            wantsPlayback = true
        }

        evaluate(
            PlaybackBridgeScript.enterBackgroundCall
        )

        if shouldRecoverDesiredPlayback {
            evaluate(
                PlaybackBridgeScript.keepAliveCall
            )

            beginTransitionRecovery(
                reason: "background"
            )
        }

        updateNowPlaying()
    }

    func applicationDidBecomeActive() {
        let returningFromBackground =
            appIsBackground

        appIsBackground = false

        foregroundRepairWindowUntil =
            returningFromBackground
                ? Date().addingTimeInterval(6)
                : .distantPast

        activateAudioSession()

        if pendingWebProcessRecovery {
            pendingWebProcessRecovery = false

            if hasPlaybackContext {
                pendingRepairResumeTime =
                    max(
                        lastStablePlaybackTime,
                        currentTime
                    )

                pendingRepairShouldPlay =
                    desiredPlayback &&
                    !explicitPauseActive
            }

            if webView?.url == nil ||
               webView?.url?.scheme == "about" {
                if let currentPlayerURL {
                    loadPlayer(
                        currentPlayerURL
                    )
                }
            } else {
                markLoading()
                webView?.reload()
            }

            return
        }

        if explicitPauseActive {
            cancelTransitionRecovery()

            evaluate(
                PlaybackBridgeScript.pauseCall
            )

            updateNowPlaying()
        } else {
            evaluate(
                PlaybackBridgeScript.resumeForegroundCall
            )

            if returningFromBackground &&
               shouldRecoverDesiredPlayback {
                beginTransitionRecovery(
                    reason: "foreground"
                )
            }
        }
    }

    func togglePlayback() {
        if wantsPlayback || isPlaying {
            pause()
        } else {
            play()
        }
    }

    func play() {
        explicitPauseActive = false
        desiredPlayback = true
        wantsPlayback = true
        cancelTransitionRecovery()
        activateAudioSession()

        guard let webView else {
            evaluate(
                PlaybackBridgeScript.playCall
            )

            updateNowPlaying()
            return
        }

        webView.setAllMediaPlaybackSuspended(
            false
        ) { [weak self] in
            guard let self else {
                return
            }

            self.evaluate(
                PlaybackBridgeScript.playCall
            )

            self.beginTransitionRecovery(
                reason: "manual-play"
            )

            self.updateNowPlaying()
        }
    }

    func pause() {
        explicitPauseActive = true
        desiredPlayback = false
        wantsPlayback = false
        wasPlayingBeforeInterruption = false
        isPlaying = false
        cancelTransitionRecovery()

        evaluate(
            PlaybackBridgeScript.pauseCall
        )

        if let webView {
            webView.setAllMediaPlaybackSuspended(
                true
            ) { [weak self] in
                self?.updateNowPlaying()
            }
        } else {
            updateNowPlaying()
        }
    }

    func seek(by seconds: Double) {
        let safeSeconds = max(-60, min(60, seconds))

        evaluate(
            PlaybackBridgeScript.seekByCall(
                seconds: safeSeconds
            )
        )
    }

    func seek(to seconds: Double) {
        let safeSeconds = max(0, seconds)

        evaluate(
            PlaybackBridgeScript.seekToCall(
                seconds: safeSeconds
            )
        )
    }

    func requestPictureInPicture() {
        if shouldRecoverDesiredPlayback {
            beginTransitionRecovery(
                reason: "pip-request"
            )
        }

        evaluate(
            PlaybackBridgeScript.requestPiPCall
        )
    }

    func requestFullscreen() {
        evaluate(PlaybackBridgeScript.requestFullscreenCall)
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        if message.name == "browserOpenVideo" {
            guard let body =
                    message.body as?
                        [String: Any],
                  let value =
                    body["url"] as?
                        String,
                  let url =
                    URL(
                        string:
                            value
                    ) else {
                return
            }

            DispatchQueue.main.async {
                self.openVideo(url)
            }

            return
        }

        if message.name == "browseRequest" {
            guard let body =
                    message.body as?
                        [String: Any],
                  let value =
                    body["url"] as?
                        String,
                  let url =
                    URL(
                        string:
                            value
                    ) else {
                return
            }

            DispatchQueue.main.async {
                self.showBrowser(url)
            }

            return
        }

        if message.name == "transitionEvent" {
            guard let body =
                    message.body as?
                        [String: Any],
                  let reason =
                    body["reason"] as?
                        String,
                  !reason.isEmpty else {
                return
            }

            DispatchQueue.main.async {
                guard self
                    .shouldRecoverDesiredPlayback else {
                    return
                }

                self.beginTransitionRecovery(
                    reason: reason
                )
            }

            return
        }

        if message.name == "mediaIntent" {
            guard let body =
                    message.body as?
                        [String: Any],
                  let intent =
                    body["intent"] as?
                        String else {
                return
            }

            DispatchQueue.main.async {
                switch intent {
                case "play":
                    self.play()

                case "pause":
                    self.pause()

                default:
                    break
                }
            }

            return
        }

        guard message.name == "mediaState",
              let body = message.body as? [String: Any] else {
            return
        }

        let newTitle = (body["title"] as? String)?
            .trimmingCharacters(in: .whitespacesAndNewlines)

        let paused = body["paused"] as? Bool ?? true
        let mediaExists = body["hasMedia"] as? Bool ?? false
        let bridgeWantsPlayback =
            body["wantsPlayback"] as? Bool ?? false
        let bridgeReallyHidden =
            body["realHidden"] as? Bool ?? false
        let bridgeTransitionArmed =
            body["transitionArmed"] as? Bool ?? false
        let bridgePresentationMode =
            body["presentationMode"] as? String ?? "inline"
        let newVideoID =
            body["videoID"] as? String ?? ""
        let newReadyState =
            Int(numericValue(body["readyState"]))
        let newNetworkState =
            Int(numericValue(body["networkState"]))
        let newInDOM =
            body["inDOM"] as? Bool ?? false
        let newCurrentTime = numericValue(body["currentTime"])
        let newDuration = numericValue(body["duration"])

        DispatchQueue.main.async {
            self.title = newTitle?.isEmpty == false
                ? newTitle!
                : "YouTube"

            self.hasMedia = mediaExists

            if mediaExists &&
               !paused &&
               !self.explicitPauseActive &&
               !self.appIsBackground &&
               !bridgeReallyHidden &&
               !bridgeTransitionArmed {
                self.desiredPlayback = true
            }

            let preserveNativeIntent =
                self.desiredPlayback &&
                !self.explicitPauseActive &&
                (
                    self.isTransitionRecoveryActive ||
                    self.appIsBackground ||
                    self.isLoading ||
                    bridgeReallyHidden ||
                    bridgeTransitionArmed
                )

            let effectiveExplicitPause =
                self.explicitPauseActive

            let effectiveWantsPlayback =
                effectiveExplicitPause
                    ? false
                    : (
                        self.desiredPlayback ||
                        bridgeWantsPlayback ||
                        preserveNativeIntent
                    )

            self.wantsPlayback =
                effectiveWantsPlayback

            if mediaExists {
                self.hasPlaybackContext = true
                self.playerAvailable = true
            }
            self.isReallyHidden = bridgeReallyHidden
            self.transitionArmed = bridgeTransitionArmed

            let previousPresentationMode =
                self.presentationMode

            self.presentationMode =
                bridgePresentationMode

            if previousPresentationMode !=
                bridgePresentationMode &&
               (
                   previousPresentationMode ==
                       "picture-in-picture" ||
                   bridgePresentationMode ==
                       "picture-in-picture"
               ) &&
               self.shouldRecoverDesiredPlayback {
                self.beginTransitionRecovery(
                    reason:
                        bridgePresentationMode ==
                            "picture-in-picture"
                            ? "pip-enter"
                            : "pip-exit"
                )
            }

            self.bridgeVideoID = newVideoID
            self.mediaReadyState = newReadyState
            self.mediaNetworkState = newNetworkState
            self.mediaElementInDOM = newInDOM

            let healthSignature =
                "\(newVideoID)|\(newReadyState)|\(newNetworkState)|\(newInDOM)|\(bridgeReallyHidden)"

            if healthSignature != self.lastMediaHealthSignature {
                self.lastMediaHealthSignature = healthSignature

                if mediaExists &&
                   !bridgeReallyHidden &&
                   (
                       newReadyState == 0 ||
                       !newInDOM
                   ) {
                    print(
                        "Web media health warning: " +
                        "videoID=\(newVideoID) " +
                        "readyState=\(newReadyState) " +
                        "networkState=\(newNetworkState) " +
                        "inDOM=\(newInDOM)"
                    )
                }
            }

            self.isPlaying =
                !effectiveExplicitPause &&
                mediaExists &&
                (
                    !paused ||
                    (
                        effectiveWantsPlayback &&
                        (
                            bridgeReallyHidden ||
                            bridgeTransitionArmed
                        )
                    )
                )

            self.currentTime = max(0, newCurrentTime)
            self.duration = max(0, newDuration)

            if mediaExists &&
               newReadyState > 0 &&
               newCurrentTime > 0 {
                self.lastStablePlaybackTime =
                    newCurrentTime
            }

            let frozenForegroundMedia =
                mediaExists &&
                effectiveWantsPlayback &&
                !self.isTransitionRecoveryActive &&
                !self.appIsBackground &&
                !bridgeReallyHidden &&
                newInDOM &&
                (
                    newReadyState == 0 ||
                    self.nativeMediaPlaybackState ==
                        .suspended
                )

            self.updateFrozenMediaRepair(
                needed: frozenForegroundMedia
            )

            if mediaExists {
                self.updateNowPlaying()
            } else if !effectiveWantsPlayback &&
                      !bridgeReallyHidden &&
                      !bridgeTransitionArmed &&
                      !self.appIsBackground {
                self.wantsPlayback = false
                self.hasPlaybackContext = false
                MPNowPlayingInfoCenter.default().nowPlayingInfo = nil
            }
        }
    }

    private var shouldRecoverDesiredPlayback:
        Bool
    {
        desiredPlayback &&
        !explicitPauseActive &&
        !systemInterruptionActive &&
        hasPlaybackContext
    }

    private var isTransitionRecoveryActive:
        Bool
    {
        shouldRecoverDesiredPlayback &&
        Date() <=
            transitionRecoveryDeadline
    }

    private func cancelTransitionRecovery() {
        transitionRecoveryGeneration += 1
        transitionRecoveryDeadline =
            .distantPast
        lastTransitionReason = ""

        transitionRecoveryWorkItems
            .forEach {
                $0.cancel()
            }

        transitionRecoveryWorkItems
            .removeAll()
    }

    private func beginTransitionRecovery(
        reason: String
    ) {
        guard shouldRecoverDesiredPlayback,
              webView != nil else {
            cancelTransitionRecovery()
            return
        }

        transitionRecoveryGeneration += 1
        let generation =
            transitionRecoveryGeneration

        lastTransitionReason =
            reason

        let delays:
            [TimeInterval] = [
                0,
                0.08,
                0.20,
                0.45,
                0.90,
                1.60,
                2.80
            ]

        transitionRecoveryDeadline =
            Date()
                .addingTimeInterval(
                    3.4
                )

        transitionRecoveryWorkItems
            .forEach {
                $0.cancel()
            }

        transitionRecoveryWorkItems
            .removeAll()

        frozenRepairWorkItem?
            .cancel()

        frozenRepairWorkItem = nil

        for delay in delays {
            let workItem =
                DispatchWorkItem {
                    [weak self] in

                    self?
                        .attemptTransitionRecovery(
                            generation:
                                generation,
                            reason:
                                reason
                        )
                }

            transitionRecoveryWorkItems
                .append(
                    workItem
                )

            DispatchQueue.main
                .asyncAfter(
                    deadline:
                        .now() +
                        delay,
                    execute:
                        workItem
                )
        }
    }

    private func attemptTransitionRecovery(
        generation: Int,
        reason: String
    ) {
        guard generation ==
                transitionRecoveryGeneration,
              shouldRecoverDesiredPlayback,
              Date() <=
                transitionRecoveryDeadline,
              let webView else {
            return
        }

        webView.requestMediaPlaybackState {
            [weak self, weak webView]
            mediaState in

            DispatchQueue.main.async {
                guard let self,
                      let webView,
                      generation ==
                        self
                            .transitionRecoveryGeneration,
                      self
                        .shouldRecoverDesiredPlayback,
                      Date() <=
                        self
                            .transitionRecoveryDeadline else {
                    return
                }

                self.nativeMediaPlaybackState =
                    mediaState

                switch mediaState {
                case .playing:
                    self.wantsPlayback =
                        true
                    self.isPlaying =
                        true
                    self.updateFrozenMediaRepair(
                        needed:
                            false
                    )

                case .paused,
                     .suspended,
                     .none:
                    self.wantsPlayback =
                        true

                    webView
                        .setAllMediaPlaybackSuspended(
                            false
                        ) { [weak self] in
                            DispatchQueue.main.async {
                                guard let self,
                                      generation ==
                                        self
                                            .transitionRecoveryGeneration,
                                      self
                                        .shouldRecoverDesiredPlayback else {
                                    return
                                }

                                self.evaluate(
                                    PlaybackBridgeScript
                                        .playCall
                                )

                                self.evaluate(
                                    PlaybackBridgeScript
                                        .keepAliveCall
                                )

                                self.updateNowPlaying()
                            }
                        }

                @unknown default:
                    break
                }

                print(
                    "V8 transition recovery: " +
                    "reason=\(reason) " +
                    "state=\(mediaState.rawValue) " +
                    "generation=\(generation)"
                )
            }
        }
    }

    private func updateFrozenMediaRepair(
        needed: Bool
    ) {
        guard needed else {
            frozenRepairWorkItem?.cancel()
            frozenRepairWorkItem = nil
            return
        }

        guard frozenRepairWorkItem == nil,
              !isTransitionRecoveryActive,
              !isLoading,
              Date() <=
                foregroundRepairWindowUntil,
              Date().timeIntervalSince(
                lastFrozenRepairDate
              ) > 15 else {
            return
        }

        let workItem = DispatchWorkItem {
            [weak self] in

            guard let self else {
                return
            }

            self.frozenRepairWorkItem = nil

            guard !self.appIsBackground,
                  Date() <=
                    self.foregroundRepairWindowUntil,
                  self.wantsPlayback,
                  self.hasPlaybackContext,
                  (
                      (
                          self.hasMedia &&
                          self.mediaElementInDOM &&
                          self.mediaReadyState == 0
                      ) ||
                      self.nativeMediaPlaybackState ==
                          .suspended
                  ),
                  !self.isLoading,
                  Date().timeIntervalSince(
                    self.lastFrozenRepairDate
                  ) > 15 else {
                return
            }

            self.repairFrozenWebMedia()
        }

        frozenRepairWorkItem = workItem

        DispatchQueue.main.asyncAfter(
            deadline: .now() + 2.0,
            execute: workItem
        )
    }

    private func repairFrozenWebMedia() {
        guard let webView,
              webView.url != nil else {
            return
        }

        lastFrozenRepairDate = Date()
        pendingRepairResumeTime =
            max(
                lastStablePlaybackTime,
                currentTime
            )
        pendingRepairShouldPlay =
            desiredPlayback &&
            !explicitPauseActive

        print(
            "Repairing frozen WebKit media: " +
            "videoID=\(bridgeVideoID) " +
            "resume=\(pendingRepairResumeTime ?? 0) " +
            "wkState=\(nativeMediaPlaybackState.rawValue)"
        )

        markLoading()
        webView.reload()
    }

    private func resumeAfterFrozenMediaRepairIfNeeded() {
        guard let resumeTime =
                pendingRepairResumeTime else {
            return
        }

        let shouldPlay =
            pendingRepairShouldPlay

        pendingRepairResumeTime = nil
        pendingRepairShouldPlay = false

        for delay in [0.25, 0.7, 1.4, 2.4] {
            DispatchQueue.main.asyncAfter(
                deadline: .now() + delay
            ) { [weak self] in
                self?.evaluate(
                    PlaybackBridgeScript
                        .restoreAfterReloadCall(
                            seconds: resumeTime,
                            shouldPlay: shouldPlay
                        )
                )
            }
        }
    }

    private func loadPlayer(
        _ url: URL
    ) {
        DispatchQueue.main.async {
            [weak self] in

            guard let self,
                  let webView =
                    self.webView else {
                return
            }

            self.currentPlayerURL =
                url

            webView.setAllMediaPlaybackSuspended(
                false
            ) { [weak self, weak webView] in
                guard let self,
                      let webView else {
                    return
                }

                self.markLoading()

                webView.load(
                    URLRequest(
                        url: url
                    )
                )
            }
        }
    }

    private func isYouTubeURL(
        _ url: URL
    ) -> Bool {
        let host =
            url.host?
                .lowercased() ?? ""

        return host == "youtube.com" ||
               host == "www.youtube.com" ||
               host == "m.youtube.com" ||
               host == "youtu.be"
    }

    private func isPlaybackURL(
        _ url: URL
    ) -> Bool {
        guard isYouTubeURL(url) else {
            return false
        }

        let host =
            url.host?
                .lowercased() ?? ""

        if host == "youtu.be" {
            return !url.path
                .split(separator: "/")
                .isEmpty
        }

        let path =
            url.path

        if path == "/watch" {
            return URLComponents(
                url: url,
                resolvingAgainstBaseURL:
                    false
            )?
            .queryItems?
            .contains {
                $0.name == "v" &&
                !($0.value ?? "")
                    .isEmpty
            } == true
        }

        return path.hasPrefix(
            "/shorts/"
        ) ||
        path.hasPrefix(
            "/live/"
        )
    }

    private func evaluate(_ script: String) {
        let work: () -> Void = { [weak self] in
            guard let webView = self?.webView else {
                return
            }

            webView.evaluateJavaScript(script) { _, error in
                if let error {
                    print(
                        "JavaScript bridge error: \(error.localizedDescription)"
                    )
                }
            }
        }

        if Thread.isMainThread {
            work()
        } else {
            DispatchQueue.main.async(execute: work)
        }
    }

    private func numericValue(_ value: Any?) -> Double {
        if let number = value as? NSNumber {
            return number.doubleValue
        }

        if let number = value as? Double {
            return number
        }

        return 0
    }

    private func configureAudioSession() {
        do {
            let audioSession = AVAudioSession.sharedInstance()

            try audioSession.setCategory(
                .playback,
                mode: .moviePlayback,
                options: []
            )

            try audioSession.setActive(true)
        } catch {
            print(
                "Audio session configuration failed: \(error.localizedDescription)"
            )
        }
    }

    private func activateAudioSession() {
        do {
            try AVAudioSession.sharedInstance().setActive(true)
        } catch {
            print(
                "Audio session activation failed: \(error.localizedDescription)"
            )
        }
    }

    private func observeAudioSession() {
        let token = NotificationCenter.default.addObserver(
            forName: AVAudioSession.interruptionNotification,
            object: AVAudioSession.sharedInstance(),
            queue: .main
        ) { [weak self] notification in
            self?.handleAudioInterruption(notification)
        }

        notificationTokens.append(token)
    }

    private func handleAudioInterruption(
        _ notification: Notification
    ) {
        guard let userInfo = notification.userInfo,
              let rawType =
                (userInfo[AVAudioSessionInterruptionTypeKey] as? NSNumber)?
                    .uintValue,
              let type =
                AVAudioSession.InterruptionType(rawValue: rawType) else {
            return
        }

        switch type {
        case .began:
            systemInterruptionActive = true
            cancelTransitionRecovery()

            wasPlayingBeforeInterruption =
                isPlaying || wantsPlayback

            evaluate(
                PlaybackBridgeScript
                    .beginSystemInterruptionCall
            )

        case .ended:
            systemInterruptionActive = false
            activateAudioSession()

            evaluate(
                PlaybackBridgeScript
                    .endSystemInterruptionCall
            )

            let rawOptions =
                (userInfo[
                    AVAudioSessionInterruptionOptionKey
                ] as? NSNumber)?.uintValue ?? 0

            let options =
                AVAudioSession.InterruptionOptions(rawValue: rawOptions)

            if wasPlayingBeforeInterruption &&
               desiredPlayback &&
               !explicitPauseActive &&
               options.contains(.shouldResume) {
                play()
            }

            wasPlayingBeforeInterruption = false

        @unknown default:
            break
        }
    }

    private func configureRemoteCommands() {
        let center = MPRemoteCommandCenter.shared()

        center.playCommand.isEnabled = true
        addRemoteTarget(center.playCommand) { [weak self] _ in
            guard let self,
                  self.hasPlaybackContext else {
                return .commandFailed
            }

            DispatchQueue.main.async {
                self.play()
            }

            return .success
        }

        center.pauseCommand.isEnabled = true
        addRemoteTarget(center.pauseCommand) { [weak self] _ in
            guard let self,
                  self.hasPlaybackContext else {
                return .commandFailed
            }

            DispatchQueue.main.async {
                self.pause()
            }

            return .success
        }

        center.togglePlayPauseCommand.isEnabled = true
        addRemoteTarget(center.togglePlayPauseCommand) { [weak self] _ in
            guard let self,
                  self.hasPlaybackContext else {
                return .commandFailed
            }

            DispatchQueue.main.async {
                self.togglePlayback()
            }

            return .success
        }

        center.skipForwardCommand.isEnabled = true
        center.skipForwardCommand.preferredIntervals = [15]

        addRemoteTarget(center.skipForwardCommand) { [weak self] _ in
            guard let self, self.hasMedia else {
                return .commandFailed
            }

            DispatchQueue.main.async {
                self.seek(by: 15)
            }

            return .success
        }

        center.skipBackwardCommand.isEnabled = true
        center.skipBackwardCommand.preferredIntervals = [15]

        addRemoteTarget(center.skipBackwardCommand) { [weak self] _ in
            guard let self, self.hasMedia else {
                return .commandFailed
            }

            DispatchQueue.main.async {
                self.seek(by: -15)
            }

            return .success
        }

        center.changePlaybackPositionCommand.isEnabled = true

        addRemoteTarget(
            center.changePlaybackPositionCommand
        ) { [weak self] event in
            guard let self,
                  self.hasMedia,
                  let event =
                    event as? MPChangePlaybackPositionCommandEvent else {
                return .commandFailed
            }

            let position =
                event.positionTime

            DispatchQueue.main.async {
                self.seek(
                    to: position
                )
            }

            return .success
        }
    }

    private func addRemoteTarget(
        _ command: MPRemoteCommand,
        handler: @escaping (
            MPRemoteCommandEvent
        ) -> MPRemoteCommandHandlerStatus
    ) {
        let token = command.addTarget(handler: handler)
        remoteTargets.append((command, token))
    }

    private func updateNowPlaying() {
        guard hasMedia ||
              hasPlaybackContext else {
            return
        }

        let reportingPlaying =
            !explicitPauseActive &&
            (
                isPlaying ||
                (
                    wantsPlayback &&
                    (
                        appIsBackground ||
                        isReallyHidden ||
                        transitionArmed
                    )
                )
            )

        var info: [String: Any] = [
            MPMediaItemPropertyTitle: title,
            MPNowPlayingInfoPropertyPlaybackRate:
                reportingPlaying ? 1.0 : 0.0,
            MPNowPlayingInfoPropertyDefaultPlaybackRate: 1.0,
            MPNowPlayingInfoPropertyElapsedPlaybackTime:
                currentTime
        ]

        if duration > 0 {
            info[MPMediaItemPropertyPlaybackDuration] =
                duration
        }

        let nowPlaying =
            MPNowPlayingInfoCenter.default()

        nowPlaying.nowPlayingInfo = info
        nowPlaying.playbackState =
            reportingPlaying ? .playing : .paused
    }
}
