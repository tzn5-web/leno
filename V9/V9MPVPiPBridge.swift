import AVKit
import CoreMedia
import CoreVideo
import Foundation
import os
import UIKit

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
    private let sampleBufferLayer =
        AVSampleBufferDisplayLayer()

    private var controller:
        AVPictureInPictureController?

    private var possibleObservation:
        NSKeyValueObservation?

    private weak var service:
        V9PlayerService?

    private weak var renderView:
        V9MPVRenderView?

    private var formatDescription:
        CMVideoFormatDescription?

    private var lastPresentationTime =
        CMTime.invalid

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
        guard controller == nil else {
            self.service =
                service

            self.renderView =
                renderView

            updateLayerFrame(
                renderView.bounds
            )

            return
        }

        self.service =
            service

        self.renderView =
            renderView

        sampleBufferLayer
            .videoGravity =
            .resizeAspect

        sampleBufferLayer
            .backgroundColor =
            UIColor.black
                .cgColor

        sampleBufferLayer
            .isHidden =
            true

        updateLayerFrame(
            renderView.bounds
        )

        renderView.layer.addSublayer(
            sampleBufferLayer
        )

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

            sampleBufferLayer
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
                        sampleBufferLayer,
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

        renderView?
            .captureFrames =
            false

        controller?
            .stopPictureInPicture()

        possibleObservation?
            .invalidate()

        possibleObservation =
            nil

        controller?.delegate =
            nil

        controller =
            nil

        sampleBufferLayer
            .sampleBufferRenderer
            .flush(
                removingDisplayedImage:
                    true,
                completionHandler:
                    nil
            )

        sampleBufferLayer
            .removeFromSuperlayer()

        formatDescription =
            nil

        hasEnqueuedFrame =
            false

        timebase =
            nil

        service =
            nil

        renderView =
            nil
    }

    func updateLayerFrame(
        _ bounds:
            CGRect
    ) {
        guard bounds.width > 1,
              bounds.height > 1
        else {
            return
        }

        CATransaction.begin()

        CATransaction
            .setDisableActions(
                true
            )

        sampleBufferLayer.frame =
            bounds

        sampleBufferLayer.bounds =
            CGRect(
                origin:
                    .zero,
                size:
                    bounds.size
            )

        CATransaction.commit()
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

        sampleBufferLayer
            .isHidden =
            false

        renderView
            .captureFrames =
            true

        renderView
            .requestRender()

        tryStartIfReady()
    }

    func enqueueFrame(
        _ pixelBuffer:
            CVPixelBuffer,
        presentationTime:
            CMTime
    ) {
        let width =
            CVPixelBufferGetWidth(
                pixelBuffer
            )

        let height =
            CVPixelBufferGetHeight(
                pixelBuffer
            )

        guard width > 0,
              height > 0
        else {
            return
        }

        let needsDescription:
            Bool

        if let formatDescription {
            let dimensions =
                CMVideoFormatDescriptionGetDimensions(
                    formatDescription
                )

            needsDescription =
                dimensions.width !=
                    Int32(
                        width
                    ) ||
                dimensions.height !=
                    Int32(
                        height
                    )
        } else {
            needsDescription =
                true
        }

        if needsDescription {
            var description:
                CMVideoFormatDescription?

            let result =
                CMVideoFormatDescriptionCreateForImageBuffer(
                    allocator:
                        kCFAllocatorDefault,
                    imageBuffer:
                        pixelBuffer,
                    formatDescriptionOut:
                        &description
                )

            guard result ==
                    noErr,
                  let description
            else {
                return
            }

            formatDescription =
                description

            sampleBufferLayer
                .sampleBufferRenderer
                .flush()
        }

        guard let formatDescription
        else {
            return
        }

        var effectivePTS =
            presentationTime

        if !effectivePTS
            .isValid ||
           effectivePTS
            .isIndefinite {
            effectivePTS =
                lastPresentationTime
                    .isValid
                    ? CMTimeAdd(
                        lastPresentationTime,
                        CMTime(
                            value:
                                1,
                            timescale:
                                30
                        )
                    )
                    : .zero
        }

        if lastPresentationTime
            .isValid &&
           effectivePTS <=
            lastPresentationTime {
            effectivePTS =
                CMTimeAdd(
                    lastPresentationTime,
                    CMTime(
                        value:
                            1,
                        timescale:
                            30
                    )
                )
        }

        var timing =
            CMSampleTimingInfo(
                duration:
                    CMTime(
                        value:
                            1,
                        timescale:
                            30
                    ),
                presentationTimeStamp:
                    effectivePTS,
                decodeTimeStamp:
                    .invalid
            )

        var sampleBuffer:
            CMSampleBuffer?

        let createStatus =
            CMSampleBufferCreateReadyWithImageBuffer(
                allocator:
                    kCFAllocatorDefault,
                imageBuffer:
                    pixelBuffer,
                formatDescription:
                    formatDescription,
                sampleTiming:
                    &timing,
                sampleBufferOut:
                    &sampleBuffer
            )

        guard createStatus ==
                noErr,
              let sampleBuffer
        else {
            return
        }

        let renderer =
            sampleBufferLayer
                .sampleBufferRenderer

        if renderer.status ==
            .failed {
            renderer.flush()
        }

        renderer.enqueue(
            sampleBuffer
        )

        lastPresentationTime =
            effectivePTS

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

        updateLayerFrame(
            renderView?
                .bounds ??
                .zero
        )

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
                .captureFrames =
                true

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

            sampleBufferLayer
                .isHidden =
                true

            renderView?
                .captureFrames =
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

            sampleBufferLayer
                .isHidden =
                true

            renderView?
                .captureFrames =
                false

            renderView?
                .resumeRendering()

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
