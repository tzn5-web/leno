import CoreMedia
import CoreVideo
import Libmpv
import OpenGLES
import UIKit

private func v9OpenGLGetProcAddress(
    _ context:
        UnsafeMutableRawPointer?,
    _ name:
        UnsafePointer<CChar>?
) -> UnsafeMutableRawPointer? {
    guard let name else {
        return nil
    }

    let frameworkURL =
        URL(
            fileURLWithPath:
                "/System/Library/Frameworks/OpenGLES.framework"
        )

    guard let bundle =
            CFBundleCreate(
                kCFAllocatorDefault,
                frameworkURL as CFURL
            )
    else {
        return nil
    }

    return CFBundleGetFunctionPointerForName(
        bundle,
        String(
            cString:
                name
        ) as CFString
    )
}

@MainActor
final class V9MPVRenderView:
    UIView
{
    override class var layerClass:
        AnyClass
    {
        CAEAGLLayer.self
    }

    private var context:
        EAGLContext?

    private var framebuffer:
        GLuint = 0

    private var colorRenderbuffer:
        GLuint = 0

    private var renderWidth:
        GLint = 0

    private var renderHeight:
        GLint = 0

    private weak var service:
        V9PlayerService?

    private var rendering =
        false

    private(set) var renderingPaused =
        false

    var captureFrames =
        false

    var onFrame:
        ((
            CVPixelBuffer,
            CMTime
        ) -> Void)?

    private var captureBuffer:
        [UInt8] = []

    override init(
        frame: CGRect
    ) {
        super.init(
            frame:
                frame
        )

        commonInit()
    }

    required init?(
        coder: NSCoder
    ) {
        super.init(
            coder:
                coder
        )

        commonInit()
    }

    deinit {
        MainActor.assumeIsolated {
            tearDownGL()
        }
    }

    func attach(
        service:
            V9PlayerService
    ) -> Bool {
        self.service =
            service

        guard setupGLIfNeeded(),
              service.createRenderContext(
                getProcAddress:
                    v9OpenGLGetProcAddress
              )
        else {
            return false
        }

        requestRender()

        return true
    }

    override func layoutSubviews() {
        super.layoutSubviews()

        guard setupGLIfNeeded() else {
            return
        }

        resizeDrawable()
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

    private func commonInit() {
        backgroundColor =
            .black

        contentScaleFactor =
            UIScreen.main.scale

        guard let layer =
                layer as?
                    CAEAGLLayer
        else {
            return
        }

        layer.isOpaque =
            true

        layer.drawableProperties = [
            kEAGLDrawablePropertyRetainedBacking:
                true,
            kEAGLDrawablePropertyColorFormat:
                kEAGLColorFormatRGBA8
        ]
    }

    private func setupGLIfNeeded()
        -> Bool
    {
        if context != nil,
           framebuffer != 0,
           colorRenderbuffer != 0 {
            return true
        }

        guard let newContext =
                EAGLContext(
                    api:
                        .openGLES3
                ),
              EAGLContext.setCurrent(
                newContext
              )
        else {
            return false
        }

        context =
            newContext

        glGenFramebuffers(
            1,
            &framebuffer
        )

        glGenRenderbuffers(
            1,
            &colorRenderbuffer
        )

        resizeDrawable()

        return framebuffer != 0 &&
               colorRenderbuffer != 0
    }

    private func resizeDrawable() {
        guard let context,
              let layer =
                layer as?
                    CAEAGLLayer,
              framebuffer != 0,
              colorRenderbuffer != 0,
              bounds.width > 1,
              bounds.height > 1
        else {
            return
        }

        EAGLContext.setCurrent(
            context
        )

        glBindFramebuffer(
            GLenum(
                GL_FRAMEBUFFER
            ),
            framebuffer
        )

        glBindRenderbuffer(
            GLenum(
                GL_RENDERBUFFER
            ),
            colorRenderbuffer
        )

        context.renderbufferStorage(
            Int(
                GL_RENDERBUFFER
            ),
            from:
                layer
        )

        glFramebufferRenderbuffer(
            GLenum(
                GL_FRAMEBUFFER
            ),
            GLenum(
                GL_COLOR_ATTACHMENT0
            ),
            GLenum(
                GL_RENDERBUFFER
            ),
            colorRenderbuffer
        )

        var width:
            GLint = 0

        var height:
            GLint = 0

        glGetRenderbufferParameteriv(
            GLenum(
                GL_RENDERBUFFER
            ),
            GLenum(
                GL_RENDERBUFFER_WIDTH
            ),
            &width
        )

        glGetRenderbufferParameteriv(
            GLenum(
                GL_RENDERBUFFER
            ),
            GLenum(
                GL_RENDERBUFFER_HEIGHT
            ),
            &height
        )

        renderWidth =
            width

        renderHeight =
            height

        glViewport(
            0,
            0,
            width,
            height
        )
    }

    private func renderFrame() {
        guard let context,
              let service,
              framebuffer != 0,
              colorRenderbuffer != 0,
              renderWidth > 0,
              renderHeight > 0,
              service.consumeRenderUpdate()
        else {
            return
        }

        EAGLContext.setCurrent(
            context
        )

        glBindFramebuffer(
            GLenum(
                GL_FRAMEBUFFER
            ),
            framebuffer
        )

        glViewport(
            0,
            0,
            renderWidth,
            renderHeight
        )

        glClearColor(
            0,
            0,
            0,
            1
        )

        glClear(
            GLbitfield(
                GL_COLOR_BUFFER_BIT
            )
        )

        service.render(
            framebuffer:
                Int32(
                    framebuffer
                ),
            width:
                Int32(
                    renderWidth
                ),
            height:
                Int32(
                    renderHeight
                )
        )

        if captureFrames {
            captureFrame(
                presentationTime:
                    service.currentTime
            )
        }

        glBindRenderbuffer(
            GLenum(
                GL_RENDERBUFFER
            ),
            colorRenderbuffer
        )

        _ =
            context.presentRenderbuffer(
                Int(
                    GL_RENDERBUFFER
                )
            )
    }

    private func captureFrame(
        presentationTime:
            Double
    ) {
        let width =
            Int(
                renderWidth
            )

        let height =
            Int(
                renderHeight
            )

        guard width > 1,
              height > 1
        else {
            return
        }

        let rowBytes =
            width * 4

        let needed =
            rowBytes * height

        if captureBuffer.count !=
            needed {
            captureBuffer =
                [UInt8](
                    repeating:
                        0,
                    count:
                        needed
                )
        }

        glPixelStorei(
            GLenum(
                GL_PACK_ALIGNMENT
            ),
            1
        )

        captureBuffer
            .withUnsafeMutableBytes {
                raw in

                guard let base =
                        raw.baseAddress
                else {
                    return
                }

                glReadPixels(
                    0,
                    0,
                    GLsizei(
                        width
                    ),
                    GLsizei(
                        height
                    ),
                    GLenum(
                        GL_BGRA
                    ),
                    GLenum(
                        GL_UNSIGNED_BYTE
                    ),
                    base
                )
            }

        var pixelBuffer:
            CVPixelBuffer?

        let attributes:
            [CFString: Any] = [
                kCVPixelBufferIOSurfacePropertiesKey:
                    [:],
                kCVPixelBufferCGImageCompatibilityKey:
                    true,
                kCVPixelBufferCGBitmapContextCompatibilityKey:
                    true
            ]

        let result =
            CVPixelBufferCreate(
                kCFAllocatorDefault,
                width,
                height,
                kCVPixelFormatType_32BGRA,
                attributes as
                    CFDictionary,
                &pixelBuffer
            )

        guard result ==
                kCVReturnSuccess,
              let pixelBuffer
        else {
            return
        }

        CVPixelBufferLockBaseAddress(
            pixelBuffer,
            []
        )

        defer {
            CVPixelBufferUnlockBaseAddress(
                pixelBuffer,
                []
            )
        }

        guard let destination =
                CVPixelBufferGetBaseAddress(
                    pixelBuffer
                )
        else {
            return
        }

        let destinationRowBytes =
            CVPixelBufferGetBytesPerRow(
                pixelBuffer
            )

        captureBuffer
            .withUnsafeBytes {
                raw in

                guard let source =
                        raw.baseAddress
                else {
                    return
                }

                for destinationRow
                    in 0..<height
                {
                    let sourceRow =
                        height -
                        1 -
                        destinationRow

                    memcpy(
                        destination
                            .advanced(
                                by:
                                    destinationRow *
                                    destinationRowBytes
                            ),
                        source
                            .advanced(
                                by:
                                    sourceRow *
                                    rowBytes
                            ),
                        rowBytes
                    )
                }
            }

        onFrame?(
            pixelBuffer,
            CMTime(
                seconds:
                    max(
                        0,
                        presentationTime
                    ),
                preferredTimescale:
                    600
            )
        )
    }

    private func tearDownGL() {
        onFrame =
            nil

        if let context {
            EAGLContext.setCurrent(
                context
            )
        }

        if framebuffer != 0 {
            glDeleteFramebuffers(
                1,
                &framebuffer
            )

            framebuffer =
                0
        }

        if colorRenderbuffer != 0 {
            glDeleteRenderbuffers(
                1,
                &colorRenderbuffer
            )

            colorRenderbuffer =
                0
        }

        if EAGLContext.current() ===
            context {
            EAGLContext.setCurrent(
                nil
            )
        }

        self.context =
            nil
    }
}
