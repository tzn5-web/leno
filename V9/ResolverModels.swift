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

    enum CodingKeys:
        String,
        CodingKey
    {
        case ok
        case version
        case relayTTL = "relay_ttl"
        case jsRuntime = "js_runtime"
        case authRequired = "auth_required"
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
