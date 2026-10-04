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

      const cleanTitle = (value) => {
        const text = String(value || "YouTube")
          .replace(/\s*-\s*YouTube\s*$/, "")
          .trim();

        return text || "YouTube";
      };

      const publishMediaCandidate = (payload) => {
        try {
          const bridge =
            window.webkit
              ?.messageHandlers
              ?.mediaCandidate;

          if (!bridge ||
              !payload ||
              typeof payload !== "object") {
            return;
          }

          const streaming =
            payload.streamingData || {};

          const details =
            payload.videoDetails || {};

          const adaptive =
            Array.isArray(
              streaming.adaptiveFormats
            )
              ? streaming.adaptiveFormats
              : [];

          const formats =
            Array.isArray(streaming.formats)
              ? streaming.formats
              : [];

          const audioMP4 = adaptive
            .filter((format) => {
              const mime =
                String(
                  format?.mimeType || ""
                ).toLowerCase();

              return !!format?.url &&
                mime.startsWith(
                  "audio/mp4"
                );
            })
            .sort(
              (left, right) =>
                Number(
                  right?.bitrate || 0
                ) -
                Number(
                  left?.bitrate || 0
                )
            )[0];

          const progressiveMP4 = formats
            .filter((format) => {
              const mime =
                String(
                  format?.mimeType || ""
                ).toLowerCase();

              return !!format?.url &&
                mime.startsWith(
                  "video/mp4"
                ) &&
                !!format?.audioQuality;
            })
            .sort(
              (left, right) =>
                Number(
                  right?.bitrate || 0
                ) -
                Number(
                  left?.bitrate || 0
                )
            )[0];

          let url = "";
          let kind = "";

          if (
            typeof streaming.hlsManifestUrl ===
              "string" &&
            streaming.hlsManifestUrl
          ) {
            url =
              streaming.hlsManifestUrl;

            kind = "hls";
          } else if (
            typeof audioMP4?.url ===
              "string"
          ) {
            url = audioMP4.url;
            kind = "audio-mp4";
          } else if (
            typeof progressiveMP4?.url ===
              "string"
          ) {
            url = progressiveMP4.url;
            kind = "progressive-mp4";
          }

          if (!/^https:\/\//i.test(url)) {
            return;
          }

          const videoID =
            String(
              details.videoId || ""
            );

          const key =
            videoID + "|" + url;

          if (
            window
              .__YOUTUBE_VCD_LAST_MEDIA_CANDIDATE__ ===
            key
          ) {
            return;
          }

          window
            .__YOUTUBE_VCD_LAST_MEDIA_CANDIDATE__ =
            key;

          bridge.postMessage({
            url,
            kind,
            videoID,
            title: cleanTitle(
              details.title ||
              document.title
            )
          });
        } catch (_) {}
      };

      const cleanKnownPlayerGlobal = () => {
        try {
          if (window.ytInitialPlayerResponse) {
            publishMediaCandidate(
              window.ytInitialPlayerResponse
            );

            prunePlayerPayload(
              window.ytInitialPlayerResponse
            );
          }
        } catch (_) {}
      };

      if (
        typeof Response !== "undefined" &&
        Response.prototype?.json
      ) {
        const originalResponseJSON =
          Response.prototype.json;

        Response.prototype.json =
          async function(...args) {
            const result =
              await originalResponseJSON
                .apply(
                  this,
                  args
                );

            try {
              const responseURL =
                String(
                  this.url || ""
                );

              if (
                responseURL.includes(
                  "/youtubei/v1/player"
                )
              ) {
                publishMediaCandidate(
                  result
                );

                prunePlayerPayload(
                  result
                );
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
        if (
          document.getElementById(
            "__youtube_vcd_v2_css__"
          )
        ) {
          return;
        }

        const style =
          document.createElement(
            "style"
          );

        style.id =
          "__youtube_vcd_v2_css__";

        style.textContent =
          HIDE_SELECTORS.join(",") +
          "{display:none!important;visibility:hidden!important;}";

        (
          document.head ||
          document.documentElement
        )?.appendChild(
          style
        );
      };

      const clickSkipButton = () => {
        try {
          const player =
            document.querySelector(
              ".html5-video-player.ad-showing, .ad-showing"
            );

          if (!player) return;

          const button =
            document.querySelector(
              ".ytp-skip-ad-button, .ytp-ad-skip-button, .ytp-ad-skip-button-modern, button.ytp-skip-ad-button"
            );

          if (button) {
            button.click();
          }
        } catch (_) {}
      };

      let maintenanceScheduled = false;

      const maintain = () => {
        if (maintenanceScheduled) {
          return;
        }

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

      const observer =
        new MutationObserver(
          maintain
        );

      const startObserver = () => {
        installCosmeticRules();

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
        startObserver();
      } else {
        document.addEventListener(
          "DOMContentLoaded",
          startObserver,
          { once: true }
        );
      }

      setInterval(() => {
        cleanKnownPlayerGlobal();
        clickSkipButton();
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
