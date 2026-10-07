import AVFoundation
import AVKit
import Combine
import MediaPlayer
import YouTubeKit

final class NativePlaybackController:
    NSObject,
    ObservableObject,
    AVPictureInPictureControllerDelegate
{
    enum State: Equatable {
        case idle
        case resolving
        case ready
        case failed(String)
    }

    enum PlaybackError: LocalizedError {
        case noPlayableStream
        case missingMediaTracks

        var errorDescription: String? {
            switch self {
            case .noPlayableStream:
                return "Nu am găsit streamuri native compatibile pentru acest clip."
            case .missingMediaTracks:
                return "Streamurile DASH nu conțin piste audio/video utilizabile."
            }
        }
    }

    let player = AVPlayer()

    @Published private(set) var state: State = .idle
    @Published private(set) var isPresented = false
    @Published private(set) var title = "YouTube"
    @Published private(set) var isPlaying = false
    @Published private(set) var currentTime: Double = 0
    @Published private(set) var duration: Double = 0
    @Published private(set) var isPiPPossible = false
    @Published private(set) var isPiPActive = false

    private var currentVideoID: String?
    private var loadTask: Task<Void, Never>?
    private var timeObserver: Any?
    private var timeControlObservation: NSKeyValueObservation?
    private var itemStatusObservation: NSKeyValueObservation?
    private var pipPossibleObservation: NSKeyValueObservation?
    private var pictureInPictureController: AVPictureInPictureController?
    private var remoteTargets: [(MPRemoteCommand, Any)] = []
    private var retainedPlaybackAssets: [AVAsset] = []

    override init() {
        super.init()
        configureAudioSession()
        configurePlayer()
        configureRemoteCommands()
    }

    deinit {
        loadTask?.cancel()

        if let timeObserver {
            player.removeTimeObserver(timeObserver)
        }

        timeControlObservation?.invalidate()
        itemStatusObservation?.invalidate()
        pipPossibleObservation?.invalidate()

        for (command, token) in remoteTargets {
            command.removeTarget(token)
        }
    }

    func open(videoID: String) {
        guard videoID.count == 11 else { return }

        loadTask?.cancel()
        currentVideoID = videoID
        isPresented = true
        state = .resolving
        title = "Se încarcă…"
        currentTime = 0
        duration = 0
        isPlaying = false

        player.pause()
        player.replaceCurrentItem(with: nil)
        clearNowPlaying()

        loadTask = Task { [weak self] in
            do {
                let youtube = YouTube(
                    videoID: videoID,
                    methods: [.local]
                )

                let streams = try await youtube.streams

                guard !Task.isCancelled else { return }

                let metadata = try? await youtube.metadata
                let resolvedTitle = metadata?.title ?? "YouTube"

                if let progressive = streams
                    .filterVideoAndAudio()
                    .filter({ $0.isNativelyPlayable })
                    .highestResolutionStream() {
                    guard !Task.isCancelled else { return }

                    await MainActor.run { [weak self] in
                        self?.prepareNativePlayback(
                            asset: AVURLAsset(url: progressive.url),
                            title: resolvedTitle
                        )
                    }

                    return
                }

                let nativeVideoOnly = streams
                    .filterVideoOnly()
                    .filter({ $0.isNativelyPlayable })

                let nativeAudioOnly = streams
                    .filterAudioOnly()
                    .filter({ $0.isNativelyPlayable })

                let preferredVideo = nativeVideoOnly
                    .filter({ $0.fileExtension == .mp4 })
                    .highestResolutionStream()
                    ?? nativeVideoOnly.highestResolutionStream()

                let preferredAudio = nativeAudioOnly
                    .filter({ $0.fileExtension == .mp4 })
                    .highestAudioBitrateStream()
                    ?? nativeAudioOnly.highestAudioBitrateStream()

                guard let videoStream = preferredVideo,
                      let audioStream = preferredAudio else {
                    throw PlaybackError.noPlayableStream
                }

                let composedAsset = try await self?.makeDASHComposition(
                    videoURL: videoStream.url,
                    audioURL: audioStream.url
                )

                guard !Task.isCancelled else { return }
                guard let composedAsset else { return }

                await MainActor.run { [weak self] in
                    self?.prepareNativePlayback(
                        asset: composedAsset,
                        title: resolvedTitle
                    )
                }
            } catch {
                guard !Task.isCancelled else { return }

                await MainActor.run { [weak self] in
                    guard let self else { return }
                    self.state = .failed(error.localizedDescription)
                    self.isPlaying = false
                    self.clearNowPlaying()
                }
            }
        }
    }

    func retry() {
        guard let currentVideoID else { return }
        open(videoID: currentVideoID)
    }

    func close() {
        loadTask?.cancel()
        loadTask = nil

        if pictureInPictureController?.isPictureInPictureActive == true {
            pictureInPictureController?.stopPictureInPicture()
        }

        player.pause()
        player.replaceCurrentItem(with: nil)
        retainedPlaybackAssets.removeAll()

        itemStatusObservation?.invalidate()
        itemStatusObservation = nil

        isPresented = false
        state = .idle
        isPlaying = false
        currentTime = 0
        duration = 0
        clearNowPlaying()
    }

    func play() {
        activateAudioSession()
        player.play()
    }

    func pause() {
        player.pause()
    }

    func togglePlayback() {
        player.timeControlStatus == .playing ? pause() : play()
    }

    func seek(by seconds: Double) {
        let current = player.currentTime().seconds
        guard current.isFinite else { return }

        let rawDuration = player.currentItem?.duration.seconds ?? 0
        let maximum = rawDuration.isFinite && rawDuration > 0
            ? rawDuration
            : max(0, current + seconds)

        seek(to: max(0, min(maximum, current + seconds)))
    }

    func seek(to seconds: Double) {
        let safe = max(0, seconds)

        player.seek(
            to: CMTime(seconds: safe, preferredTimescale: 600),
            toleranceBefore: .zero,
            toleranceAfter: .zero
        )
    }

    func attach(playerLayer: AVPlayerLayer) {
        playerLayer.player = player
        playerLayer.videoGravity = .resizeAspect

        guard AVPictureInPictureController.isPictureInPictureSupported() else {
            isPiPPossible = false
            return
        }

        pipPossibleObservation?.invalidate()

        guard let pip = AVPictureInPictureController(playerLayer: playerLayer) else {
            isPiPPossible = false
            return
        }

        pip.delegate = self
        pip.canStartPictureInPictureAutomaticallyFromInline = true
        pictureInPictureController = pip

        pipPossibleObservation = pip.observe(
            \.isPictureInPicturePossible,
            options: [.initial, .new]
        ) { [weak self] pip, _ in
            DispatchQueue.main.async {
                self?.isPiPPossible = pip.isPictureInPicturePossible
            }
        }
    }

    func requestPictureInPicture() {
        guard let pip = pictureInPictureController else { return }

        if pip.isPictureInPictureActive {
            pip.stopPictureInPicture()
        } else if pip.isPictureInPicturePossible {
            pip.startPictureInPicture()
        }
    }

    func pictureInPictureControllerDidStartPictureInPicture(
        _ pictureInPictureController: AVPictureInPictureController
    ) {
        DispatchQueue.main.async {
            self.isPiPActive = true
        }
    }

    func pictureInPictureControllerDidStopPictureInPicture(
        _ pictureInPictureController: AVPictureInPictureController
    ) {
        DispatchQueue.main.async {
            self.isPiPActive = false
        }
    }

    private func configurePlayer() {
        player.automaticallyWaitsToMinimizeStalling = true
        player.preventsDisplaySleepDuringVideoPlayback = true
        player.audiovisualBackgroundPlaybackPolicy = .continuesIfPossible

        timeControlObservation = player.observe(
            \.timeControlStatus,
            options: [.initial, .new]
        ) { [weak self] player, _ in
            DispatchQueue.main.async {
                guard let self else { return }
                self.isPlaying = player.timeControlStatus == .playing
                self.updateNowPlaying()
            }
        }

        timeObserver = player.addPeriodicTimeObserver(
            forInterval: CMTime(seconds: 1, preferredTimescale: 2),
            queue: .main
        ) { [weak self] time in
            guard let self else { return }

            self.currentTime = time.seconds.isFinite
                ? max(0, time.seconds)
                : 0

            let rawDuration = self.player.currentItem?.duration.seconds ?? 0
            self.duration = rawDuration.isFinite
                ? max(0, rawDuration)
                : 0

            self.updateNowPlaying()
        }
    }

    private func prepareNativePlayback(asset: AVAsset, title: String) {
        activateAudioSession()
        self.title = title.isEmpty ? "YouTube" : title
        retainedPlaybackAssets = [asset]

        let item = AVPlayerItem(asset: asset)

        itemStatusObservation?.invalidate()
        itemStatusObservation = item.observe(
            \.status,
            options: [.initial, .new]
        ) { [weak self] item, _ in
            DispatchQueue.main.async {
                guard let self else { return }

                switch item.status {
                case .readyToPlay:
                    self.state = .ready

                    let rawDuration = item.duration.seconds
                    self.duration = rawDuration.isFinite
                        ? max(0, rawDuration)
                        : 0

                    self.player.play()
                    self.updateNowPlaying()

                case .failed:
                    self.state = .failed(
                        item.error?.localizedDescription ??
                        "Playerul nativ nu a putut deschide streamul."
                    )
                    self.clearNowPlaying()

                case .unknown:
                    break

                @unknown default:
                    break
                }
            }
        }

        player.replaceCurrentItem(with: item)
    }

    private func makeDASHComposition(
        videoURL: URL,
        audioURL: URL
    ) async throws -> AVMutableComposition {
        let videoAsset = AVURLAsset(url: videoURL)
        let audioAsset = AVURLAsset(url: audioURL)

        async let videoTracks = videoAsset.loadTracks(withMediaType: .video)
        async let audioTracks = audioAsset.loadTracks(withMediaType: .audio)
        async let videoDuration = videoAsset.load(.duration)
        async let audioDuration = audioAsset.load(.duration)

        guard let sourceVideoTrack = try await videoTracks.first,
              let sourceAudioTrack = try await audioTracks.first else {
            throw PlaybackError.missingMediaTracks
        }

        let resolvedVideoDuration = try await videoDuration
        let resolvedAudioDuration = try await audioDuration

        let playableDuration = CMTimeMinimum(
            resolvedVideoDuration,
            resolvedAudioDuration
        )

        guard playableDuration.isNumeric,
              playableDuration > .zero else {
            throw PlaybackError.missingMediaTracks
        }

        let composition = AVMutableComposition()

        guard let compositionVideoTrack = composition.addMutableTrack(
            withMediaType: .video,
            preferredTrackID: kCMPersistentTrackID_Invalid
        ),
        let compositionAudioTrack = composition.addMutableTrack(
            withMediaType: .audio,
            preferredTrackID: kCMPersistentTrackID_Invalid
        ) else {
            throw PlaybackError.missingMediaTracks
        }

        let timeRange = CMTimeRange(
            start: .zero,
            duration: playableDuration
        )

        try compositionVideoTrack.insertTimeRange(
            timeRange,
            of: sourceVideoTrack,
            at: .zero
        )

        try compositionAudioTrack.insertTimeRange(
            timeRange,
            of: sourceAudioTrack,
            at: .zero
        )

        if let transform = try? await sourceVideoTrack.load(.preferredTransform) {
            compositionVideoTrack.preferredTransform = transform
        }

        await MainActor.run { [weak self] in
            self?.retainedPlaybackAssets = [
                videoAsset,
                audioAsset,
                composition
            ]
        }

        return composition
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
            print("Audio session configuration failed: \(error.localizedDescription)")
        }
    }

    private func activateAudioSession() {
        do {
            try AVAudioSession.sharedInstance().setActive(true)
        } catch {
            print("Audio session activation failed: \(error.localizedDescription)")
        }
    }

    private func configureRemoteCommands() {
        let center = MPRemoteCommandCenter.shared()

        center.playCommand.isEnabled = true
        addRemoteTarget(center.playCommand) { [weak self] _ in
            guard let self, self.state == .ready else {
                return .commandFailed
            }

            self.play()
            return .success
        }

        center.pauseCommand.isEnabled = true
        addRemoteTarget(center.pauseCommand) { [weak self] _ in
            guard let self, self.state == .ready else {
                return .commandFailed
            }

            self.pause()
            return .success
        }

        center.togglePlayPauseCommand.isEnabled = true
        addRemoteTarget(center.togglePlayPauseCommand) { [weak self] _ in
            guard let self, self.state == .ready else {
                return .commandFailed
            }

            self.togglePlayback()
            return .success
        }

        center.skipForwardCommand.isEnabled = true
        center.skipForwardCommand.preferredIntervals = [15]
        addRemoteTarget(center.skipForwardCommand) { [weak self] _ in
            guard let self, self.state == .ready else {
                return .commandFailed
            }

            self.seek(by: 15)
            return .success
        }

        center.skipBackwardCommand.isEnabled = true
        center.skipBackwardCommand.preferredIntervals = [15]
        addRemoteTarget(center.skipBackwardCommand) { [weak self] _ in
            guard let self, self.state == .ready else {
                return .commandFailed
            }

            self.seek(by: -15)
            return .success
        }

        center.changePlaybackPositionCommand.isEnabled = true
        addRemoteTarget(center.changePlaybackPositionCommand) { [weak self] event in
            guard let self,
                  self.state == .ready,
                  let event = event as? MPChangePlaybackPositionCommandEvent else {
                return .commandFailed
            }

            self.seek(to: event.positionTime)
            return .success
        }
    }

    private func addRemoteTarget(
        _ command: MPRemoteCommand,
        handler: @escaping (MPRemoteCommandEvent) -> MPRemoteCommandHandlerStatus
    ) {
        let token = command.addTarget(handler: handler)
        remoteTargets.append((command, token))
    }

    private func updateNowPlaying() {
        guard state == .ready else { return }

        var info: [String: Any] = [
            MPMediaItemPropertyTitle: title,
            MPNowPlayingInfoPropertyPlaybackRate: isPlaying ? 1.0 : 0.0,
            MPNowPlayingInfoPropertyDefaultPlaybackRate: 1.0,
            MPNowPlayingInfoPropertyElapsedPlaybackTime: currentTime
        ]

        if duration > 0 {
            info[MPMediaItemPropertyPlaybackDuration] = duration
        }

        let center = MPNowPlayingInfoCenter.default()
        center.nowPlayingInfo = info
        center.playbackState = isPlaying ? .playing : .paused
    }

    private func clearNowPlaying() {
        let center = MPNowPlayingInfoCenter.default()
        center.nowPlayingInfo = nil
        center.playbackState = .stopped
    }
}
