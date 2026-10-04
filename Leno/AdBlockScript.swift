import Foundation

enum AdBlockScript {
    static let source = #"""
    (() => {
      "use strict";

      if (window.__YOUTUBE_VCD_COSMETIC_FILTER__) {
        return;
      }

      window.__YOUTUBE_VCD_COSMETIC_FILTER__ = true;

      const HIDE_SELECTORS = [
        "#player-ads",
        ".ytp-ad-module",
        ".video-ads",
        ".ytp-ad-overlay-container",
        ".ytp-ad-player-overlay",
        ".ytp-ad-text-overlay",
        ".ytp-ad-message-container",
        ".ytp-ad-image-overlay",
        ".ytp-ad-overlay-slot",
        "ytd-ad-slot-renderer",
        "ytd-in-feed-ad-layout-renderer",
        "ytd-display-ad-renderer",
        "ytd-promoted-sparkles-web-renderer",
        "ytd-promoted-video-renderer",
        "ytd-compact-promoted-video-renderer",
        "ytd-video-masthead-ad-v3-renderer",
        "ytd-action-companion-ad-renderer",
        "ytd-ads-engagement-panel-content-renderer",
        "ytd-search-pyv-renderer",
        "ytm-ad-slot-renderer",
        "ytm-in-feed-ad-layout-renderer",
        "ytm-promoted-sparkles-web-renderer",
        "ytm-companion-ad-renderer",
        "ad-slot-renderer"
      ];

      const installCSS = () => {
        if (
          document.getElementById(
            "__youtube_vcd_cosmetic_css__"
          )
        ) {
          return;
        }

        const style =
          document.createElement("style");

        style.id =
          "__youtube_vcd_cosmetic_css__";

        style.textContent =
          HIDE_SELECTORS.join(",") +
          "{display:none!important;visibility:hidden!important;}";

        (
          document.head ||
          document.documentElement
        )?.appendChild(style);
      };

      const cleanUI = () => {
        installCSS();

        for (const selector of HIDE_SELECTORS) {
          document
            .querySelectorAll(selector)
            .forEach((node) => {
              try {
                node.remove();
              } catch (_) {}
            });
        }

        try {
          const skip =
            document.querySelector(
              ".ytp-skip-ad-button, .ytp-ad-skip-button, .ytp-ad-skip-button-modern, button.ytp-skip-ad-button"
            );

          if (skip) {
            skip.click();
          }
        } catch (_) {}
      };

      let scheduled = false;

      const scheduleClean = () => {
        if (scheduled) return;

        scheduled = true;

        setTimeout(() => {
          scheduled = false;
          cleanUI();
        }, 180);
      };

      cleanUI();

      const observer =
        new MutationObserver(scheduleClean);

      const start = () => {
        cleanUI();

        if (document.documentElement) {
          observer.observe(
            document.documentElement,
            {
              childList: true,
              subtree: true
            }
          );
        }
      };

      if (document.documentElement) {
        start();
      } else {
        document.addEventListener(
          "DOMContentLoaded",
          start,
          { once: true }
        );
      }

      setInterval(cleanUI, 2000);
    })();
    """#

    static let contentRules = #"""
    [
      {
        "trigger": {
          "url-filter": ".*doubleclick\\.net.*",
          "resource-type": [
            "document",
            "image",
            "style-sheet",
            "script",
            "font",
            "raw",
            "svg-document",
            "media",
            "popup"
          ]
        },
        "action": {
          "type": "block"
        }
      },
      {
        "trigger": {
          "url-filter": ".*googlesyndication\\.com.*"
        },
        "action": {
          "type": "block"
        }
      },
      {
        "trigger": {
          "url-filter": ".*googleadservices\\.com.*"
        },
        "action": {
          "type": "block"
        }
      },
      {
        "trigger": {
          "url-filter": ".*imasdk\\.googleapis\\.com.*"
        },
        "action": {
          "type": "block"
        }
      }
    ]
    """#
}
