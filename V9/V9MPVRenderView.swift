import AVFoundation
import CoreMedia
import CoreVideo
import Foundation
import QuartzCore
import UIKit

private final class V9PixelBufferBox:
    @unchecked Sendable
{
    let buffer:
        CVPixelBuffer

    init(
        _ buffer:
            CVPixelBuffer
    ) {
        self.buffer =
            buffer
    }
}

@MainActor
final class V9MPVRenderView:
    UIView
{
    let sampleBufferLayer =
        AVSampleBufferDisplayLayer()

    private weak var service:
        V9PlayerService?

    private var renderCore:
        V9MPVRenderCore?

    private let renderQueue =
        DispatchQueue(
            label:
                "com.tzn5web.leno.v9.render",
            qos:
                .userInteractive
        )

    private var rendering =
        false

    private var renderPending =
        false

    private(set) var renderingPaused =
        false

    private var pixelBufferPool:
        CVPixelBufferPool?

    private var pixelBufferPoolWidth =
        0

    private var pixelBufferPoolHeight =
        0

    private var formatDescription:
        CMVideoFormatDescription?

    private var lastPresentationTime =
        CMTime.invalid

    private var lastRenderHostTime:
        CFTimeInterval =
            0

    private var frameGeneration:
        UInt64 = 0

    var onFrameEnqueued:
        ((CMTime) -> Void)?

    override init(
        frame:
            CGRect
    ) {
        super.init(
            frame:
                frame
        )

        commonInit()
    }

    required init?(
        coder:
            NSCoder
    ) {
        super.init(
            coder:
                coder
        )

        commonInit()
    }

    deinit {
        MainActor.assumeIsolated {
            frameGeneration &+=
                1

            onFrameEnqueued =
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

            pixelBufferPool =
                nil

            renderCore =
                nil
        }
    }

    func attach(
        service:
            V9PlayerService
    ) -> Bool {
        self.service =
            service

        guard service
            .createRenderContext()
        else {
            return false
        }

        renderCore =
            service
                .renderCoreReference()

        requestRender()

        return true
    }

    override func layoutSubviews() {
        super.layoutSubviews()

        guard bounds.width
                .isFinite,
              bounds.height
                .isFinite,
              bounds.width > 1,
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

        CATransaction.commit()

        requestRender()
    }

    func requestRender() {
        guard let renderCore
        else {
            return
        }

        if rendering {
            renderPending =
                true

            return
        }

        rendering =
            true

        let generation =
            frameGeneration

        let presentationTime =
            service?
                .currentTime ??
            0

        let now =
            CACurrentMediaTime()

        let throttled =
            !renderingPaused &&
            lastRenderHostTime > 0 &&
            now - lastRenderHostTime <
                (1.0 / 30.0)

        if renderingPaused ||
           throttled {
            scheduleSkip(
                core:
                    renderCore,
                generation:
                    generation
            )

            return
        }

        lastRenderHostTime =
            now

        let size =
            renderTargetSize()

        guard size.width > 1,
              size.height > 1,
              let pixelBuffer =
                acquirePixelBuffer(
                    width:
                        size.width,
                    height:
                        size.height
                )
        else {
            scheduleSkip(
                core:
                    renderCore,
                generation:
                    generation
            )

            return
        }

        let box =
            V9PixelBufferBox(
                pixelBuffer
            )

        let width =
            size.width

        let height =
            size.height

        renderQueue.async {
            [weak self] in

            guard renderCore
                .consumeUpdate()
            else {
                DispatchQueue
                    .main
                    .async {
                        self?
                            .completeRender(
                                generation:
                                    generation
                            )
                    }

                return
            }

            let buffer =
                box.buffer

            guard CVPixelBufferLockBaseAddress(
                buffer,
                []
            ) ==
                kCVReturnSuccess
            else {
                renderCore
                    .skipFrame()

                DispatchQueue
                    .main
                    .async {
                        self?
                            .completeRender(
                                generation:
                                    generation
                            )
                    }

                return
            }

            var rendered =
                false

            if let baseAddress =
                    CVPixelBufferGetBaseAddress(
                        buffer
                    ) {
                let stride =
                    CVPixelBufferGetBytesPerRow(
                        buffer
                    )

                rendered =
                    renderCore
                        .renderSoftware(
                            width:
                                Int32(
                                    width
                                ),
                            height:
                                Int32(
                                    height
                                ),
                            stride:
                                stride,
                            pixels:
                                baseAddress
                        )

                if rendered {
                    Self
                        .forceOpaqueAlpha(
                            baseAddress:
                                baseAddress,
                            width:
                                width,
                            height:
                                height,
                            stride:
                                stride
                        )
                }
            }

            CVPixelBufferUnlockBaseAddress(
                buffer,
                []
            )

            if !rendered {
                renderCore
                    .skipFrame()
            }

            DispatchQueue
                .main
                .async {
                    guard let self
                    else {
                        return
                    }

                    if rendered,
                       generation ==
                        self.frameGeneration {
                        self.enqueue(
                            buffer,
                            presentationTime:
                                presentationTime
                        )
                    }

                    self.completeRender(
                        generation:
                            generation
                    )
                }
        }
    }

    func pauseRendering() {
        renderingPaused =
            true

        // Consume pending video updates without producing pixels. This keeps
        // libmpv video from applying back-pressure to background audio.
        requestRender()
    }

    func resumeRendering() {
        renderingPaused =
            false

        requestRender()
    }

    func resetFrameTimeline() {
        frameGeneration &+=
            1

        lastPresentationTime =
            .invalid

        lastRenderHostTime =
            0

        formatDescription =
            nil

        sampleBufferLayer
            .sampleBufferRenderer
            .flush(
                removingDisplayedImage:
                    true,
                completionHandler:
                    nil
            )

        requestRender()
    }

    private func scheduleSkip(
        core:
            V9MPVRenderCore,
        generation:
            UInt64
    ) {
        renderQueue.async {
            [weak self] in

            if core
                .consumeUpdate() {
                core
                    .skipFrame()
            }

            DispatchQueue
                .main
                .async {
                    self?
                        .completeRender(
                            generation:
                                generation
                        )
                }
        }
    }

    private func completeRender(
        generation:
            UInt64
    ) {
        rendering =
            false

        let shouldRenderAgain =
            renderPending

        renderPending =
            false

        if shouldRenderAgain {
            requestRender()
        }
    }

    private nonisolated static func forceOpaqueAlpha(
        baseAddress:
            UnsafeMutableRawPointer,
        width:
            Int,
        height:
            Int,
        stride:
            Int
    ) {
        let bytes =
            baseAddress
                .assumingMemoryBound(
                    to:
                        UInt8.self
                )

        for row in 0..<height {
            let rowStart =
                bytes.advanced(
                    by:
                        row *
                        stride
                )

            for column in 0..<width {
                rowStart[
                    column *
                    4 +
                    3
                ] =
                    255
            }
        }
    }

    private func commonInit() {
        backgroundColor =
            .black

        clipsToBounds =
            true

        sampleBufferLayer
            .videoGravity =
            .resizeAspect

        sampleBufferLayer
            .backgroundColor =
            UIColor.black
                .cgColor

        layer.addSublayer(
            sampleBufferLayer
        )
    }

    private func renderTargetSize()
        -> (
            width:
                Int,
            height:
                Int
        )
    {
        let scale =
            max(
                1,
                traitCollection
                    .displayScale
            )

        var width =
            max(
                2,
                Int(
                    (
                        bounds.width *
                        scale
                    )
                    .rounded()
                )
            )

        var height =
            max(
                2,
                Int(
                    (
                        bounds.height *
                        scale
                    )
                    .rounded()
                )
            )

        let maximumLongEdge =
            1280.0

        let maximumPixels =
            1280.0 *
            720.0

        let longEdge =
            Double(
                max(
                    width,
                    height
                )
            )

        let pixelCount =
            Double(
                width *
                height
            )

        var downscale =
            min(
                1.0,
                maximumLongEdge /
                max(
                    1,
                    longEdge
                )
            )

        if pixelCount *
            downscale *
            downscale >
            maximumPixels {
            downscale =
                min(
                    downscale,
                    sqrt(
                        maximumPixels /
                        pixelCount
                    )
                )
        }

        width =
            max(
                2,
                Int(
                    (
                        Double(
                            width
                        ) *
                        downscale
                    )
                    .rounded(
                        .down
                    )
                )
            )

        height =
            max(
                2,
                Int(
                    (
                        Double(
                            height
                        ) *
                        downscale
                    )
                    .rounded(
                        .down
                    )
                )
            )

        width -=
            width %
            2

        height -=
            height %
            2

        return (
            max(
                2,
                width
            ),
            max(
                2,
                height
            )
        )
    }

    private func acquirePixelBuffer(
        width:
            Int,
        height:
            Int
    ) -> CVPixelBuffer? {
        if pixelBufferPool == nil ||
           pixelBufferPoolWidth !=
            width ||
           pixelBufferPoolHeight !=
            height {
            pixelBufferPool =
                nil

            pixelBufferPoolWidth =
                width

            pixelBufferPoolHeight =
                height

            formatDescription =
                nil

            let poolAttributes:
                [CFString: Any] = [
                    kCVPixelBufferPoolMinimumBufferCountKey:
                        4
                ]

            let pixelAttributes:
                [CFString: Any] = [
                    kCVPixelBufferPixelFormatTypeKey:
                        kCVPixelFormatType_32BGRA,
                    kCVPixelBufferWidthKey:
                        width,
                    kCVPixelBufferHeightKey:
                        height,
                    kCVPixelBufferIOSurfacePropertiesKey:
                        [:],
                    kCVPixelBufferCGImageCompatibilityKey:
                        true,
                    kCVPixelBufferCGBitmapContextCompatibilityKey:
                        true,
                    kCVPixelBufferBytesPerRowAlignmentKey:
                        64
                ]

            var pool:
                CVPixelBufferPool?

            let result =
                CVPixelBufferPoolCreate(
                    kCFAllocatorDefault,
                    poolAttributes as
                        CFDictionary,
                    pixelAttributes as
                        CFDictionary,
                    &pool
                )

            guard result ==
                    kCVReturnSuccess,
                  let pool
            else {
                return nil
            }

            pixelBufferPool =
                pool
        }

        guard let pixelBufferPool
        else {
            return nil
        }

        var pixelBuffer:
            CVPixelBuffer?

        let result =
            CVPixelBufferPoolCreatePixelBuffer(
                kCFAllocatorDefault,
                pixelBufferPool,
                &pixelBuffer
            )

        guard result ==
                kCVReturnSuccess
        else {
            return nil
        }

        return pixelBuffer
    }

    private func enqueue(
        _ pixelBuffer:
            CVPixelBuffer,
        presentationTime:
            Double
    ) {
        if formatDescription == nil {
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
        }

        guard let formatDescription
        else {
            return
        }

        let renderer =
            sampleBufferLayer
                .sampleBufferRenderer

        if renderer.status ==
            .failed {
            renderer.flush()

            lastPresentationTime =
                .invalid
        }

        var effectivePTS =
            CMTime(
                seconds:
                    max(
                        0,
                        presentationTime
                    ),
                preferredTimescale:
                    600
            )

        if !effectivePTS
            .isValid ||
           effectivePTS
            .isIndefinite {
            effectivePTS =
                .zero
        }

        if lastPresentationTime
            .isValid,
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

        renderer.enqueue(
            sampleBuffer
        )

        lastPresentationTime =
            effectivePTS

        onFrameEnqueued?(
            effectivePTS
        )
    }
}
