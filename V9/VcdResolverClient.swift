import Darwin
import Foundation

private final class ResolverNoRedirectDelegate:
    NSObject,
    URLSessionTaskDelegate,
    @unchecked Sendable
{
    func urlSession(
        _ session:
            URLSession,
        task:
            URLSessionTask,
        willPerformHTTPRedirection
            response:
                HTTPURLResponse,
        newRequest request:
            URLRequest,
        completionHandler:
            @escaping (
                URLRequest?
            ) -> Void
    ) {
        completionHandler(
            nil
        )
    }
}

enum ResolverClientError:
    LocalizedError
{
    case invalidEndpoint
    case loopbackEndpointOnDevice
    case insecurePublicHTTP
    case insecureTokenTransport
    case invalidRelayURL
    case insecureRelayTransport
    case relayOriginMismatch
    case invalidVideoID
    case badResponse(Int)
    case server(String)

    var errorDescription: String? {
        switch self {
        case .invalidEndpoint:
            return "Endpoint resolver invalid."

        case .loopbackEndpointOnDevice:
            return "127.0.0.1/localhost indică iPhone-ul, nu PC-ul. Folosește IP-ul LAN al PC-ului sau un resolver HTTPS."

        case .insecurePublicHTTP:
            return "HTTP simplu este permis doar pentru resolverul din rețeaua locală. Pentru Internet/VPS folosește HTTPS."

        case .insecureTokenTransport:
            return "Tokenul resolverului nu este trimis prin HTTP necriptat. Folosește HTTPS sau golește tokenul pentru test LAN."

        case .invalidRelayURL:
            return "Resolverul a returnat un URL media invalid."

        case .insecureRelayTransport:
            return "Resolverul a returnat media printr-un transport nesigur. HTTP este acceptat doar în rețeaua locală; un endpoint HTTPS trebuie să livreze relay HTTPS."

        case .relayOriginMismatch:
            return "Resolverul a returnat media de pe altă origine. V9 acceptă doar relay controlat de același resolver."

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

    private let redirectDelegate:
        ResolverNoRedirectDelegate

    private let session:
        URLSession

    init() {
        decoder =
            JSONDecoder()

        let redirectDelegate =
            ResolverNoRedirectDelegate()

        self.redirectDelegate =
            redirectDelegate

        let configuration =
            URLSessionConfiguration
                .ephemeral

        configuration
            .waitsForConnectivity =
            false

        configuration
            .requestCachePolicy =
            .reloadIgnoringLocalCacheData

        session =
            URLSession(
                configuration:
                    configuration,
                delegate:
                    redirectDelegate,
                delegateQueue:
                    nil
            )
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

    func home(
        endpoint:
            String,
        bearerToken:
            String = ""
    ) async throws
        -> BrowseResponse
    {
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
                        "home"
                )

        let data =
            try await request(
                url,
                bearerToken:
                    bearerToken
            )

        let result =
            try decoder.decode(
                BrowseResponse.self,
                from:
                    data
            )

        try validateBrowseResponse(
            result,
            endpointBase:
                base
        )

        return result
    }

    func search(
        query:
            String,
        endpoint:
            String,
        bearerToken:
            String = ""
    ) async throws
        -> BrowseResponse
    {
        let base =
            try baseURL(
                endpoint
            )

        var components =
            URLComponents(
                url:
                    base
                    .appending(
                        path:
                            "v1"
                    )
                    .appending(
                        path:
                            "search"
                    ),
                resolvingAgainstBaseURL:
                    false
            )

        components?
            .queryItems = [
                URLQueryItem(
                    name:
                        "q",
                    value:
                        query
                )
            ]

        guard let url =
                components?
                    .url
        else {
            throw ResolverClientError
                .invalidEndpoint
        }

        let data =
            try await request(
                url,
                bearerToken:
                    bearerToken
            )

        let result =
            try decoder.decode(
                BrowseResponse.self,
                from:
                    data
            )

        try validateBrowseResponse(
            result,
            endpointBase:
                base
        )

        return result
    }

    func channel(
        channelID:
            String,
        endpoint:
            String,
        bearerToken:
            String = ""
    ) async throws
        -> BrowseResponse
    {
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
                        "channel"
                )
                .appending(
                    path:
                        channelID
                )

        let data =
            try await request(
                url,
                bearerToken:
                    bearerToken
            )

        let result =
            try decoder.decode(
                BrowseResponse.self,
                from:
                    data
            )

        try validateBrowseResponse(
            result,
            endpointBase:
                base
        )

        return result
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

        let resolved =
            try decoder.decode(
                ResolvedVideo.self,
                from:
                    data
            )

        try validateResolvedVideo(
            resolved,
            endpointBase:
                base
        )

        return resolved
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

        if scheme == "http",
           !isLocalNetworkHost(
                host
           ) {
            throw ResolverClientError
                .insecurePublicHTTP
        }

        guard components.user == nil,
              components.password == nil,
              components.query == nil,
              components.fragment == nil
        else {
            throw ResolverClientError
                .invalidEndpoint
        }

        while components.path.count > 1,
              components.path.hasSuffix(
                "/"
              ) {
            components.path
                .removeLast()
        }

        if components.path ==
            "/" {
            components.path =
                ""
        }

        guard let url =
                components.url else {
            throw ResolverClientError
                .invalidEndpoint
        }

        return url
    }

    private func validateBrowseResponse(
        _ response:
            BrowseResponse,
        endpointBase:
            URL
    ) throws {
        for item in response.items {
            guard item.id.count ==
                    11,
                  item.id.allSatisfy({
                      $0.isLetter ||
                      $0.isNumber ||
                      $0 == "_" ||
                      $0 == "-"
                  })
            else {
                throw ResolverClientError
                    .server(
                        "Resolverul a returnat un video ID invalid."
                    )
            }

            let thumbnail =
                item.thumbnailURL

            guard
                let scheme =
                    thumbnail.scheme?
                        .lowercased(),
                scheme == "http" ||
                scheme == "https",
                sameOrigin(
                    thumbnail,
                    endpointBase
                ),
                thumbnail.query == nil,
                thumbnail.fragment == nil,
                thumbnail.path ==
                    "/v1/thumb/\(item.id)"
            else {
                throw ResolverClientError
                    .relayOriginMismatch
            }

            if endpointBase.scheme?
                    .lowercased() ==
                    "https",
               scheme != "https" {
                throw ResolverClientError
                    .insecureRelayTransport
            }
        }
    }

    private func validateResolvedVideo(
        _ resolved:
            ResolvedVideo,
        endpointBase:
            URL
    ) throws {
        var streams:
            [ResolvedStream] = [
                resolved.video
            ]

        if let audio =
                resolved.audio {
            streams.append(
                audio
            )
        }

        for stream in streams {
            let url =
                stream.relayURL

            guard
                let scheme =
                    url.scheme?
                        .lowercased(),
                scheme == "https" ||
                scheme == "http",
                let host =
                    url.host,
                !host.isEmpty,
                url.user == nil,
                url.password == nil
            else {
                throw ResolverClientError
                    .invalidRelayURL
            }

            if scheme == "http",
               !isLocalNetworkHost(
                    host
               ) {
                throw ResolverClientError
                    .insecureRelayTransport
            }

            if endpointBase.scheme?
                    .lowercased() ==
                    "https",
               scheme != "https" {
                throw ResolverClientError
                    .insecureRelayTransport
            }

            guard sameOrigin(
                url,
                endpointBase
            ),
            url.query == nil,
            url.fragment == nil,
            url.path.contains(
                "/v1/relay/"
            )
            else {
                throw ResolverClientError
                    .relayOriginMismatch
            }
        }
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
            guard url.scheme?
                    .lowercased() ==
                    "https"
            else {
                throw ResolverClientError
                    .insecureTokenTransport
            }

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
            try await session
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

    private func sameOrigin(
        _ lhs:
            URL,
        _ rhs:
            URL
    ) -> Bool {
        guard
            let lhsScheme =
                lhs.scheme?
                    .lowercased(),
            let rhsScheme =
                rhs.scheme?
                    .lowercased(),
            let lhsHost =
                lhs.host?
                    .lowercased(),
            let rhsHost =
                rhs.host?
                    .lowercased()
        else {
            return false
        }

        func effectivePort(
            _ url:
                URL,
            scheme:
                String
        ) -> Int {
            if let port =
                    url.port {
                return port
            }

            return scheme ==
                "https"
                    ? 443
                    : 80
        }

        return lhsScheme ==
                rhsScheme &&
               lhsHost ==
                rhsHost &&
               effectivePort(
                    lhs,
                    scheme:
                        lhsScheme
               ) ==
               effectivePort(
                    rhs,
                    scheme:
                        rhsScheme
               )
    }

    private func isLocalNetworkHost(
        _ host:
            String
    ) -> Bool {
        let value =
            host
                .lowercased()
                .trimmingCharacters(
                    in:
                        CharacterSet(
                            charactersIn:
                                "[]"
                        )
                )

        if value ==
                "localhost" ||
           value.hasSuffix(
                ".local"
           ) {
            return true
        }

        if value.contains(
            ":"
        ) {
            var address =
                in6_addr()

            guard inet_pton(
                AF_INET6,
                value,
                &address
            ) ==
                1
            else {
                return false
            }

            let bytes =
                withUnsafeBytes(
                    of:
                        address
                ) {
                    Array(
                        $0
                    )
                }

            guard bytes.count >=
                    16
            else {
                return false
            }

            let isLoopback =
                bytes[
                    0..<15
                ]
                .allSatisfy {
                    $0 ==
                        0
                } &&
                bytes[
                    15
                ] ==
                1

            let isLinkLocal =
                bytes[
                    0
                ] ==
                0xfe &&
                (
                    bytes[
                        1
                    ] &
                    0xc0
                ) ==
                0x80

            let isUniqueLocal =
                (
                    bytes[
                        0
                    ] &
                    0xfe
                ) ==
                0xfc

            let isIPv4Mapped =
                bytes[
                    0..<10
                ]
                .allSatisfy {
                    $0 ==
                        0
                } &&
                bytes[
                    10
                ] ==
                0xff &&
                bytes[
                    11
                ] ==
                0xff

            if isIPv4Mapped {
                return isPrivateIPv4(
                    [
                        Int(
                            bytes[
                                12
                            ]
                        ),
                        Int(
                            bytes[
                                13
                            ]
                        ),
                        Int(
                            bytes[
                                14
                            ]
                        ),
                        Int(
                            bytes[
                                15
                            ]
                        )
                    ]
                )
            }

            return isLoopback ||
                   isLinkLocal ||
                   isUniqueLocal
        }

        let parts =
            value
                .split(
                    separator:
                        "."
                )
                .compactMap {
                    Int(
                        $0
                    )
                }

        if parts.count ==
                4 {
            return isPrivateIPv4(
                parts
            )
        }

        // A dotless, non-IP hostname is treated as a LAN/mDNS-style local
        // name. Public IPv6 addresses never reach this branch.
        return !value.isEmpty &&
               !value.contains(
                   "."
               )
    }

    private func isPrivateIPv4(
        _ parts:
            [Int]
    ) -> Bool {
        guard parts.count ==
                4,
              parts.allSatisfy({
                  (0...255)
                      .contains(
                          $0
                      )
              })
        else {
            return false
        }

        if parts[
            0
        ] ==
            10 {
            return true
        }

        if parts[
                0
           ] ==
                127 {
            return true
        }

        if parts[
                0
           ] ==
                172,
           (16...31)
            .contains(
                parts[
                    1
                ]
            ) {
            return true
        }

        if parts[
                0
           ] ==
                192,
           parts[
                1
           ] ==
                168 {
            return true
        }

        if parts[
                0
           ] ==
                169,
           parts[
                1
           ] ==
                254 {
            return true
        }

        return false
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
