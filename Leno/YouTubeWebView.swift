import SwiftUI
import WebKit

struct YouTubeWebView: UIViewRepresentable {
    @ObservedObject var session: YouTubeSession

    func makeCoordinator() -> Coordinator {
        Coordinator(session: session)
    }

    func makeUIView(context: Context) -> WKWebView {
        let userContentController =
            WKUserContentController()

        userContentController.addUserScript(
            WKUserScript(
                source: AdBlockScript.source,
                injectionTime: .atDocumentStart,
                forMainFrameOnly: false
            )
        )

        userContentController.addUserScript(
            WKUserScript(
                source:
                    NavigationBridgeScript.source,
                injectionTime: .atDocumentStart,
                forMainFrameOnly: true
            )
        )

        userContentController.add(
            session,
            name: "openVideo"
        )

        let configuration =
            WKWebViewConfiguration()

        configuration.userContentController =
            userContentController

        configuration.websiteDataStore =
            .default()

        configuration.allowsInlineMediaPlayback =
            true

        configuration.allowsAirPlayForMediaPlayback =
            true

        configuration
            .allowsPictureInPictureMediaPlayback =
            true

        configuration
            .mediaTypesRequiringUserActionForPlayback =
            []

        let preferences =
            WKWebpagePreferences()

        preferences.allowsContentJavaScript =
            true

        configuration.defaultWebpagePreferences =
            preferences

        let webView = WKWebView(
            frame: .zero,
            configuration: configuration
        )

        webView.navigationDelegate =
            context.coordinator

        webView.uiDelegate =
            context.coordinator

        webView.allowsBackForwardNavigationGestures =
            true

        webView.scrollView
            .contentInsetAdjustmentBehavior =
            .never

        webView.isOpaque = false
        webView.backgroundColor =
            .systemBackground

        webView.scrollView.backgroundColor =
            .systemBackground

        session.attach(webView: webView)

        context.coordinator.observe(webView)

        installRulesAndLoad(
            on: webView,
            coordinator: context.coordinator
        )

        return webView
    }

    func updateUIView(
        _ uiView: WKWebView,
        context: Context
    ) {}

    static func dismantleUIView(
        _ uiView: WKWebView,
        coordinator: Coordinator
    ) {
        coordinator.invalidateObservations()

        uiView.configuration
            .userContentController
            .removeScriptMessageHandler(
                forName: "openVideo"
            )

        uiView.navigationDelegate = nil
        uiView.uiDelegate = nil
    }

    private func installRulesAndLoad(
        on webView: WKWebView,
        coordinator: Coordinator
    ) {
        guard let store =
                WKContentRuleListStore.default()
        else {
            session.loadHome()
            return
        }

        let identifier =
            "YoutubeVcdAdRules-v6"

        store.lookUpContentRuleList(
            forIdentifier: identifier
        ) { cached, _ in
            DispatchQueue.main.async {
                guard !coordinator
                    .didStartInitialLoad else {
                    return
                }

                if let cached {
                    webView.configuration
                        .userContentController
                        .add(cached)

                    coordinator
                        .didStartInitialLoad = true

                    session.loadHome()
                    return
                }

                store.compileContentRuleList(
                    forIdentifier: identifier,
                    encodedContentRuleList:
                        AdBlockScript.contentRules
                ) { compiled, error in
                    DispatchQueue.main.async {
                        if let compiled {
                            webView.configuration
                                .userContentController
                                .add(compiled)
                        } else if let error {
                            print(
                                "Content rule compilation failed: \(error.localizedDescription)"
                            )
                        }

                        guard !coordinator
                            .didStartInitialLoad else {
                            return
                        }

                        coordinator
                            .didStartInitialLoad = true

                        session.loadHome()
                    }
                }
            }
        }
    }

    final class Coordinator:
        NSObject,
        WKNavigationDelegate,
        WKUIDelegate
    {
        private let session: YouTubeSession

        private var observations:
            [NSKeyValueObservation] = []

        var didStartInitialLoad = false

        init(session: YouTubeSession) {
            self.session = session
        }

        func observe(_ webView: WKWebView) {
            observations = [
                webView.observe(
                    \.canGoBack,
                    options: [.initial, .new]
                ) { [weak self] webView, _ in
                    self?.syncNavigationState(
                        from: webView
                    )
                },

                webView.observe(
                    \.canGoForward,
                    options: [.initial, .new]
                ) { [weak self] webView, _ in
                    self?.syncNavigationState(
                        from: webView
                    )
                },

                webView.observe(
                    \.estimatedProgress,
                    options: [.initial, .new]
                ) { [weak self] webView, _ in
                    self?.syncNavigationState(
                        from: webView
                    )
                },

                webView.observe(
                    \.url,
                    options: [.initial, .new]
                ) { [weak self] webView, _ in
                    self?.syncNavigationState(
                        from: webView
                    )
                },

                webView.observe(
                    \.isLoading,
                    options: [.initial, .new]
                ) { [weak self] webView, _ in
                    self?.syncNavigationState(
                        from: webView
                    )
                }
            ]
        }

        func invalidateObservations() {
            observations.forEach {
                $0.invalidate()
            }

            observations.removeAll()
        }

        func webView(
            _ webView: WKWebView,
            didStartProvisionalNavigation:
                WKNavigation!
        ) {
            session.markLoading()
            syncNavigationState(from: webView)
        }

        func webView(
            _ webView: WKWebView,
            didCommit navigation: WKNavigation!
        ) {
            syncNavigationState(from: webView)
        }

        func webView(
            _ webView: WKWebView,
            didFinish navigation: WKNavigation!
        ) {
            session.markReady()
            syncNavigationState(from: webView)
            ensureHomeContainsVideos(webView)
        }

        func webView(
            _ webView: WKWebView,
            didFail navigation: WKNavigation!,
            withError error: Error
        ) {
            guard shouldRecover(from: error)
            else {
                return
            }

            session.recover(after: error)
        }

        func webView(
            _ webView: WKWebView,
            didFailProvisionalNavigation:
                WKNavigation!,
            withError error: Error
        ) {
            guard shouldRecover(from: error)
            else {
                return
            }

            session.recover(after: error)
        }

        func webViewWebContentProcessDidTerminate(
            _ webView: WKWebView
        ) {
            session.recover()
        }

        func webView(
            _ webView: WKWebView,
            createWebViewWith configuration:
                WKWebViewConfiguration,
            for navigationAction:
                WKNavigationAction,
            windowFeatures:
                WKWindowFeatures
        ) -> WKWebView? {
            if let url =
                    navigationAction.request.url,
               session.interceptVideoURL(url) {
                return nil
            }

            if navigationAction.targetFrame == nil {
                webView.load(
                    navigationAction.request
                )
            }

            return nil
        }

        func webView(
            _ webView: WKWebView,
            decidePolicyFor navigationAction:
                WKNavigationAction,
            decisionHandler:
                @escaping (
                    WKNavigationActionPolicy
                ) -> Void
        ) {
            guard let url =
                    navigationAction.request.url
            else {
                decisionHandler(.cancel)
                return
            }

            if session.interceptVideoURL(url) {
                decisionHandler(.cancel)
                return
            }

            let scheme =
                url.scheme?.lowercased() ?? ""

            let allowedSchemes = [
                "http",
                "https",
                "about",
                "data",
                "blob"
            ]

            decisionHandler(
                allowedSchemes.contains(scheme)
                    ? .allow
                    : .cancel
            )
        }

        private func ensureHomeContainsVideos(
            _ webView: WKWebView
        ) {
            guard let url = webView.url,
                  url.path == "/" else {
                return
            }

            DispatchQueue.main.asyncAfter(
                deadline: .now() + 2
            ) { [weak webView] in
                guard let webView,
                      webView.url?.path == "/"
                else {
                    return
                }

                let script = #"""
                (() => {
                  const text =
                    (document.body?.innerText || "")
                      .toLowerCase();

                  const emptyPrompt =
                    text.includes(
                      "try searching to get started"
                    ) ||
                    text.includes(
                      "start watching videos"
                    );

                  const candidates =
                    Array.from(
                      document.querySelectorAll(
                        'a[href*="/watch?v="], ytm-video-with-context-renderer, ytm-compact-video-renderer'
                      )
                    );

                  const visibleVideoCard =
                    candidates.some((node) => {
                      const rect =
                        node.getBoundingClientRect();

                      return rect.width > 120 &&
                             rect.height > 60 &&
                             rect.bottom > 0 &&
                             rect.top <
                               window.innerHeight * 2;
                    });

                  return {
                    emptyPrompt,
                    visibleVideoCard
                  };
                })();
                """#

                webView.evaluateJavaScript(
                    script
                ) { result, _ in
                    guard let result =
                            result as?
                            [String: Any]
                    else {
                        return
                    }

                    let emptyPrompt =
                        result["emptyPrompt"]
                            as? Bool ?? false

                    let visibleVideoCard =
                        result["visibleVideoCard"]
                            as? Bool ?? false

                    guard emptyPrompt ||
                          !visibleVideoCard else {
                        return
                    }

                    var components =
                        URLComponents(
                            string:
                              "https://m.youtube.com/results"
                        )

                    components?.queryItems = [
                        URLQueryItem(
                            name:
                                "search_query",
                            value:
                                "trending videos"
                        )
                    ]

                    guard let fallback =
                            components?.url
                    else {
                        return
                    }

                    DispatchQueue.main.async {
                        webView.load(
                            URLRequest(
                                url: fallback
                            )
                        )
                    }
                }
            }
        }

        private func syncNavigationState(
            from webView: WKWebView
        ) {
            session.updateNavigationState(
                canGoBack: webView.canGoBack,
                canGoForward:
                    webView.canGoForward,
                url: webView.url,
                progress:
                    webView.estimatedProgress,
                isLoading:
                    webView.isLoading
            )
        }

        private func shouldRecover(
            from error: Error
        ) -> Bool {
            let nsError = error as NSError

            if nsError.domain ==
                    NSURLErrorDomain &&
               nsError.code ==
                    NSURLErrorCancelled {
                return false
            }

            return true
        }
    }
}
