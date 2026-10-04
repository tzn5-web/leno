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
        installContentRules(on: webView, coordinator: context.coordinator)

        if let url = URL(string: "https://www.youtube.com/") {
            session.markLoading()
            webView.load(URLRequest(url: url))
        }

        return webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}

    static func dismantleUIView(_ uiView: WKWebView, coordinator: Coordinator) {
        uiView.configuration.userContentController.removeScriptMessageHandler(forName: "mediaState")
        uiView.navigationDelegate = nil
        uiView.uiDelegate = nil
    }

    private func installContentRules(on webView: WKWebView, coordinator: Coordinator) {
        WKContentRuleListStore.default().compileContentRuleList(
            forIdentifier: "LenoAdBlockRules-v2",
            encodedContentRuleList: AdBlockScript.contentRules
        ) { ruleList, error in
            guard let ruleList else {
                if let error {
                    print("Content rule compilation failed: \(error.localizedDescription)")
                }
                return
            }

            DispatchQueue.main.async {
                webView.configuration.userContentController.add(ruleList)

                guard !coordinator.didReloadAfterInstallingRules else { return }
                coordinator.didReloadAfterInstallingRules = true

                if webView.url != nil {
                    webView.reload()
                }
            }
        }
    }

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        private let session: YouTubeSession
        var didReloadAfterInstallingRules = false

        init(session: YouTubeSession) {
            self.session = session
        }

        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            session.markLoading()
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            session.markReady()
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
            decidePolicyFor navigationAction: WKNavigationAction,
            decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
        ) {
            guard let url = navigationAction.request.url else {
                decisionHandler(.cancel)
                return
            }

            let scheme = url.scheme?.lowercased()
            if scheme == "http" || scheme == "https" || scheme == "about" {
                decisionHandler(.allow)
            } else {
                decisionHandler(.cancel)
            }
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
