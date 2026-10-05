import Foundation
import YouTubeKit

@MainActor
final class V9NativeYouTubeClient:
    ObservableObject
{
    enum NativeError:
        LocalizedError
    {
        case noHomeResults
        case invalidChannel

        var errorDescription:
            String?
        {
            switch self {
            case .noHomeResults:
                return "YouTube nu a returnat videoclipuri pentru Home."

            case .invalidChannel:
                return "Canalul YouTube nu a putut fi încărcat."
            }
        }
    }

    private let youtube =
        YouTubeModel()

    private let playbackWorker =
        V9NativePlaybackWorker()

    private var homeState:
        HomeScreenResponse?

    private var discoveryState:
        SearchResponse?

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
            return try await discoveryFallback(
                reset:
                    reset
            )
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
        try await playbackWorker
            .resolve(
                videoID:
                    videoID
            )
    }

    private func discoveryFallback(
        reset:
            Bool
    ) async throws
        -> BrowsePage
    {
        if reset ||
           discoveryState ==
            nil {
            discoveryState =
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
        } else if var current =
                    discoveryState,
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

            discoveryState =
                current
        }

        guard let response =
                discoveryState
        else {
            throw NativeError
                .noHomeResults
        }

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
                response
                    .continuationToken !=
                nil
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


}
