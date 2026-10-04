import Combine
import WebKit

final class YouTubeSession: NSObject, ObservableObject, WKScriptMessageHandler {
    enum State: Equatable {
        case idle
        case loading
        case ready
        case recovering(Int)
        case failed(String)
    }

    @Published private(set) var state: State = .idle
    @Published private(set) var canGoBack = false
    @Published private(set) var canGoForward = false
    @Published private(set) var currentURL: URL?
    @Published private(set) var progress: Double = 0
    @Published private(set) var isLoading = false

    weak var webView: WKWebView?
    var onVideoSelected: ((String) -> Void)?

    private var retryCount = 0
    private let maxRetries = 3
    private var lastVideoID: String?
    private var lastVideoDate = Date.distantPast

    private static let homeURL = URL(string: "https://m.youtube.com/")!

    func attach(webView: WKWebView) {
        self.webView = webView
    }

    func loadHome() {
        load(Self.homeURL)
    }

    func reloadFromHome() {
        retryCount = 0
        loadHome()
    }

    func goBack() {
        guard let webView, webView.canGoBack else { return }
        webView.goBack()
    }

    func updateNavigationState(
        canGoBack: Bool,
        canGoForward: Bool,
        url: URL?,
        progress: Double,
        isLoading: Bool
    ) {
        DispatchQueue.main.async {
            self.canGoBack = canGoBack
            self.canGoForward = canGoForward
            self.currentURL = url
            self.progress = min(max(progress, 0), 1)
            self.isLoading = isLoading
        }
    }

    func markLoading() {
        DispatchQueue.main.async {
            self.state = .loading
            self.isLoading = true
        }
    }

    func markReady() {
        DispatchQueue.main.async {
            self.retryCount = 0
            self.state = .ready
            self.isLoading = false
            self.progress = 1
        }
    }

    func recover(after error: Error? = nil) {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }

            guard self.retryCount < self.maxRetries else {
                self.isLoading = false
                self.state = .failed(error?.localizedDescription ?? "YouTube could not be loaded.")
                return
            }

            self.retryCount += 1
            let attempt = self.retryCount
            self.state = .recovering(attempt)

            let delay = min(1.2 * Double(attempt), 3.6)
            DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in
                guard let self else { return }

                if self.webView?.url == nil {
                    self.loadHome()
                } else {
                    self.webView?.reload()
                }
            }
        }
    }

    @discardableResult
    func interceptVideoURL(_ url: URL) -> Bool {
        guard let videoID = Self.videoID(from: url) else {
            return false
        }

        presentVideo(videoID)
        return true
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        guard message.name == "openVideo" else { return }

        if let body = message.body as? [String: Any],
           let videoID = body["videoID"] as? String,
           Self.isValidVideoID(videoID) {
            presentVideo(videoID)
            return
        }

        if let href = message.body as? String,
           let url = URL(string: href),
           let videoID = Self.videoID(from: url) {
            presentVideo(videoID)
        }
    }

    private func presentVideo(_ videoID: String) {
        let now = Date()

        if lastVideoID == videoID,
           now.timeIntervalSince(lastVideoDate) < 1.5 {
            return
        }

        lastVideoID = videoID
        lastVideoDate = now

        DispatchQueue.main.async { [weak self] in
            self?.onVideoSelected?(videoID)
        }
    }

    private func load(_ url: URL) {
        DispatchQueue.main.async { [weak self] in
            guard let self, let webView = self.webView else { return }
            self.markLoading()
            webView.load(URLRequest(url: url))
        }
    }

    private static func videoID(from url: URL) -> String? {
        guard let host = url.host?.lowercased() else { return nil }

        if host == "youtu.be" || host.hasSuffix(".youtu.be") {
            let candidate = url.pathComponents.dropFirst().first ?? ""
            return isValidVideoID(candidate) ? candidate : nil
        }

        guard host == "youtube.com" || host.hasSuffix(".youtube.com") else {
            return nil
        }

        let components = url.pathComponents.filter { $0 != "/" }

        if url.path == "/watch",
           let queryItems = URLComponents(
                url: url,
                resolvingAgainstBaseURL: false
           )?.queryItems,
           let candidate = queryItems.first(where: { $0.name == "v" })?.value,
           isValidVideoID(candidate) {
            return candidate
        }

        if let first = components.first,
           ["shorts", "embed", "live"].contains(first),
           components.count >= 2 {
            let candidate = components[1]
            return isValidVideoID(candidate) ? candidate : nil
        }

        return nil
    }

    private static func isValidVideoID(_ value: String) -> Bool {
        guard value.count == 11 else { return false }

        let allowed = CharacterSet(
            charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        )

        return value.unicodeScalars.allSatisfy { allowed.contains($0) }
    }
}
