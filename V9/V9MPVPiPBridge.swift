import AVKit
import CoreMedia
import Foundation

private final class V9PiPStateBox:
    @unchecked Sendable
{
    private let lock =
        NSLock()

    private var duration:
        Double = 0

    private var paused =
        true

    func update(
        duration:
            Double,
        paused:
            Bool
    ) {
        lock.lock()

        self.duration =
            max(
                0,
                duration
            )

        self.paused =
            paused

        lock.unlock()
    }

    func snapshot()
        -> (
            duration:
                Double,
            paused:
                Bool
        )
    {
        lock.lock()

        let value =
            (
                duration,
                paused
            )

        lock.unlock()

        return value
    }
}

@MainActor
final class V9MPVPiPBridge:
    NSObject
{
    private var controller:
        AVPictureInPictureController?

    private var possibleObservation:
        NSKeyValueObservation?

    private weak var service:
        V9PlayerService?

    private weak var renderView:
        V9MPVRenderView?

    private var pendingStart =
        false

    private var hasEnqueuedFrame =
        false

    private var timebase:
        CMTimebase?

    private let stateBox =
        V9PiPStateBox()

    var onPossibleChanged:
        ((Bool) -> Void)?

    var onActiveChanged:
        ((Bool) -> Void)?

    var isActive:
        Bool
    {
        controller?
            .isPictureInPictureActive ??
            false
    }

    var isPossible:
        Bool
    {
        controller?
            .isPictureInPicturePossible ??
            false
    }

    var shouldKeepRendering:
        Bool
    {
        pendingStart ||
        isActive
    }

    func setup(
        service:
            V9PlayerService,
        renderView:
            V9MPVRenderView
    ) {
        if let existingRenderView =
                self.renderView,
           existingRenderView !==
                renderView {
            cleanup()
        }

        self.service =
            service

        self.renderView =
            renderView

        renderView.onFrameEnqueued = {
            [weak self] _ in

            self?
                .frameEnqueued()
        }

        guard controller == nil
        else {
            return
        }

        var createdTimebase:
            CMTimebase?

        let timebaseStatus =
            CMTimebaseCreateWithSourceClock(
                allocator:
                    kCFAllocatorDefault,
                sourceClock:
                    CMClockGetHostTimeClock(),
                timebaseOut:
                    &createdTimebase
            )

        if timebaseStatus ==
                noErr,
           let createdTimebase {
            timebase =
                createdTimebase

            renderView
                .sampleBufferLayer
                .controlTimebase =
                createdTimebase

            CMTimebaseSetTime(
                createdTimebase,
                time:
                    .zero
            )

            CMTimebaseSetRate(
                createdTimebase,
                rate:
                    0
            )
        }

        let source =
            AVPictureInPictureController
                .ContentSource(
                    sampleBufferDisplayLayer:
                        renderView
                            .sampleBufferLayer,
                    playbackDelegate:
                        self
                )

        let controller =
            AVPictureInPictureController(
                contentSource:
                    source
            )

        controller.delegate =
            self

        controller
            .canStartPictureInPictureAutomaticallyFromInline =
            true

        self.controller =
            controller

        possibleObservation =
            controller.observe(
                \.isPictureInPicturePossible,
                options:
                    [.initial, .new]
            ) {
                [weak self] controller,
                change in

                let value =
                    change.newValue ??
                    controller
                        .isPictureInPicturePossible

                Task {
                    @MainActor in

                    self?
                        .onPossibleChanged?(
                            value
                        )
                }
            }
    }

    func cleanup() {
        pendingStart =
            false

        hasEnqueuedFrame =
            false

        possibleObservation?
            .invalidate()

        possibleObservation =
            nil

        controller?
            .stopPictureInPicture()

        controller?
            .delegate =
            nil

        controller =
            nil

        renderView?
            .onFrameEnqueued =
            nil

        renderView?
            .sampleBufferLayer
            .controlTimebase =
            nil

        renderView?
            .resetFrameTimeline()

        timebase =
            nil

        service =
            nil

        renderView =
            nil
    }

    func prepareForMediaChange() {
        pendingStart =
            false

        hasEnqueuedFrame =
            false

        renderView?
            .resetFrameTimeline()
    }

    func updatePlaybackState(
        duration:
            Double,
        currentTime:
            Double,
        isPaused:
            Bool
    ) {
        stateBox.update(
            duration:
                duration,
            paused:
                isPaused
        )

        if let timebase {
            CMTimebaseSetTime(
                timebase,
                time:
                    CMTime(
                        seconds:
                            max(
                                0,
                                currentTime
                            ),
                        preferredTimescale:
                            600
                    )
            )

            CMTimebaseSetRate(
                timebase,
                rate:
                    isPaused
                        ? 0
                        : 1
            )
        }

        controller?
            .invalidatePlaybackState()
    }

    func requestToggle() {
        guard let controller,
              let renderView
        else {
            return
        }

        if controller
            .isPictureInPictureActive {
            controller
                .stopPictureInPicture()

            return
        }

        pendingStart =
            true

        renderView
            .resumeRendering()

        renderView
            .requestRender()

        tryStartIfReady()
    }

    private func frameEnqueued() {
        hasEnqueuedFrame =
            true

        tryStartIfReady()
    }

    private func tryStartIfReady() {
        guard pendingStart,
              hasEnqueuedFrame,
              let controller,
              controller
                .isPictureInPicturePossible
        else {
            onPossibleChanged?(
                controller?
                    .isPictureInPicturePossible ??
                    false
            )

            return
        }

        pendingStart =
            false

        controller
            .startPictureInPicture()
    }
}

extension V9MPVPiPBridge:
    AVPictureInPictureSampleBufferPlaybackDelegate
{
    nonisolated func pictureInPictureController(
        _ pictureInPictureController:
            AVPictureInPictureController,
        setPlaying playing:
            Bool
    ) {
        Task {
            @MainActor in

            if playing {
                service?
                    .play()
            } else {
                service?
                    .pause()
            }

            pictureInPictureController
                .invalidatePlaybackState()
        }
    }

    nonisolated func pictureInPictureControllerTimeRangeForPlayback(
        _ pictureInPictureController:
            AVPictureInPictureController
    ) -> CMTimeRange {
        let state =
            stateBox
                .snapshot()

        let resolvedDuration =
            state.duration > 0
                ? state.duration
                : 24 * 60 * 60

        return CMTimeRange(
            start:
                .zero,
            duration:
                CMTime(
                    seconds:
                        resolvedDuration,
                    preferredTimescale:
                        600
                )
        )
    }

    nonisolated func pictureInPictureControllerIsPlaybackPaused(
        _ pictureInPictureController:
            AVPictureInPictureController
    ) -> Bool {
        stateBox
            .snapshot()
            .paused
    }

    nonisolated func pictureInPictureController(
        _ pictureInPictureController:
            AVPictureInPictureController,
        skipByInterval skipInterval:
            CMTime,
        completion completionHandler:
            @escaping @Sendable () -> Void
    ) {
        Task {
            @MainActor in

            service?
                .seek(
                    by:
                        skipInterval
                            .seconds
                )

            completionHandler()
        }
    }

    nonisolated func pictureInPictureControllerShouldProhibitBackgroundAudioPlayback(
        _ pictureInPictureController:
            AVPictureInPictureController
    ) -> Bool {
        false
    }

    nonisolated func pictureInPictureController(
        _ pictureInPictureController:
            AVPictureInPictureController,
        didTransitionToRenderSize
            newRenderSize:
                CMVideoDimensions
    ) {}
}

extension V9MPVPiPBridge:
    AVPictureInPictureControllerDelegate
{
    nonisolated func pictureInPictureControllerWillStartPictureInPicture(
        _ pictureInPictureController:
            AVPictureInPictureController
    ) {
        Task {
            @MainActor in

            renderView?
                .resumeRendering()
        }
    }

    nonisolated func pictureInPictureControllerDidStartPictureInPicture(
        _ pictureInPictureController:
            AVPictureInPictureController
    ) {
        Task {
            @MainActor in

            onActiveChanged?(
                true
            )
        }
    }

    nonisolated func pictureInPictureController(
        _ pictureInPictureController:
            AVPictureInPictureController,
        failedToStartPictureInPictureWithError
            error:
                Error
    ) {
        Task {
            @MainActor in

            pendingStart =
                false

            onActiveChanged?(
                false
            )
        }
    }

    nonisolated func pictureInPictureControllerWillStopPictureInPicture(
        _ pictureInPictureController:
            AVPictureInPictureController
    ) {
        Task {
            @MainActor in

            renderView?
                .resumeRendering()
        }
    }

    nonisolated func pictureInPictureControllerDidStopPictureInPicture(
        _ pictureInPictureController:
            AVPictureInPictureController
    ) {
        Task {
            @MainActor in

            pendingStart =
                false

            onActiveChanged?(
                false
            )
        }
    }

    nonisolated func pictureInPictureController(
        _ pictureInPictureController:
            AVPictureInPictureController,
        restoreUserInterfaceForPictureInPictureStopWithCompletionHandler
            completionHandler:
                @escaping (Bool) -> Void
    ) {
        Task {
            @MainActor in

            renderView?
                .resumeRendering()

            completionHandler(
                true
            )
        }
    }
}
