import Foundation

struct ResolverHealth:
    Decodable,
    Equatable
{
    let ok: Bool
    let version: String
    let relayTTL: Int
    let jsRuntime: String?
    let authRequired: Bool?
    let maxVideoHeight: Int?
    let maxVideoFPS: Double?

    enum CodingKeys:
        String,
        CodingKey
    {
        case ok
        case version
        case relayTTL = "relay_ttl"
        case jsRuntime = "js_runtime"
        case authRequired = "auth_required"
        case maxVideoHeight = "max_video_height"
        case maxVideoFPS = "max_video_fps"
    }
}

struct ResolvedStream:
    Decodable,
    Equatable
{
    let relayURL: URL
    let formatID: String
    let container: String
    let videoCodec: String?
    let audioCodec: String?
    let height: Int?
    let fps: Double?
    let bitrate: Double?
}

struct ResolvedVideo:
    Decodable,
    Equatable
{
    let videoID: String
    let title: String
    let duration: Double?
    let thumbnail: URL?
    let video: ResolvedStream
    let audio: ResolvedStream?
    let expiresIn: Int
}


struct BrowseVideo:
    Decodable,
    Equatable,
    Hashable,
    Identifiable
{
    let id: String
    let title: String
    let channel: String
    let channelID: String?
    let duration: Double?
    let viewCount: Int?
    let viewCountText: String?
    let thumbnailURL: URL
    let isLive: Bool
}

struct BrowseResponse:
    Decodable,
    Equatable
{
    let title: String
    let channelID: String?
    let items: [BrowseVideo]

    enum CodingKeys:
        String,
        CodingKey
    {
        case title
        case channelID
        case items
    }

    init(
        title:
            String,
        channelID:
            String? = nil,
        items:
            [BrowseVideo]
    ) {
        self.title =
            title

        self.channelID =
            channelID

        self.items =
            items
    }

    init(
        from decoder:
            Decoder
    ) throws {
        let container =
            try decoder.container(
                keyedBy:
                    CodingKeys.self
            )

        title =
            try container.decode(
                String.self,
                forKey:
                    .title
            )

        channelID =
            try container.decodeIfPresent(
                String.self,
                forKey:
                    .channelID
            )

        items =
            try container.decode(
                [BrowseVideo].self,
                forKey:
                    .items
            )
    }
}


struct BrowsePage:
    Equatable
{
    let title: String
    let channelID: String?
    let items: [BrowseVideo]
    let hasMore: Bool
}
