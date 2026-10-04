import AVFoundation

final class BackgroundAudioHandoff {
    struct Candidate: Equatable {
        let url: URL
        let videoID: String?
        let title: String
        let kind: String
    }

    let player = AVPlayer()

    private(set) var candidate: Candidate?
    private(set) var isActive = false

    var onProgress: ((Double, Bool) -> Void)?
    var onFailure: ((String) -> Void)?

    private var timeObserver: Any?
    private var itemStatusObservation: NSKeyValueObservation?
    private var failedToEndToken: NSObjectProtocol?

    init() {
        player.automaticallyWaitsToMinimizeStalling = true
        player.preventsDisplaySleepDuringVideoPlayback = false
        player.audiovisualBackgroundPlaybackPolicy =
            .continuesIfPossible

        timeObserver = player.addPeriodicTimeObserver(
            forInterval: CMTime(
                seconds: 0.5,
                preferredTimescale: 2
            ),
            queue: .main
        ) { [weak self] time in
            guard let self else { return }

            let seconds = time.seconds.isFinite
                ? max(0, time.seconds)
                : 0

            self.onProgress?(
                seconds,
                self.player.timeControlStatus == .playing ||
                self.player.rate > 0
            )
        }
    }

    deinit {
        if let timeObserver {
            player.removeTimeObserver(timeObserver)
        }

        itemStatusObservation?.invalidate()

        if let failedToEndToken {
            NotificationCenter.default.removeObserver(
                failedToEndToken
            )
        }
    }

    var hasCandidate: Bool {
        candidate != nil &&
        player.currentItem != nil
    }

    var currentTime: Double {
        let seconds = player.currentTime().seconds

        return seconds.isFinite
            ? max(0, seconds)
            : 0
    }

    var isPlaying: Bool {
        player.timeControlStatus == .playing ||
        player.rate > 0
    }

    func matches(videoID: String?) -> Bool {
        guard let candidate else {
            return false
        }

        guard let videoID,
              !videoID.isEmpty else {
            return true
        }

        guard let candidateVideoID =
                candidate.videoID,
              !candidateVideoID.isEmpty else {
            return true
        }

        return candidateVideoID == videoID
    }

    func prepare(
        url: URL,
        videoID: String?,
        title: String,
        kind: String
    ) {
        let next = Candidate(
            url: url,
            videoID: videoID,
            title: title,
            kind: kind
        )

        if candidate?.url == next.url {
            candidate = next
            return
        }

        isActive = false
        player.pause()

        itemStatusObservation?.invalidate()
        itemStatusObservation = nil

        if let failedToEndToken {
            NotificationCenter.default.removeObserver(
                failedToEndToken
            )
            self.failedToEndToken = nil
        }

        candidate = next

        let item = AVPlayerItem(url: url)
        item.preferredForwardBufferDuration = 8

        itemStatusObservation = item.observe(
            \.status,
            options: [.new]
        ) { [weak self] item, _ in
            guard item.status == .failed else {
                return
            }

            let message =
                item.error?.localizedDescription ??
                "Native background audio failed."

            DispatchQueue.main.async {
                self?.onFailure?(message)
            }
        }

        failedToEndToken =
            NotificationCenter.default.addObserver(
                forName:
                    .AVPlayerItemFailedToPlayToEndTime,
                object: item,
                queue: .main
            ) { [weak self] notification in
                let error =
                    notification.userInfo?[
                        AVPlayerItemFailedToPlayToEndTimeErrorKey
                    ] as? Error

                self?.onFailure?(
                    error?.localizedDescription ??
                    "Native background audio stopped."
                )
            }

        player.replaceCurrentItem(with: item)
    }

    @discardableResult
    func start(
        at seconds: Double,
        shouldPlay: Bool
    ) -> Bool {
        guard player.currentItem != nil else {
            return false
        }

        isActive = true

        let safeSeconds = max(0, seconds)
        let target = CMTime(
            seconds: safeSeconds,
            preferredTimescale: 600
        )

        player.seek(
            to: target,
            toleranceBefore: CMTime(
                seconds: 0.35,
                preferredTimescale: 600
            ),
            toleranceAfter: CMTime(
                seconds: 0.35,
                preferredTimescale: 600
            )
        ) { [weak self] _ in
            guard let self,
                  self.isActive,
                  shouldPlay else {
                return
            }

            self.player.play()
        }

        if shouldPlay && safeSeconds < 0.05 {
            player.play()
        }

        return true
    }

    func stopForForeground() -> Double {
        let seconds = currentTime

        player.pause()
        isActive = false

        return seconds
    }

    func play() {
        guard player.currentItem != nil else {
            return
        }

        isActive = true
        player.play()
    }

    func pause() {
        player.pause()
    }

    func seek(by seconds: Double) {
        seek(to: currentTime + seconds)
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
}
