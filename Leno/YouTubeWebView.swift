import SwiftUI
import WebKit

struct YouTubeWebView: UIViewRepresentable {
    @ObservedObject var session: YouTubeSession

    func makeCoordinator() -> Coordinator {
        Coordinator(session: session)
    }

    func makeUIView(context: Context) -> WKWebView {
        let userContentController = WKUserContentController()

        // Playback lifecycle shielding must be the first project script:
        // it captures pristine WebKit APIs before YouTube or our other hooks.
        userContentController.addUserScript(
            WKUserScript(
                source: PlaybackBridgeScript.source,
                injectionTime: .atDocumentStart,
                forMainFrameOnly: true
            )
        )

        userContentController.addUserScript(
            WKUserScript(
                source: AdBlockScript.source,
                injectionTime: .atDocumentStart,
                forMainFrameOnly: false
            )
        )

        userContentController.add(
            session,
            name: "mediaState"
        )

        userContentController.add(
            session,
            name: "mediaIntent"
        )

        let configuration = WKWebViewConfiguration()
        configuration.userContentController =
            userContentController
        configuration.websiteDataStore = .default()
        configuration.allowsInlineMediaPlayback = true
        configuration.allowsAirPlayForMediaPlayback = true
        configuration.allowsPictureInPictureMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []

        let preferences = WKWebpagePreferences()
        preferences.allowsContentJavaScript = true
        configuration.defaultWebpagePreferences = preferences

        let webView = WKWebView(
            frame: .zero,
            configuration: configuration
        )

        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        webView.allowsBackForwardNavigationGestures = true
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.isOpaque = false
        webView.backgroundColor = .systemBackground
        webView.scrollView.backgroundColor = .systemBackground

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

        uiView.configuration.userContentController
            .removeScriptMessageHandler(
                forName: "mediaState"
            )

        uiView.configuration.userContentController
            .removeScriptMessageHandler(
                forName: "mediaIntent"
            )

        uiView.navigationDelegate = nil
        uiView.uiDelegate = nil
    }

    private func installRulesAndLoad(
        on webView: WKWebView,
        coordinator: Coordinator
    ) {
        guard let store =
                WKContentRuleListStore.default() else {
            session.loadHome()
            return
        }

        let identifier = "YoutubeVcdAdRules-v5"

        store.lookUpContentRuleList(
            forIdentifier: identifier
        ) { cached, _ in
            DispatchQueue.main.async {
                guard !coordinator.didStartInitialLoad else {
                    return
                }

                if let cached {
                    webView.configuration
                        .userContentController
                        .add(cached)

                    coordinator.didStartInitialLoad = true
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

                        guard !coordinator.didStartInitialLoad else {
                            return
                        }

                        coordinator.didStartInitialLoad = true
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
            didStartProvisionalNavigation navigation: WKNavigation!
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
            guard shouldRecover(from: error) else {
                return
            }

            session.recover(after: error)
        }

        func webView(
            _ webView: WKWebView,
            didFailProvisionalNavigation navigation: WKNavigation!,
            withError error: Error
        ) {
            guard shouldRecover(from: error) else {
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
                @escaping (WKNavigationActionPolicy) -> Void
        ) {
            guard let url =
                    navigationAction.request.url else {
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
            guard let url = webView.url else {
                return
            }

            let path = url.path

            guard path == "/" ||
                  path == "/feed/trending" else {
                return
            }

            DispatchQueue.main.asyncAfter(
                deadline: .now() + 1.8
            ) { [weak webView] in
                guard let webView,
                      let currentURL = webView.url,
                      currentURL.path == path else {
                    return
                }

                let script = #"""
                (() => {
                  const validID = (value) =>
                    typeof value === "string" &&
                    /^[A-Za-z0-9_-]{11}$/.test(value);

                  return Array.from(
                    document.querySelectorAll("a[href]")
                  ).some((anchor) => {
                    try {
                      const url = new URL(
                        anchor.href,
                        location.href
                      );

                      if (url.pathname === "/watch") {
                        return validID(
                          url.searchParams.get("v") || ""
                        );
                      }

                      const parts =
                        url.pathname
                          .split("/")
                          .filter(Boolean);

                      if (
                        parts[0] === "shorts" &&
                        parts.length >= 2
                      ) {
                        return validID(parts[1]);
                      }

                      if (
                        url.hostname === "youtu.be" &&
                        parts.length >= 1
                      ) {
                        return validID(parts[0]);
                      }

                      return false;
                    } catch (_) {
                      return false;
                    }
                  });
                })();
                """#

                webView.evaluateJavaScript(
                    script
                ) { result, _ in
                    let hasVideo =
                        result as? Bool ?? false

                    guard !hasVideo else {
                        return
                    }

                    DispatchQueue.main.async {
                        if path == "/" {
                            guard let trending =
                                    URL(
                                      string:
                                        "https://m.youtube.com/feed/trending"
                                    ) else {
                                return
                            }

                            webView.load(
                                URLRequest(
                                    url: trending
                                )
                            )
                        } else {
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
                                    components?.url else {
                                return
                            }

                            webView.load(
                                URLRequest(
                                    url: fallback
                                )
                            )
                        }
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
            let nsError =
                error as NSError

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
