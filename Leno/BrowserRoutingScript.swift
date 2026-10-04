import Foundation

enum BrowserRoutingScript {
    static let source = #"""
    (() => {
      "use strict";

      if (window.__YOUTUBE_VCD_BROWSER_V7__) return;
      window.__YOUTUBE_VCD_BROWSER_V7__ = true;

      const isYouTubeHost = (host) => {
        const value =
          String(host || "")
            .toLowerCase();

        return value ===
          "youtube.com" ||
          value ===
          "www.youtube.com" ||
          value ===
          "m.youtube.com" ||
          value ===
          "youtu.be";
      };

      const isPlaybackURL = (value) => {
        try {
          const url =
            new URL(
              value,
              location.href
            );

          if (!isYouTubeHost(url.host)) {
            return false;
          }

          if (
            url.host.toLowerCase() ===
            "youtu.be"
          ) {
            return (
              url.pathname
                .split("/")
                .filter(Boolean)
                .length > 0
            );
          }

          if (
            url.pathname ===
            "/watch"
          ) {
            return !!url.searchParams
              .get("v");
          }

          return (
            url.pathname.startsWith(
              "/shorts/"
            ) ||
            url.pathname.startsWith(
              "/live/"
            )
          );
        } catch (_) {
          return false;
        }
      };

      const postVideo = (value) => {
        try {
          const url =
            new URL(
              value,
              location.href
            );

          window.webkit
            ?.messageHandlers
            ?.browserOpenVideo
            ?.postMessage({
              url:
                url.href
            });

          return true;
        } catch (_) {
          return false;
        }
      };

      const interceptAnchor = (
        event
      ) => {
        const target =
          event.target;

        if (
          !(target instanceof Element)
        ) {
          return;
        }

        const anchor =
          target.closest(
            "a[href]"
          );

        if (
          !(anchor instanceof
            HTMLAnchorElement)
        ) {
          return;
        }

        if (
          !isPlaybackURL(
            anchor.href
          )
        ) {
          return;
        }

        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        postVideo(
          anchor.href
        );
      };

      document.addEventListener(
        "click",
        interceptAnchor,
        true
      );

      document.addEventListener(
        "auxclick",
        interceptAnchor,
        true
      );

      const nativePushState =
        history.pushState
          .bind(history);

      history.pushState =
        function(
          state,
          title,
          url
        ) {
          if (
            url &&
            isPlaybackURL(url)
          ) {
            postVideo(url);
            return;
          }

          return nativePushState(
            state,
            title,
            url
          );
        };

      // Browsing view must never own Lock Screen / Control Center transport.
      try {
        const mediaSession =
          navigator.mediaSession;

        if (mediaSession) {
          const proto =
            Object.getPrototypeOf(
              mediaSession
            );

          const blocked =
            function() {
              return undefined;
            };

          if (proto) {
            try {
              Object.defineProperty(
                proto,
                "setActionHandler",
                {
                  configurable: true,
                  enumerable: false,
                  get() {
                    return blocked;
                  },
                  set(_) {}
                }
              );
            } catch (_) {}
          }
        }
      } catch (_) {}

      // Browsing previews are not a second player.
      const nativePause =
        HTMLMediaElement
          .prototype
          .pause;

      document.addEventListener(
        "play",
        (event) => {
          const media =
            event.target;

          if (
            media instanceof
              HTMLMediaElement
          ) {
            try {
              nativePause.call(media);
            } catch (_) {}
          }
        },
        true
      );
    })();
    """#
}
