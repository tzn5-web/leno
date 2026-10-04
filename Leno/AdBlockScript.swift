import Foundation

enum AdBlockScript {
    static let source = #"""
    (() => {
      "use strict";

      if (window.__LENO_ADBLOCK_INSTALLED__) return;
      window.__LENO_ADBLOCK_INSTALLED__ = true;

      const AD_KEYS = new Set([
        "adPlacements",
        "playerAds",
        "adSlots"
      ]);

      const AD_RENDERER_KEYS = new Set([
        "adSlotRenderer",
        "inFeedAdLayoutRenderer",
        "displayAdRenderer",
        "searchPyvRenderer",
        "promotedVideoRenderer",
        "promotedSparklesWebRenderer",
        "promotedSparklesTextSearchRenderer",
        "compactPromotedItemRenderer",
        "compactPromotedVideoRenderer",
        "gridPromotedVideoRenderer",
        "carouselAdRenderer",
        "adPlacementRenderer",
        "playerLegacyDesktopWatchAdsRenderer",
        "videoMastheadAdV3Renderer",
        "actionCompanionAdRenderer",
        "actionEngagementPanelContentRenderer",
        "adsEngagementPanelContentRenderer",
        "companionAdRenderer"
      ]);

      const isAdObject = (value) => {
        if (!value || typeof value !== "object" || Array.isArray(value)) return false;
        for (const key of Object.keys(value)) {
          if (AD_RENDERER_KEYS.has(key)) return true;
        }
        return false;
      };

      const stripAds = (root) => {
        if (!root || typeof root !== "object") return root;

        const stack = [{ value: root, depth: 0 }];
        let visited = 0;
        const maxVisited = 4000;
        const maxDepth = 12;

        while (stack.length && visited < maxVisited) {
          const { value, depth } = stack.pop();
          if (!value || typeof value !== "object" || depth > maxDepth) continue;
          visited++;

          if (Array.isArray(value)) {
            for (let index = value.length - 1; index >= 0; index--) {
              const child = value[index];

              if (isAdObject(child)) {
                value.splice(index, 1);
                continue;
              }

              if (child && typeof child === "object") {
                stack.push({ value: child, depth: depth + 1 });
              }
            }
            continue;
          }

          for (const key of Object.keys(value)) {
            if (AD_KEYS.has(key) || AD_RENDERER_KEYS.has(key)) {
              try { delete value[key]; } catch (_) {}
              continue;
            }

            const child = value[key];
            if (child && typeof child === "object") {
              stack.push({ value: child, depth: depth + 1 });
            }
          }
        }

        return root;
      };

      const originalParse = JSON.parse;
      JSON.parse = function(...args) {
        const result = originalParse.apply(this, args);
        try { stripAds(result); } catch (_) {}
        return result;
      };

      if (typeof Response !== "undefined" && Response.prototype?.json) {
        const originalResponseJSON = Response.prototype.json;
        Response.prototype.json = async function(...args) {
          const result = await originalResponseJSON.apply(this, args);
          try { stripAds(result); } catch (_) {}
          return result;
        };
      }

      const cleanKnownGlobals = () => {
        try {
          if (window.ytInitialPlayerResponse) stripAds(window.ytInitialPlayerResponse);
        } catch (_) {}
        try {
          if (window.ytInitialData) stripAds(window.ytInitialData);
        } catch (_) {}
      };

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
        if (document.getElementById("__leno_adblock_css__")) return;

        const style = document.createElement("style");
        style.id = "__leno_adblock_css__";
        style.textContent = HIDE_SELECTORS.join(",") + "{display:none!important;visibility:hidden!important;}";

        const parent = document.head || document.documentElement;
        if (parent) parent.appendChild(style);
      };

      const skipActiveAdFallback = () => {
        try {
          const player = document.querySelector(".html5-video-player.ad-showing, .ad-showing");
          if (!player) return;

          const skipButton = document.querySelector(
            ".ytp-skip-ad-button, .ytp-ad-skip-button, .ytp-ad-skip-button-modern, button.ytp-skip-ad-button"
          );

          if (skipButton) {
            try { skipButton.click(); } catch (_) {}
            return;
          }

          const video = document.querySelector("video");
          if (!video) return;

          const duration = Number(video.duration);
          if (Number.isFinite(duration) && duration > 0 && duration <= 600) {
            video.currentTime = Math.max(0, duration - 0.05);
          }
        } catch (_) {}
      };

      const removeAdUI = () => {
        installCosmeticRules();

        for (const selector of HIDE_SELECTORS) {
          document.querySelectorAll(selector).forEach((node) => {
            try { node.remove(); } catch (_) {}
          });
        }

        skipActiveAdFallback();
      };

      const reportMediaState = () => {
        try {
          const video = document.querySelector("video");
          if (!video || !window.webkit?.messageHandlers?.mediaState) return;

          window.webkit.messageHandlers.mediaState.postMessage({
            title: (document.title || "YouTube").replace(/\s*-\s*YouTube\s*$/, ""),
            paused: !!video.paused,
            currentTime: Number.isFinite(video.currentTime) ? video.currentTime : 0,
            duration: Number.isFinite(video.duration) ? video.duration : 0
          });
        } catch (_) {}
      };

      let scheduled = false;
      const scheduleMaintenance = () => {
        if (scheduled) return;
        scheduled = true;

        setTimeout(() => {
          scheduled = false;
          cleanKnownGlobals();
          removeAdUI();
        }, 120);
      };

      installCosmeticRules();
      cleanKnownGlobals();
      removeAdUI();

      const observer = new MutationObserver(scheduleMaintenance);

      const startObserver = () => {
        installCosmeticRules();

        if (document.documentElement) {
          observer.observe(document.documentElement, {
            childList: true,
            subtree: true
          });
        }
      };

      if (document.documentElement) startObserver();
      else document.addEventListener("DOMContentLoaded", startObserver, { once: true });

      document.addEventListener("play", reportMediaState, true);
      document.addEventListener("pause", reportMediaState, true);
      document.addEventListener("durationchange", reportMediaState, true);
      document.addEventListener("loadedmetadata", reportMediaState, true);
      document.addEventListener("timeupdate", () => {
        if (!window.__LENO_LAST_MEDIA_REPORT__ ||
            Date.now() - window.__LENO_LAST_MEDIA_REPORT__ > 1000) {
          window.__LENO_LAST_MEDIA_REPORT__ = Date.now();
          reportMediaState();
        }
      }, true);

      setInterval(() => {
        cleanKnownGlobals();
        removeAdUI();
        reportMediaState();
      }, 1500);
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
