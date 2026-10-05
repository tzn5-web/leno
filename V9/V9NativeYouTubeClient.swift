import Foundation
import YouTubeKit

@MainActor
final class V9NativeYouTubeClient:
    ObservableObject
{
    enum NativeError:
        LocalizedError
    {
        case noPlayableFormats
        case noHomeResults
        case invalidChannel

        var errorDescription:
            String?
        {
            switch self {
            case .noPlayableFormats:
                return "YouTube nu a returnat un flux compatibil pentru acest videoclip."

            case .noHomeResults:
                return "YouTube nu a returnat videoclipuri pentru Home."

            case .invalidChannel:
                return "Canalul YouTube nu a putut fi încărcat."
            }
        }
    }

    private let youtube =
        YouTubeModel()

    private let tvHtml =
        YouTubeModel()

    init() {
        installTVHTML5Overrides()
    }

    private var homeState:
        HomeScreenResponse?

    private var searchState:
        SearchResponse?

    private var searchQuery =
        ""

    private var channelStates:
        [String: ChannelInfosResponse] =
            [:]

    func home(
        reset:
            Bool = true
    ) async throws
        -> BrowsePage
    {
        if reset ||
           homeState == nil {
            homeState =
                try await HomeScreenResponse
                    .sendThrowingRequest(
                        youtubeModel:
                            youtube,
                        data:
                            [:]
                    )
        } else if var current =
                    homeState,
                  current.continuationToken !=
                    nil {
            let continuation =
                try await current
                    .fetchContinuationThrowing(
                        youtubeModel:
                            youtube
                    )

            current.mergeContinuation(
                continuation
            )

            homeState =
                current
        }

        guard let state =
                homeState
        else {
            throw NativeError
                .noHomeResults
        }

        let items =
            state.results
                .compactMap(
                    mapVideo
                )

        guard !items.isEmpty
        else {
            // Anonymous Home can be empty. Keep the application autonomous
            // and provide a normal YouTube search-based discovery feed.
            return try await discoveryFallback()
        }

        return BrowsePage(
            title:
                "Home",
            channelID:
                nil,
            items:
                items,
            hasMore:
                state
                    .continuationToken !=
                nil
        )
    }

    func search(
        query:
            String,
        reset:
            Bool = true
    ) async throws
        -> BrowsePage
    {
        let trimmed =
            query.trimmingCharacters(
                in:
                    .whitespacesAndNewlines
            )

        if reset ||
           searchState == nil ||
           searchQuery !=
            trimmed {
            searchState =
                try await SearchResponse
                    .sendThrowingRequest(
                        youtubeModel:
                            youtube,
                        data:
                            [
                                .query:
                                    trimmed
                            ]
                    )

            searchQuery =
                trimmed
        } else if var current =
                    searchState,
                  current.continuationToken !=
                    nil {
            let continuation =
                try await current
                    .fetchContinuationThrowing(
                        youtubeModel:
                            youtube
                    )

            current.mergeContinuation(
                continuation
            )

            searchState =
                current
        }

        guard let state =
                searchState
        else {
            return BrowsePage(
                title:
                    trimmed,
                channelID:
                    nil,
                items:
                    [],
                hasMore:
                    false
            )
        }

        return BrowsePage(
            title:
                trimmed,
            channelID:
                nil,
            items:
                state.results
                    .compactMap {
                        result in

                        guard let video =
                                result as?
                                    YTVideo
                        else {
                            return nil
                        }

                        return mapVideo(
                            video
                        )
                    },
            hasMore:
                state
                    .continuationToken !=
                nil
        )
    }

    func channel(
        channelID:
            String,
        reset:
            Bool = true
    ) async throws
        -> BrowsePage
    {
        var response:
            ChannelInfosResponse

        if reset ||
           channelStates[
               channelID
           ] ==
            nil {
            let initial =
                try await ChannelInfosResponse
                    .sendThrowingRequest(
                        youtubeModel:
                            youtube,
                        data:
                            [
                                .browseId:
                                    channelID
                            ]
                    )

            response =
                try await initial
                    .getChannelContentReusingCacheThrowing(
                        forType:
                            .videos,
                        youtubeModel:
                            youtube
                    )
        } else {
            guard var current =
                    channelStates[
                        channelID
                    ]
            else {
                throw NativeError
                    .invalidChannel
            }

            let token =
                current
                    .channelContentContinuationStore[
                        .videos
                    ] ??
                nil

            if token != nil {
                let continuation =
                    try await current
                        .getChannelContentContinuationThrowing(
                            ChannelInfosResponse
                                .Videos
                                .self,
                            youtubeModel:
                                youtube
                        )

                current
                    .mergeListableChannelContentContinuation(
                        continuation
                    )
            }

            response =
                current
        }

        channelStates[
            channelID
        ] =
            response

        let videos:
            [BrowseVideo] =
            (
                response
                    .channelContentStore[
                        .videos
                    ] as?
                    ChannelInfosResponse
                        .Videos
            )?
            .items
            .compactMap {
                result ->
                    BrowseVideo? in

                guard let video =
                        result as?
                            YTVideo
                else {
                    return nil
                }

                return mapVideo(
                    video
                )
            } ??
            []

        let token =
            response
                .channelContentContinuationStore[
                    .videos
                ] ??
            nil

        return BrowsePage(
            title:
                response.name ??
                "Canal",
            channelID:
                channelID,
            items:
                videos,
            hasMore:
                token != nil
        )
    }

    func resolve(
        videoID:
            String
    ) async throws
        -> ResolvedVideo
    {
        await ensureVisitorData()

        // First choice: TVHTML5_SIMPLY_EMBEDDED_PLAYER. This profile is used
        // by current native YouTube clients because its direct media URLs are
        // normally exempt from the GVS Proof-of-Origin requirement.
        do {
            let tvInfo =
                try await VideoInfosResponse
                    .sendThrowingRequest(
                        youtubeModel:
                            tvHtml,
                        data:
                            [
                                .query:
                                    videoID
                            ]
                    )

            if let resolved =
                    try? makeResolvedVideo(
                        videoID:
                            videoID,
                        info:
                            tvInfo,
                        adaptiveFormats:
                            tvInfo.downloadFormats,
                        progressiveFormats:
                            tvInfo.defaultFormats
                    ) {
                return resolved
            }
        } catch {
            // Continue to the player.js decipher path below.
        }

        // Second choice: normal YouTubeKit watch-page extraction. This path
        // obtains the current player and deciphers signatureCipher + n using
        // JavaScriptCore inside YouTubeKit.
        let video =
            YTVideo(
                videoId:
                    videoID
            )

        var response =
            try await video
                .fetchStreamingInfosWithDownloadFormatsThrowing(
                    youtubeModel:
                        youtube
                )

        if let player =
                response
                    .videoInfos
                    .player {
            try response
                .deciphersURLs(
                    player:
                        player
                )
        }

        return try makeResolvedVideo(
            videoID:
                videoID,
            info:
                response.videoInfos,
            adaptiveFormats:
                response.downloadFormats,
            progressiveFormats:
                response.defaultFormats
        )
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
        if info.isLive ==
                true,
           let hls =
                info.streamingURL {
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
                            "hls",
                        container:
                            "m3u8",
                        videoCodec:
                            nil,
                        audioCodec:
                            nil,
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

        let compatibleVideos =
            adaptiveVideos.filter {
                isPreferredH264MP4(
                    $0
                )
            }

        let selectedVideo =
            bestVideo(
                compatibleVideos
                    .isEmpty
                    ? adaptiveVideos
                    : compatibleVideos
            )

        let adaptiveAudio =
            adaptiveFormats
                .compactMap {
                    $0 as?
                        AudioOnlyFormat
                }
                .filter {
                    $0.url !=
                        nil
                }

        let compatibleAudio =
            adaptiveAudio.filter {
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
                compatibleAudio
                    .isEmpty
                    ? adaptiveAudio
                    : compatibleAudio
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

        // If adaptive pairing is unavailable, use a progressive YouTube
        // format as one complete stream. Never pair a progressive format
        // that already contains audio with another audio stream.
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

        let compatibleProgressive =
            progressiveVideos.filter {
                isPreferredH264MP4(
                    $0
                )
            }

        guard let progressive =
                bestVideo(
                    compatibleProgressive
                        .isEmpty
                        ? progressiveVideos
                        : compatibleProgressive
                ),
              let progressiveURL =
                progressive.url
        else {
            throw NativeError
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
        guard format.url !=
                nil
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
            if tvHtml
                .visitorData
                .isEmpty {
                tvHtml.visitorData =
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

            tvHtml.visitorData =
                visitorData
        } catch {
            // Video requests can still succeed without an explicitly
            // bootstrapped visitor token; do not block playback here.
        }
    }

    private func installTVHTML5Overrides() {
        let bodyPrefix =
            #"{"context":{"client":{"clientName":"TVHTML5_SIMPLY_EMBEDDED_PLAYER","clientVersion":"2.0","clientScreen":"EMBED","platform":"TV","hl":"en","gl":"US","clientFormFactor":"UNKNOWN_FORM_FACTOR"},"thirdParty":{"embedUrl":"https://www.youtube.com/"}},"contentCheckOk":true,"racyCheckOk":true,"videoId":""#

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
                        HeadersList.Header(
                            name:
                                "Accept",
                            content:
                                "*/*"
                        ),
                        HeadersList.Header(
                            name:
                                "Accept-Encoding",
                            content:
                                "gzip, deflate, br"
                        ),
                        HeadersList.Header(
                            name:
                                "Host",
                            content:
                                "www.youtube.com"
                        ),
                        HeadersList.Header(
                            name:
                                "User-Agent",
                            content:
                                "Mozilla/5.0 (PlayStation; PlayStation 4/12.55) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15"
                        ),
                        HeadersList.Header(
                            name:
                                "Content-Type",
                            content:
                                "application/json"
                        ),
                        HeadersList.Header(
                            name:
                                "Origin",
                            content:
                                "https://www.youtube.com"
                        ),
                        HeadersList.Header(
                            name:
                                "Referer",
                            content:
                                "https://www.youtube.com/"
                        )
                    ],
                customHeaders:
                    [
                        "X-Goog-Visitor-Id":
                            .visitorData
                    ],
                addQueryAfterParts:
                    [
                        HeadersList.AddQueryInfo(
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
                        HeadersList.ParameterToAdd(
                            name:
                                "prettyPrint",
                            content:
                                "false"
                        )
                    ]
            )

        tvHtml
            .customHeaders[
                .videoInfos
            ] =
            headers
    }

    private func discoveryFallback()
        async throws
        -> BrowsePage
    {
        let response =
            try await SearchResponse
                .sendThrowingRequest(
                    youtubeModel:
                        youtube,
                    data:
                        [
                            .query:
                                "popular"
                        ]
                )

        return BrowsePage(
            title:
                "Descoperă",
            channelID:
                nil,
            items:
                response.results
                    .compactMap {
                        result in

                        guard let video =
                                result as?
                                    YTVideo
                        else {
                            return nil
                        }

                        return mapVideo(
                            video
                        )
                    },
            hasMore:
                false
        )
    }

    private func mapVideo(
        _ video:
            YTVideo
    ) -> BrowseVideo? {
        guard video.videoId
            .count ==
                11,
              let thumbnail =
                video.thumbnails
                    .last?
                    .url
        else {
            return nil
        }

        let live =
            video.timeLength?
                .lowercased() ==
            "live"

        return BrowseVideo(
            id:
                video.videoId,
            title:
                video.title ??
                "YouTube",
            channel:
                video.channel?
                    .name ??
                "",
            channelID:
                video.channel?
                    .channelId,
            duration:
                live
                    ? nil
                    : video
                        .timeLengthSeconds
                        .map(
                            Double.init
                        ),
            viewCount:
                nil,
            viewCountText:
                video.viewCount,
            thumbnailURL:
                thumbnail,
            isLive:
                live
        )
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
