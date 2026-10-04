import AVFoundation
import Combine
import MediaPlayer
import UIKit
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
    private var backgroundArmed = false

    private static let homeURL = URL(string: "https://m.youtube.com/")!

    override init() {
        super.init()
        configureAudioSession()
        configureRemoteCommands()
        observeAudioSession()
        observeApplicationLifecycle()
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

        webView.setAllMediaPlaybackSuspended(
            false,
            completionHandler: nil
        )
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
        guard hasMedia else {
            return
        }

        if wantsPlayback || isPlaying {
            backgroundArmed = true
            wantsPlayback = true
        }

        activateAudioSession()

        webView?.setAllMediaPlaybackSuspended(
            false
        ) { [weak self] in
            guard let self,
                  self.backgroundArmed else {
                return
            }

            self.evaluate(
                PlaybackBridgeScript.armBackgroundCall
            )

            self.evaluate(
                PlaybackBridgeScript.keepAliveCall
            )
        }

        updateNowPlaying()
    }

    func applicationDidEnterBackground() {
        guard hasMedia else {
            return
        }

        if wantsPlayback || isPlaying ||
           backgroundArmed {
            backgroundArmed = true
            wantsPlayback = true
        }

        activateAudioSession()

        webView?.setAllMediaPlaybackSuspended(
            false
        ) { [weak self] in
            guard let self,
                  self.backgroundArmed else {
                return
            }

            self.evaluate(
                PlaybackBridgeScript.armBackgroundCall
            )

            self.evaluate(
                PlaybackBridgeScript.keepAliveCall
            )
        }

        updateNowPlaying()
    }

    func applicationDidBecomeActive() {
        activateAudioSession()

        webView?.setAllMediaPlaybackSuspended(
            false,
            completionHandler: nil
        )

        evaluate(
            PlaybackBridgeScript.disarmBackgroundCall
        )

        backgroundArmed = false

        if wantsPlayback && hasMedia {
            evaluate(
                PlaybackBridgeScript.userPlayCall
            )
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
        wantsPlayback = true
        activateAudioSession()

        webView?.setAllMediaPlaybackSuspended(
            false,
            completionHandler: nil
        )

        evaluate(
            PlaybackBridgeScript.userPlayCall
        )
    }

    func pause() {
        wantsPlayback = false
        backgroundArmed = false

        evaluate(
            PlaybackBridgeScript.userPauseCall
        )

        updateNowPlaying()
    }

    func seek(by seconds: Double) {
        let safeSeconds = max(-60, min(60, seconds))

        evaluate("""
        (() => {
          const video = document.querySelector("video");
          if (!video) return false;

          const duration = Number.isFinite(video.duration)
            ? video.duration
            : Number.POSITIVE_INFINITY;

          video.currentTime = Math.max(
            0,
            Math.min(duration, video.currentTime + \(safeSeconds))
          );

          return true;
        })();
        """)
    }

    func seek(to seconds: Double) {
        let safeSeconds = max(0, seconds)

        evaluate("""
        (() => {
          const video = document.querySelector("video");
          if (!video) return false;

          const duration = Number.isFinite(video.duration)
            ? video.duration
            : Number.POSITIVE_INFINITY;

          video.currentTime = Math.max(
            0,
            Math.min(duration, \(safeSeconds))
          );

          return true;
        })();
        """)
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
        let newCurrentTime = numericValue(body["currentTime"])
        let newDuration = numericValue(body["duration"])

        DispatchQueue.main.async {
            self.title = newTitle?.isEmpty == false
                ? newTitle!
                : "YouTube"

            self.hasMedia = mediaExists
            self.isPlaying = mediaExists && !paused
            self.currentTime = max(0, newCurrentTime)
            self.duration = max(0, newDuration)

            let appState =
                UIApplication.shared.applicationState

            if mediaExists && !paused {
                self.wantsPlayback = true
            } else if mediaExists &&
                      paused &&
                      appState == .active &&
                      !self.backgroundArmed {
                self.wantsPlayback = false
            }

            if mediaExists {
                self.updateNowPlaying()
            } else if appState == .active {
                self.wantsPlayback = false
                MPNowPlayingInfoCenter.default().nowPlayingInfo = nil
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
        DispatchQueue.main.async { [weak self] in
            self?.webView?.evaluateJavaScript(script) { _, error in
                if let error {
                    print(
                        "JavaScript bridge error: \(error.localizedDescription)"
                    )
                }
            }
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

    private func observeApplicationLifecycle() {
        let center = NotificationCenter.default

        let resign = center.addObserver(
            forName:
                UIApplication.willResignActiveNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.applicationWillResignActive()
        }

        let background = center.addObserver(
            forName:
                UIApplication.didEnterBackgroundNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.applicationDidEnterBackground()
        }

        let active = center.addObserver(
            forName:
                UIApplication.didBecomeActiveNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.applicationDidBecomeActive()
        }

        notificationTokens.append(contentsOf: [
            resign,
            background,
            active
        ])
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
            wasPlayingBeforeInterruption = isPlaying

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

        var info: [String: Any] = [
            MPMediaItemPropertyTitle: title,
            MPNowPlayingInfoPropertyPlaybackRate:
                isPlaying ? 1.0 : 0.0,
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
            isPlaying ? .playing : .paused
    }
}
