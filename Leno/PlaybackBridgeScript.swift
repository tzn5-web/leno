import Foundation

enum PlaybackBridgeScript {
    static let source = #"""
    (() => {
      "use strict";

      if (window.__YOUTUBE_VCD_PLAYBACK_BRIDGE_V4__) return;
      window.__YOUTUBE_VCD_PLAYBACK_BRIDGE_V4__ = true;

      const nativeDocumentAddEventListener =
        document.addEventListener.bind(document);

      const nativeWindowAddEventListener =
        window.addEventListener.bind(window);

      const nativeSetTimeout =
        window.setTimeout.bind(window);

      const nativeClearTimeout =
        window.clearTimeout.bind(window);

      const nativePlay =
        HTMLMediaElement.prototype.play;

      const nativePause =
        HTMLMediaElement.prototype.pause;

      const inheritedDescriptor = (object, property) => {
        let current = object;

        while (current) {
          const descriptor =
            Object.getOwnPropertyDescriptor(
              current,
              property
            );

          if (descriptor) return descriptor;

          current =
            Object.getPrototypeOf(current);
        }

        return null;
      };

      const nativeHiddenDescriptor =
        inheritedDescriptor(
          document,
          "hidden"
        );

      const nativeWebKitHiddenDescriptor =
        inheritedDescriptor(
          document,
          "webkitHidden"
        );

      const nativeVisibilityDescriptor =
        inheritedDescriptor(
          document,
          "visibilityState"
        );

      const nativeWebKitVisibilityDescriptor =
        inheritedDescriptor(
          document,
          "webkitVisibilityState"
        );

      const readNative = (
        descriptor,
        fallback
      ) => {
        try {
          return descriptor?.get
            ? descriptor.get.call(document)
            : fallback;
        } catch (_) {
          return fallback;
        }
      };

      const isReallyHidden = () => {
        const hidden =
          readNative(
            nativeHiddenDescriptor,
            null
          );

        if (typeof hidden === "boolean") {
          return hidden;
        }

        const webkitHidden =
          readNative(
            nativeWebKitHiddenDescriptor,
            null
          );

        if (
          typeof webkitHidden ===
          "boolean"
        ) {
          return webkitHidden;
        }

        const visibility =
          readNative(
            nativeVisibilityDescriptor,
            "visible"
          );

        return visibility === "hidden";
      };

      const spoofDocumentProperty = (
        property,
        value
      ) => {
        const descriptor =
          inheritedDescriptor(
            document,
            property
          );

        const replacement = {
          configurable:
            descriptor?.configurable ??
            true,
          enumerable:
            descriptor?.enumerable ??
            true,
          get: () => value
        };

        if (descriptor?.set) {
          replacement.set = function(next) {
            return descriptor.set.call(
              this,
              next
            );
          };
        }

        try {
          Object.defineProperty(
            Document.prototype,
            property,
            replacement
          );

          return;
        } catch (_) {}

        try {
          Object.defineProperty(
            document,
            property,
            {
              configurable: true,
              enumerable:
                replacement.enumerable,
              get: () => value
            }
          );
        } catch (_) {}
      };

      // YouTube should continue believing the page is visible.
      // Our code still reads the real values through the saved descriptors.
      spoofDocumentProperty(
        "hidden",
        false
      );

      spoofDocumentProperty(
        "webkitHidden",
        false
      );

      spoofDocumentProperty(
        "visibilityState",
        "visible"
      );

      spoofDocumentProperty(
        "webkitVisibilityState",
        "visible"
      );

      const state = {
        video: null,
        wantsPlayback: false,
        userPauseUntil: 0,
        recoveryTimers:
          new Set(),
        lastKnownTime: 0,
        lastReportAt: 0,
        lastMediaHandlerInstallAt: 0,
        actionStamp:
          new Map()
      };

      const cleanTitle = () => {
        const value =
          String(
            document.title ||
            "YouTube"
          )
          .replace(
            /\s*-\s*YouTube\s*$/,
            ""
          )
          .trim();

        return value || "YouTube";
      };

      const currentVideoID = () => {
        try {
          const url =
            new URL(location.href);

          if (
            url.pathname === "/watch"
          ) {
            const value =
              url.searchParams.get("v") ||
              "";

            return /^[A-Za-z0-9_-]{11}$/.test(
              value
            )
              ? value
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

      const isPreviewVideo = (video) => {
        try {
          return !!video.closest(
            "#inline-preview-player, #inline-player, ytm-reel-video-renderer"
          );
        } catch (_) {
          return false;
        }
      };

      const findWatchVideo = () => {
        const videos =
          Array.from(
            document.querySelectorAll(
              "video"
            )
          )
          .filter(
            (video) =>
              video instanceof
                HTMLVideoElement &&
              video.isConnected &&
              !isPreviewVideo(video)
          );

        if (!videos.length) {
          return null;
        }

        const main =
          videos.find(
            (video) =>
              video.classList.contains(
                "html5-main-video"
              )
          );

        if (main) return main;

        const inPlayer =
          videos.find(
            (video) =>
              !!video.closest(
                "#movie_player, .html5-video-player, #player-container, #player-container-id, ytm-player"
              )
          );

        if (inPlayer) return inPlayer;

        const playing =
          videos.find(
            (video) =>
              !video.paused &&
              !video.ended &&
              video.readyState > 0
          );

        if (playing) return playing;

        return (
          videos.find(
            (video) =>
              !video.ended &&
              video.readyState > 0
          ) ||
          videos[0]
        );
      };

      const enforceInlinePlayback = (
        video
      ) => {
        if (
          !(video instanceof
            HTMLVideoElement)
        ) {
          return;
        }

        try {
          video.setAttribute(
            "playsinline",
            ""
          );

          video.setAttribute(
            "webkit-playsinline",
            ""
          );

          video.setAttribute(
            "x-webkit-airplay",
            "allow"
          );

          video.playsInline = true;

          if (
            "webkitPlaysInline" in
            video
          ) {
            video.webkitPlaysInline =
              true;
          }

          video.removeAttribute(
            "disablepictureinpicture"
          );

          if (
            "disablePictureInPicture" in
            video
          ) {
            video.disablePictureInPicture =
              false;
          }
        } catch (_) {}
      };

      const configureWebAudioSession =
        () => {
          try {
            if (
              navigator.audioSession
            ) {
              navigator.audioSession.type =
                "playback";
            }
          } catch (_) {}
        };

      const clearRecoveryTimers = () => {
        for (
          const timer of
          state.recoveryTimers
        ) {
          nativeClearTimeout(timer);
        }

        state.recoveryTimers.clear();
      };

      const safePlay = (
        video = state.video
      ) => {
        if (
          !video ||
          video.ended ||
          video.error
        ) {
          return false;
        }

        enforceInlinePlayback(video);
        configureWebAudioSession();

        try {
          const result =
            nativePlay.call(video);

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

      const postState = (
        force = false
      ) => {
        try {
          const now = Date.now();

          if (
            !force &&
            now -
              state.lastReportAt <
              500
          ) {
            return;
          }

          state.lastReportAt = now;

          const bridge =
            window.webkit
              ?.messageHandlers
              ?.mediaState;

          if (!bridge) return;

          const video =
            state.video ||
            findWatchVideo();

          if (!video) {
            bridge.postMessage({
              title: cleanTitle(),
              videoID:
                currentVideoID(),
              paused: true,
              hasMedia: false,
              wantsPlayback:
                state.wantsPlayback,
              realHidden:
                isReallyHidden(),
              presentationMode:
                "none",
              currentTime: 0,
              duration: 0
            });

            return;
          }

          let presentationMode =
            "inline";

          try {
            presentationMode =
              video.webkitPresentationMode ||
              "inline";
          } catch (_) {}

          bridge.postMessage({
            title: cleanTitle(),
            videoID:
              currentVideoID(),
            paused: !!video.paused,
            hasMedia: true,
            wantsPlayback:
              state.wantsPlayback,
            realHidden:
              isReallyHidden(),
            presentationMode,
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

      const updateMediaSession = () => {
        try {
          if (
            !navigator.mediaSession
          ) {
            return;
          }

          const video =
            state.video ||
            findWatchVideo();

          navigator.mediaSession
            .playbackState =
            video &&
            !video.paused &&
            !video.ended
              ? "playing"
              : "paused";

          if (
            video &&
            Number.isFinite(
              video.duration
            ) &&
            video.duration > 0 &&
            Number.isFinite(
              video.currentTime
            )
          ) {
            try {
              navigator.mediaSession
                .setPositionState({
                  duration:
                    video.duration,
                  playbackRate:
                    Number.isFinite(
                      video.playbackRate
                    ) &&
                    video.playbackRate > 0
                      ? video.playbackRate
                      : 1,
                  position:
                    Math.max(
                      0,
                      Math.min(
                        video.duration,
                        video.currentTime
                      )
                    )
                });
            } catch (_) {}
          }
        } catch (_) {}
      };

      const actionAllowed = (
        key,
        minimumGap = 220
      ) => {
        const now = Date.now();

        const previous =
          state.actionStamp.get(key) ||
          0;

        if (
          now - previous <
          minimumGap
        ) {
          return false;
        }

        state.actionStamp.set(
          key,
          now
        );

        return true;
      };

      const recoverPlayback = (
        video = state.video
      ) => {
        if (
          !video ||
          !state.wantsPlayback ||
          video.ended ||
          Date.now() <=
            state.userPauseUntil
        ) {
          return;
        }

        safePlay(video);
        clearRecoveryTimers();

        for (
          const delay of
          [80, 250, 750, 1500]
        ) {
          const timer =
            nativeSetTimeout(
              () => {
                state.recoveryTimers
                  .delete(timer);

                if (
                  state.wantsPlayback &&
                  isReallyHidden() &&
                  Date.now() >
                    state.userPauseUntil &&
                  !video.ended
                ) {
                  safePlay(video);
                }
              },
              delay
            );

          state.recoveryTimers
            .add(timer);
        }
      };

      const mediaPlay = () => {
        const video =
          state.video ||
          findWatchVideo();

        if (!video) return false;

        attachVideo(video);

        state.wantsPlayback = true;
        state.userPauseUntil = 0;

        const result =
          safePlay(video);

        installMediaSessionHandlers(
          true
        );

        updateMediaSession();
        postState(true);

        return result;
      };

      const mediaPause = () => {
        const video =
          state.video ||
          findWatchVideo();

        if (!video) return false;

        attachVideo(video);

        state.wantsPlayback = false;
        state.userPauseUntil =
          Date.now() + 5000;

        clearRecoveryTimers();

        try {
          nativePause.call(video);
        } catch (_) {
          return false;
        }

        updateMediaSession();
        postState(true);

        return true;
      };

      const seekTo = (seconds) => {
        const video =
          state.video ||
          findWatchVideo();

        if (!video) return false;

        const numeric =
          Number(seconds);

        if (!Number.isFinite(numeric)) {
          return false;
        }

        const maximum =
          Number.isFinite(
            video.duration
          )
            ? video.duration
            : Number.POSITIVE_INFINITY;

        try {
          video.currentTime =
            Math.max(
              0,
              Math.min(
                maximum,
                numeric
              )
            );

          state.lastKnownTime =
            video.currentTime;

          updateMediaSession();
          postState(true);

          return true;
        } catch (_) {
          return false;
        }
      };

      const seekBy = (seconds) => {
        const video =
          state.video ||
          findWatchVideo();

        if (!video) return false;

        if (
          !actionAllowed(
            "seek",
            260
          )
        ) {
          return true;
        }

        const current =
          Number.isFinite(
            video.currentTime
          )
            ? video.currentTime
            : 0;

        return seekTo(
          current +
          Number(seconds || 0)
        );
      };

      const installMediaSessionHandlers =
        (force = false) => {
          try {
            if (
              !navigator.mediaSession
            ) {
              return;
            }

            const now = Date.now();

            if (
              !force &&
              now -
                state
                  .lastMediaHandlerInstallAt <
                1200
            ) {
              return;
            }

            state.lastMediaHandlerInstallAt =
              now;

            navigator.mediaSession
              .setActionHandler(
                "play",
                () => {
                  if (
                    actionAllowed(
                      "play",
                      180
                    )
                  ) {
                    mediaPlay();
                  }
                }
              );

            navigator.mediaSession
              .setActionHandler(
                "pause",
                () => {
                  if (
                    actionAllowed(
                      "pause",
                      180
                    )
                  ) {
                    mediaPause();
                  }
                }
              );

            navigator.mediaSession
              .setActionHandler(
                "seekbackward",
                (details) => {
                  seekBy(
                    -(
                      details
                        ?.seekOffset ||
                      15
                    )
                  );
                }
              );

            navigator.mediaSession
              .setActionHandler(
                "seekforward",
                (details) => {
                  seekBy(
                    details?.seekOffset ||
                    15
                  );
                }
              );

            navigator.mediaSession
              .setActionHandler(
                "seekto",
                (details) => {
                  if (
                    details?.seekTime !=
                    null
                  ) {
                    seekTo(
                      details.seekTime
                    );
                  }
                }
              );

            updateMediaSession();
          } catch (_) {}
        };

      const onPlay = () => {
        state.wantsPlayback = true;
        state.userPauseUntil = 0;

        configureWebAudioSession();
        installMediaSessionHandlers(
          true
        );

        updateMediaSession();
        postState(true);
      };

      const onPause = () => {
        const video =
          state.video;

        if (!video) return;

        if (
          Number.isFinite(
            video.currentTime
          )
        ) {
          state.lastKnownTime =
            video.currentTime;
        }

        if (
          Date.now() <=
            state.userPauseUntil ||
          !state.wantsPlayback
        ) {
          state.wantsPlayback = false;
          clearRecoveryTimers();
        } else if (
          isReallyHidden() &&
          !video.ended
        ) {
          recoverPlayback(video);
        } else {
          // WebKit may emit pause immediately before the
          // real visibility state flips to hidden.
          const waitForHidden = () => {
            if (
              isReallyHidden() &&
              state.wantsPlayback &&
              Date.now() >
                state.userPauseUntil &&
              !video.ended
            ) {
              recoverPlayback(video);
            } else if (
              !isReallyHidden()
            ) {
              state.wantsPlayback =
                false;

              clearRecoveryTimers();
            }

            postState(true);
          };

          nativeDocumentAddEventListener(
            "visibilitychange",
            waitForHidden,
            { once: true }
          );

          nativeSetTimeout(
            () => {
              if (
                !isReallyHidden() &&
                video.paused
              ) {
                state.wantsPlayback =
                  false;

                clearRecoveryTimers();
              }
            },
            1800
          );
        }

        updateMediaSession();
        postState(true);
      };

      const onPresentationModeChanged =
        (event) => {
          // YouTube listens for this event and may pause when PiP starts.
          // Keep the system presentation transition, but do not let the
          // site consume the transition as a playback-stop signal.
          event.stopPropagation();

          const video =
            event.currentTarget;

          if (
            video instanceof
              HTMLVideoElement
          ) {
            enforceInlinePlayback(video);

            if (
              state.wantsPlayback &&
              video.paused &&
              !video.ended
            ) {
              safePlay(video);

              nativeSetTimeout(
                () => {
                  if (
                    state.wantsPlayback &&
                    video.paused &&
                    !video.ended
                  ) {
                    safePlay(video);
                  }
                },
                120
              );
            }
          }

          updateMediaSession();
          postState(true);
        };

      const lifecycleEvents = [
        "loadstart",
        "loadeddata",
        "canplay",
        "canplaythrough",
        "emptied",
        "webkitbeginfullscreen",
        "webkitendfullscreen",
        "webkitcurrentplaybacktargetiswirelesschanged"
      ];

      const detachVideo = (video) => {
        if (!video) return;

        video.removeEventListener(
          "play",
          onPlay,
          true
        );

        video.removeEventListener(
          "playing",
          onPlay,
          true
        );

        video.removeEventListener(
          "pause",
          onPause,
          true
        );

        video.removeEventListener(
          "ended",
          onPause,
          true
        );

        video.removeEventListener(
          "timeupdate",
          onTimeUpdate,
          true
        );

        video.removeEventListener(
          "loadedmetadata",
          onMetadata,
          true
        );

        video.removeEventListener(
          "webkitpresentationmodechanged",
          onPresentationModeChanged,
          true
        );

        for (
          const eventName of
          lifecycleEvents
        ) {
          video.removeEventListener(
            eventName,
            onInlineLifecycle,
            true
          );
        }
      };

      const onTimeUpdate = () => {
        const video =
          state.video;

        if (!video) return;

        if (
          Number.isFinite(
            video.currentTime
          )
        ) {
          state.lastKnownTime =
            video.currentTime;
        }

        updateMediaSession();
        postState(false);
      };

      const onMetadata = () => {
        enforceInlinePlayback(
          state.video
        );

        installMediaSessionHandlers(
          true
        );

        updateMediaSession();
        postState(true);
      };

      const onInlineLifecycle = (
        event
      ) => {
        const video =
          event.currentTarget;

        if (
          video instanceof
            HTMLVideoElement
        ) {
          enforceInlinePlayback(video);
        }

        updateMediaSession();
        postState(false);
      };

      function attachVideo(video) {
        if (
          !(video instanceof
            HTMLVideoElement)
        ) {
          return null;
        }

        if (state.video === video) {
          enforceInlinePlayback(video);
          return video;
        }

        detachVideo(state.video);

        state.video = video;

        try {
          video.setAttribute(
            "data-youtube-vcd-attached",
            "true"
          );
        } catch (_) {}

        enforceInlinePlayback(video);

        state.wantsPlayback =
          !video.paused &&
          !video.ended;

        if (
          Number.isFinite(
            video.currentTime
          )
        ) {
          state.lastKnownTime =
            video.currentTime;
        }

        video.addEventListener(
          "play",
          onPlay,
          true
        );

        video.addEventListener(
          "playing",
          onPlay,
          true
        );

        video.addEventListener(
          "pause",
          onPause,
          true
        );

        video.addEventListener(
          "ended",
          onPause,
          true
        );

        video.addEventListener(
          "timeupdate",
          onTimeUpdate,
          true
        );

        video.addEventListener(
          "loadedmetadata",
          onMetadata,
          true
        );

        video.addEventListener(
          "webkitpresentationmodechanged",
          onPresentationModeChanged,
          true
        );

        for (
          const eventName of
          lifecycleEvents
        ) {
          video.addEventListener(
            eventName,
            onInlineLifecycle,
            true
          );
        }

        configureWebAudioSession();

        if (
          !video.paused &&
          !video.ended
        ) {
          installMediaSessionHandlers(
            true
          );
        }

        postState(true);

        return video;
      }

      // A JS call to pause on the attached watch video is considered an
      // explicit pause. WebKit's own internal background pause does not pass
      // through this JavaScript prototype method.
      HTMLMediaElement.prototype.pause =
        function(...args) {
          if (
            this === state.video ||
            this.classList
              ?.contains(
                "html5-main-video"
              )
          ) {
            state.wantsPlayback =
              false;

            state.userPauseUntil =
              Date.now() + 5000;

            clearRecoveryTimers();
          }

          return nativePause.apply(
            this,
            args
          );
        };

      HTMLMediaElement.prototype.play =
        function(...args) {
          if (
            this instanceof
              HTMLVideoElement
          ) {
            const active =
              findWatchVideo();

            if (
              this === active ||
              this.classList
                ?.contains(
                  "html5-main-video"
                )
            ) {
              attachVideo(this);

              state.wantsPlayback =
                true;

              state.userPauseUntil =
                0;

              enforceInlinePlayback(
                this
              );

              configureWebAudioSession();
            }
          }

          return nativePlay.apply(
            this,
            args
          );
        };

      const prepareForBackground =
        () => {
          const video =
            state.video ||
            findWatchVideo();

          if (!video) return false;

          attachVideo(video);
          configureWebAudioSession();
          installMediaSessionHandlers(
            true
          );

          if (
            !video.paused &&
            !video.ended &&
            Date.now() >
              state.userPauseUntil
          ) {
            state.wantsPlayback =
              true;
          }

          if (
            state.wantsPlayback &&
            Date.now() >
              state.userPauseUntil
          ) {
            recoverPlayback(video);
          }

          updateMediaSession();
          postState(true);

          return true;
        };

      const resumeForeground = () => {
        const video =
          state.video ||
          findWatchVideo();

        if (!video) return false;

        attachVideo(video);
        configureWebAudioSession();
        installMediaSessionHandlers(
          true
        );

        clearRecoveryTimers();

        if (
          state.wantsPlayback &&
          video.paused &&
          !video.ended &&
          Date.now() >
            state.userPauseUntil
        ) {
          safePlay(video);
        }

        updateMediaSession();
        postState(true);

        return true;
      };

      const requestPiP = () => {
        const video =
          state.video ||
          findWatchVideo();

        if (!video) return false;

        attachVideo(video);

        const shouldResume =
          state.wantsPlayback ||
          (
            !video.paused &&
            !video.ended
          );

        if (
          video.paused &&
          !video.ended
        ) {
          state.wantsPlayback =
            true;

          state.userPauseUntil = 0;

          safePlay(video);
        }

        try {
          video.removeAttribute(
            "disablepictureinpicture"
          );

          if (
            "disablePictureInPicture" in
            video
          ) {
            video.disablePictureInPicture =
              false;
          }
        } catch (_) {}

        let requested = false;

        try {
          if (
            typeof video
              .webkitSetPresentationMode ===
              "function"
          ) {
            const current =
              video.webkitPresentationMode;

            if (
              current ===
              "picture-in-picture"
            ) {
              video.webkitSetPresentationMode(
                "inline"
              );
            } else {
              const supports =
                typeof video
                  .webkitSupportsPresentationMode !==
                  "function" ||
                video.webkitSupportsPresentationMode(
                  "picture-in-picture"
                );

              if (supports) {
                video.webkitSetPresentationMode(
                  "picture-in-picture"
                );

                requested = true;
              }
            }
          }
        } catch (_) {}

        if (!requested) {
          try {
            if (
              document
                .pictureInPictureElement ===
              video
            ) {
              document
                .exitPictureInPicture
                ?.();

              requested = true;
            } else if (
              typeof video
                .requestPictureInPicture ===
                "function"
            ) {
              video
                .requestPictureInPicture()
                .catch(
                  () => {}
                );

              requested = true;
            }
          } catch (_) {}
        }

        if (shouldResume) {
          state.wantsPlayback = true;
          state.userPauseUntil = 0;

          for (
            const delay of
            [0, 120, 350]
          ) {
            nativeSetTimeout(
              () => {
                if (
                  state.wantsPlayback &&
                  video.paused &&
                  !video.ended
                ) {
                  safePlay(video);
                }
              },
              delay
            );
          }
        }

        installMediaSessionHandlers(
          true
        );

        updateMediaSession();
        postState(true);

        return requested;
      };

      const requestFullscreen = () => {
        const video =
          state.video ||
          findWatchVideo();

        if (!video) return false;

        attachVideo(video);

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
            video.closest(
              "#movie_player, .html5-video-player"
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
        } catch (_) {}

        return false;
      };

      window.__YOUTUBE_VCD_MEDIA_CONTROL__ = {
        play: mediaPlay,
        pause: mediaPause,

        toggle() {
          const video =
            state.video ||
            findWatchVideo();

          if (!video) return false;

          return (
            video.paused ||
            video.ended
          )
            ? mediaPlay()
            : mediaPause();
        },

        seekBy,
        seekTo,

        prepareForBackground,
        resumeForeground,

        keepAlive() {
          if (
            state.wantsPlayback &&
            Date.now() >
              state.userPauseUntil
          ) {
            recoverPlayback(
              state.video ||
              findWatchVideo()
            );
          }

          return state.wantsPlayback;
        },

        requestPiP,
        requestFullscreen,

        snapshot() {
          const video =
            state.video ||
            findWatchVideo();

          return {
            hasVideo: !!video,
            paused:
              video
                ? !!video.paused
                : true,
            wantsPlayback:
              state.wantsPlayback,
            realHidden:
              isReallyHidden(),
            currentTime:
              video &&
              Number.isFinite(
                video.currentTime
              )
                ? video.currentTime
                : 0,
            presentationMode:
              video
                ?.webkitPresentationMode ||
              "inline"
          };
        }
      };

      const refreshVideo = () => {
        const video =
          findWatchVideo();

        if (video) {
          attachVideo(video);
        }
      };

      nativeDocumentAddEventListener(
        "play",
        (event) => {
          if (
            event.target instanceof
              HTMLVideoElement
          ) {
            const active =
              findWatchVideo();

            if (
              event.target === active ||
              event.target.classList
                ?.contains(
                  "html5-main-video"
                )
            ) {
              attachVideo(
                event.target
              );
            }
          }
        },
        true
      );

      nativeDocumentAddEventListener(
        "visibilitychange",
        () => {
          if (isReallyHidden()) {
            prepareForBackground();
          } else {
            resumeForeground();
          }
        },
        true
      );

      nativeDocumentAddEventListener(
        "webkitvisibilitychange",
        () => {
          if (isReallyHidden()) {
            prepareForBackground();
          }
        },
        true
      );

      nativeDocumentAddEventListener(
        "freeze",
        prepareForBackground,
        true
      );

      nativeWindowAddEventListener(
        "blur",
        () => {
          const video =
            state.video ||
            findWatchVideo();

          if (
            video &&
            !video.paused
          ) {
            prepareForBackground();
          }
        },
        true
      );

      nativeWindowAddEventListener(
        "pagehide",
        prepareForBackground,
        true
      );

      nativeWindowAddEventListener(
        "pageshow",
        resumeForeground,
        true
      );

      nativeDocumentAddEventListener(
        "yt-navigate-finish",
        () => {
          nativeSetTimeout(
            refreshVideo,
            0
          );

          nativeSetTimeout(
            refreshVideo,
            300
          );
        },
        true
      );

      const observer =
        new MutationObserver(
          () => {
            const video =
              findWatchVideo();

            if (
              video &&
              video !== state.video
            ) {
              attachVideo(video);
            }
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

        refreshVideo();
        configureWebAudioSession();
      };

      if (document.documentElement) {
        begin();
      } else {
        nativeDocumentAddEventListener(
          "DOMContentLoaded",
          begin,
          { once: true }
        );
      }

      window.setInterval(
        () => {
          refreshVideo();

          if (
            state.wantsPlayback &&
            isReallyHidden() &&
            Date.now() >
              state.userPauseUntil
          ) {
            recoverPlayback(
              state.video
            );
          }

          installMediaSessionHandlers(
            false
          );

          updateMediaSession();
          postState(false);
        },
        1500
      );
    })();
    """#

    static let playCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      return control
        ? control.play()
        : false;
    })();
    """#

    static let pauseCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      return control
        ? control.pause()
        : false;
    })();
    """#

    static let toggleCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      return control
        ? control.toggle()
        : false;
    })();
    """#

    static let prepareBackgroundCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      return control
        ? control.prepareForBackground()
        : false;
    })();
    """#

    static let resumeForegroundCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      return control
        ? control.resumeForeground()
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

    static let snapshotCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      return control
        ? control.snapshot()
        : null;
    })();
    """#

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
        let safe =
            max(
                0,
                seconds
            )

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
