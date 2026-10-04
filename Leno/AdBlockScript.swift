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

      const stripAds = (value, depth = 0) => {
        if (!value || depth > 12) return value;

        if (Array.isArray(value)) {
          for (const item of value) stripAds(item, depth + 1);
          return value;
        }

        if (typeof value !== "object") return value;

        for (const key of Object.keys(value)) {
          if (AD_KEYS.has(key)) {
            try { delete value[key]; } catch (_) {}
            continue;
          }

          const child = value[key];
          if (child && typeof child === "object") {
            stripAds(child, depth + 1);
          }
        }

        return value;
      };

      const originalParse = JSON.parse;
      JSON.parse = function(...args) {
        const result = originalParse.apply(this, args);
        try { stripAds(result); } catch (_) {}
        return result;
      };

      const originalResponseJSON = Response.prototype.json;
      Response.prototype.json = async function(...args) {
        const result = await originalResponseJSON.apply(this, args);
        try { stripAds(result); } catch (_) {}
        return result;
      };

      const cleanKnownGlobals = () => {
        try {
          if (window.ytInitialPlayerResponse) stripAds(window.ytInitialPlayerResponse);
        } catch (_) {}
        try {
          if (window.ytInitialData) stripAds(window.ytInitialData);
        } catch (_) {}
      };

      const removeAdUI = () => {
        const selectors = [
          ".ytp-ad-module",
          ".video-ads",
          ".ytp-ad-overlay-container",
          ".ytp-ad-player-overlay",
          ".ytp-ad-text-overlay",
          "ytd-display-ad-renderer",
          "ytd-promoted-sparkles-web-renderer",
          "ytd-promoted-video-renderer",
          "ytm-promoted-sparkles-web-renderer",
          "ytm-companion-ad-renderer"
        ];

        for (const selector of selectors) {
          document.querySelectorAll(selector).forEach((node) => {
            try { node.remove(); } catch (_) {}
          });
        }

        const skipSelectors = [
          ".ytp-skip-ad-button",
          ".ytp-ad-skip-button",
          ".ytp-ad-skip-button-modern",
          "button.ytp-skip-ad-button"
        ];

        for (const selector of skipSelectors) {
          const button = document.querySelector(selector);
          if (button) {
            try { button.click(); } catch (_) {}
          }
        }
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

      cleanKnownGlobals();
      removeAdUI();

      const observer = new MutationObserver(() => {
        cleanKnownGlobals();
        removeAdUI();
      });

      const startObserver = () => {
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
