import Foundation

enum NavigationBridgeScript {
    static let source = #"""
    (() => {
      "use strict";

      if (window.__YOUTUBE_VCD_NATIVE_NAV__) return;
      window.__YOUTUBE_VCD_NATIVE_NAV__ = true;

      const validID = (value) =>
        typeof value === "string" &&
        /^[A-Za-z0-9_-]{11}$/.test(value);

      const videoIDFromURL = (rawURL) => {
        try {
          const url = new URL(
            rawURL,
            window.location.href
          );

          const host =
            url.hostname.toLowerCase();

          if (
            host === "youtu.be" ||
            host.endsWith(".youtu.be")
          ) {
            const candidate =
              url.pathname
                .split("/")
                .filter(Boolean)[0] || "";

            return validID(candidate)
              ? candidate
              : null;
          }

          if (!(
            host === "youtube.com" ||
            host.endsWith(".youtube.com")
          )) {
            return null;
          }

          if (url.pathname === "/watch") {
            const candidate =
              url.searchParams.get("v") || "";

            return validID(candidate)
              ? candidate
              : null;
          }

          const parts =
            url.pathname
              .split("/")
              .filter(Boolean);

          if (
            parts.length >= 2 &&
            ["shorts", "embed", "live"]
              .includes(parts[0]) &&
            validID(parts[1])
          ) {
            return parts[1];
          }

          return null;
        } catch (_) {
          return null;
        }
      };

      document.addEventListener(
        "click",
        (event) => {
          try {
            const anchor =
              event.target?.closest?.("a[href]");

            if (!anchor) return;

            const videoID =
              videoIDFromURL(anchor.href);

            if (!videoID) return;

            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            window.webkit
              ?.messageHandlers
              ?.openVideo
              ?.postMessage({
                videoID,
                href: anchor.href
              });
          } catch (_) {}
        },
        true
      );
    })();
    """#
}
