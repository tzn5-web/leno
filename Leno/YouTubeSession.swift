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

    weak var webView: WKWebView?

    private var retryCount = 0
    private let maxRetries = 3
    private var remoteTargets: [(MPRemoteCommand, Any)] = []
    private var notificationTokens: [NSObjectProtocol] = []
    private var wasPlayingBeforeInterruption = false
    private var wantsPlayback = false
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

    func loadHome() {
        load(Self.homeURL)
    }

    func reloadFromHome() {
        retryCount = 0
        loadHome()
    }

    func goBack() {
        guard let webView, webView.canGoBack else { return }
        webView.goBack()
    }

    func goForward() {
        guard let webView, webView.canGoForward else { return }
        webView.goForward()
    }

    func reload() {
        guard let webView else { return }

        if webView.url == nil {
            loadHome()
        } else {
            markLoading()
            webView.reload()
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

                if self.webView?.url == nil {
                    self.loadHome()
                } else {
                    self.webView?.reload()
                }
            }
        }
    }

    func applicationWillResignActive() {
        activateAudioSession()

        if isPlaying {
            wantsPlayback = true
        }

        if wantsPlayback {
            evaluate(
                PlaybackBridgeScript.prepareBackgroundCall
            )
        }

        updateNowPlaying()
    }

    func applicationDidEnterBackground() {
        appIsBackground = true
        frozenRepairWorkItem?.cancel()
        frozenRepairWorkItem = nil
        activateAudioSession()

        if isPlaying {
            wantsPlayback = true
        }

        evaluate(
            PlaybackBridgeScript.enterBackgroundCall
        )

        if wantsPlayback {
            evaluate(
                PlaybackBridgeScript.keepAliveCall
            )
        }

        updateNowPlaying()
    }

    func applicationDidBecomeActive() {
        appIsBackground = false
        activateAudioSession()

        evaluate(
            PlaybackBridgeScript.resumeForegroundCall
        )
    }

    func togglePlayback() {
        if wantsPlayback || isPlaying {
            pause()
        } else {
            play()
        }
    }

    func play() {
        wantsPlayback = true
        activateAudioSession()

        evaluate(
            PlaybackBridgeScript.playCall
        )

        updateNowPlaying()
    }

    func pause() {
        wantsPlayback = false

        evaluate(
            PlaybackBridgeScript.pauseCall
        )

        isPlaying = false
        updateNowPlaying()
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
        evaluate(PlaybackBridgeScript.requestPiPCall)
    }

    func requestFullscreen() {
        evaluate(PlaybackBridgeScript.requestFullscreenCall)
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
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
            self.wantsPlayback = bridgeWantsPlayback
            self.isReallyHidden = bridgeReallyHidden
            self.transitionArmed = bridgeTransitionArmed
            self.presentationMode = bridgePresentationMode
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
                mediaExists &&
                (
                    !paused ||
                    (
                        bridgeWantsPlayback &&
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
                bridgeWantsPlayback &&
                !self.appIsBackground &&
                !bridgeReallyHidden &&
                newInDOM &&
                newReadyState == 0

            self.updateFrozenMediaRepair(
                needed: frozenForegroundMedia
            )

            if mediaExists {
                self.updateNowPlaying()
            } else if !bridgeReallyHidden {
                self.wantsPlayback = false
                MPNowPlayingInfoCenter.default().nowPlayingInfo = nil
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
              !isLoading,
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
                  self.wantsPlayback,
                  self.hasMedia,
                  self.mediaElementInDOM,
                  self.mediaReadyState == 0,
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
            wantsPlayback

        print(
            "Repairing frozen WebKit media: " +
            "videoID=\(bridgeVideoID) " +
            "resume=\(pendingRepairResumeTime ?? 0)"
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

    private func load(_ url: URL) {
        DispatchQueue.main.async { [weak self] in
            guard let self,
                  let webView = self.webView else {
                return
            }

            self.markLoading()
            webView.load(URLRequest(url: url))
        }
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
            wasPlayingBeforeInterruption =
                isPlaying || wantsPlayback

        case .ended:
            activateAudioSession()

            let rawOptions =
                (userInfo[
                    AVAudioSessionInterruptionOptionKey
                ] as? NSNumber)?.uintValue ?? 0

            let options =
                AVAudioSession.InterruptionOptions(rawValue: rawOptions)

            if wasPlayingBeforeInterruption &&
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
            guard let self, self.hasMedia else {
                return .commandFailed
            }

            self.play()
            return .success
        }

        center.pauseCommand.isEnabled = true
        addRemoteTarget(center.pauseCommand) { [weak self] _ in
            guard let self, self.hasMedia else {
                return .commandFailed
            }

            self.pause()
            return .success
        }

        center.togglePlayPauseCommand.isEnabled = true
        addRemoteTarget(center.togglePlayPauseCommand) { [weak self] _ in
            guard let self, self.hasMedia else {
                return .commandFailed
            }

            self.togglePlayback()
            return .success
        }

        center.skipForwardCommand.isEnabled = true
        center.skipForwardCommand.preferredIntervals = [15]

        addRemoteTarget(center.skipForwardCommand) { [weak self] _ in
            guard let self, self.hasMedia else {
                return .commandFailed
            }

            self.seek(by: 15)
            return .success
        }

        center.skipBackwardCommand.isEnabled = true
        center.skipBackwardCommand.preferredIntervals = [15]

        addRemoteTarget(center.skipBackwardCommand) { [weak self] _ in
            guard let self, self.hasMedia else {
                return .commandFailed
            }

            self.seek(by: -15)
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

            self.seek(to: event.positionTime)
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
        guard hasMedia else { return }

        let reportingPlaying =
            isPlaying ||
            (
                wantsPlayback &&
                (
                    appIsBackground ||
                    isReallyHidden ||
                    transitionArmed
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
