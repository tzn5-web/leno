import AVFoundation
import Combine
import MediaPlayer

@MainActor
enum PlaybackPhase: Equatable {
    case idle
    case loading
    case ready
    case playing
    case paused
    case stalled
    case failed(String)

    var label: String {
        switch self {
        case .idle: return "Idle"
        case .loading: return "Loading"
        case .ready: return "Ready"
        case .playing: return "Playing"
        case .paused: return "Paused"
        case .stalled: return "Recovering"
        case .failed: return "Playback error"
        }
    }
}

@MainActor
final class PlayerModel: ObservableObject {
    let player = AVPlayer()

    @Published private(set) var hasItem = false
    @Published private(set) var isPlaying = false
    @Published private(set) var phase: PlaybackPhase = .idle
    @Published private(set) var errorMessage: String?

    private var currentURL: URL?
    private var currentTitle = "Leno Media"
    private var retryAttempt = 0
    private let maximumAutomaticRetries = 2

    private var timeControlObservation: NSKeyValueObservation?
    private var itemStatusObservation: NSKeyValueObservation?
    private var notificationTokens: [NSObjectProtocol] = []
    private var remoteCommandTargetsInstalled = false

    init() {
        player.automaticallyWaitsToMinimizeStalling = true
        configureAudioSession()
        observePlayer()
        configureRemoteCommands()
    }

    deinit {
        timeControlObservation?.invalidate()
        itemStatusObservation?.invalidate()
        notificationTokens.forEach(NotificationCenter.default.removeObserver)
    }

    func load(urlString: String) {
        let trimmed = urlString.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: trimmed),
              let scheme = url.scheme?.lowercased(),
              scheme == "https" || scheme == "http" else {
            fail("Use a valid HTTP or HTTPS media URL.")
            return
        }

        currentURL = url
        currentTitle = url.lastPathComponent.isEmpty ? "Leno Media" : url.lastPathComponent
        retryAttempt = 0
        startPlayback(url: url)
    }

    func togglePlayback() {
        guard hasItem else { return }
        if player.timeControlStatus == .playing {
            player.pause()
        } else {
            reactivateAudioSessionIfNeeded()
            player.play()
        }
    }

    func seek(by seconds: Double) {
        guard hasItem else { return }
        let current = CMTimeGetSeconds(player.currentTime())
        guard current.isFinite else { return }

        let duration = CMTimeGetSeconds(player.currentItem?.duration ?? .invalid)
        var target = max(0, current + seconds)
        if duration.isFinite, duration > 0 {
            target = min(target, duration)
        }

        player.seek(
            to: CMTime(seconds: target, preferredTimescale: 600),
            toleranceBefore: .zero,
            toleranceAfter: .zero
        )
    }

    func retry() {
        guard let currentURL else { return }
        retryAttempt = 0
        startPlayback(url: currentURL)
    }

    func clear() {
        player.pause()
        player.replaceCurrentItem(with: nil)
        detachItemObservers()
        currentURL = nil
        hasItem = false
        isPlaying = false
        errorMessage = nil
        phase = .idle
        MPNowPlayingInfoCenter.default().nowPlayingInfo = nil
    }

    private func startPlayback(url: URL) {
        detachItemObservers()
        errorMessage = nil
        phase = .loading
        reactivateAudioSessionIfNeeded()

        let asset = AVURLAsset(url: url, options: [
            AVURLAssetPreferPreciseDurationAndTimingKey: false
        ])
        let item = AVPlayerItem(asset: asset)
        item.preferredForwardBufferDuration = 5

        attachItemObservers(to: item)
        player.replaceCurrentItem(with: item)
        hasItem = true
        updateNowPlaying(title: currentTitle)
        player.play()
    }

    private func attachItemObservers(to item: AVPlayerItem) {
        itemStatusObservation = item.observe(\.status, options: [.initial, .new]) { [weak self] item, _ in
            Task { @MainActor in
                guard let self, self.player.currentItem === item else { return }
                switch item.status {
                case .readyToPlay:
                    self.retryAttempt = 0
                    self.phase = self.player.timeControlStatus == .playing ? .playing : .ready
                    self.refreshNowPlayingState()
                case .failed:
                    self.handlePlaybackFailure(item.error)
                case .unknown:
                    if self.phase != .loading { self.phase = .loading }
                @unknown default:
                    self.handlePlaybackFailure(nil)
                }
            }
        }

        let failed = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemFailedToPlayToEndTime,
            object: item,
            queue: .main
        ) { [weak self] note in
            let error = note.userInfo?[AVPlayerItemFailedToPlayToEndTimeErrorKey] as? Error
            Task { @MainActor in self?.handlePlaybackFailure(error) }
        }

        let stalled = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemPlaybackStalled,
            object: item,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.handlePlaybackStall() }
        }

        notificationTokens.append(contentsOf: [failed, stalled])
    }

    private func detachItemObservers() {
        itemStatusObservation?.invalidate()
        itemStatusObservation = nil
        notificationTokens.forEach(NotificationCenter.default.removeObserver)
        notificationTokens.removeAll()
    }

    private func handlePlaybackStall() {
        guard hasItem else { return }
        phase = .stalled
        Task { [weak self] in
            try? await Task.sleep(for: .seconds(1))
            guard let self, self.hasItem else { return }
            self.player.play()
        }
    }

    private func handlePlaybackFailure(_ error: Error?) {
        let message = error?.localizedDescription ?? "The media stream could not be played."

        guard retryAttempt < maximumAutomaticRetries, let currentURL else {
            fail(message)
            return
        }

        retryAttempt += 1
        phase = .stalled
        errorMessage = "Recovering playback (attempt \(retryAttempt)/\(maximumAutomaticRetries))…"

        let delay = Double(self.retryAttempt)
        Task { [weak self] in
            try? await Task.sleep(for: .seconds(delay))
            guard let self, self.currentURL == currentURL else { return }
            self.startPlayback(url: currentURL)
        }
    }

    private func fail(_ message: String) {
        player.pause()
        isPlaying = false
        errorMessage = message
        phase = .failed(message)
        refreshNowPlayingState()
    }

    private func configureAudioSession() {
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playback, mode: .moviePlayback, options: [])
            try session.setActive(true)
        } catch {
            errorMessage = "Audio session: \(error.localizedDescription)"
        }
    }

    private func reactivateAudioSessionIfNeeded() {
        do {
            try AVAudioSession.sharedInstance().setActive(true)
        } catch {
            errorMessage = "Audio session: \(error.localizedDescription)"
        }
    }

    private func observePlayer() {
        timeControlObservation = player.observe(
            \.timeControlStatus,
            options: [.initial, .new]
        ) { [weak self] player, _ in
            Task { @MainActor in
                guard let self else { return }
                self.isPlaying = player.timeControlStatus == .playing

                switch player.timeControlStatus {
                case .playing:
                    self.phase = .playing
                case .paused:
                    if self.hasItem, !self.phase.isFailure {
                        self.phase = .paused
                    }
                case .waitingToPlayAtSpecifiedRate:
                    if self.hasItem, !self.phase.isFailure {
                        self.phase = .loading
                    }
                @unknown default:
                    break
                }

                self.refreshNowPlayingState()
            }
        }
    }

    private func configureRemoteCommands() {
        guard !remoteCommandTargetsInstalled else { return }
        remoteCommandTargetsInstalled = true

        let center = MPRemoteCommandCenter.shared()

        center.playCommand.addTarget { [weak self] _ in
            Task { @MainActor in
                self?.reactivateAudioSessionIfNeeded()
                self?.player.play()
            }
            return .success
        }

        center.pauseCommand.addTarget { [weak self] _ in
            Task { @MainActor in self?.player.pause() }
            return .success
        }

        center.skipForwardCommand.preferredIntervals = [15]
        center.skipForwardCommand.addTarget { [weak self] _ in
            Task { @MainActor in self?.seek(by: 15) }
            return .success
        }

        center.skipBackwardCommand.preferredIntervals = [15]
        center.skipBackwardCommand.addTarget { [weak self] _ in
            Task { @MainActor in self?.seek(by: -15) }
            return .success
        }
    }

    private func updateNowPlaying(title: String) {
        MPNowPlayingInfoCenter.default().nowPlayingInfo = [
            MPMediaItemPropertyTitle: title,
            MPNowPlayingInfoPropertyPlaybackRate: 1.0
        ]
    }

    private func refreshNowPlayingState() {
        guard hasItem else { return }
        var info = MPNowPlayingInfoCenter.default().nowPlayingInfo ?? [:]
        info[MPNowPlayingInfoPropertyPlaybackRate] = isPlaying ? 1.0 : 0.0

        let elapsed = CMTimeGetSeconds(player.currentTime())
        if elapsed.isFinite {
            info[MPNowPlayingInfoPropertyElapsedPlaybackTime] = elapsed
        }

        let duration = CMTimeGetSeconds(player.currentItem?.duration ?? .invalid)
        if duration.isFinite, duration > 0 {
            info[MPMediaItemPropertyPlaybackDuration] = duration
        }

        MPNowPlayingInfoCenter.default().nowPlayingInfo = info
    }
}

private extension PlaybackPhase {
    var isFailure: Bool {
        if case .failed = self { return true }
        return false
    }
}