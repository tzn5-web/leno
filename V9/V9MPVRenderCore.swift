import Foundation
import Libmpv

final class V9MPVRenderCore:
    @unchecked Sendable
{
    private final class CallbackBox:
        @unchecked Sendable
    {
        let callback:
            () -> Void

        init(
            callback:
                @escaping () -> Void
        ) {
            self.callback =
                callback
        }
    }

    private let lock =
        NSLock()

    private var context:
        OpaquePointer?

    private var callbackBox:
        Unmanaged<CallbackBox>?

    func create(
        mpv:
            OpaquePointer,
        onUpdate:
            @escaping () -> Void
    ) -> Bool {
        lock.lock()
        defer {
            lock.unlock()
        }

        if context != nil {
            return true
        }

        let apiType =
            UnsafeMutableRawPointer(
                mutating:
                    (
                        MPV_RENDER_API_TYPE_SW
                            as NSString
                    )
                    .utf8String
            )

        var created:
            OpaquePointer?

        var parameters:
            [mpv_render_param] = [
                mpv_render_param(
                    type:
                        MPV_RENDER_PARAM_API_TYPE,
                    data:
                        apiType
                ),
                mpv_render_param(
                    type:
                        MPV_RENDER_PARAM_INVALID,
                    data:
                        nil
                )
            ]

        let result =
            parameters
                .withUnsafeMutableBufferPointer {
                    buffer in

                    mpv_render_context_create(
                        &created,
                        mpv,
                        buffer.baseAddress
                    )
                }

        guard result >= 0,
              let created
        else {
            return false
        }

        let box =
            Unmanaged
                .passRetained(
                    CallbackBox(
                        callback:
                            onUpdate
                    )
                )

        mpv_render_context_set_update_callback(
            created,
            {
                raw in

                guard let raw
                else {
                    return
                }

                Unmanaged<
                    CallbackBox
                >
                .fromOpaque(
                    raw
                )
                .takeUnretainedValue()
                .callback()
            },
            box.toOpaque()
        )

        context =
            created

        callbackBox =
            box

        return true
    }

    func consumeUpdate()
        -> Bool
    {
        lock.lock()
        defer {
            lock.unlock()
        }

        guard let context
        else {
            return false
        }

        let flags =
            mpv_render_context_update(
                context
            )

        return (
            flags &
            UInt64(
                MPV_RENDER_UPDATE_FRAME
                    .rawValue
            )
        ) != 0
    }

    func renderSoftware(
        width:
            Int32,
        height:
            Int32,
        stride:
            Int,
        pixels:
            UnsafeMutableRawPointer
    ) -> Bool {
        guard width > 0,
              height > 0,
              stride > 0
        else {
            return false
        }

        lock.lock()
        defer {
            lock.unlock()
        }

        guard let context
        else {
            return false
        }

        var size:
            [Int32] = [
                width,
                height
            ]

        var strideValue =
            stride

        let format =
            UnsafeMutableRawPointer(
                mutating:
                    (
                        "bgr0"
                            as NSString
                    )
                    .utf8String
            )

        return size
            .withUnsafeMutableBufferPointer {
                sizeBuffer in

                withUnsafeMutablePointer(
                    to:
                        &strideValue
                ) {
                    stridePointer in

                    var parameters:
                        [mpv_render_param] = [
                            mpv_render_param(
                                type:
                                    MPV_RENDER_PARAM_SW_SIZE,
                                data:
                                    sizeBuffer
                                        .baseAddress
                            ),
                            mpv_render_param(
                                type:
                                    MPV_RENDER_PARAM_SW_FORMAT,
                                data:
                                    format
                            ),
                            mpv_render_param(
                                type:
                                    MPV_RENDER_PARAM_SW_STRIDE,
                                data:
                                    stridePointer
                            ),
                            mpv_render_param(
                                type:
                                    MPV_RENDER_PARAM_SW_POINTER,
                                data:
                                    pixels
                            ),
                            mpv_render_param(
                                type:
                                    MPV_RENDER_PARAM_INVALID,
                                data:
                                    nil
                            )
                        ]

                    return parameters
                        .withUnsafeMutableBufferPointer {
                            buffer in

                            mpv_render_context_render(
                                context,
                                buffer.baseAddress
                            )
                        } >= 0
                }
            }
    }

    func skipFrame() {
        lock.lock()
        defer {
            lock.unlock()
        }

        guard let context
        else {
            return
        }

        var skip:
            Int32 = 1

        withUnsafeMutablePointer(
            to:
                &skip
        ) {
            skipPointer in

            var parameters:
                [mpv_render_param] = [
                    mpv_render_param(
                        type:
                            MPV_RENDER_PARAM_SKIP_RENDERING,
                        data:
                            skipPointer
                    ),
                    mpv_render_param(
                        type:
                            MPV_RENDER_PARAM_INVALID,
                        data:
                            nil
                    )
                ]

            _ =
                parameters
                    .withUnsafeMutableBufferPointer {
                        buffer in

                        mpv_render_context_render(
                            context,
                            buffer.baseAddress
                        )
                    }
        }
    }

    func shutdown() {
        lock.lock()
        defer {
            lock.unlock()
        }

        guard let context
        else {
            callbackBox?
                .release()

            callbackBox =
                nil

            return
        }

        mpv_render_context_set_update_callback(
            context,
            nil,
            nil
        )

        mpv_render_context_free(
            context
        )

        self.context =
            nil

        callbackBox?
            .release()

        callbackBox =
            nil
    }
}
