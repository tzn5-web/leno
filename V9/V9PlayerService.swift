import AVFoundation
import Combine
import Foundation
import Libmpv
import MediaPlayer
import SwiftUI
import UIKit

@MainActor
final class V9PlayerService:
    ObservableObject
{
    enum LabState:
        Equatable
    {
        case idle
        case initializing
        case ready
        case loading
        case playing
        case paused
        case failed(String)
    }

    @Published
    private(set) var state:
        LabState = .idle

    @Published
    private(set) var title =
        "YoutubeVcd"

    @Published
    private(set) var isPlaying =
        false

    @Published
    private(set) var currentTime:
        Double = 0

    @Published
    private(set) var duration:
        Double = 0

    @Published
    private(set) var hasLoadedMedia =
        false

    @Published
    private(set) var hasVideoRelay =
        false

    @Published
    private(set) var hasAudioRelay =
        false

    @Published
    private(set) var isPiPPossible =
        false

    @Published
    private(set) var isPiPActive =
        false

    var stateDescription:
        String
    {
        switch state {
        case .idle:
            return "idle"
        case .initializing:
            return "initializing"
        case .ready:
            return "ready"
        case .loading:
            return "loading"
        case .playing:
            return "playing"
        case .paused:
            return "paused"
        case .failed(let message):
            return "failed: \(message)"
        }
    }

    private var mpv:
        OpaquePointer?

    private var renderContext:
        OpaquePointer?

    private weak var renderView:
        V9MPVRenderView?

    private var pipBridge:
        V9MPVPiPBridge?

    private var remoteTargets:
        [(MPRemoteCommand, Any)] =
            []

    private var pendingMedia:
        ResolvedVideo?

    private var desiredPlayback =
        false

    init() {
        configureAudioSession()
        configureRemoteCommands()
    }

    deinit {
        MainActor.assumeIsolated {
            pipBridge?
                .cleanup()

            for (
                command,
                token
            ) in remoteTargets {
                command.removeTarget(
                    token
                )
            }

            if let renderContext {
                mpv_render_context_set_update_callback(
                    renderContext,
                    nil,
                    nil
                )

                mpv_render_context_free(
                    renderContext
                )
            }

            if let mpv {
                mpv_set_wakeup_callback(
                    mpv,
                    nil,
                    nil
                )

                mpv_terminate_destroy(
                    mpv
                )
            }
        }
    }

    func attach(
        renderView:
            V9MPVRenderView
    ) {
        self.renderView =
            renderView

        if mpv != nil {
            if renderContext == nil {
                guard renderView.attach(
                    service:
                        self
                ) else {
                    fail(
                        "Nu am putut crea suprafața libmpv."
                    )
                    return
                }
            }

            setupPiPIfNeeded(
                renderView:
                    renderView
            )

            renderView.requestRender()
            return
        }

        state =
            .initializing

        guard let handle =
                mpv_create()
        else {
            fail(
                "mpv_create() a eșuat."
            )
            return
        }

        mpv =
            handle

        guard
            setOptionString(
                "vo",
                "libmpv"
            ),
            setOptionString(
                "hwdec",
                "videotoolbox-copy"
            ),
            setOptionString(
                "keep-open",
                "yes"
            ),
            setOptionString(
                "pause",
                "yes"
            ),
            setOptionString(
                "audio-display",
                "no"
            ),
            setOptionString(
                "terminal",
                "no"
            )
        else {
            fail(
                "Configurarea libmpv a eșuat."
            )
            return
        }

        let initResult =
            mpv_initialize(
                handle
            )

        guard initResult >= 0 else {
            fail(
                mpvErrorString(
                    initResult
                )
            )
            return
        }

        observe(
            "time-pos",
            format:
                MPV_FORMAT_DOUBLE
        )

        observe(
            "duration",
            format:
                MPV_FORMAT_DOUBLE
        )

        observe(
            "pause",
            format:
                MPV_FORMAT_FLAG
        )

        observe(
            "core-idle",
            format:
                MPV_FORMAT_FLAG
        )

        observe(
            "eof-reached",
            format:
                MPV_FORMAT_FLAG
        )

        mpv_set_wakeup_callback(
            handle,
            { context in
                guard let context else {
                    return
                }

                let service =
                    Unmanaged<
                        V9PlayerService
                    >
                    .fromOpaque(
                        context
                    )
                    .takeUnretainedValue()

                Task {
                    @MainActor in

                    service
                        .drainEvents()
                }
            },
            Unmanaged
                .passUnretained(
                    self
                )
                .toOpaque()
        )

        guard renderView.attach(
            service:
                self
        ) else {
            fail(
                "mpv_render_context_create() a eșuat."
            )
            return
        }

        setupPiPIfNeeded(
            renderView:
                renderView
        )

        state =
            .ready

        if let pendingMedia {
            self.pendingMedia =
                nil

            load(
                pendingMedia
            )
        }
    }

    func createRenderContext(
        getProcAddress:
            @escaping
            @convention(c)
            (
                UnsafeMutableRawPointer?,
                UnsafePointer<CChar>?
            ) ->
                UnsafeMutableRawPointer?
    ) -> Bool {
        if renderContext != nil {
            return true
        }

        guard let mpv else {
            return false
        }

        var apiType =
            MPV_RENDER_API_TYPE_OPENGL

        var glParameters =
            mpv_opengl_init_params(
                get_proc_address:
                    getProcAddress,
                get_proc_address_ctx:
                    nil
            )

        var context:
            OpaquePointer?

        let result =
            withUnsafeMutablePointer(
                to:
                    &apiType
            ) {
                apiPointer in

                withUnsafeMutablePointer(
                    to:
                        &glParameters
                ) {
                    glPointer in

                    var parameters:
                        [mpv_render_param] = [
                            mpv_render_param(
                                type:
                                    MPV_RENDER_PARAM_API_TYPE,
                                data:
                                    apiPointer
                            ),
                            mpv_render_param(
                                type:
                                    MPV_RENDER_PARAM_OPENGL_INIT_PARAMS,
                                data:
                                    glPointer
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

                            mpv_render_context_create(
                                &context,
                                mpv,
                                buffer.baseAddress
                            )
                        }
                }
            }

        guard result >= 0,
              let context
        else {
            return false
        }

        renderContext =
            context

        mpv_render_context_set_update_callback(
            context,
            { raw in
                guard let raw else {
                    return
                }

                let service =
                    Unmanaged<
                        V9PlayerService
                    >
                    .fromOpaque(
                        raw
                    )
                    .takeUnretainedValue()

                Task {
                    @MainActor in

                    service
                        .renderView?
                        .requestRender()
                }
            },
            Unmanaged
                .passUnretained(
                    self
                )
                .toOpaque()
        )

        return true
    }

    func consumeRenderUpdate()
        -> Bool
    {
        guard let renderContext
        else {
            return false
        }

        let flags =
            mpv_render_context_update(
                renderContext
            )

        return (
            flags &
            UInt64(
                MPV_RENDER_UPDATE_FRAME
                    .rawValue
            )
        ) != 0
    }

    func render(
        framebuffer:
            Int32,
        width:
            Int32,
        height:
            Int32
    ) {
        guard let renderContext,
              width > 0,
              height > 0
        else {
            return
        }

        var target =
            mpv_opengl_fbo(
                fbo:
                    framebuffer,
                w:
                    width,
                h:
                    height,
                internal_format:
                    0x8058
            )

        var flipY:
            Int32 = 1

        withUnsafeMutablePointer(
            to:
                &target
        ) {
            targetPointer in

            withUnsafeMutablePointer(
                to:
                    &flipY
            ) {
                flipPointer in

                var parameters:
                    [mpv_render_param] = [
                        mpv_render_param(
                            type:
                                MPV_RENDER_PARAM_OPENGL_FBO,
                            data:
                                targetPointer
                        ),
                        mpv_render_param(
                            type:
                                MPV_RENDER_PARAM_FLIP_Y,
                            data:
                                flipPointer
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
                                renderContext,
                                buffer.baseAddress
                            )
                        }
            }
        }
    }

    func load(
        _ media:
            ResolvedVideo
    ) {
        guard mpv != nil,
              renderContext != nil
        else {
            pendingMedia =
                media
            title =
                media.title
            return
        }

        title =
            media.title

        hasVideoRelay =
            true

        hasAudioRelay =
            media.audio != nil

        hasLoadedMedia =
            false

        currentTime =
            0

        duration =
            media.duration ?? 0

        desiredPlayback =
            true

        state =
            .loading

        activateAudioSession()

        command(
            [
                "loadfile",
                media.video
                    .relayURL
                    .absoluteString,
                "replace"
            ]
        )

        if let audio =
                media.audio {
            command(
                [
                    "audio-add",
                    audio.relayURL
                        .absoluteString,
                    "select",
                    "VcdResolver"
                ]
            )
        }

        setPause(
            false
        )
    }

    func play() {
        guard hasLoadedMedia ||
              state == .loading
        else {
            return
        }

        desiredPlayback =
            true

        activateAudioSession()

        setPause(
            false
        )
    }

    func pause() {
        desiredPlayback =
            false

        setPause(
            true
        )
    }

    func toggle() {
        isPlaying
            ? pause()
            : play()
    }

    func seek(
        by seconds:
            Double
    ) {
        seek(
            to:
                currentTime +
                seconds
        )
    }

    func seek(
        to seconds:
            Double
    ) {
        let target =
            max(
                0,
                duration > 0
                    ? min(
                        duration,
                        seconds
                    )
                    : seconds
            )

        command(
            [
                "seek",
                String(
                    format:
                        "%.3f",
                    target
                ),
                "absolute+exact"
            ]
        )
    }

    func togglePiP() {
        guard hasLoadedMedia else {
            return
        }

        pipBridge?
            .requestToggle()
    }

    func updatePiPLayerFrame(
        _ bounds:
            CGRect
    ) {
        pipBridge?
            .updateLayerFrame(
                bounds
            )
    }

    func handleScenePhase(
        _ phase:
            ScenePhase
    ) {
        switch phase {
        case .background:
            // Playback remains alive in the single MPV engine.
            // Without PiP, stop only visual rendering.
            // With PiP, keep producing frames for AVSampleBufferDisplayLayer.
            if pipBridge?
                .shouldKeepRendering ==
                true {
                renderView?
                    .resumeRendering()
            } else {
                renderView?
                    .pauseRendering()
            }

            activateAudioSession()

        case .active:
            activateAudioSession()

            renderView?
                .resumeRendering()

            if desiredPlayback,
               hasLoadedMedia {
                setPause(
                    false
                )
            }

        case .inactive:
            break

        @unknown default:
            break
        }
    }

    private func configureAudioSession() {
        do {
            let session =
                AVAudioSession
                    .sharedInstance()

            try session.setCategory(
                .playback,
                mode:
                    .moviePlayback,
                options:
                    []
            )

            try session.setActive(
                true
            )
        } catch {
            print(
                "V9 audio session: \(error)"
            )
        }
    }

    private func activateAudioSession() {
        do {
            try AVAudioSession
                .sharedInstance()
                .setActive(
                    true
                )
        } catch {
            print(
                "V9 audio activation: \(error)"
            )
        }
    }

    private func configureRemoteCommands() {
        let center =
            MPRemoteCommandCenter
                .shared()

        center.playCommand
            .isEnabled =
            true

        addRemoteTarget(
            center.playCommand
        ) {
            [weak self] _ in

            DispatchQueue.main.async {
                self?.play()
            }

            return .success
        }

        center.pauseCommand
            .isEnabled =
            true

        addRemoteTarget(
            center.pauseCommand
        ) {
            [weak self] _ in

            DispatchQueue.main.async {
                self?.pause()
            }

            return .success
        }

        center.togglePlayPauseCommand
            .isEnabled =
            true

        addRemoteTarget(
            center
                .togglePlayPauseCommand
        ) {
            [weak self] _ in

            DispatchQueue.main.async {
                self?.toggle()
            }

            return .success
        }

        center.skipForwardCommand
            .isEnabled =
            true

        center.skipForwardCommand
            .preferredIntervals =
            [15]

        addRemoteTarget(
            center.skipForwardCommand
        ) {
            [weak self] _ in

            DispatchQueue.main.async {
                self?.seek(
                    by:
                        15
                )
            }

            return .success
        }

        center.skipBackwardCommand
            .isEnabled =
            true

        center.skipBackwardCommand
            .preferredIntervals =
            [15]

        addRemoteTarget(
            center.skipBackwardCommand
        ) {
            [weak self] _ in

            DispatchQueue.main.async {
                self?.seek(
                    by:
                        -15
                )
            }

            return .success
        }

        center
            .changePlaybackPositionCommand
            .isEnabled =
            true

        addRemoteTarget(
            center
                .changePlaybackPositionCommand
        ) {
            [weak self] event in

            guard let event =
                    event as?
                        MPChangePlaybackPositionCommandEvent
            else {
                return .commandFailed
            }

            let position =
                event.positionTime

            DispatchQueue.main.async {
                self?.seek(
                    to:
                        position
                )
            }

            return .success
        }
    }

    private func addRemoteTarget(
        _ command:
            MPRemoteCommand,
        handler:
            @escaping (
                MPRemoteCommandEvent
            ) ->
                MPRemoteCommandHandlerStatus
    ) {
        let token =
            command.addTarget(
                handler:
                    handler
            )

        remoteTargets.append(
            (
                command,
                token
            )
        )
    }

    private func setPause(
        _ paused:
            Bool
    ) {
        guard let mpv else {
            return
        }

        var flag:
            Int32 =
            paused
                ? 1
                : 0

        let result =
            mpv_set_property(
                mpv,
                "pause",
                MPV_FORMAT_FLAG,
                &flag
            )

        if result < 0 {
            fail(
                mpvErrorString(
                    result
                )
            )
        }
    }

    private func setOptionString(
        _ name:
            String,
        _ value:
            String
    ) -> Bool {
        guard let mpv else {
            return false
        }

        return mpv_set_option_string(
            mpv,
            name,
            value
        ) >= 0
    }

    private func observe(
        _ name:
            String,
        format:
            mpv_format
    ) {
        guard let mpv else {
            return
        }

        _ =
            mpv_observe_property(
                mpv,
                0,
                name,
                format
            )
    }

    private func command(
        _ arguments:
            [String]
    ) {
        guard let mpv else {
            return
        }

        var storage =
            arguments.map {
                strdup(
                    $0
                )
            }

        storage.append(
            nil
        )

        defer {
            for pointer in storage
                where pointer != nil {
                    free(
                        pointer
                    )
            }
        }

        var pointers =
            storage.map {
                $0.map {
                    UnsafePointer(
                        $0
                    )
                }
            }

        let result =
            pointers
                .withUnsafeMutableBufferPointer {
                    buffer in

                    mpv_command(
                        mpv,
                        buffer.baseAddress
                    )
                }

        if result < 0 {
            fail(
                mpvErrorString(
                    result
                )
            )
        }
    }

    private func drainEvents() {
        guard let mpv else {
            return
        }

        while true {
            guard let event =
                    mpv_wait_event(
                        mpv,
                        0
                    )
            else {
                return
            }

            let eventID =
                event.pointee
                    .event_id

            if eventID ==
                MPV_EVENT_NONE {
                return
            }

            switch eventID {
            case MPV_EVENT_PROPERTY_CHANGE:
                handlePropertyEvent(
                    event
                )

            case MPV_EVENT_FILE_LOADED:
                hasLoadedMedia =
                    true

                if desiredPlayback {
                    setPause(
                        false
                    )
                }

                updatePiPPlaybackState()

                renderView?
                    .requestRender()

            case MPV_EVENT_END_FILE:
                isPlaying =
                    false

                state =
                    .paused

                updateNowPlaying()

            case MPV_EVENT_SHUTDOWN:
                return

            default:
                break
            }
        }
    }

    private func handlePropertyEvent(
        _ event:
            UnsafePointer<mpv_event>
    ) {
        guard let raw =
                event.pointee.data
        else {
            return
        }

        let property =
            raw
                .assumingMemoryBound(
                    to:
                        mpv_event_property
                            .self
                )
                .pointee

        guard let namePointer =
                property.name
        else {
            return
        }

        let name =
            String(
                cString:
                    namePointer
            )

        switch name {
        case "time-pos":
            guard property.format ==
                    MPV_FORMAT_DOUBLE,
                  let data =
                    property.data
            else {
                return
            }

            let value =
                data
                    .assumingMemoryBound(
                        to:
                            Double.self
                    )
                    .pointee

            currentTime =
                max(
                    0,
                    value
                )

            updateNowPlaying()
            updatePiPPlaybackState()

        case "duration":
            guard property.format ==
                    MPV_FORMAT_DOUBLE,
                  let data =
                    property.data
            else {
                return
            }

            let value =
                data
                    .assumingMemoryBound(
                        to:
                            Double.self
                    )
                    .pointee

            if value.isFinite {
                duration =
                    max(
                        0,
                        value
                    )
            }

            updateNowPlaying()
            updatePiPPlaybackState()

        case "pause":
            guard property.format ==
                    MPV_FORMAT_FLAG,
                  let data =
                    property.data
            else {
                return
            }

            let paused =
                data
                    .assumingMemoryBound(
                        to:
                            Int32.self
                    )
                    .pointee != 0

            isPlaying =
                !paused

            if hasLoadedMedia {
                state =
                    paused
                        ? .paused
                        : .playing
            }

            updateNowPlaying()
            updatePiPPlaybackState()

        default:
            break
        }
    }

    private func setupPiPIfNeeded(
        renderView:
            V9MPVRenderView
    ) {
        if pipBridge == nil {
            pipBridge =
                V9MPVPiPBridge()
        }

        guard let pipBridge else {
            return
        }

        pipBridge.setup(
            service:
                self,
            renderView:
                renderView
        )

        pipBridge.onPossibleChanged = {
            [weak self] possible in

            self?.isPiPPossible =
                possible
        }

        pipBridge.onActiveChanged = {
            [weak self] active in

            guard let self else {
                return
            }

            self.isPiPActive =
                active

            if active {
                self.renderView?
                    .resumeRendering()
            } else if UIApplication
                .shared
                .applicationState ==
                .background {
                self.renderView?
                    .pauseRendering()
            }
        }

        renderView.onFrame = {
            [weak pipBridge] pixelBuffer,
            presentationTime in

            pipBridge?
                .enqueueFrame(
                    pixelBuffer,
                    presentationTime:
                        presentationTime
                )
        }

        updatePiPPlaybackState()
    }

    private func updatePiPPlaybackState() {
        pipBridge?
            .updatePlaybackState(
                duration:
                    duration,
                currentTime:
                    currentTime,
                isPaused:
                    !isPlaying
            )
    }

    private func updateNowPlaying() {
        guard hasLoadedMedia else {
            return
        }

        var info:
            [String: Any] = [
                MPMediaItemPropertyTitle:
                    title,
                MPNowPlayingInfoPropertyElapsedPlaybackTime:
                    currentTime,
                MPNowPlayingInfoPropertyPlaybackRate:
                    isPlaying
                        ? 1.0
                        : 0.0,
                MPNowPlayingInfoPropertyDefaultPlaybackRate:
                    1.0
            ]

        if duration > 0 {
            info[
                MPMediaItemPropertyPlaybackDuration
            ] =
                duration
        }

        let center =
            MPNowPlayingInfoCenter
                .default()

        center.nowPlayingInfo =
            info

        center.playbackState =
            isPlaying
                ? .playing
                : .paused
    }

    private func fail(
        _ message:
            String
    ) {
        state =
            .failed(
                message
            )

        isPlaying =
            false
    }

    private func mpvErrorString(
        _ code:
            Int32
    ) -> String {
        guard let pointer =
                mpv_error_string(
                    code
                )
        else {
            return "libmpv error \(code)"
        }

        return String(
            cString:
                pointer
        )
    }
}
