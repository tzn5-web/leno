import Foundation

struct ResolvedMedia: Sendable {
    let url: URL
    let title: String
    let thumbnailURL: URL?
    let source: String
    let height: Int
    let isLive: Bool
}

enum StreamResolverError: LocalizedError {
    case invalidVideoID
    case noPublicStream

    var errorDescription: String? {
        switch self {
        case .invalidVideoID:
            return "ID video invalid."
        case .noPublicStream:
            return "Nu am găsit un stream public compatibil."
        }
    }
}

final class StreamResolver: @unchecked Sendable {
    private let session: URLSession

    private let pipedInstances: [URL] = [
        URL(string: "https://pipedapi.kavin.rocks")!,
        URL(string: "https://pipedapi.tokhmi.xyz")!,
        URL(string: "https://pipedapi.moomoo.me")!,
        URL(string: "https://pipedapi.syncpundit.io")!,
        URL(string: "https://ytapi.dc09.ru")!,
        URL(string: "https://api-piped.mha.fi")!
    ]

    private let invidiousInstances: [URL] = [
        URL(string: "https://inv.nadeko.net")!,
        URL(string: "https://invidious.nerdvpn.de")!,
        URL(string: "https://yt.chocolatemoo53.com")!,
        URL(string: "https://invidious.tiekoetter.com")!
    ]

    init() {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 4
        configuration.timeoutIntervalForResource = 6
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.httpAdditionalHeaders = [
            "Accept": "application/json",
            "User-Agent": "YoutubeVcd/0.5 iOS"
        ]

        session = URLSession(configuration: configuration)
    }

    func resolveCandidates(videoID: String) async throws -> [ResolvedMedia] {
        guard Self.isValidVideoID(videoID) else {
            throw StreamResolverError.invalidVideoID
        }

        async let pipedTask =
            resolvePipedBatch(videoID: videoID)

        async let invidiousTask =
            resolveInvidiousBatch(videoID: videoID)

        let piped = await pipedTask
        let invidious = await invidiousTask

        var candidates: [ResolvedMedia] = []

        let maximum =
            max(piped.count, invidious.count)

        for index in 0..<maximum {
            // Invidious is preferred first because its current
            // public instances are actively maintained while Piped
            // remains useful as an independent fallback family.
            if index < invidious.count {
                candidates.append(invidious[index])
            }

            if index < piped.count {
                candidates.append(piped[index])
            }

            if candidates.count >= 6 {
                break
            }
        }

        guard !candidates.isEmpty else {
            throw StreamResolverError.noPublicStream
        }

        return candidates
    }

    private func resolvePipedBatch(videoID: String) async -> [ResolvedMedia] {
        await withTaskGroup(of: ResolvedMedia?.self) { group in
            for baseURL in pipedInstances {
                group.addTask { [session] in
                    await Self.resolvePiped(
                        videoID: videoID,
                        baseURL: baseURL,
                        session: session
                    )
                }
            }

            var values: [ResolvedMedia] = []

            for await value in group {
                if let value {
                    values.append(value)
                }
            }

            return values.sorted {
                if $0.height == $1.height {
                    return $0.source < $1.source
                }

                return $0.height > $1.height
            }
        }
    }

    private func resolveInvidiousBatch(videoID: String) async -> [ResolvedMedia] {
        await withTaskGroup(of: ResolvedMedia?.self) { group in
            for baseURL in invidiousInstances {
                group.addTask { [session] in
                    await Self.resolveInvidious(
                        videoID: videoID,
                        baseURL: baseURL,
                        session: session
                    )
                }
            }

            var values: [ResolvedMedia] = []

            for await value in group {
                if let value {
                    values.append(value)
                }
            }

            return values.sorted {
                if $0.height == $1.height {
                    return $0.source < $1.source
                }

                return $0.height > $1.height
            }
        }
    }

    private static func resolvePiped(
        videoID: String,
        baseURL: URL,
        session: URLSession
    ) async -> ResolvedMedia? {
        guard let requestURL = URL(
            string: "/streams/\(videoID)",
            relativeTo: baseURL
        )?.absoluteURL else {
            return nil
        }

        do {
            let (data, response) = try await session.data(from: requestURL)

            guard let http = response as? HTTPURLResponse,
                  (200..<300).contains(http.statusCode) else {
                return nil
            }

            let payload = try JSONDecoder().decode(
                PipedResponse.self,
                from: data
            )

            let title = payload.title?.trimmingCharacters(
                in: .whitespacesAndNewlines
            )

            let safeTitle = title?.isEmpty == false
                ? title!
                : "YouTube"

            let thumbnailURL = payload.thumbnailUrl.flatMap(URL.init(string:))

            if payload.livestream == true,
               let hls = payload.hls,
               let hlsURL = URL(string: hls) {
                return ResolvedMedia(
                    url: hlsURL,
                    title: safeTitle,
                    thumbnailURL: thumbnailURL,
                    source: "Piped HLS • \(baseURL.host ?? "instance")",
                    height: 0,
                    isLive: true
                )
            }

            let progressive = (payload.videoStreams ?? [])
                .filter { stream in
                    stream.videoOnly != true &&
                    stream.url != nil &&
                    Self.isMP4Video(stream)
                }
                .sorted {
                    ($0.height ?? 0) > ($1.height ?? 0)
                }

            guard let stream = progressive.first,
                  let rawURL = stream.url,
                  let streamURL = URL(string: rawURL) else {
                return nil
            }

            return ResolvedMedia(
                url: streamURL,
                title: safeTitle,
                thumbnailURL: thumbnailURL,
                source: "Piped • \(baseURL.host ?? "instance")",
                height: stream.height ?? Self.height(from: stream.quality),
                isLive: false
            )
        } catch {
            return nil
        }
    }

    private static func resolveInvidious(
        videoID: String,
        baseURL: URL,
        session: URLSession
    ) async -> ResolvedMedia? {
        guard let requestURL = URL(
            string: "/api/v1/videos/\(videoID)?region=RO&local=true",
            relativeTo: baseURL
        )?.absoluteURL else {
            return nil
        }

        do {
            let (data, response) = try await session.data(from: requestURL)

            guard let http = response as? HTTPURLResponse,
                  (200..<300).contains(http.statusCode) else {
                return nil
            }

            let payload = try JSONDecoder().decode(
                InvidiousResponse.self,
                from: data
            )

            guard payload.paid != true,
                  payload.premium != true else {
                return nil
            }

            let safeTitle = payload.title?.isEmpty == false
                ? payload.title!
                : "YouTube"

            let thumbnailURL = payload.videoThumbnails?
                .sorted { ($0.width ?? 0) > ($1.width ?? 0) }
                .first?
                .url
                .flatMap(URL.init(string:))

            if payload.liveNow == true,
               let hls = payload.hlsUrl,
               let hlsURL = Self.absoluteURL(
                    hls,
                    relativeTo: baseURL
               ) {
                return ResolvedMedia(
                    url: hlsURL,
                    title: safeTitle,
                    thumbnailURL: thumbnailURL,
                    source: "Invidious HLS • \(baseURL.host ?? "instance")",
                    height: 0,
                    isLive: true
                )
            }

            let formats = (payload.formatStreams ?? [])
                .filter { stream in
                    let container = stream.container?.lowercased() ?? ""
                    let type = stream.type?.lowercased() ?? ""
                    return stream.url != nil &&
                           (container == "mp4" || type.contains("video/mp4"))
                }
                .sorted {
                    Self.height(from: $0.qualityLabel ?? $0.resolution) >
                    Self.height(from: $1.qualityLabel ?? $1.resolution)
                }

            guard let stream = formats.first,
                  let rawURL = stream.url,
                  let streamURL = Self.absoluteURL(
                    rawURL,
                    relativeTo: baseURL
                  ) else {
                return nil
            }

            return ResolvedMedia(
                url: streamURL,
                title: safeTitle,
                thumbnailURL: thumbnailURL,
                source: "Invidious • \(baseURL.host ?? "instance")",
                height: Self.height(
                    from: stream.qualityLabel ?? stream.resolution
                ),
                isLive: false
            )
        } catch {
            return nil
        }
    }

    private static func isMP4Video(_ stream: PipedStream) -> Bool {
        let mime = stream.mimeType?.lowercased() ?? ""
        let format = stream.format?.lowercased() ?? ""
        let codec = stream.codec?.lowercased() ?? ""

        if mime.contains("video/mp4") || format.contains("mpeg_4") {
            return codec.isEmpty ||
                   codec.contains("avc") ||
                   codec.contains("h264")
        }

        return false
    }

    private static func absoluteURL(
        _ raw: String,
        relativeTo baseURL: URL
    ) -> URL? {
        if let direct = URL(string: raw),
           direct.scheme != nil {
            return direct
        }

        return URL(
            string: raw,
            relativeTo: baseURL
        )?.absoluteURL
    }

    private static func height(from value: String?) -> Int {
        guard let value else { return 0 }

        let digits = value.prefix { $0.isNumber }

        if let number = Int(digits) {
            return number
        }

        let allDigits = value.filter { $0.isNumber }
        return Int(allDigits) ?? 0
    }

    private static func isValidVideoID(_ value: String) -> Bool {
        guard value.count == 11 else { return false }

        let allowed = CharacterSet(
            charactersIn:
                "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        )

        return value.unicodeScalars.allSatisfy {
            allowed.contains($0)
        }
    }
}

private struct PipedResponse: Decodable {
    let title: String?
    let thumbnailUrl: String?
    let hls: String?
    let livestream: Bool?
    let videoStreams: [PipedStream]?
}

private struct PipedStream: Decodable {
    let url: String?
    let mimeType: String?
    let codec: String?
    let format: String?
    let quality: String?
    let height: Int?
    let videoOnly: Bool?
}

private struct InvidiousResponse: Decodable {
    let title: String?
    let paid: Bool?
    let premium: Bool?
    let liveNow: Bool?
    let hlsUrl: String?
    let formatStreams: [InvidiousFormat]?
    let videoThumbnails: [InvidiousThumbnail]?
}

private struct InvidiousFormat: Decodable {
    let url: String?
    let type: String?
    let container: String?
    let encoding: String?
    let qualityLabel: String?
    let resolution: String?
}

private struct InvidiousThumbnail: Decodable {
    let url: String?
    let width: Int?
    let height: Int?
}
