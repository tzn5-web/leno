import Foundation
import YouTubeKit

actor V9NativePlaybackWorker
{
    enum PlaybackError:
        LocalizedError
    {
        case noPlayableFormats

        var errorDescription:
            String?
        {
            "YouTube nu a returnat un flux redabil pentru acest videoclip."
        }
    }

    private let youtube =
        YouTubeModel()

    private let tv =
        YouTubeModel()

    init() {
        Self
            .installTVOverrides(
                on:
                    tv
            )
    }

    func resolve(
        videoID:
            String
    ) async throws
        -> ResolvedVideo
    {
        await ensureVisitorData()

        var watchInfo:
            VideoInfosResponse?

        var watchPlayer:
            PlayerProcessing.Player?

        // First obtain the real /watch page. This gives us the current
        // base.js player so both signatureCipher and n can be processed with
        // the exact JavaScript YouTube is serving right now.
        do {
            var info =
                try await VideoInfosResponse
                    .sendThrowingRequest(
                        youtubeModel:
                            youtube,
                        data:
                            [
                                .query:
                                    videoID
                            ]
                    )

            watchPlayer =
                info.player

            // VideoInfosResponse.decodeData already decodes n in the watch
            // HLS URL. Prefer that PO-token-light path immediately when it is
            // available.
            if let resolved =
                    try? makeResolvedVideo(
                        videoID:
                            videoID,
                        info:
                            info,
                        adaptiveFormats:
                            [],
                        progressiveFormats:
                            []
                    ) {
                return resolved
            }

            watchInfo =
                info
        } catch {
            watchInfo =
                nil

            watchPlayer =
                nil
        }

        // Next ask the current TVHTML5 Innertube client for streamingData.
        // Plain TVHTML5 is intentionally used instead of TVHTML5_SIMPLY:
        // current yt-dlp policy does not mark plain TVHTML5 GVS as requiring
        // a PO token. If we got the watch-page player above, apply it to the
        // TV URLs as well so n/signatureCipher are not left raw.
        do {
            let response =
                try await VideoInfosWithDownloadFormatsResponse
                    .sendThrowingRequest(
                        youtubeModel:
                            tv,
                        data:
                            [
                                .query:
                                    videoID
                            ]
                    )

            var info =
                response
                    .videoInfos

            var adaptiveFormats =
                response
                    .downloadFormats

            var progressiveFormats =
                response
                    .defaultFormats

            if let watchPlayer {
                if let hls =
                        info.streamingURL {
                    info.streamingURL =
                        watchPlayer
                            .decodeNParameterInHLSManifestURL(
                                hls
                                    .absoluteString
                            )
                }

                try processFormats(
                    &adaptiveFormats,
                    player:
                        watchPlayer
                )

                try processFormats(
                    &progressiveFormats,
                    player:
                        watchPlayer
                )
            }

            return try makeResolvedVideo(
                videoID:
                    videoID,
                info:
                    info,
                adaptiveFormats:
                    adaptiveFormats,
                progressiveFormats:
                    progressiveFormats
            )
        } catch {
            // If TV extraction itself fails, still use the watch-page formats
            // after deciphering them with the player that came from that same
            // page. WEB direct GVS can be stricter than HLS, so this remains
            // the last on-device path before the optional external resolver.
        }

        guard var info =
                watchInfo
        else {
            throw PlaybackError
                .noPlayableFormats
        }

        var adaptiveFormats =
            info.downloadFormats

        var progressiveFormats =
            info.defaultFormats

        if let watchPlayer {
            try processFormats(
                &adaptiveFormats,
                player:
                    watchPlayer
            )

            try processFormats(
                &progressiveFormats,
                player:
                    watchPlayer
            )

            if let hls =
                    info.streamingURL {
                info.streamingURL =
                    watchPlayer
                        .decodeNParameterInHLSManifestURL(
                            hls
                                .absoluteString
                        )
            }
        }

        return try makeResolvedVideo(
            videoID:
                videoID,
            info:
                info,
            adaptiveFormats:
                adaptiveFormats,
            progressiveFormats:
                progressiveFormats
        )
    }

    private func processFormats(
        _ formats:
            inout [any AdaptiveDownloadFormat],
        player:
            PlayerProcessing.Player
    ) throws {
        for index in
            formats.indices {
            var format =
                formats[
                    index
                ]

            try player
                .processDownloadFormatURL(
                    item:
                        &format
                )

            formats[
                index
            ] =
                format
        }
    }

    private func makeResolvedVideo(
        videoID:
            String,
        info:
            VideoInfosResponse,
        adaptiveFormats:
            [any AdaptiveDownloadFormat],
        progressiveFormats:
            [any AdaptiveDownloadFormat]
    ) throws
        -> ResolvedVideo
    {
        // Use HLS for both VOD and live whenever YouTube provides it. Current
        // WebPO policy makes direct HTTPS/DASH considerably more fragile than
        // HLS, and MPV handles the same HLS URL for foreground/background/PiP.
        if let hls =
                info.streamingURL,
           isHTTPS(
                hls
           ) {
            return ResolvedVideo(
                videoID:
                    videoID,
                title:
                    info.title ??
                    "YouTube",
                duration:
                    nil,
                thumbnail:
                    info.thumbnails
                        .last?
                        .url,
                video:
                    ResolvedStream(
                        relayURL:
                            hls,
                        formatID:
                            info.isLive ==
                                true
                                ? "hls-live"
                                : "hls-vod",
                        container:
                            "m3u8",
                        videoCodec:
                            nil,
                        audioCodec:
                            "embedded",
                        height:
                            nil,
                        fps:
                            nil,
                        bitrate:
                            nil
                    ),
                audio:
                    nil,
                expiresIn:
                    secondsUntilExpiry(
                        info.videoURLsExpireAt
                    )
            )
        }

        let adaptiveVideos =
            adaptiveFormats
                .compactMap {
                    $0 as?
                        VideoDownloadFormat
                }
                .filter {
                    isEligibleVideo(
                        $0
                    )
                }

        let preferredVideos =
            adaptiveVideos
                .filter {
                    isPreferredH264MP4(
                        $0
                    )
                }

        let selectedVideo =
            bestVideo(
                preferredVideos
                    .isEmpty
                    ? adaptiveVideos
                    : preferredVideos
            )

        let adaptiveAudio =
            adaptiveFormats
                .compactMap {
                    $0 as?
                        AudioOnlyFormat
                }
                .filter {
                    guard let url =
                            $0.url
                    else {
                        return false
                    }

                    return isHTTPS(
                        url
                    )
                }

        let preferredAudio =
            adaptiveAudio
                .filter {
                    format in

                    let mime =
                        format.mimeType?
                            .lowercased() ??
                        ""

                    let codec =
                        format.codec?
                            .lowercased() ??
                        ""

                    return mime.contains(
                        "mp4"
                    ) &&
                    (
                        codec.contains(
                            "mp4a"
                        ) ||
                        codec.contains(
                            "aac"
                        )
                    ) &&
                    !format.isDrc
                }

        let selectedAudio =
            (
                preferredAudio
                    .isEmpty
                    ? adaptiveAudio
                    : preferredAudio
            )
            .max {
                lhs,
                rhs in

                (
                    lhs.bitrate ??
                    lhs.averageBitrate ??
                    0
                ) <
                (
                    rhs.bitrate ??
                    rhs.averageBitrate ??
                    0
                )
            }

        if let selectedVideo,
           let videoURL =
                selectedVideo.url,
           let selectedAudio,
           let audioURL =
                selectedAudio.url {
            return ResolvedVideo(
                videoID:
                    videoID,
                title:
                    info.title ??
                    "YouTube",
                duration:
                    selectedVideo
                        .contentDuration
                        .map {
                            Double(
                                $0
                            ) /
                            1000
                        },
                thumbnail:
                    info.thumbnails
                        .last?
                        .url,
                video:
                    stream(
                        video:
                            selectedVideo,
                        url:
                            videoURL
                    ),
                audio:
                    stream(
                        audio:
                            selectedAudio,
                        url:
                            audioURL
                    ),
                expiresIn:
                    secondsUntilExpiry(
                        info.videoURLsExpireAt
                    )
            )
        }

        let progressiveVideos =
            progressiveFormats
                .compactMap {
                    $0 as?
                        VideoDownloadFormat
                }
                .filter {
                    isEligibleVideo(
                        $0
                    )
                }

        let preferredProgressive =
            progressiveVideos
                .filter {
                    isPreferredH264MP4(
                        $0
                    )
                }

        guard let progressive =
                bestVideo(
                    preferredProgressive
                        .isEmpty
                        ? progressiveVideos
                        : preferredProgressive
                ),
              let progressiveURL =
                progressive.url
        else {
            throw PlaybackError
                .noPlayableFormats
        }

        return ResolvedVideo(
            videoID:
                videoID,
            title:
                info.title ??
                "YouTube",
            duration:
                progressive
                    .contentDuration
                    .map {
                        Double(
                            $0
                        ) /
                        1000
                    },
            thumbnail:
                info.thumbnails
                    .last?
                    .url,
            video:
                ResolvedStream(
                    relayURL:
                        progressiveURL,
                    formatID:
                        String(
                            progressive.itag
                        ),
                    container:
                        container(
                            progressive.mimeType
                        ),
                    videoCodec:
                        progressive.codec,
                    audioCodec:
                        "embedded",
                    height:
                        progressive.height,
                    fps:
                        progressive.fps
                            .map(
                                Double.init
                            ),
                    bitrate:
                        Double(
                            progressive.bitrate ??
                            progressive.averageBitrate ??
                            0
                        )
                ),
            audio:
                nil,
            expiresIn:
                secondsUntilExpiry(
                    info.videoURLsExpireAt
                )
        )
    }

    private func isEligibleVideo(
        _ format:
            VideoDownloadFormat
    ) -> Bool {
        guard let url =
                format.url,
              isHTTPS(
                url
              )
        else {
            return false
        }

        let height =
            format.height ??
            0

        let fps =
            format.fps ??
            0

        return height <=
                1080 &&
               (
                   fps ==
                   0 ||
                   fps <=
                   30
               )
    }

    private func isPreferredH264MP4(
        _ format:
            VideoDownloadFormat
    ) -> Bool {
        let mime =
            format.mimeType?
                .lowercased() ??
            ""

        let codec =
            format.codec?
                .lowercased() ??
            ""

        return mime.contains(
            "mp4"
        ) &&
        (
            codec.contains(
                "avc1"
            ) ||
            codec.contains(
                "h264"
            )
        )
    }

    private func bestVideo(
        _ formats:
            [VideoDownloadFormat]
    ) -> VideoDownloadFormat? {
        formats.max {
            lhs,
            rhs in

            let left =
                (
                    lhs.height ??
                    0,
                    lhs.bitrate ??
                    lhs.averageBitrate ??
                    0
                )

            let right =
                (
                    rhs.height ??
                    0,
                    rhs.bitrate ??
                    rhs.averageBitrate ??
                    0
                )

            return left <
                right
        }
    }

    private func stream(
        video:
            VideoDownloadFormat,
        url:
            URL
    ) -> ResolvedStream {
        ResolvedStream(
            relayURL:
                url,
            formatID:
                String(
                    video.itag
                ),
            container:
                container(
                    video.mimeType
                ),
            videoCodec:
                video.codec,
            audioCodec:
                nil,
            height:
                video.height,
            fps:
                video.fps
                    .map(
                        Double.init
                    ),
            bitrate:
                Double(
                    video.bitrate ??
                    video.averageBitrate ??
                    0
                )
        )
    }

    private func stream(
        audio:
            AudioOnlyFormat,
        url:
            URL
    ) -> ResolvedStream {
        ResolvedStream(
            relayURL:
                url,
            formatID:
                String(
                    audio.itag
                ),
            container:
                container(
                    audio.mimeType
                ),
            videoCodec:
                nil,
            audioCodec:
                audio.codec,
            height:
                nil,
            fps:
                nil,
            bitrate:
                Double(
                    audio.bitrate ??
                    audio.averageBitrate ??
                    0
                )
        )
    }

    private func ensureVisitorData()
        async
    {
        guard youtube
            .visitorData
            .isEmpty
        else {
            if tv
                .visitorData
                .isEmpty {
                tv.visitorData =
                    youtube.visitorData
            }

            return
        }

        do {
            let response =
                try await SearchResponse
                    .sendThrowingRequest(
                        youtubeModel:
                            youtube,
                        data:
                            [
                                .query:
                                    "music"
                            ]
                    )

            guard let visitorData =
                    response.visitorData,
                  !visitorData
                    .isEmpty
            else {
                return
            }

            youtube.visitorData =
                visitorData

            tv.visitorData =
                visitorData
        } catch {
            // The player request may still succeed without a bootstrapped
            // visitor token. Playback must not be blocked by this probe.
        }
    }

    private static func installTVOverrides(
        on model:
            YouTubeModel
    ) {
        let clientVersion =
            "7.20260707.07.00"

        let userAgent =
            "Mozilla/5.0 (ChromiumStylePlatform) Cobalt/25.lts.30.1034943-gold (unlike Gecko), Unknown_TV_Unknown_0/Unknown (Unknown, Unknown)"

        let bodyPrefix =
            #"{"contentCheckOk":true,"context":{"client":{"clientName":"TVHTML5","clientVersion":"7.20260707.07.00","hl":"en","gl":"US","userAgent":"Mozilla/5.0 (ChromiumStylePlatform) Cobalt/25.lts.30.1034943-gold (unlike Gecko), Unknown_TV_Unknown_0/Unknown (Unknown, Unknown)"},"request":{"useSsl":true}},"playbackContext":{"contentPlaybackContext":{"html5Preference":"HTML5_PREF_WANTS"}},"racyCheckOk":true,"videoId":""#

        let headers =
            HeadersList(
                url:
                    URL(
                        string:
                            "https://www.youtube.com/youtubei/v1/player"
                    )!,
                method:
                    .POST,
                headers:
                    [
                        .init(
                            name:
                                "Accept",
                            content:
                                "*/*"
                        ),
                        .init(
                            name:
                                "Accept-Encoding",
                            content:
                                "gzip, deflate, br"
                        ),
                        .init(
                            name:
                                "Host",
                            content:
                                "www.youtube.com"
                        ),
                        .init(
                            name:
                                "User-Agent",
                            content:
                                userAgent
                        ),
                        .init(
                            name:
                                "Content-Type",
                            content:
                                "application/json"
                        ),
                        .init(
                            name:
                                "Origin",
                            content:
                                "https://www.youtube.com"
                        ),
                        .init(
                            name:
                                "Referer",
                            content:
                                "https://www.youtube.com/"
                        ),
                        .init(
                            name:
                                "X-Youtube-Client-Name",
                            content:
                                "7"
                        ),
                        .init(
                            name:
                                "X-Youtube-Client-Version",
                            content:
                                clientVersion
                        )
                    ],
                customHeaders:
                    [
                        "X-Goog-Visitor-Id":
                            .visitorData
                    ],
                addQueryAfterParts:
                    [
                        .init(
                            index:
                                0,
                            encode:
                                false,
                            content:
                                .query
                        )
                    ],
                httpBody:
                    [
                        bodyPrefix,
                        "\"}"
                    ],
                parameters:
                    [
                        .init(
                            name:
                                "prettyPrint",
                            content:
                                "false"
                        )
                    ]
            )

        model
            .customHeaders[
                .videoInfosWithDownloadFormats
            ] =
            headers
    }

    private func isHTTPS(
        _ url:
            URL
    ) -> Bool {
        url.scheme?
            .lowercased() ==
            "https"
    }

    private func secondsUntilExpiry(
        _ date:
            Date?
    ) -> Int {
        guard let date
        else {
            return 21_600
        }

        return max(
            60,
            Int(
                date
                    .timeIntervalSinceNow
            )
        )
    }

    private func container(
        _ mimeType:
            String?
    ) -> String {
        let value =
            mimeType?
                .lowercased() ??
            ""

        if value.contains(
            "webm"
        ) {
            return "webm"
        }

        if value.contains(
            "mp4"
        ) {
            return "mp4"
        }

        return "unknown"
    }
}
