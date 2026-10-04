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
    @Published private(set) var currentTime: Double = 0
    @Published private(set) var duration: Double = 0

    weak var webView: WKWebView?

    private var retryCount = 0
    private let maxRetries = 3
    private var remoteCommandsConfigured = false

    override init() {
        super.init()
        configureAudioSession()
        configureRemoteCommands()
    }

    func attach(webView: WKWebView) {
        self.webView = webView
    }

    func markLoading() {
        DispatchQueue.main.async {
            self.state = .loading
        }
    }

    func markReady() {
        DispatchQueue.main.async {
            self.retryCount = 0
            self.state = .ready
        }
    }

    func recover(after error: Error? = nil) {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }

            guard self.retryCount < self.maxRetries else {
                self.state = .failed(error?.localizedDescription ?? "YouTube could not be loaded.")
                return
            }

            self.retryCount += 1
            let attempt = self.retryCount
            self.state = .recovering(attempt)

            let delay = min(1.5 * Double(attempt), 4.5)
            DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in
                guard let self else { return }

                if self.webView?.url == nil {
                    self.reloadFromHome()
                } else {
                    self.webView?.reload()
                }
            }
        }
    }

    func reloadFromHome() {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }

            self.retryCount = 0
            self.state = .loading

            guard let url = URL(string: "https://www.youtube.com/") else { return }
            self.webView?.load(URLRequest(url: url))
        }
    }

    func togglePlayback() {
        evaluate(#"""
        (() => {
          const v = document.querySelector("video");
          if (!v) return false;
          if (v.paused) {
            v.play().catch(() => {});
          } else {
            v.pause();
          }
          return true;
        })();
        """#)
    }

    func play() {
        evaluate(#"""
        (() => {
          const v = document.querySelector("video");
          if (!v) return false;
          v.play().catch(() => {});
          return true;
        })();
        """#)
    }

    func pause() {
        evaluate(#"""
        (() => {
          const v = document.querySelector("video");
          if (!v) return false;
          v.pause();
          return true;
        })();
        """#)
    }

    func seek(by seconds: Double) {
        let safeSeconds = max(-60, min(60, seconds))
        evaluate("""
        (() => {
          const v = document.querySelector("video");
          if (!v) return false;
          const duration = Number.isFinite(v.duration) ? v.duration : Number.POSITIVE_INFINITY;
          const target = Math.max(0, Math.min(duration, v.currentTime + \(safeSeconds)));
          v.currentTime = target;
          return true;
        })();
        """)
    }

    func seek(to seconds: Double) {
        let safeSeconds = max(0, seconds)
        evaluate("""
        (() => {
          const v = document.querySelector("video");
          if (!v) return false;
          const duration = Number.isFinite(v.duration) ? v.duration : Number.POSITIVE_INFINITY;
          v.currentTime = Math.max(0, Math.min(duration, \(safeSeconds)));
          return true;
        })();
        """)
    }

    func requestPictureInPicture() {
        evaluate(#"""
        (() => {
          const v = document.querySelector("video");
          if (!v) return false;

          if (typeof v.webkitSetPresentationMode === "function") {
            try {
              v.webkitSetPresentationMode("picture-in-picture");
              return true;
            } catch (_) {}
          }

          if (document.pictureInPictureEnabled && v.requestPictureInPicture) {
            v.requestPictureInPicture().catch(() => {});
            return true;
          }

          return false;
        })();
        """#)
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        guard message.name == "mediaState",
              let body = message.body as? [String: Any] else {
            return
        }

        let newTitle = body["title"] as? String ?? "YouTube"
        let paused = body["paused"] as? Bool ?? true
        let newCurrentTime = body["currentTime"] as? Double ?? 0
        let newDuration = body["duration"] as? Double ?? 0

        DispatchQueue.main.async {
            self.title = newTitle.isEmpty ? "YouTube" : newTitle
            self.isPlaying = !paused
            self.currentTime = max(0, newCurrentTime)
            self.duration = max(0, newDuration)
            self.updateNowPlaying()
        }
    }

    private func evaluate(_ script: String) {
        DispatchQueue.main.async { [weak self] in
            self?.webView?.evaluateJavaScript(script) { _, error in
                if let error {
                    print("JavaScript bridge error: \(error.localizedDescription)")
                }
            }
        }
    }

    private func configureAudioSession() {
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playback, mode: .moviePlayback, options: [])
            try session.setActive(true)
        } catch {
            print("YouTube audio session configuration failed: \(error.localizedDescription)")
        }
    }

    private func configureRemoteCommands() {
        guard !remoteCommandsConfigured else { return }
        remoteCommandsConfigured = true

        let center = MPRemoteCommandCenter.shared()

        center.playCommand.isEnabled = true
        center.playCommand.addTarget { [weak self] _ in
            self?.play()
            return .success
        }

        center.pauseCommand.isEnabled = true
        center.pauseCommand.addTarget { [weak self] _ in
            self?.pause()
            return .success
        }

        center.togglePlayPauseCommand.isEnabled = true
        center.togglePlayPauseCommand.addTarget { [weak self] _ in
            self?.togglePlayback()
            return .success
        }

        center.skipForwardCommand.isEnabled = true
        center.skipForwardCommand.preferredIntervals = [15]
        center.skipForwardCommand.addTarget { [weak self] _ in
            self?.seek(by: 15)
            return .success
        }

        center.skipBackwardCommand.isEnabled = true
        center.skipBackwardCommand.preferredIntervals = [15]
        center.skipBackwardCommand.addTarget { [weak self] _ in
            self?.seek(by: -15)
            return .success
        }

        center.changePlaybackPositionCommand.isEnabled = true
        center.changePlaybackPositionCommand.addTarget { [weak self] event in
            guard let event = event as? MPChangePlaybackPositionCommandEvent else {
                return .commandFailed
            }

            self?.seek(to: event.positionTime)
            return .success
        }
    }

    private func updateNowPlaying() {
        var info: [String: Any] = [
            MPMediaItemPropertyTitle: title,
            MPNowPlayingInfoPropertyPlaybackRate: isPlaying ? 1.0 : 0.0,
            MPNowPlayingInfoPropertyDefaultPlaybackRate: 1.0,
            MPNowPlayingInfoPropertyElapsedPlaybackTime: currentTime
        ]

        if duration > 0 {
            info[MPMediaItemPropertyPlaybackDuration] = duration
        }

        let nowPlaying = MPNowPlayingInfoCenter.default()
        nowPlaying.nowPlayingInfo = info
        nowPlaying.playbackState = isPlaying ? .playing : .paused
    }
}
