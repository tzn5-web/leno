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

        let info =
            response
                .videoInfos

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

        let allFormats =
            response.downloadFormats +
            response.defaultFormats

        let videoFormats =
            allFormats
                .compactMap {
                    $0 as?
                        VideoDownloadFormat
                }
                .filter {
                    format in

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

        let compatibleVideos =
            videoFormats.filter {
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
                        "avc1"
                    ) ||
                    codec.contains(
                        "h264"
                    )
                )
            }

        let selectedVideo =
            (
                compatibleVideos
                    .isEmpty
                    ? videoFormats
                    : compatibleVideos
            )
            .max {
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

        let audioFormats =
            allFormats
                .compactMap {
                    $0 as?
                        AudioOnlyFormat
                }
                .filter {
                    $0.url !=
                        nil
                }

        let compatibleAudio =
            audioFormats.filter {
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
                    ? audioFormats
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

        guard let selectedVideo,
              let videoURL =
                selectedVideo.url
        else {
            throw NativeError
                .noPlayableFormats
        }

        let audioStream:
            ResolvedStream?

        if let selectedAudio,
           let audioURL =
            selectedAudio.url {
            audioStream =
                ResolvedStream(
                    relayURL:
                        audioURL,
                    formatID:
                        String(
                            selectedAudio.itag
                        ),
                    container:
                        container(
                            selectedAudio
                                .mimeType
                        ),
                    videoCodec:
                        nil,
                    audioCodec:
                        selectedAudio
                            .codec,
                    height:
                        nil,
                    fps:
                        nil,
                    bitrate:
                        Double(
                            selectedAudio.bitrate ??
                            selectedAudio.averageBitrate ??
                            0
                        )
                )
        } else {
            audioStream =
                nil
        }

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
                ResolvedStream(
                    relayURL:
                        videoURL,
                    formatID:
                        String(
                            selectedVideo
                                .itag
                        ),
                    container:
                        container(
                            selectedVideo
                                .mimeType
                        ),
                    videoCodec:
                        selectedVideo
                            .codec,
                    audioCodec:
                        nil,
                    height:
                        selectedVideo
                            .height,
                    fps:
                        selectedVideo
                            .fps
                            .map(
                                Double.init
                            ),
                    bitrate:
                        Double(
                            selectedVideo.bitrate ??
                            selectedVideo.averageBitrate ??
                            0
                        )
                ),
            audio:
                audioStream,
            expiresIn:
                secondsUntilExpiry(
                    info.videoURLsExpireAt
                )
        )
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
