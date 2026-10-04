import Foundation

enum ResolverClientError:
    LocalizedError
{
    case invalidEndpoint
    case loopbackEndpointOnDevice
    case invalidVideoID
    case badResponse(Int)
    case server(String)

    var errorDescription: String? {
        switch self {
        case .invalidEndpoint:
            return "Endpoint resolver invalid."

        case .loopbackEndpointOnDevice:
            return "127.0.0.1/localhost indică iPhone-ul, nu PC-ul. Folosește IP-ul LAN al PC-ului sau un resolver HTTPS."

        case .invalidVideoID:
            return "Video ID trebuie să aibă exact 11 caractere valide."

        case .badResponse(let status):
            return "Resolver HTTP \(status)."

        case .server(let message):
            return message
        }
    }
}

actor VcdResolverClient {
    private let decoder:
        JSONDecoder

    init() {
        decoder =
            JSONDecoder()
    }

    func health(
        endpoint: String
    ) async throws
        -> ResolverHealth
    {
        let base =
            try baseURL(
                endpoint
            )

        let url =
            base.appending(
                path:
                    "health"
            )

        let data =
            try await request(
                url,
                bearerToken:
                    ""
            )

        return try decoder.decode(
            ResolverHealth.self,
            from:
                data
        )
    }

    func resolve(
        videoID: String,
        endpoint: String,
        bearerToken: String = ""
    ) async throws
        -> ResolvedVideo
    {
        guard
            videoID.count == 11,
            videoID.allSatisfy({
                $0.isLetter ||
                $0.isNumber ||
                $0 == "_" ||
                $0 == "-"
            })
        else {
            throw ResolverClientError
                .invalidVideoID
        }

        let base =
            try baseURL(
                endpoint
            )

        let url =
            base
                .appending(
                    path:
                        "v1"
                )
                .appending(
                    path:
                        "video"
                )
                .appending(
                    path:
                        videoID
                )

        let data =
            try await request(
                url,
                bearerToken:
                    bearerToken
            )

        return try decoder.decode(
            ResolvedVideo.self,
            from:
                data
        )
    }

    private func baseURL(
        _ value: String
    ) throws -> URL {
        let trimmed =
            value.trimmingCharacters(
                in:
                    .whitespacesAndNewlines
            )

        guard var components =
                URLComponents(
                    string:
                        trimmed
                ),
              let scheme =
                components.scheme?
                    .lowercased(),
              scheme == "https" ||
              scheme == "http",
              let host =
                components.host,
              !host.isEmpty
        else {
            throw ResolverClientError
                .invalidEndpoint
        }

        #if !targetEnvironment(simulator)
        let normalizedHost =
            host.lowercased()

        if normalizedHost == "localhost" ||
           normalizedHost == "127.0.0.1" ||
           normalizedHost == "::1" {
            throw ResolverClientError
                .loopbackEndpointOnDevice
        }
        #endif

        components.path =
            components.path
                .trimmingCharacters(
                    in:
                        CharacterSet(
                            charactersIn:
                                "/"
                        )
                )

        guard let url =
                components.url else {
            throw ResolverClientError
                .invalidEndpoint
        }

        return url
    }

    private func request(
        _ url: URL,
        bearerToken: String
    ) async throws -> Data {
        var request =
            URLRequest(
                url:
                    url
            )

        request.timeoutInterval =
            120

        request.setValue(
            "application/json",
            forHTTPHeaderField:
                "Accept"
        )

        let trimmedToken =
            bearerToken
                .trimmingCharacters(
                    in:
                        .whitespacesAndNewlines
                )

        if !trimmedToken.isEmpty {
            request.setValue(
                "Bearer \(trimmedToken)",
                forHTTPHeaderField:
                    "Authorization"
            )
        }

        let (
            data,
            response
        ) =
            try await URLSession.shared
                .data(
                    for:
                        request
                )

        guard let http =
                response as?
                    HTTPURLResponse else {
            throw ResolverClientError
                .server(
                    "Răspuns resolver invalid."
                )
        }

        guard
            (200..<300)
                .contains(
                    http.statusCode
                )
        else {
            let detail =
                parseServerDetail(
                    data
                )

            if let detail {
                throw ResolverClientError
                    .server(
                        detail
                    )
            }

            throw ResolverClientError
                .badResponse(
                    http.statusCode
                )
        }

        return data
    }

    private func parseServerDetail(
        _ data: Data
    ) -> String? {
        guard
            let json =
                try? JSONSerialization
                    .jsonObject(
                        with:
                            data
                    ) as?
                    [String: Any],
            let detail =
                json["detail"]
                    as? String
        else {
            return nil
        }

        return detail
    }
}
