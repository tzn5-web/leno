import Foundation

enum AdBlockScript {
    static let source = #"""
    (() => {
      "use strict";

      if (window.__YOUTUBE_VCD_V2_FILTER__) return;
      window.__YOUTUBE_VCD_V2_FILTER__ = true;

      const PLAYER_AD_KEYS = [
        "adPlacements",
        "playerAds",
        "adSlots",
        "adBreakHeartbeatParams",
        "adBreakParams",
        "adPlacementConfig",
        "adParams",
        "adBreaks"
      ];

      const prunePlayerPayload = (payload) => {
        if (!payload || typeof payload !== "object") return payload;

        for (const key of PLAYER_AD_KEYS) {
          try {
            if (Object.prototype.hasOwnProperty.call(payload, key)) {
              delete payload[key];
            }
          } catch (_) {}
        }

        return payload;
      };

      const cleanKnownPlayerGlobal = () => {
        try {
          if (window.ytInitialPlayerResponse) {
            prunePlayerPayload(window.ytInitialPlayerResponse);
          }
        } catch (_) {}
      };

      if (typeof Response !== "undefined" && Response.prototype?.json) {
        const originalResponseJSON = Response.prototype.json;

        Response.prototype.json = async function(...args) {
          const result = await originalResponseJSON.apply(this, args);

          try {
            const responseURL = String(this.url || "");
            if (responseURL.includes("/youtubei/v1/player")) {
              prunePlayerPayload(result);
            }
          } catch (_) {}

          return result;
        };
      }

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

      const installCosmeticRules = () => {
        if (document.getElementById("__youtube_vcd_v2_css__")) return;

        const style = document.createElement("style");
        style.id = "__youtube_vcd_v2_css__";
        style.textContent =
          HIDE_SELECTORS.join(",") +
          "{display:none!important;visibility:hidden!important;}";

        (document.head || document.documentElement)?.appendChild(style);
      };

      const clickSkipButton = () => {
        try {
          const player = document.querySelector(".html5-video-player.ad-showing, .ad-showing");
          if (!player) return;

          const button = document.querySelector(
            ".ytp-skip-ad-button, .ytp-ad-skip-button, .ytp-ad-skip-button-modern, button.ytp-skip-ad-button"
          );

          if (button) {
            button.click();
          }
        } catch (_) {}
      };

      const reportMediaState = () => {
        try {
          const bridge = window.webkit?.messageHandlers?.mediaState;
          if (!bridge) return;

          const videos = Array.from(document.querySelectorAll("video"));
          const video =
            videos.find((item) =>
              !item.paused &&
              !item.ended &&
              item.readyState >= 2 &&
              !!item.currentSrc
            ) ||
            videos.find((item) => {
              const rect = item.getBoundingClientRect();
              return rect.width * rect.height > 12000 &&
                     item.readyState >= 1 &&
                     !!item.currentSrc;
            }) ||
            null;

          if (!video) {
            bridge.postMessage({
              title: "YouTube",
              paused: true,
              hasMedia: false,
              currentTime: 0,
              duration: 0
            });
            return;
          }

          bridge.postMessage({
            title: (document.title || "YouTube").replace(/\s*-\s*YouTube\s*$/, ""),
            paused: !!video.paused,
            hasMedia: true,
            currentTime: Number.isFinite(video.currentTime) ? video.currentTime : 0,
            duration: Number.isFinite(video.duration) ? video.duration : 0
          });
        } catch (_) {}
      };

      let maintenanceScheduled = false;

      const maintain = () => {
        if (maintenanceScheduled) return;
        maintenanceScheduled = true;

        setTimeout(() => {
          maintenanceScheduled = false;
          installCosmeticRules();
          cleanKnownPlayerGlobal();
          clickSkipButton();
        }, 180);
      };

      installCosmeticRules();
      cleanKnownPlayerGlobal();
      clickSkipButton();

      const observer = new MutationObserver(maintain);

      const startObserver = () => {
        installCosmeticRules();

        if (document.documentElement) {
          observer.observe(document.documentElement, {
            childList: true,
            subtree: true
          });
        }
      };

      if (document.documentElement) {
        startObserver();
      } else {
        document.addEventListener("DOMContentLoaded", startObserver, { once: true });
      }

      document.addEventListener("play", reportMediaState, true);
      document.addEventListener("pause", reportMediaState, true);
      document.addEventListener("loadedmetadata", reportMediaState, true);
      document.addEventListener("durationchange", reportMediaState, true);
      document.addEventListener("emptied", reportMediaState, true);

      document.addEventListener("timeupdate", () => {
        const now = Date.now();
        if (!window.__YOUTUBE_VCD_LAST_MEDIA_REPORT__ ||
            now - window.__YOUTUBE_VCD_LAST_MEDIA_REPORT__ > 1000) {
          window.__YOUTUBE_VCD_LAST_MEDIA_REPORT__ = now;
          reportMediaState();
        }
      }, true);

      setInterval(() => {
        cleanKnownPlayerGlobal();
        clickSkipButton();
        reportMediaState();
      }, 2000);
    })();
    """#

    static let contentRules = #"""
    [
      {
        "trigger": {
          "url-filter": ".*doubleclick\\.net.*",
          "resource-type": ["document", "image", "style-sheet", "script", "font", "raw", "svg-document", "media", "popup"]
        },
        "action": { "type": "block" }
      },
      {
        "trigger": {
          "url-filter": ".*googlesyndication\\.com.*"
        },
        "action": { "type": "block" }
      },
      {
        "trigger": {
          "url-filter": ".*googleadservices\\.com.*"
        },
        "action": { "type": "block" }
      },
      {
        "trigger": {
          "url-filter": ".*imasdk\\.googleapis\\.com.*"
        },
        "action": { "type": "block" }
      }
    ]
    """#
}
