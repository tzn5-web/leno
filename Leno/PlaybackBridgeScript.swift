import Foundation

enum PlaybackBridgeScript {
    static let source = #"""
    (() => {
      "use strict";

      if (window.__YOUTUBE_VCD_PLAYBACK_BRIDGE__) return;
      window.__YOUTUBE_VCD_PLAYBACK_BRIDGE__ = true;

      const state =
        window.__YOUTUBE_VCD_MEDIA_STATE__ =
          window.__YOUTUBE_VCD_MEDIA_STATE__ || {
            wantsPlayback: false,
            backgroundArmed: false
          };

      let lastKnownTime = 0;

      const currentVideo = () => document.querySelector("video");

      const postState = () => {
        try {
          const bridge = window.webkit?.messageHandlers?.mediaState;
          if (!bridge) return;

          const video = currentVideo();

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

      const resumeIfNeeded = () => {
        try {
          const video = currentVideo();
          if (!video || !state.wantsPlayback) return;

          if (video.paused || video.ended) {
            if (Number.isFinite(lastKnownTime) &&
                Math.abs((video.currentTime || 0) - lastKnownTime) > 2) {
              video.currentTime = lastKnownTime;
            }

            video.play().catch(() => {});
          }
        } catch (_) {}
      };

      window.__YOUTUBE_VCD_MEDIA_CONTROL__ = {
        armBackground() {
          state.backgroundArmed = true;
          state.wantsPlayback = true;
          resumeIfNeeded();
          return true;
        },

        disarmBackground() {
          state.backgroundArmed = false;
          return true;
        },

        play() {
          state.wantsPlayback = true;

          const video = currentVideo();
          if (!video) return false;

          try {
            video.play().catch(() => {});
            return true;
          } catch (_) {
            return false;
          }
        },

        pause() {
          state.wantsPlayback = false;

          const video = currentVideo();
          if (!video) return false;

          try {
            video.pause();
            return true;
          } catch (_) {
            return false;
          }
        },

        keepAlive() {
          state.wantsPlayback = true;
          resumeIfNeeded();
          return true;
        }
      };

      document.addEventListener("play", (event) => {
        if (event.target?.tagName !== "VIDEO") return;
        state.wantsPlayback = true;
        postState();
      }, true);

      document.addEventListener("pause", (event) => {
        if (event.target?.tagName !== "VIDEO") return;

        const video = event.target;
        if (Number.isFinite(video.currentTime)) {
          lastKnownTime = video.currentTime;
        }

        if ((document.hidden || state.backgroundArmed) && state.wantsPlayback) {
          event.stopImmediatePropagation();
          Promise.resolve().then(resumeIfNeeded);
        } else {
          state.wantsPlayback = false;
        }

        postState();
      }, true);

      document.addEventListener("timeupdate", (event) => {
        if (event.target?.tagName !== "VIDEO") return;

        const video = event.target;
        if (Number.isFinite(video.currentTime)) {
          lastKnownTime = video.currentTime;
        }

        const now = Date.now();
        if (!window.__YOUTUBE_VCD_LAST_MEDIA_REPORT__ ||
            now - window.__YOUTUBE_VCD_LAST_MEDIA_REPORT__ > 1000) {
          window.__YOUTUBE_VCD_LAST_MEDIA_REPORT__ = now;
          postState();
        }
      }, true);

      document.addEventListener("loadedmetadata", postState, true);
      document.addEventListener("durationchange", postState, true);
      document.addEventListener("emptied", postState, true);

      document.addEventListener("visibilitychange", (event) => {
        if ((document.hidden || state.backgroundArmed) && state.wantsPlayback) {
          event.stopImmediatePropagation();
          Promise.resolve().then(resumeIfNeeded);
          setTimeout(resumeIfNeeded, 80);
          setTimeout(resumeIfNeeded, 300);
        }
      }, true);

      const makeButton = (id, title, symbol, action) => {
        let button = document.getElementById(id);
        if (button) return button;

        button = document.createElement("button");
        button.id = id;
        button.type = "button";
        button.title = title;
        button.textContent = symbol;
        button.style.cssText = [
          "width:44px",
          "height:44px",
          "border:0",
          "border-radius:22px",
          "background:rgba(18,18,18,.78)",
          "color:white",
          "font:600 20px -apple-system,BlinkMacSystemFont,sans-serif",
          "display:flex",
          "align-items:center",
          "justify-content:center",
          "box-shadow:0 5px 18px rgba(0,0,0,.28)",
          "-webkit-backdrop-filter:blur(16px)",
          "backdrop-filter:blur(16px)",
          "touch-action:manipulation"
        ].join(";");

        button.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
          event.stopImmediatePropagation();
          action();
        }, true);

        return button;
      };

      const requestPiP = () => {
        const video = currentVideo();
        if (!video) return false;

        try {
          if (typeof video.webkitSetPresentationMode === "function") {
            const mode = video.webkitPresentationMode;
            video.webkitSetPresentationMode(
              mode === "picture-in-picture" ? "inline" : "picture-in-picture"
            );
            return true;
          }
        } catch (_) {}

        try {
          if (document.pictureInPictureElement) {
            document.exitPictureInPicture?.();
            return true;
          }

          if (document.pictureInPictureEnabled &&
              typeof video.requestPictureInPicture === "function") {
            video.requestPictureInPicture().catch(() => {});
            return true;
          }
        } catch (_) {}

        return false;
      };

      const requestFullscreen = () => {
        const video = currentVideo();
        if (!video) return false;

        try {
          if (typeof video.webkitEnterFullscreen === "function") {
            video.webkitEnterFullscreen();
            return true;
          }
        } catch (_) {}

        try {
          const player =
            document.querySelector(".html5-video-player") ||
            video.parentElement ||
            video;

          if (typeof player.requestFullscreen === "function") {
            player.requestFullscreen().catch(() => {});
            return true;
          }

          if (typeof player.webkitRequestFullscreen === "function") {
            player.webkitRequestFullscreen();
            return true;
          }
        } catch (_) {}

        return false;
      };

      const ensureControls = () => {
        const video = currentVideo();
        let root = document.getElementById("__youtube_vcd_media_controls__");

        if (!video) {
          if (root) root.style.display = "none";
          return;
        }

        if (!root) {
          root = document.createElement("div");
          root.id = "__youtube_vcd_media_controls__";
          root.style.cssText = [
            "position:fixed",
            "right:12px",
            "top:max(72px,calc(env(safe-area-inset-top) + 54px))",
            "z-index:2147483647",
            "display:flex",
            "gap:8px",
            "pointer-events:auto"
          ].join(";");

          const pip = makeButton(
            "__youtube_vcd_pip__",
            "Picture in Picture",
            "◱",
            requestPiP
          );

          const fullscreen = makeButton(
            "__youtube_vcd_fullscreen__",
            "Fullscreen",
            "⛶",
            requestFullscreen
          );

          root.appendChild(pip);
          root.appendChild(fullscreen);
          (document.body || document.documentElement)?.appendChild(root);
        }

        root.style.display = "flex";
      };

      const observer = new MutationObserver(() => {
        ensureControls();
        postState();
      });

      const begin = () => {
        if (document.documentElement) {
          observer.observe(document.documentElement, {
            childList: true,
            subtree: true
          });
        }

        ensureControls();
        postState();
      };

      if (document.documentElement) begin();
      else document.addEventListener("DOMContentLoaded", begin, { once: true });

      setInterval(() => {
        ensureControls();
        if ((document.hidden || state.backgroundArmed) && state.wantsPlayback) {
          resumeIfNeeded();
        }
        postState();
      }, 1200);
    })();
    """#

    static let armBackgroundCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      if (!control) return false;
      return control.armBackground();
    })();
    """#

    static let disarmBackgroundCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      if (!control) return false;
      return control.disarmBackground();
    })();
    """#

    static let userPlayCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      if (!control) return false;
      return control.play();
    })();
    """#

    static let userPauseCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      if (!control) return false;
      return control.pause();
    })();
    """#

    static let keepAliveCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      if (!control) return false;
      return control.keepAlive();
    })();
    """#

    static let requestPiPCall = #"""
    (() => {
      const video = document.querySelector("video");
      if (!video) return false;

      try {
        if (typeof video.webkitSetPresentationMode === "function") {
          const mode = video.webkitPresentationMode;
          video.webkitSetPresentationMode(
            mode === "picture-in-picture" ? "inline" : "picture-in-picture"
          );
          return true;
        }
      } catch (_) {}

      try {
        if (document.pictureInPictureElement) {
          document.exitPictureInPicture?.();
          return true;
        }

        if (document.pictureInPictureEnabled &&
            typeof video.requestPictureInPicture === "function") {
          video.requestPictureInPicture().catch(() => {});
          return true;
        }
      } catch (_) {}

      return false;
    })();
    """#

    static let requestFullscreenCall = #"""
    (() => {
      const video = document.querySelector("video");
      if (!video) return false;

      try {
        if (typeof video.webkitEnterFullscreen === "function") {
          video.webkitEnterFullscreen();
          return true;
        }
      } catch (_) {}

      try {
        const player =
          document.querySelector(".html5-video-player") ||
          video.parentElement ||
          video;

        if (typeof player.requestFullscreen === "function") {
          player.requestFullscreen().catch(() => {});
          return true;
        }
      } catch (_) {}

      return false;
    })();
    """#
}
