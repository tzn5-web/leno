import AVFoundation
import Combine
import MediaPlayer

@MainActor
final class PlayerModel: ObservableObject {
    let player = AVPlayer()

    @Published private(set) var hasItem = false
    @Published private(set) var isPlaying = false

    private var timeControlObservation: NSKeyValueObservation?
    private var remoteCommandTargetsInstalled = false

    init() {
        configureAudioSession()
        observePlayer()
        configureRemoteCommands()
    }

    deinit {
        timeControlObservation?.invalidate()
    }

    func load(urlString: String) {
        guard let url = URL(string: urlString) else { return }

        let item = AVPlayerItem(url: url)
        player.replaceCurrentItem(with: item)
        hasItem = true
        updateNowPlaying(title: url.lastPathComponent.isEmpty ? "Leno Media" : url.lastPathComponent)
        player.play()
    }

    func togglePlayback() {
        if player.timeControlStatus == .playing {
            player.pause()
        } else {
            player.play()
        }
    }

    func seek(by seconds: Double) {
        let current = player.currentTime()
        let target = CMTimeGetSeconds(current) + seconds
        guard target.isFinite else { return }

        let clamped = max(0, target)
        player.seek(to: CMTime(seconds: clamped, preferredTimescale: 600))
    }

    private func configureAudioSession() {
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playback, mode: .moviePlayback)
            try session.setActive(true)
        } catch {
            print("Audio session configuration failed: \(error.localizedDescription)")
        }
    }

    private func observePlayer() {
        timeControlObservation = player.observe(
            \.timeControlStatus,
            options: [.initial, .new]
        ) { [weak self] player, _ in
            Task { @MainActor in
                self?.isPlaying = player.timeControlStatus == .playing
                self?.refreshNowPlayingState()
            }
        }
    }

    private func configureRemoteCommands() {
        guard !remoteCommandTargetsInstalled else { return }
        remoteCommandTargetsInstalled = true

        let center = MPRemoteCommandCenter.shared()

        center.playCommand.addTarget { [weak self] _ in
            Task { @MainActor in self?.player.play() }
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
        var info = MPNowPlayingInfoCenter.default().nowPlayingInfo ?? [:]
        info[MPNowPlayingInfoPropertyPlaybackRate] = isPlaying ? 1.0 : 0.0

        let elapsed = CMTimeGetSeconds(player.currentTime())
        if elapsed.isFinite {
            info[MPNowPlayingInfoPropertyElapsedPlaybackTime] = elapsed
        }

        MPNowPlayingInfoCenter.default().nowPlayingInfo = info
    }
}
