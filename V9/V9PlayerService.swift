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

    typealias RefreshProvider =
        (String) async throws -> ResolvedVideo

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

    private var refreshProvider:
        RefreshProvider?

    private var currentVideoID:
        String?

    private var refreshTask:
        Task<Void, Never>?

    private var refreshAttempts =
        0

    private let maximumRefreshAttempts =
        3

    private var pendingSeekAfterLoad:
        Double?

    private var interruptionActive =
        false

    private var audioNotificationTokens:
        [NSObjectProtocol] =
            []

    init() {
        configureAudioSession()
        configureAudioNotifications()
        configureRemoteCommands()
    }

    deinit {
        MainActor.assumeIsolated {
            refreshTask?
                .cancel()

            for token in
                audioNotificationTokens {
                NotificationCenter
                    .default
                    .removeObserver(
                        token
                    )
            }

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
            // SwiftUI may recreate the UIView while the mpv core/render
            // context stays alive. Always bind the new surface to the
            // persistent service; createRenderContext() is idempotent.
            guard renderView.attach(
                service:
                    self
            ) else {
                fail(
                    "Nu am putut atașa suprafața libmpv."
                )
                return
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

            let resumeAt =
                pendingSeekAfterLoad

            beginLoad(
                pendingMedia,
                resumeAt:
                    resumeAt
            )
        }
    }

    func createRenderContext()
        -> Bool
    {
        if renderContext != nil {
            return true
        }

        guard let mpv else {
            return false
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

        var context:
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
                        &context,
                        mpv,
                        buffer.baseAddress
                    )
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
        guard let renderContext,
              width > 0,
              height > 0,
              stride > 0
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

        var parameters:
            [mpv_render_param] = []

        let result =
            size
                .withUnsafeMutableBufferPointer {
                    sizeBuffer in

                    withUnsafeMutablePointer(
                        to:
                            &strideValue
                    ) {
                        stridePointer in

                        parameters = [
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
                                    renderContext,
                                    buffer.baseAddress
                                )
                            }
                    }
                }

        return result >= 0
    }

    func skipRenderFrame() {
        guard let renderContext
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
                            renderContext,
                            buffer.baseAddress
                        )
                    }
        }
    }

    func load(
        _ media:
            ResolvedVideo,
        refreshProvider:
            RefreshProvider? = nil
    ) {
        refreshTask?
            .cancel()

        refreshTask =
            nil

        self.refreshProvider =
            refreshProvider

        currentVideoID =
            media.videoID

        refreshAttempts =
            0

        pendingSeekAfterLoad =
            nil

        beginLoad(
            media,
            resumeAt:
                nil
        )
    }

    private func beginLoad(
        _ media:
            ResolvedVideo,
        resumeAt:
            Double?
    ) {
        if resumeAt == nil {
            desiredPlayback =
                true
        }

        pendingSeekAfterLoad =
            resumeAt

        guard mpv != nil,
              renderContext != nil
        else {
            pendingMedia =
                media

            title =
                media.title

            return
        }

        pipBridge?
            .prepareForMediaChange()

        title =
            media.title

        hasVideoRelay =
            true

        hasAudioRelay =
            media.audio != nil

        hasLoadedMedia =
            false

        currentTime =
            max(
                0,
                resumeAt ?? 0
            )

        duration =
            media.duration ?? 0

        state =
            .loading

        clearNowPlaying()
        activateAudioSession()

        let loadTarget:
            String

        if let audio =
                media.audio {
            loadTarget =
                makeEDL(
                    video:
                        media.video
                            .relayURL,
                    audio:
                        audio.relayURL
                )
        } else {
            loadTarget =
                media.video
                    .relayURL
                    .absoluteString
        }

        // Keep the replacement paused until FILE_LOADED so a refreshed
        // stream can be restored to the previous timestamp before resuming.
        setPause(
            true
        )

        command(
            [
                "loadfile",
                loadTarget,
                "replace"
            ]
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

            if desiredPlayback,
               hasLoadedMedia,
               !interruptionActive {
                activateAudioSession()
            }

        case .active:
            if desiredPlayback,
               hasLoadedMedia,
               !interruptionActive {
                activateAudioSession()
            }

            renderView?
                .resumeRendering()

            if desiredPlayback,
               hasLoadedMedia,
               !interruptionActive {
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

    private func makeEDL(
        video: URL,
        audio: URL
    ) -> String {
        func escape(
            _ url: URL
        ) -> String {
            let value =
                url.absoluteString

            return "%\(value.utf8.count)%\(value)"
        }

        return "edl://!new_stream;!no_clip;!no_chapters;\(escape(video));!new_stream;\(escape(audio))"
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

    private func configureAudioNotifications() {
        let center =
            NotificationCenter
                .default

        let session =
            AVAudioSession
                .sharedInstance()

        audioNotificationTokens.append(
            center.addObserver(
                forName:
                    AVAudioSession
                        .interruptionNotification,
                object:
                    session,
                queue:
                    .main
            ) {
                [weak self] notification in

                Task {
                    @MainActor in

                    self?
                        .handleAudioInterruption(
                            notification
                        )
                }
            }
        )

        audioNotificationTokens.append(
            center.addObserver(
                forName:
                    AVAudioSession
                        .routeChangeNotification,
                object:
                    session,
                queue:
                    .main
            ) {
                [weak self] notification in

                Task {
                    @MainActor in

                    self?
                        .handleRouteChange(
                            notification
                        )
                }
            }
        )

        audioNotificationTokens.append(
            center.addObserver(
                forName:
                    AVAudioSession
                        .mediaServicesWereResetNotification,
                object:
                    session,
                queue:
                    .main
            ) {
                [weak self] _ in

                Task {
                    @MainActor in

                    self?
                        .handleMediaServicesReset()
                }
            }
        )
    }

    private func handleAudioInterruption(
        _ notification:
            Notification
    ) {
        guard
            let rawType =
                notification
                    .userInfo?[
                        AVAudioSessionInterruptionTypeKey
                    ] as?
                    UInt,
            let type =
                AVAudioSession
                    .InterruptionType(
                        rawValue:
                            rawType
                    )
        else {
            return
        }

        switch type {
        case .began:
            interruptionActive =
                true

            if desiredPlayback,
               hasLoadedMedia {
                // System interruption is not a user Pause. Preserve intent.
                setPause(
                    true
                )
            }

        case .ended:
            interruptionActive =
                false

            let rawOptions =
                notification
                    .userInfo?[
                        AVAudioSessionInterruptionOptionKey
                    ] as?
                    UInt ?? 0

            let options =
                AVAudioSession
                    .InterruptionOptions(
                        rawValue:
                            rawOptions
                    )

            if options.contains(
                .shouldResume
            ),
               desiredPlayback,
               hasLoadedMedia {
                activateAudioSession()

                setPause(
                    false
                )
            } else if desiredPlayback {
                // The system explicitly did not grant automatic resume.
                // Treat this as a stopped intent so scene activation cannot
                // restart playback behind the user's back.
                desiredPlayback =
                    false

                if hasLoadedMedia {
                    setPause(
                        true
                    )
                }
            }

        @unknown default:
            break
        }
    }

    private func handleRouteChange(
        _ notification:
            Notification
    ) {
        guard
            let rawReason =
                notification
                    .userInfo?[
                        AVAudioSessionRouteChangeReasonKey
                    ] as?
                    UInt,
            let reason =
                AVAudioSession
                    .RouteChangeReason(
                        rawValue:
                            rawReason
                    )
        else {
            return
        }

        if reason ==
            .oldDeviceUnavailable {
            // Unplugging headphones is a real safety pause.
            pause()
        }
    }

    private func handleMediaServicesReset() {
        configureAudioSession()

        if desiredPlayback,
           hasLoadedMedia,
           !interruptionActive {
            activateAudioSession()

            setPause(
                false
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

                if let pendingSeekAfterLoad {
                    self.pendingSeekAfterLoad =
                        nil

                    seek(
                        to:
                            pendingSeekAfterLoad
                    )
                }

                if desiredPlayback,
                   !interruptionActive {
                    setPause(
                        false
                    )
                } else {
                    setPause(
                        true
                    )
                }

                updatePiPPlaybackState()

                renderView?
                    .requestRender()

            case MPV_EVENT_END_FILE:
                handleEndFile(
                    event
                )

            case MPV_EVENT_SHUTDOWN:
                return

            default:
                break
            }
        }
    }

    private func handleEndFile(
        _ event:
            UnsafePointer<mpv_event>
    ) {
        guard let raw =
                event.pointee.data
        else {
            return
        }

        let endFile =
            raw
                .assumingMemoryBound(
                    to:
                        mpv_event_end_file
                            .self
                )
                .pointee

        switch endFile.reason {
        case MPV_END_FILE_REASON_EOF:
            let endedNaturally =
                duration > 0 &&
                currentTime >=
                    max(
                        0,
                        duration - 2
                    )

            if desiredPlayback,
               !endedNaturally {
                recoverFromStreamFailure(
                    "Fluxul s-a închis înainte de final."
                )
            } else {
                desiredPlayback =
                    false

                isPlaying =
                    false

                state =
                    .paused

                updateNowPlaying()
                updatePiPPlaybackState()
            }

        case MPV_END_FILE_REASON_ERROR:
            recoverFromStreamFailure(
                mpvErrorString(
                    endFile.error
                )
            )

        case MPV_END_FILE_REASON_STOP:
            // Expected when loadfile replace switches to another source.
            break

        case MPV_END_FILE_REASON_REDIRECT:
            break

        case MPV_END_FILE_REASON_QUIT:
            desiredPlayback =
                false

            isPlaying =
                false

        default:
            if desiredPlayback {
                recoverFromStreamFailure(
                    "Redarea s-a oprit neașteptat."
                )
            }
        }
    }

    private func recoverFromStreamFailure(
        _ detail:
            String
    ) {
        guard desiredPlayback,
              let currentVideoID,
              let refreshProvider
        else {
            fail(
                detail
            )
            return
        }

        let resumeAt =
            max(
                0,
                currentTime
            )

        hasLoadedMedia =
            false

        state =
            .loading

        refreshTask?
            .cancel()

        refreshTask =
            Task {
                [weak self] in

                guard let self else {
                    return
                }

                var lastError:
                    Error?

                while self.refreshAttempts <
                        self.maximumRefreshAttempts {
                    self.refreshAttempts +=
                        1

                    let attempt =
                        self.refreshAttempts

                    if attempt > 1 {
                        let delayNanoseconds:
                            UInt64

                        switch attempt {
                        case 2:
                            delayNanoseconds =
                                800_000_000

                        default:
                            delayNanoseconds =
                                2_000_000_000
                        }

                        try? await Task.sleep(
                            nanoseconds:
                                delayNanoseconds
                        )
                    }

                    guard !Task
                        .isCancelled
                    else {
                        return
                    }

                    do {
                        let refreshed =
                            try await refreshProvider(
                                currentVideoID
                            )

                        guard !Task
                            .isCancelled
                        else {
                            return
                        }

                        self.refreshTask =
                            nil

                        self.beginLoad(
                            refreshed,
                            resumeAt:
                                resumeAt
                        )

                        return
                    } catch {
                        lastError =
                            error
                    }
                }

                self.refreshTask =
                    nil

                self.fail(
                    "Reîmprospătarea streamului a eșuat după \(self.maximumRefreshAttempts) încercări: \(lastError?.localizedDescription ?? detail)"
                )
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

        isPiPPossible =
            pipBridge.isPossible

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

    private func clearNowPlaying() {
        let center =
            MPNowPlayingInfoCenter
                .default()

        center.nowPlayingInfo =
            nil

        center.playbackState =
            .stopped
    }

    private func fail(
        _ message:
            String
    ) {
        refreshTask?
            .cancel()

        refreshTask =
            nil

        desiredPlayback =
            false

        state =
            .failed(
                message
            )

        hasLoadedMedia =
            false

        isPlaying =
            false

        clearNowPlaying()
        updatePiPPlaybackState()
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
