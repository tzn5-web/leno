import AVFoundation
import Combine
import MediaPlayer

@MainActor
final class NativePlaybackController: NSObject, ObservableObject {
    enum State: Equatable {
        case idle
        case resolving(String)
        case ready
        case failed(String)
    }

    let player = AVPlayer()

    @Published private(set) var state: State = .idle
    @Published private(set) var isPresented = false
    @Published private(set) var title = "YouTube"
    @Published private(set) var sourceLabel = ""
    @Published private(set) var isPlaying = false
    @Published private(set) var currentTime: Double = 0
    @Published private(set) var duration: Double = 0

    var onWebFallback: ((String) -> Void)?

    private let resolver = StreamResolver()
    private var currentVideoID: String?
    private var candidates: [ResolvedMedia] = []
    private var candidateIndex = 0

    private var resolutionTask: Task<Void, Never>?
    private var readinessTask: Task<Void, Never>?
    private var fallbackTask: Task<Void, Never>?

    private var timeObserver: Any?
    private var timeControlObservation: NSKeyValueObservation?
    private var itemStatusObservation: NSKeyValueObservation?
    private var remoteTargets: [(MPRemoteCommand, Any)] = []
    private var interruptionToken: NSObjectProtocol?
    private var wasPlayingBeforeInterruption = false

    override init() {
        super.init()

        configureAudioSession()
        configurePlayer()
        configureRemoteCommands()
        observeAudioInterruptions()
    }

    deinit {
        resolutionTask?.cancel()
        readinessTask?.cancel()
        fallbackTask?.cancel()

        if let timeObserver {
            player.removeTimeObserver(timeObserver)
        }

        timeControlObservation?.invalidate()
        itemStatusObservation?.invalidate()

        for (command, token) in remoteTargets {
            command.removeTarget(token)
        }

        if let interruptionToken {
            NotificationCenter.default.removeObserver(interruptionToken)
        }
    }

    func open(videoID: String) {
        guard videoID.count == 11 else { return }

        cancelTransientWork()

        currentVideoID = videoID
        candidates = []
        candidateIndex = 0
        isPresented = true
        title = "YouTube"
        sourceLabel = ""
        currentTime = 0
        duration = 0
        state = .resolving("Caut sursă video…")

        player.pause()
        player.replaceCurrentItem(with: nil)
        clearNowPlaying()

        resolutionTask = Task { [weak self] in
            guard let self else { return }

            do {
                let resolved = try await resolver.resolveCandidates(
                    videoID: videoID
                )

                guard !Task.isCancelled,
                      currentVideoID == videoID else {
                    return
                }

                candidates = Array(resolved.prefix(3))
                candidateIndex = 0
                startCurrentCandidate()
            } catch {
                guard !Task.isCancelled,
                      currentVideoID == videoID else {
                    return
                }

                failAndReturnToWeb(
                    message: error.localizedDescription
                )
            }
        }
    }

    func retry() {
        guard let currentVideoID else { return }
        open(videoID: currentVideoID)
    }

    func close() {
        cancelTransientWork()

        player.pause()
        player.replaceCurrentItem(with: nil)
        itemStatusObservation?.invalidate()
        itemStatusObservation = nil

        isPresented = false
        state = .idle
        isPlaying = false
        currentTime = 0
        duration = 0
        sourceLabel = ""
        clearNowPlaying()
    }

    func play() {
        guard case .ready = state else { return }
        activateAudioSession()
        player.play()
    }

    func pause() {
        player.pause()
    }

    func togglePlayback() {
        if player.timeControlStatus == .playing {
            pause()
        } else {
            play()
        }
    }

    func seek(by seconds: Double) {
        let current = player.currentTime().seconds

        guard current.isFinite else { return }

        let rawDuration = player.currentItem?.duration.seconds ?? 0
        let maximum = rawDuration.isFinite && rawDuration > 0
            ? rawDuration
            : max(0, current + seconds)

        seek(
            to: max(
                0,
                min(maximum, current + seconds)
            )
        )
    }

    func seek(to seconds: Double) {
        let safe = max(0, seconds)

        player.seek(
            to: CMTime(
                seconds: safe,
                preferredTimescale: 600
            ),
            toleranceBefore: .zero,
            toleranceAfter: .zero
        )
    }

    private func startCurrentCandidate() {
        guard candidateIndex < candidates.count else {
            failAndReturnToWeb(
                message: "Sursele native nu au putut porni clipul."
            )
            return
        }

        let media = candidates[candidateIndex]

        state = .resolving(
            "Pornesc sursa \(candidateIndex + 1)/\(candidates.count)…"
        )

        title = media.title
        sourceLabel = media.source
        duration = 0
        currentTime = 0

        activateAudioSession()

        let item = AVPlayerItem(url: media.url)

        itemStatusObservation?.invalidate()
        itemStatusObservation = item.observe(
            \.status,
            options: [.initial, .new]
        ) { [weak self] item, _ in
            Task { @MainActor [weak self] in
                guard let self else { return }

                switch item.status {
                case .readyToPlay:
                    self.readinessTask?.cancel()
                    self.readinessTask = nil
                    self.state = .ready

                    let rawDuration = item.duration.seconds

                    self.duration = rawDuration.isFinite
                        ? max(0, rawDuration)
                        : 0

                    self.player.play()
                    self.updateNowPlaying()

                case .failed:
                    self.tryNextCandidate(
                        reason:
                            item.error?.localizedDescription ??
                            "Sursa media a eșuat."
                    )

                case .unknown:
                    break

                @unknown default:
                    break
                }
            }
        }

        player.replaceCurrentItem(with: item)

        readinessTask?.cancel()
        let expectedIndex = candidateIndex

        readinessTask = Task { [weak self] in
            do {
                try await Task.sleep(
                    nanoseconds: 7_000_000_000
                )
            } catch {
                return
            }

            guard let self,
                  !Task.isCancelled,
                  self.candidateIndex == expectedIndex,
                  self.state != .ready else {
                return
            }

            self.tryNextCandidate(
                reason: "Timeout la pornirea sursei."
            )
        }
    }

    private func tryNextCandidate(reason: String) {
        readinessTask?.cancel()
        readinessTask = nil

        itemStatusObservation?.invalidate()
        itemStatusObservation = nil

        player.pause()
        player.replaceCurrentItem(with: nil)

        candidateIndex += 1

        if candidateIndex < candidates.count {
            startCurrentCandidate()
        } else {
            failAndReturnToWeb(message: reason)
        }
    }

    private func failAndReturnToWeb(message: String) {
        guard let currentVideoID else { return }

        readinessTask?.cancel()
        readinessTask = nil

        itemStatusObservation?.invalidate()
        itemStatusObservation = nil

        player.pause()
        player.replaceCurrentItem(with: nil)
        clearNowPlaying()

        state = .failed(
            message.isEmpty
                ? "Redarea nativă nu este disponibilă."
                : message
        )

        fallbackTask?.cancel()

        fallbackTask = Task { [weak self] in
            do {
                try await Task.sleep(
                    nanoseconds: 650_000_000
                )
            } catch {
                return
            }

            guard let self,
                  !Task.isCancelled,
                  self.currentVideoID == currentVideoID else {
                return
            }

            self.isPresented = false
            self.onWebFallback?(currentVideoID)
        }
    }

    private func cancelTransientWork() {
        resolutionTask?.cancel()
        resolutionTask = nil

        readinessTask?.cancel()
        readinessTask = nil

        fallbackTask?.cancel()
        fallbackTask = nil

        itemStatusObservation?.invalidate()
        itemStatusObservation = nil
    }

    private func configurePlayer() {
        player.automaticallyWaitsToMinimizeStalling = true
        player.preventsDisplaySleepDuringVideoPlayback = true
        player.audiovisualBackgroundPlaybackPolicy =
            .continuesIfPossible

        timeControlObservation = player.observe(
            \.timeControlStatus,
            options: [.initial, .new]
        ) { [weak self] player, _ in
            Task { @MainActor [weak self] in
                guard let self else { return }

                self.isPlaying =
                    player.timeControlStatus == .playing

                self.updateNowPlaying()
            }
        }

        timeObserver = player.addPeriodicTimeObserver(
            forInterval: CMTime(
                seconds: 1,
                preferredTimescale: 2
            ),
            queue: .main
        ) { [weak self] time in
            guard let self else { return }

            Task { @MainActor in
                self.currentTime =
                    time.seconds.isFinite
                        ? max(0, time.seconds)
                        : 0

                let rawDuration =
                    self.player.currentItem?
                        .duration.seconds ?? 0

                self.duration =
                    rawDuration.isFinite
                        ? max(0, rawDuration)
                        : 0

                self.updateNowPlaying()
            }
        }
    }

    private func configureAudioSession() {
        do {
            let audioSession =
                AVAudioSession.sharedInstance()

            try audioSession.setCategory(
                .playback,
                mode: .moviePlayback,
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
            try AVAudioSession.sharedInstance()
                .setActive(true)
        } catch {
            print(
                "Audio session activation failed: \(error.localizedDescription)"
            )
        }
    }

    private func observeAudioInterruptions() {
        interruptionToken =
            NotificationCenter.default.addObserver(
                forName:
                    AVAudioSession.interruptionNotification,
                object:
                    AVAudioSession.sharedInstance(),
                queue: .main
            ) { [weak self] notification in
                Task { @MainActor [weak self] in
                    self?.handleInterruption(notification)
                }
            }
    }

    private func handleInterruption(
        _ notification: Notification
    ) {
        guard let info = notification.userInfo,
              let rawType =
                (info[
                    AVAudioSessionInterruptionTypeKey
                ] as? NSNumber)?.uintValue,
              let type =
                AVAudioSession.InterruptionType(
                    rawValue: rawType
                ) else {
            return
        }

        switch type {
        case .began:
            wasPlayingBeforeInterruption = isPlaying

        case .ended:
            activateAudioSession()

            let rawOptions =
                (info[
                    AVAudioSessionInterruptionOptionKey
                ] as? NSNumber)?.uintValue ?? 0

            let options =
                AVAudioSession.InterruptionOptions(
                    rawValue: rawOptions
                )

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
            Task { @MainActor [weak self] in
                self?.play()
            }
            return .success
        }

        center.pauseCommand.isEnabled = true
        addRemoteTarget(center.pauseCommand) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.pause()
            }
            return .success
        }

        center.togglePlayPauseCommand.isEnabled = true
        addRemoteTarget(
            center.togglePlayPauseCommand
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.togglePlayback()
            }
            return .success
        }

        center.skipForwardCommand.isEnabled = true
        center.skipForwardCommand.preferredIntervals = [15]

        addRemoteTarget(
            center.skipForwardCommand
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.seek(by: 15)
            }
            return .success
        }

        center.skipBackwardCommand.isEnabled = true
        center.skipBackwardCommand.preferredIntervals = [15]

        addRemoteTarget(
            center.skipBackwardCommand
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.seek(by: -15)
            }
            return .success
        }

        center.changePlaybackPositionCommand.isEnabled = true

        addRemoteTarget(
            center.changePlaybackPositionCommand
        ) { [weak self] event in
            guard let event =
                    event as?
                    MPChangePlaybackPositionCommandEvent else {
                return .commandFailed
            }

            Task { @MainActor [weak self] in
                self?.seek(to: event.positionTime)
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
        let token = command.addTarget(
            handler: handler
        )

        remoteTargets.append(
            (command, token)
        )
    }

    private func updateNowPlaying() {
        guard case .ready = state else { return }

        var info: [String: Any] = [
            MPMediaItemPropertyTitle: title,
            MPNowPlayingInfoPropertyPlaybackRate:
                isPlaying ? 1.0 : 0.0,
            MPNowPlayingInfoPropertyDefaultPlaybackRate:
                1.0,
            MPNowPlayingInfoPropertyElapsedPlaybackTime:
                currentTime
        ]

        if duration > 0 {
            info[
                MPMediaItemPropertyPlaybackDuration
            ] = duration
        }

        let center =
            MPNowPlayingInfoCenter.default()

        center.nowPlayingInfo = info
        center.playbackState =
            isPlaying ? .playing : .paused
    }

    private func clearNowPlaying() {
        let center =
            MPNowPlayingInfoCenter.default()

        center.nowPlayingInfo = nil
        center.playbackState = .stopped
    }
}
