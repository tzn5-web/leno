import AVFoundation
import Combine
import MediaPlayer
import UIKit
import WebKit

final class YouTubeSession:
    NSObject,
    ObservableObject,
    WKScriptMessageHandler
{
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

    private var remoteTargets:
        [(MPRemoteCommand, Any)] = []

    private var notificationTokens:
        [NSObjectProtocol] = []

    private var wasPlayingBeforeInterruption = false
    private var wantsPlayback = false
    private var backgroundArmed = false
    private var nativeHandoffActive = false
    private var currentVideoID: String?

    private let backgroundAudio =
        BackgroundAudioHandoff()

    private static let homeURL =
        URL(
            string:
                "https://m.youtube.com/"
        )!

    override init() {
        super.init()

        configureAudioSession()
        configureBackgroundAudioCallbacks()
        configureRemoteCommands()
        observeAudioSession()
        observeApplicationLifecycle()
    }

    deinit {
        for (command, token)
        in remoteTargets {
            command.removeTarget(
                token
            )
        }

        notificationTokens.forEach {
            NotificationCenter.default
                .removeObserver(
                    $0
                )
        }

        MPNowPlayingInfoCenter
            .default()
            .nowPlayingInfo = nil
    }

    func attach(
        webView: WKWebView
    ) {
        self.webView = webView

        webView
            .setAllMediaPlaybackSuspended(
                false,
                completionHandler: nil
            )
    }

    func loadHome() {
        load(
            Self.homeURL
        )
    }

    func reloadFromHome() {
        retryCount = 0
        loadHome()
    }

    func goBack() {
        guard let webView,
              webView.canGoBack else {
            return
        }

        webView.goBack()
    }

    func goForward() {
        guard let webView,
              webView.canGoForward else {
            return
        }

        webView.goForward()
    }

    func reload() {
        guard let webView else {
            return
        }

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
            self.canGoBack =
                canGoBack

            self.canGoForward =
                canGoForward

            self.currentURL =
                url

            self.progress =
                min(
                    max(
                        progress,
                        0
                    ),
                    1
                )

            self.isLoading =
                isLoading
        }
    }

    func markLoading() {
        DispatchQueue.main.async {
            self.state =
                .loading

            self.isLoading =
                true
        }
    }

    func markReady() {
        DispatchQueue.main.async {
            self.retryCount = 0
            self.state = .ready
            self.isLoading = false
            self.progress = 1
        }
    }

    func recover(
        after error: Error? = nil
    ) {
        DispatchQueue.main.async {
            [weak self] in

            guard let self else {
                return
            }

            guard self.retryCount <
                    self.maxRetries else {
                self.isLoading = false

                self.state =
                    .failed(
                        error?
                            .localizedDescription ??
                        "YouTube could not be loaded."
                    )

                return
            }

            self.retryCount += 1

            let attempt =
                self.retryCount

            self.state =
                .recovering(
                    attempt
                )

            let delay =
                min(
                    1.2 *
                    Double(
                        attempt
                    ),
                    3.6
                )

            DispatchQueue.main
                .asyncAfter(
                    deadline:
                        .now() +
                        delay
                ) {
                    [weak self] in

                    guard let self else {
                        return
                    }

                    if self
                        .webView?
                        .url == nil {
                        self.loadHome()
                    } else {
                        self
                            .webView?
                            .reload()
                    }
                }
        }
    }

    func applicationWillResignActive() {
        guard hasMedia ||
              backgroundAudio
                .hasCandidate else {
            return
        }

        if isPlaying {
            wantsPlayback = true
        }

        backgroundArmed =
            wantsPlayback

        activateAudioSession()

        if beginNativeHandoffIfPossible() {
            updateNowPlaying()
            return
        }

        if wantsPlayback {
            armWebBackgroundFallback()
        }

        updateNowPlaying()
    }

    func applicationDidEnterBackground() {
        if nativeHandoffActive {
            if wantsPlayback {
                backgroundAudio.play()
                isPlaying = true
            }

            updateNowPlaying()
            return
        }

        if wantsPlayback {
            backgroundArmed = true
            activateAudioSession()
            armWebBackgroundFallback()
        }

        updateNowPlaying()
    }

    func applicationDidBecomeActive() {
        activateAudioSession()

        if nativeHandoffActive {
            let resumeTime =
                backgroundAudio
                    .stopForForeground()

            nativeHandoffActive =
                false

            backgroundArmed =
                false

            currentTime =
                resumeTime

            let script =
                PlaybackBridgeScript
                    .resumeFromNativeCall(
                        time:
                            resumeTime,
                        shouldPlay:
                            wantsPlayback
                    )

            webView?
                .setAllMediaPlaybackSuspended(
                    false
                ) { [weak self] in
                    self?
                        .evaluate(
                            script
                        )
                }

            isPlaying =
                wantsPlayback

            updateNowPlaying()
            return
        }

        webView?
            .setAllMediaPlaybackSuspended(
                false,
                completionHandler: nil
            )

        evaluate(
            PlaybackBridgeScript
                .disarmBackgroundCall
        )

        backgroundArmed = false

        if wantsPlayback &&
           hasMedia {
            evaluate(
                PlaybackBridgeScript
                    .userPlayCall
            )
        }

        updateNowPlaying()
    }

    func togglePlayback() {
        if wantsPlayback ||
           isPlaying {
            pause()
        } else {
            play()
        }
    }

    func play() {
        wantsPlayback = true
        activateAudioSession()

        if nativeHandoffActive {
            backgroundAudio.play()
            isPlaying = true
            updateNowPlaying()
            return
        }

        if UIApplication
            .shared
            .applicationState !=
            .active {
            backgroundArmed = true

            if beginNativeHandoffIfPossible() {
                updateNowPlaying()
                return
            }

            armWebBackgroundFallback()
            updateNowPlaying()
            return
        }

        webView?
            .setAllMediaPlaybackSuspended(
                false,
                completionHandler: nil
            )

        evaluate(
            PlaybackBridgeScript
                .userPlayCall
        )

        updateNowPlaying()
    }

    func pause() {
        wantsPlayback = false

        if nativeHandoffActive {
            backgroundAudio.pause()
            isPlaying = false
            updateNowPlaying()
            return
        }

        backgroundArmed = false

        evaluate(
            PlaybackBridgeScript
                .userPauseCall
        )

        isPlaying = false
        updateNowPlaying()
    }

    func seek(
        by seconds: Double
    ) {
        let safeSeconds =
            max(
                -60,
                min(
                    60,
                    seconds
                )
            )

        if nativeHandoffActive {
            backgroundAudio
                .seek(
                    by:
                        safeSeconds
                )

            currentTime =
                backgroundAudio
                    .currentTime

            updateNowPlaying()
            return
        }

        evaluate(
            PlaybackBridgeScript
                .seekByCall(
                    seconds:
                        safeSeconds
                )
        )
    }

    func seek(
        to seconds: Double
    ) {
        let safeSeconds =
            max(
                0,
                seconds
            )

        if nativeHandoffActive {
            backgroundAudio
                .seek(
                    to:
                        safeSeconds
                )

            currentTime =
                safeSeconds

            updateNowPlaying()
            return
        }

        evaluate(
            PlaybackBridgeScript
                .seekToCall(
                    seconds:
                        safeSeconds
                )
        )
    }

    func requestPictureInPicture() {
        evaluate(
            PlaybackBridgeScript
                .requestPiPCall
        )
    }

    func requestFullscreen() {
        evaluate(
            PlaybackBridgeScript
                .requestFullscreenCall
        )
    }

    func userContentController(
        _ userContentController:
            WKUserContentController,
        didReceive message:
            WKScriptMessage
    ) {
        switch message.name {
        case "mediaCandidate":
            handleMediaCandidate(
                message.body
            )

        case "mediaState":
            handleMediaState(
                message.body
            )

        default:
            break
        }
    }

    private func handleMediaCandidate(
        _ rawBody: Any
    ) {
        guard !nativeHandoffActive,
              let body =
                rawBody as?
                [String: Any],
              let rawURL =
                body["url"] as?
                String,
              let url =
                URL(
                    string:
                        rawURL
                ),
              url.scheme?
                .lowercased() ==
                "https" else {
            return
        }

        let videoID =
            normalizedVideoID(
                body["videoID"]
                    as? String
            )

        let candidateTitle =
            cleanTitle(
                body["title"]
                    as? String
            )

        let kind =
            (
                body["kind"]
                    as? String
            )?
            .trimmingCharacters(
                in:
                    .whitespacesAndNewlines
            ) ?? "media"

        backgroundAudio
            .prepare(
                url: url,
                videoID:
                    videoID,
                title:
                    candidateTitle,
                kind:
                    kind
            )
    }

    private func handleMediaState(
        _ rawBody: Any
    ) {
        guard let body =
                rawBody as?
                [String: Any] else {
            return
        }

        let newTitle =
            cleanTitle(
                body["title"]
                    as? String
            )

        let videoID =
            normalizedVideoID(
                body["videoID"]
                    as? String
            )

        let paused =
            body["paused"]
                as? Bool ??
                true

        let mediaExists =
            body["hasMedia"]
                as? Bool ??
                false

        let newCurrentTime =
            numericValue(
                body[
                    "currentTime"
                ]
            )

        let newDuration =
            numericValue(
                body[
                    "duration"
                ]
            )

        DispatchQueue.main.async {
            self.title =
                newTitle

            self.currentVideoID =
                videoID

            self.hasMedia =
                mediaExists

            self.duration =
                max(
                    0,
                    newDuration
                )

            if self.nativeHandoffActive {
                self.currentTime =
                    self.backgroundAudio
                        .currentTime

                self.isPlaying =
                    self.wantsPlayback

                self.updateNowPlaying()
                return
            }

            self.isPlaying =
                mediaExists &&
                !paused

            self.currentTime =
                max(
                    0,
                    newCurrentTime
                )

            let appState =
                UIApplication
                    .shared
                    .applicationState

            if mediaExists &&
               !paused {
                self.wantsPlayback =
                    true
            } else if mediaExists &&
                      paused &&
                      appState ==
                        .active &&
                      !self.backgroundArmed {
                self.wantsPlayback =
                    false
            }

            if mediaExists {
                self.updateNowPlaying()
            } else if appState ==
                        .active {
                self.wantsPlayback =
                    false

                self.currentVideoID =
                    nil

                MPNowPlayingInfoCenter
                    .default()
                    .nowPlayingInfo =
                    nil
            }
        }
    }

    private func beginNativeHandoffIfPossible()
        -> Bool
    {
        guard wantsPlayback,
              backgroundAudio
                .hasCandidate,
              backgroundAudio
                .matches(
                    videoID:
                        currentVideoID
                ) else {
            return false
        }

        evaluate(
            PlaybackBridgeScript
                .prepareNativeHandoffCall
        )

        let started =
            backgroundAudio
                .start(
                    at:
                        currentTime,
                    shouldPlay:
                        true
                )

        guard started else {
            return false
        }

        nativeHandoffActive =
            true

        backgroundArmed =
            true

        isPlaying =
            true

        webView?
            .setAllMediaPlaybackSuspended(
                true,
                completionHandler: nil
            )

        return true
    }

    private func armWebBackgroundFallback() {
        backgroundArmed = true

        webView?
            .setAllMediaPlaybackSuspended(
                false,
                completionHandler: nil
            )

        evaluate(
            PlaybackBridgeScript
                .armBackgroundCall
        )

        evaluate(
            PlaybackBridgeScript
                .keepAliveCall
        )
    }

    private func configureBackgroundAudioCallbacks() {
        backgroundAudio
            .onProgress = {
                [weak self]
                seconds,
                playing in

                guard let self,
                      self
                        .nativeHandoffActive else {
                    return
                }

                self.currentTime =
                    seconds

                self.isPlaying =
                    self.wantsPlayback &&
                    (
                        playing ||
                        self
                            .backgroundAudio
                            .isActive
                    )

                self.updateNowPlaying()
            }

        backgroundAudio
            .onFailure = {
                [weak self]
                message in

                guard let self,
                      self
                        .nativeHandoffActive else {
                    return
                }

                print(
                    "Native background audio failed: \(message)"
                )

                let resumeTime =
                    self
                        .backgroundAudio
                        .stopForForeground()

                self.nativeHandoffActive =
                    false

                self.currentTime =
                    resumeTime

                self.evaluate(
                    PlaybackBridgeScript
                        .resumeFromNativeCall(
                            time:
                                resumeTime,
                            shouldPlay:
                                self.wantsPlayback
                        )
                )

                if self.wantsPlayback {
                    self
                        .armWebBackgroundFallback()
                }

                self.updateNowPlaying()
            }
    }

    private func load(
        _ url: URL
    ) {
        DispatchQueue.main.async {
            [weak self] in

            guard let self,
                  let webView =
                    self.webView else {
                return
            }

            self.markLoading()

            webView.load(
                URLRequest(
                    url:
                        url
                )
            )
        }
    }

    private func evaluate(
        _ script: String
    ) {
        let work: () -> Void = {
            [weak self] in

            guard let self,
                  let webView =
                    self.webView else {
                return
            }

            webView.evaluateJavaScript(
                script
            ) {
                _,
                error in

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
            DispatchQueue.main.async(
                execute: work
            )
        }
    }

    private func numericValue(
        _ value: Any?
    ) -> Double {
        if let number =
            value as?
            NSNumber {
            return number
                .doubleValue
        }

        if let number =
            value as?
            Double {
            return number
        }

        return 0
    }

    private func cleanTitle(
        _ value: String?
    ) -> String {
        let trimmed =
            value?
                .trimmingCharacters(
                    in:
                        .whitespacesAndNewlines
                )

        return trimmed?
            .isEmpty ==
            false
            ? trimmed!
            : "YouTube"
    }

    private func normalizedVideoID(
        _ value: String?
    ) -> String? {
        guard let value else {
            return nil
        }

        let trimmed =
            value
                .trimmingCharacters(
                    in:
                        .whitespacesAndNewlines
                )

        guard trimmed.count ==
                11 else {
            return nil
        }

        let allowed =
            CharacterSet(
                charactersIn:
                    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
            )

        guard trimmed
            .unicodeScalars
            .allSatisfy({
                allowed.contains(
                    $0
                )
            }) else {
            return nil
        }

        return trimmed
    }

    private func configureAudioSession() {
        do {
            let audioSession =
                AVAudioSession
                    .sharedInstance()

            try audioSession
                .setCategory(
                    .playback,
                    mode:
                        .moviePlayback,
                    options: []
                )
        } catch {
            print(
                "Audio session configuration failed: \(error.localizedDescription)"
            )
        }
    }

    private func activateAudioSession() {
        do {
            try AVAudioSession
                .sharedInstance()
                .setActive(
                    true
                )
        } catch {
            print(
                "Audio session activation failed: \(error.localizedDescription)"
            )
        }
    }

    private func observeApplicationLifecycle() {
        let center =
            NotificationCenter
                .default

        let resign =
            center.addObserver(
                forName:
                    UIApplication
                        .willResignActiveNotification,
                object:
                    nil,
                queue:
                    .main
            ) {
                [weak self]
                _ in

                self?
                    .applicationWillResignActive()
            }

        let background =
            center.addObserver(
                forName:
                    UIApplication
                        .didEnterBackgroundNotification,
                object:
                    nil,
                queue:
                    .main
            ) {
                [weak self]
                _ in

                self?
                    .applicationDidEnterBackground()
            }

        let active =
            center.addObserver(
                forName:
                    UIApplication
                        .didBecomeActiveNotification,
                object:
                    nil,
                queue:
                    .main
            ) {
                [weak self]
                _ in

                self?
                    .applicationDidBecomeActive()
            }

        notificationTokens
            .append(
                contentsOf: [
                    resign,
                    background,
                    active
                ]
            )
    }

    private func observeAudioSession() {
        let token =
            NotificationCenter
                .default
                .addObserver(
                    forName:
                        AVAudioSession
                            .interruptionNotification,
                    object:
                        AVAudioSession
                            .sharedInstance(),
                    queue:
                        .main
                ) {
                    [weak self]
                    notification in

                    self?
                        .handleAudioInterruption(
                            notification
                        )
                }

        notificationTokens
            .append(
                token
            )
    }

    private func handleAudioInterruption(
        _ notification:
            Notification
    ) {
        guard let userInfo =
                notification.userInfo,
              let rawType =
                (
                    userInfo[
                        AVAudioSessionInterruptionTypeKey
                    ] as?
                    NSNumber
                )?
                .uintValue,
              let type =
                AVAudioSession
                    .InterruptionType(
                        rawValue:
                            rawType
                    ) else {
            return
        }

        switch type {
        case .began:
            wasPlayingBeforeInterruption =
                wantsPlayback ||
                isPlaying

        case .ended:
            activateAudioSession()

            let rawOptions =
                (
                    userInfo[
                        AVAudioSessionInterruptionOptionKey
                    ] as?
                    NSNumber
                )?
                .uintValue ??
                0

            let options =
                AVAudioSession
                    .InterruptionOptions(
                        rawValue:
                            rawOptions
                    )

            if wasPlayingBeforeInterruption &&
               options.contains(
                    .shouldResume
               ) {
                play()
            }

            wasPlayingBeforeInterruption =
                false

        @unknown default:
            break
        }
    }

    private var hasControllableMedia: Bool {
        hasMedia ||
        nativeHandoffActive ||
        backgroundAudio
            .hasCandidate
    }

    private func configureRemoteCommands() {
        let center =
            MPRemoteCommandCenter
                .shared()

        center.playCommand
            .isEnabled = true

        addRemoteTarget(
            center.playCommand
        ) {
            [weak self]
            _ in

            guard let self,
                  self
                    .hasControllableMedia else {
                return .commandFailed
            }

            self.play()
            return .success
        }

        center.pauseCommand
            .isEnabled = true

        addRemoteTarget(
            center.pauseCommand
        ) {
            [weak self]
            _ in

            guard let self,
                  self
                    .hasControllableMedia else {
                return .commandFailed
            }

            self.pause()
            return .success
        }

        center
            .togglePlayPauseCommand
            .isEnabled = true

        addRemoteTarget(
            center
                .togglePlayPauseCommand
        ) {
            [weak self]
            _ in

            guard let self,
                  self
                    .hasControllableMedia else {
                return .commandFailed
            }

            self.togglePlayback()
            return .success
        }

        center
            .skipForwardCommand
            .isEnabled = true

        center
            .skipForwardCommand
            .preferredIntervals =
            [15]

        addRemoteTarget(
            center
                .skipForwardCommand
        ) {
            [weak self]
            _ in

            guard let self,
                  self
                    .hasControllableMedia else {
                return .commandFailed
            }

            self.seek(
                by: 15
            )

            return .success
        }

        center
            .skipBackwardCommand
            .isEnabled = true

        center
            .skipBackwardCommand
            .preferredIntervals =
            [15]

        addRemoteTarget(
            center
                .skipBackwardCommand
        ) {
            [weak self]
            _ in

            guard let self,
                  self
                    .hasControllableMedia else {
                return .commandFailed
            }

            self.seek(
                by: -15
            )

            return .success
        }

        center
            .changePlaybackPositionCommand
            .isEnabled = true

        addRemoteTarget(
            center
                .changePlaybackPositionCommand
        ) {
            [weak self]
            event in

            guard let self,
                  self
                    .hasControllableMedia,
                  let event =
                    event as?
                    MPChangePlaybackPositionCommandEvent else {
                return .commandFailed
            }

            self.seek(
                to:
                    event
                        .positionTime
            )

            return .success
        }
    }

    private func addRemoteTarget(
        _ command:
            MPRemoteCommand,
        handler:
            @escaping (
                MPRemoteCommandEvent
            ) ->
            MPRemoteCommandHandlerStatus
    ) {
        let token =
            command.addTarget(
                handler:
                    handler
            )

        remoteTargets
            .append(
                (
                    command,
                    token
                )
            )
    }

    private func updateNowPlaying() {
        guard hasControllableMedia else {
            return
        }

        let reportingPlaying =
            nativeHandoffActive
                ? wantsPlayback
                : isPlaying ||
                  (
                    backgroundArmed &&
                    wantsPlayback
                  )

        let elapsed =
            nativeHandoffActive
                ? backgroundAudio
                    .currentTime
                : currentTime

        var info:
            [String: Any] = [
                MPMediaItemPropertyTitle:
                    title,
                MPNowPlayingInfoPropertyPlaybackRate:
                    reportingPlaying
                        ? 1.0
                        : 0.0,
                MPNowPlayingInfoPropertyDefaultPlaybackRate:
                    1.0,
                MPNowPlayingInfoPropertyElapsedPlaybackTime:
                    elapsed
            ]

        if duration > 0 {
            info[
                MPMediaItemPropertyPlaybackDuration
            ] = duration
        }

        let nowPlaying =
            MPNowPlayingInfoCenter
                .default()

        nowPlaying.nowPlayingInfo =
            info

        nowPlaying.playbackState =
            reportingPlaying
                ? .playing
                : .paused
    }
}
