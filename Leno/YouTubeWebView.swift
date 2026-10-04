import SwiftUI
import WebKit

struct YouTubeWebView: UIViewRepresentable {
    @ObservedObject var session: YouTubeSession

    func makeCoordinator() -> Coordinator {
        Coordinator(session: session)
    }

    func makeUIView(context: Context) -> WKWebView {
        let userContentController = WKUserContentController()
        userContentController.addUserScript(
            WKUserScript(
                source: AdBlockScript.source,
                injectionTime: .atDocumentStart,
                forMainFrameOnly: false
            )
        )
        userContentController.add(session, name: "mediaState")

        let configuration = WKWebViewConfiguration()
        configuration.userContentController = userContentController
        configuration.websiteDataStore = .default()
        configuration.allowsInlineMediaPlayback = true
        configuration.allowsAirPlayForMediaPlayback = true
        configuration.allowsPictureInPictureMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []

        let preferences = WKWebpagePreferences()
        preferences.allowsContentJavaScript = true
        configuration.defaultWebpagePreferences = preferences

        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        webView.allowsBackForwardNavigationGestures = true
        webView.scrollView.contentInsetAdjustmentBehavior = .never

        session.attach(webView: webView)
        context.coordinator.observe(webView)
        installContentRulesThenLoad(on: webView, coordinator: context.coordinator)

        return webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}

    static func dismantleUIView(_ uiView: WKWebView, coordinator: Coordinator) {
        coordinator.invalidateObservations()
        uiView.configuration.userContentController.removeScriptMessageHandler(forName: "mediaState")
        uiView.navigationDelegate = nil
        uiView.uiDelegate = nil
    }

    private func installContentRulesThenLoad(on webView: WKWebView, coordinator: Coordinator) {
        WKContentRuleListStore.default().compileContentRuleList(
            forIdentifier: "YoutubeVcdAdRules-v3",
            encodedContentRuleList: AdBlockScript.contentRules
        ) { ruleList, error in
            DispatchQueue.main.async {
                if let ruleList {
                    webView.configuration.userContentController.add(ruleList)
                } else if let error {
                    print("Content rule compilation failed: \(error.localizedDescription)")
                }

                guard !coordinator.didLoadInitialPage else { return }
                coordinator.didLoadInitialPage = true
                session.loadHome()
            }
        }
    }

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        private let session: YouTubeSession
        private var observations: [NSKeyValueObservation] = []
        var didLoadInitialPage = false

        init(session: YouTubeSession) {
            self.session = session
        }

        func observe(_ webView: WKWebView) {
            observations = [
                webView.observe(\.canGoBack, options: [.initial, .new]) { [weak self] webView, _ in
                    self?.syncNavigationState(from: webView)
                },
                webView.observe(\.canGoForward, options: [.initial, .new]) { [weak self] webView, _ in
                    self?.syncNavigationState(from: webView)
                },
                webView.observe(\.estimatedProgress, options: [.initial, .new]) { [weak self] webView, _ in
                    self?.syncNavigationState(from: webView)
                },
                webView.observe(\.url, options: [.initial, .new]) { [weak self] webView, _ in
                    self?.syncNavigationState(from: webView)
                },
                webView.observe(\.isLoading, options: [.initial, .new]) { [weak self] webView, _ in
                    self?.syncNavigationState(from: webView)
                }
            ]
        }

        func invalidateObservations() {
            observations.forEach { $0.invalidate() }
            observations.removeAll()
        }

        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            session.markLoading()
            syncNavigationState(from: webView)
        }

        func webView(_ webView: WKWebView, didCommit navigation: WKNavigation!) {
            syncNavigationState(from: webView)
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            session.markReady()
            syncNavigationState(from: webView)
        }

        func webView(
            _ webView: WKWebView,
            didFail navigation: WKNavigation!,
            withError error: Error
        ) {
            guard shouldRecover(from: error) else { return }
            session.recover(after: error)
        }

        func webView(
            _ webView: WKWebView,
            didFailProvisionalNavigation navigation: WKNavigation!,
            withError error: Error
        ) {
            guard shouldRecover(from: error) else { return }
            session.recover(after: error)
        }

        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
            session.recover()
        }

        func webView(
            _ webView: WKWebView,
            createWebViewWith configuration: WKWebViewConfiguration,
            for navigationAction: WKNavigationAction,
            windowFeatures: WKWindowFeatures
        ) -> WKWebView? {
            if navigationAction.targetFrame == nil {
                webView.load(navigationAction.request)
            }
            return nil
        }

        func webView(
            _ webView: WKWebView,
            decidePolicyFor navigationAction: WKNavigationAction,
            decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
        ) {
            guard let url = navigationAction.request.url else {
                decisionHandler(.cancel)
                return
            }

            let scheme = url.scheme?.lowercased()
            switch scheme {
            case "http", "https", "about", "data", "blob":
                decisionHandler(.allow)
            default:
                decisionHandler(.cancel)
            }
        }

        private func syncNavigationState(from webView: WKWebView) {
            session.updateNavigationState(
                canGoBack: webView.canGoBack,
                canGoForward: webView.canGoForward,
                url: webView.url,
                progress: webView.estimatedProgress,
                isLoading: webView.isLoading
            )
        }

        private func shouldRecover(from error: Error) -> Bool {
            let nsError = error as NSError

            if nsError.domain == NSURLErrorDomain && nsError.code == NSURLErrorCancelled {
                return false
            }

            return true
        }
    }
}
