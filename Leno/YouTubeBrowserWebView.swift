import SwiftUI
import WebKit

struct YouTubeBrowserWebView:
    UIViewRepresentable
{
    @ObservedObject var session:
        YouTubeSession

    func makeCoordinator()
        -> Coordinator
    {
        Coordinator(
            session:
                session
        )
    }

    func makeUIView(
        context: Context
    ) -> WKWebView {
        let controller =
            WKUserContentController()

        controller.addUserScript(
            WKUserScript(
                source:
                    BrowserRoutingScript
                        .source,
                injectionTime:
                    .atDocumentStart,
                forMainFrameOnly:
                    true
            )
        )

        controller.addUserScript(
            WKUserScript(
                source:
                    AdBlockScript.source,
                injectionTime:
                    .atDocumentStart,
                forMainFrameOnly:
                    false
            )
        )

        controller.add(
            session,
            name:
                "browserOpenVideo"
        )

        let configuration =
            WKWebViewConfiguration()

        configuration
            .userContentController =
            controller

        configuration
            .websiteDataStore =
            .default()

        configuration
            .allowsInlineMediaPlayback =
            true

        configuration
            .allowsPictureInPictureMediaPlayback =
            false

        configuration
            .allowsAirPlayForMediaPlayback =
            false

        configuration
            .mediaTypesRequiringUserActionForPlayback =
            [.all]

        let preferences =
            WKWebpagePreferences()

        preferences
            .allowsContentJavaScript =
            true

        configuration
            .defaultWebpagePreferences =
            preferences

        let webView =
            WKWebView(
                frame: .zero,
                configuration:
                    configuration
            )

        webView.navigationDelegate =
            context.coordinator

        webView.uiDelegate =
            context.coordinator

        webView
            .allowsBackForwardNavigationGestures =
            true

        webView.scrollView
            .contentInsetAdjustmentBehavior =
            .never

        webView.isOpaque = false

        webView.backgroundColor =
            .systemBackground

        webView.scrollView
            .backgroundColor =
            .systemBackground

        session.attachBrowser(
            webView:
                webView
        )

        context.coordinator
            .loadInitialHome(
                in:
                    webView
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
        uiView.configuration
            .userContentController
            .removeScriptMessageHandler(
                forName:
                    "browserOpenVideo"
            )

        uiView.navigationDelegate =
            nil

        uiView.uiDelegate =
            nil
    }

    final class Coordinator:
        NSObject,
        WKNavigationDelegate,
        WKUIDelegate
    {
        private let session:
            YouTubeSession

        private var initialLoadStarted =
            false

        init(
            session:
                YouTubeSession
        ) {
            self.session =
                session
        }

        func loadInitialHome(
            in webView: WKWebView
        ) {
            guard !initialLoadStarted else {
                return
            }

            initialLoadStarted =
                true

            guard let url =
                    URL(
                        string:
                            "https://m.youtube.com/"
                    ) else {
                return
            }

            webView.load(
                URLRequest(
                    url: url
                )
            )
        }

        func webView(
            _ webView: WKWebView,
            decidePolicyFor
                navigationAction:
                    WKNavigationAction,
            decisionHandler:
                @escaping (
                    WKNavigationActionPolicy
                ) -> Void
        ) {
            guard let url =
                    navigationAction
                        .request
                        .url else {
                decisionHandler(
                    .cancel
                )
                return
            }

            if isYouTubeAppPromotion(
                url
            ) {
                decisionHandler(
                    .cancel
                )
                return
            }

            if session
                .shouldOpenInPlayer(
                    url
                ) {
                decisionHandler(
                    .cancel
                )

                DispatchQueue.main.async {
                    self.session
                        .openVideo(
                            url
                        )
                }

                return
            }

            let scheme =
                url.scheme?
                    .lowercased() ?? ""

            let allowed = [
                "http",
                "https",
                "about",
                "data",
                "blob"
            ]

            decisionHandler(
                allowed.contains(
                    scheme
                )
                    ? .allow
                    : .cancel
            )
        }

        func webView(
            _ webView: WKWebView,
            createWebViewWith
                configuration:
                    WKWebViewConfiguration,
            for navigationAction:
                WKNavigationAction,
            windowFeatures:
                WKWindowFeatures
        ) -> WKWebView? {
            guard let url =
                    navigationAction
                        .request
                        .url else {
                return nil
            }

            if session
                .shouldOpenInPlayer(
                    url
                ) {
                DispatchQueue.main.async {
                    self.session
                        .openVideo(
                            url
                        )
                }

                return nil
            }

            if !isYouTubeAppPromotion(
                url
            ) {
                webView.load(
                    navigationAction
                        .request
                )
            }

            return nil
        }

        private func
            isYouTubeAppPromotion(
                _ url: URL
            ) -> Bool
        {
            let scheme =
                url.scheme?
                    .lowercased() ?? ""

            if [
                "youtube",
                "vnd.youtube",
                "itms-apps",
                "itms-services",
                "intent"
            ].contains(
                scheme
            ) {
                return true
            }

            let host =
                url.host?
                    .lowercased() ?? ""

            if host ==
                "apps.apple.com" ||
               host ==
                "itunes.apple.com"
            {
                return true
            }

            let value =
                url.absoluteString
                    .lowercased()

            return value.contains(
                "mweb_to_native_app"
            ) ||
            value.contains(
                "redirect_app_store_ios=1"
            )
        }
    }
}
