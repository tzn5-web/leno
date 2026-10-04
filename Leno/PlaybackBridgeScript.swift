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
            backgroundArmed: false,
            nativeHandoff: false
          };

      let lastKnownTime = 0;
      let handoffPause = false;

      const videos = () =>
        Array.from(
          document.querySelectorAll(
            "video"
          )
        );

      const videoIDFromLocation = () => {
        try {
          const url =
            new URL(
              location.href
            );

          if (
            url.pathname === "/watch"
          ) {
            const id =
              url.searchParams.get(
                "v"
              ) || "";

            return /^[A-Za-z0-9_-]{11}$/.test(id)
              ? id
              : "";
          }

          const parts =
            url.pathname
              .split("/")
              .filter(Boolean);

          if (
            parts.length >= 2 &&
            [
              "shorts",
              "live",
              "embed"
            ].includes(parts[0]) &&
            /^[A-Za-z0-9_-]{11}$/.test(
              parts[1]
            )
          ) {
            return parts[1];
          }
        } catch (_) {}

        return "";
      };

      const videoScore = (video) => {
        if (!video || video.ended) {
          return -1;
        }

        let score = 0;

        if (!video.paused) {
          score += 1_000_000;
        }

        if (video.readyState >= 2) {
          score += 20_000;
        }

        if (video.currentSrc) {
          score += 10_000;
        }

        if (
          Number.isFinite(
            video.duration
          ) &&
          video.duration > 0
        ) {
          score += 5_000;
        }

        try {
          const mode =
            video.webkitPresentationMode;

          if (
            mode ===
              "picture-in-picture" ||
            mode === "fullscreen"
          ) {
            score += 2_000_000;
          }
        } catch (_) {}

        try {
          const rect =
            video.getBoundingClientRect();

          const area =
            Math.max(
              0,
              rect.width
            ) *
            Math.max(
              0,
              rect.height
            );

          score +=
            Math.min(
              area,
              1_000_000
            ) / 100;
        } catch (_) {}

        return score;
      };

      const currentVideo = () => {
        let best = null;
        let bestScore = -1;

        for (const video of videos()) {
          const score =
            videoScore(
              video
            );

          if (score > bestScore) {
            best = video;
            bestScore = score;
          }
        }

        return best;
      };

      const safePlay = (video) => {
        if (!video) {
          return false;
        }

        try {
          const result =
            video.play();

          if (
            result &&
            typeof result.catch ===
              "function"
          ) {
            result.catch(
              () => {}
            );
          }

          return true;
        } catch (_) {
          return false;
        }
      };

      const pauseVideo = (
        video,
        preserveIntent = false
      ) => {
        if (!video) {
          return false;
        }

        if (preserveIntent) {
          handoffPause = true;
        }

        try {
          video.pause();
          return true;
        } catch (_) {
          return false;
        } finally {
          if (preserveIntent) {
            Promise.resolve().then(
              () => {
                handoffPause = false;
              }
            );
          }
        }
      };

      const postState = () => {
        try {
          const bridge =
            window.webkit
              ?.messageHandlers
              ?.mediaState;

          if (!bridge) return;

          const video =
            currentVideo();

          if (!video) {
            bridge.postMessage({
              title: "YouTube",
              videoID:
                videoIDFromLocation(),
              paused: true,
              hasMedia: false,
              currentTime: 0,
              duration: 0
            });

            return;
          }

          bridge.postMessage({
            title:
              (
                document.title ||
                "YouTube"
              ).replace(
                /\s*-\s*YouTube\s*$/,
                ""
              ),
            videoID:
              videoIDFromLocation(),
            paused:
              !!video.paused,
            hasMedia: true,
            currentTime:
              Number.isFinite(
                video.currentTime
              )
                ? video.currentTime
                : 0,
            duration:
              Number.isFinite(
                video.duration
              )
                ? video.duration
                : 0
          });
        } catch (_) {}
      };

      const resumeWebIfNeeded = () => {
        try {
          if (
            state.nativeHandoff ||
            !state.wantsPlayback
          ) {
            return;
          }

          const video =
            currentVideo();

          if (!video) return;

          if (
            video.paused ||
            video.ended
          ) {
            if (
              Number.isFinite(
                lastKnownTime
              ) &&
              Math.abs(
                (
                  video.currentTime ||
                  0
                ) -
                lastKnownTime
              ) > 2
            ) {
              video.currentTime =
                lastKnownTime;
            }

            safePlay(video);
          }
        } catch (_) {}
      };

      const requestPiP = () => {
        const video =
          currentVideo();

        if (!video) {
          return false;
        }

        try {
          if (
            typeof video
              .webkitSetPresentationMode ===
            "function"
          ) {
            const mode =
              video.webkitPresentationMode;

            video.webkitSetPresentationMode(
              mode ===
                "picture-in-picture"
                ? "inline"
                : "picture-in-picture"
            );

            return true;
          }
        } catch (_) {}

        try {
          if (
            document
              .pictureInPictureElement
          ) {
            document
              .exitPictureInPicture
              ?.();

            return true;
          }

          if (
            document
              .pictureInPictureEnabled &&
            typeof video
              .requestPictureInPicture ===
              "function"
          ) {
            video
              .requestPictureInPicture()
              .catch(
                () => {}
              );

            return true;
          }
        } catch (_) {}

        return false;
      };

      const requestFullscreen = () => {
        const video =
          currentVideo();

        if (!video) {
          return false;
        }

        try {
          if (
            typeof video
              .webkitEnterFullscreen ===
            "function"
          ) {
            video.webkitEnterFullscreen();
            return true;
          }
        } catch (_) {}

        try {
          const player =
            document.querySelector(
              ".html5-video-player"
            ) ||
            video.parentElement ||
            video;

          if (
            typeof player
              .requestFullscreen ===
            "function"
          ) {
            player
              .requestFullscreen()
              .catch(
                () => {}
              );

            return true;
          }

          if (
            typeof player
              .webkitRequestFullscreen ===
            "function"
          ) {
            player
              .webkitRequestFullscreen();

            return true;
          }
        } catch (_) {}

        return false;
      };

      window.__YOUTUBE_VCD_MEDIA_CONTROL__ = {
        armBackground() {
          state.backgroundArmed = true;
          resumeWebIfNeeded();
          postState();
          return true;
        },

        disarmBackground() {
          state.backgroundArmed = false;
          postState();
          return true;
        },

        prepareNativeHandoff() {
          const video =
            currentVideo();

          if (!video) {
            return false;
          }

          state.nativeHandoff = true;
          state.backgroundArmed = false;

          if (
            !video.paused &&
            !video.ended
          ) {
            state.wantsPlayback = true;
          }

          if (
            Number.isFinite(
              video.currentTime
            )
          ) {
            lastKnownTime =
              video.currentTime;
          }

          pauseVideo(
            video,
            true
          );

          postState();
          return true;
        },

        resumeFromNative(
          seconds,
          shouldPlay
        ) {
          const video =
            currentVideo();

          state.nativeHandoff = false;
          state.backgroundArmed = false;
          state.wantsPlayback =
            !!shouldPlay;

          if (!video) {
            postState();
            return false;
          }

          const safeSeconds =
            Number.isFinite(
              Number(seconds)
            )
              ? Math.max(
                  0,
                  Number(seconds)
                )
              : 0;

          try {
            video.currentTime =
              safeSeconds;

            lastKnownTime =
              safeSeconds;
          } catch (_) {}

          if (shouldPlay) {
            safePlay(video);
          } else {
            pauseVideo(
              video,
              false
            );
          }

          postState();
          return true;
        },

        play() {
          state.wantsPlayback = true;

          if (state.nativeHandoff) {
            postState();
            return true;
          }

          const started =
            safePlay(
              currentVideo()
            );

          postState();
          return started;
        },

        pause() {
          state.wantsPlayback = false;

          if (state.nativeHandoff) {
            postState();
            return true;
          }

          const paused =
            pauseVideo(
              currentVideo(),
              false
            );

          postState();
          return paused;
        },

        seekTo(seconds) {
          const video =
            currentVideo();

          if (!video) {
            return false;
          }

          const safeSeconds =
            Number.isFinite(
              Number(seconds)
            )
              ? Math.max(
                  0,
                  Number(seconds)
                )
              : 0;

          const maximum =
            Number.isFinite(
              video.duration
            )
              ? video.duration
              : Number
                  .POSITIVE_INFINITY;

          video.currentTime =
            Math.max(
              0,
              Math.min(
                maximum,
                safeSeconds
              )
            );

          lastKnownTime =
            video.currentTime;

          postState();
          return true;
        },

        seekBy(seconds) {
          const video =
            currentVideo();

          if (!video) {
            return false;
          }

          const delta =
            Number.isFinite(
              Number(seconds)
            )
              ? Number(seconds)
              : 0;

          return this.seekTo(
            (
              Number.isFinite(
                video.currentTime
              )
                ? video.currentTime
                : 0
            ) + delta
          );
        },

        keepAlive() {
          resumeWebIfNeeded();
          return state.wantsPlayback;
        },

        requestPiP,
        requestFullscreen
      };

      document.addEventListener(
        "play",
        (event) => {
          if (
            event.target?.tagName !==
            "VIDEO"
          ) {
            return;
          }

          if (!state.nativeHandoff) {
            state.wantsPlayback = true;
          }

          postState();
        },
        true
      );

      document.addEventListener(
        "pause",
        (event) => {
          if (
            event.target?.tagName !==
            "VIDEO"
          ) {
            return;
          }

          const video =
            event.target;

          if (
            Number.isFinite(
              video.currentTime
            )
          ) {
            lastKnownTime =
              video.currentTime;
          }

          if (
            !handoffPause &&
            !state.nativeHandoff
          ) {
            if (
              document.hidden &&
              state.backgroundArmed &&
              state.wantsPlayback
            ) {
              Promise.resolve()
                .then(
                  resumeWebIfNeeded
                );
            } else {
              state.wantsPlayback =
                false;
            }
          }

          postState();
        },
        true
      );

      document.addEventListener(
        "timeupdate",
        (event) => {
          if (
            event.target?.tagName !==
            "VIDEO"
          ) {
            return;
          }

          const video =
            event.target;

          if (
            Number.isFinite(
              video.currentTime
            )
          ) {
            lastKnownTime =
              video.currentTime;
          }

          const now = Date.now();

          if (
            !window
              .__YOUTUBE_VCD_LAST_MEDIA_REPORT__ ||
            now -
              window
                .__YOUTUBE_VCD_LAST_MEDIA_REPORT__ >
              1000
          ) {
            window
              .__YOUTUBE_VCD_LAST_MEDIA_REPORT__ =
              now;

            postState();
          }
        },
        true
      );

      [
        "playing",
        "loadedmetadata",
        "durationchange",
        "emptied"
      ].forEach(
        (eventName) => {
          document.addEventListener(
            eventName,
            postState,
            true
          );
        }
      );

      document.addEventListener(
        "visibilitychange",
        () => {
          if (
            document.hidden &&
            state.backgroundArmed &&
            state.wantsPlayback &&
            !state.nativeHandoff
          ) {
            Promise.resolve()
              .then(
                resumeWebIfNeeded
              );
          }
        },
        true
      );

      const makeButton = (
        id,
        title,
        symbol,
        action
      ) => {
        let button =
          document.getElementById(
            id
          );

        if (button) {
          return button;
        }

        button =
          document.createElement(
            "button"
          );

        button.id = id;
        button.type = "button";
        button.title = title;
        button.textContent =
          symbol;

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

        button.addEventListener(
          "click",
          (event) => {
            event.preventDefault();
            event.stopPropagation();
            event
              .stopImmediatePropagation();

            action();
          },
          true
        );

        return button;
      };

      const ensureControls = () => {
        const video =
          currentVideo();

        let root =
          document.getElementById(
            "__youtube_vcd_media_controls__"
          );

        if (!video) {
          if (root) {
            root.style.display =
              "none";
          }

          return;
        }

        if (!root) {
          root =
            document.createElement(
              "div"
            );

          root.id =
            "__youtube_vcd_media_controls__";

          root.style.cssText = [
            "position:fixed",
            "right:12px",
            "top:max(72px,calc(env(safe-area-inset-top) + 54px))",
            "z-index:2147483647",
            "display:flex",
            "gap:8px",
            "pointer-events:auto"
          ].join(";");

          root.appendChild(
            makeButton(
              "__youtube_vcd_pip__",
              "Picture in Picture",
              "◱",
              requestPiP
            )
          );

          root.appendChild(
            makeButton(
              "__youtube_vcd_fullscreen__",
              "Fullscreen",
              "⛶",
              requestFullscreen
            )
          );

          (
            document.body ||
            document.documentElement
          )?.appendChild(
            root
          );
        }

        root.style.display =
          "flex";
      };

      const observer =
        new MutationObserver(
          () => {
            ensureControls();
            postState();
          }
        );

      const begin = () => {
        if (document.documentElement) {
          observer.observe(
            document.documentElement,
            {
              childList: true,
              subtree: true
            }
          );
        }

        ensureControls();
        postState();
      };

      if (document.documentElement) {
        begin();
      } else {
        document.addEventListener(
          "DOMContentLoaded",
          begin,
          { once: true }
        );
      }

      setInterval(() => {
        ensureControls();

        if (
          document.hidden &&
          state.backgroundArmed &&
          state.wantsPlayback &&
          !state.nativeHandoff
        ) {
          resumeWebIfNeeded();
        }

        postState();
      }, 1500);
    })();
    """#

    static let armBackgroundCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      return control
        ? control.armBackground()
        : false;
    })();
    """#

    static let disarmBackgroundCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      return control
        ? control.disarmBackground()
        : false;
    })();
    """#

    static let prepareNativeHandoffCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      return control
        ? control.prepareNativeHandoff()
        : false;
    })();
    """#

    static let userPlayCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      return control
        ? control.play()
        : false;
    })();
    """#

    static let userPauseCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      return control
        ? control.pause()
        : false;
    })();
    """#

    static let keepAliveCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      return control
        ? control.keepAlive()
        : false;
    })();
    """#

    static let requestPiPCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      return control
        ? control.requestPiP()
        : false;
    })();
    """#

    static let requestFullscreenCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      return control
        ? control.requestFullscreen()
        : false;
    })();
    """#

    static func resumeFromNativeCall(
        time: Double,
        shouldPlay: Bool
    ) -> String {
        let safeTime = max(0, time)
        let playLiteral =
            shouldPlay ? "true" : "false"

        return """
        (() => {
          const control =
            window.__YOUTUBE_VCD_MEDIA_CONTROL__;

          return control
            ? control.resumeFromNative(
                \(safeTime),
                \(playLiteral)
              )
            : false;
        })();
        """
    }

    static func seekByCall(
        seconds: Double
    ) -> String {
        """
        (() => {
          const control =
            window.__YOUTUBE_VCD_MEDIA_CONTROL__;

          return control
            ? control.seekBy(\(seconds))
            : false;
        })();
        """
    }

    static func seekToCall(
        seconds: Double
    ) -> String {
        let safe = max(0, seconds)

        return """
        (() => {
          const control =
            window.__YOUTUBE_VCD_MEDIA_CONTROL__;

          return control
            ? control.seekTo(\(safe))
            : false;
        })();
        """
    }
}
