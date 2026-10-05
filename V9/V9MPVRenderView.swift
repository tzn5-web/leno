import AVFoundation
import CoreMedia
import CoreVideo
import QuartzCore
import UIKit

@MainActor
final class V9MPVRenderView:
    UIView
{
    let sampleBufferLayer =
        AVSampleBufferDisplayLayer()

    private weak var service:
        V9PlayerService?

    private var rendering =
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
        guard !renderingPaused,
              !rendering
        else {
            return
        }

        rendering =
            true

        renderFrame()

        rendering =
            false
    }

    func pauseRendering() {
        renderingPaused =
            true
    }

    func resumeRendering() {
        renderingPaused =
            false

        requestRender()
    }

    func resetFrameTimeline() {
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

    private func renderFrame() {
        guard let service,
              service.consumeRenderUpdate()
        else {
            return
        }

        let now =
            CACurrentMediaTime()

        // Bound software conversion/copy cost. 60 fps YouTube sources are
        // intentionally sampled to at most 30 fps for the V9 PiP path.
        if lastRenderHostTime > 0,
           now - lastRenderHostTime <
            (1.0 / 30.0) {
            service
                .skipRenderFrame()

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
            service
                .skipRenderFrame()

            return
        }

        let lockResult =
            CVPixelBufferLockBaseAddress(
                pixelBuffer,
                []
            )

        guard lockResult ==
                kCVReturnSuccess
        else {
            service
                .skipRenderFrame()

            return
        }

        defer {
            CVPixelBufferUnlockBaseAddress(
                pixelBuffer,
                []
            )
        }

        guard let baseAddress =
                CVPixelBufferGetBaseAddress(
                    pixelBuffer
                )
        else {
            service
                .skipRenderFrame()

            return
        }

        let stride =
            CVPixelBufferGetBytesPerRow(
                pixelBuffer
            )

        guard service
            .renderSoftware(
                width:
                    Int32(
                        size.width
                    ),
                height:
                    Int32(
                        size.height
                    ),
                stride:
                    stride,
                pixels:
                    baseAddress
            )
        else {
            return
        }

        // libmpv's guaranteed "bgr0" software format leaves the fourth
        // byte undefined/zero. AVSampleBufferDisplayLayer receives BGRA,
        // so force the alpha channel opaque before enqueuing the frame.
        let bytes =
            baseAddress
                .assumingMemoryBound(
                    to:
                        UInt8.self
                )

        for row in 0..<size.height {
            let rowStart =
                bytes.advanced(
                    by:
                        row *
                        stride
                )

            for column in 0..<size.width {
                rowStart[
                    column *
                    4 +
                    3
                ] =
                    255
            }
        }

        enqueue(
            pixelBuffer,
            presentationTime:
                service.currentTime
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

        // Keep dimensions friendly to video conversion paths.
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
                        true
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

        onFrameEnqueued?(
            effectivePTS
        )
    }
}
