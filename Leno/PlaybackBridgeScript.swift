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

      // Keep YouTube from registering page-lifecycle handlers that can
      // explicitly pause the watch player. The bridge captured pristine
      // addEventListener functions above, so our own real lifecycle listeners
      // still receive the native events.
      const originalEventTargetAddEventListener =
        EventTarget.prototype.addEventListener;

      const blockedLifecycleEvents =
        new Set([
          "visibilitychange",
          "webkitvisibilitychange",
          "pagehide",
          "freeze"
        ]);

      EventTarget.prototype.addEventListener =
        function(type, listener, options) {
          if (
            blockedLifecycleEvents.has(
              String(type)
            )
          ) {
            return;
          }

          return originalEventTargetAddEventListener.call(
            this,
            type,
            listener,
            options
          );
        };

      try {
        document.hasFocus = () => true;
      } catch (_) {}

      try {
        Object.defineProperty(
          document,
          "onvisibilitychange",
          {
            configurable: true,
            get: () => null,
            set: () => {}
          }
        );
      } catch (_) {}

      try {
        Object.defineProperty(
          document,
          "onwebkitvisibilitychange",
          {
            configurable: true,
            get: () => null,
            set: () => {}
          }
        );
      } catch (_) {}

      const shieldPageMediaActions = () => {
        try {
          const mediaSession =
            navigator.mediaSession;

          if (!mediaSession) return;

          const proto =
            Object.getPrototypeOf(
              mediaSession
            );

          if (
            proto &&
            typeof proto
              .setActionHandler ===
              "function" &&
            !proto
              .__youtubeVcdActionShield
          ) {
            Object.defineProperty(
              proto,
              "__youtubeVcdActionShield",
              {
                configurable: false,
                enumerable: false,
                writable: false,
                value: true
              }
            );

            Object.defineProperty(
              proto,
              "setActionHandler",
              {
                configurable: true,
                enumerable: false,
                writable: true,
                value:
                  function() {
                    return undefined;
                  }
              }
            );
          }
        } catch (_) {
          try {
            navigator.mediaSession
              .setActionHandler =
              function() {
                return undefined;
              };
          } catch (_) {}
        }
      };

      shieldPageMediaActions();

      const state = {
        video: null,
        wantsPlayback: false,
        explicitPause: false,
        userPauseUntil: 0,
        nativeBackground: false,
        videoID: "",
        systemInterruption: false,
        recoveryTimers:
          new Set(),
        lastKnownTime: 0,
        lastReportAt: 0,
        transitionRecoveryUntil: 0,
        actionStamp:
          new Map()
      };

      const isBackgrounded = () =>
        state.nativeBackground ||
        isReallyHidden();

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
            "#inline-preview-player, #inline-player"
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
              transitionArmed:
                Date.now() <=
                  state.transitionRecoveryUntil,
              realHidden:
                isBackgrounded(),
              presentationMode:
                "none",
              readyState: 0,
              networkState: 0,
              inDOM: false,
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
            transitionArmed:
              Date.now() <=
                state.transitionRecoveryUntil,
            realHidden:
              isBackgrounded(),
            presentationMode,
            readyState:
              video.readyState,
            networkState:
              video.networkState,
            inDOM:
              document.contains(video),
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

      // System transport ownership stays native in YouTubeSession.
      // Do not install a second set of JS transport handlers or overwrite
      // playbackState/position from two independent owners.
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
          state.explicitPause ||
          state.systemInterruption ||
          video.ended ||
          Date.now() <=
            state.userPauseUntil
        ) {
          return;
        }

        if (
          Number.isFinite(state.lastKnownTime) &&
          state.lastKnownTime > 0 &&
          Number.isFinite(video.currentTime) &&
          Math.abs(
            video.currentTime -
            state.lastKnownTime
          ) > 2
        ) {
          try {
            video.currentTime =
              state.lastKnownTime;
          } catch (_) {}
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
                  (
                    isBackgrounded() ||
                    Date.now() <=
                      state.transitionRecoveryUntil
                  ) &&
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

        state.explicitPause = false;
        state.wantsPlayback = true;
        state.userPauseUntil = 0;
        state.transitionRecoveryUntil = 0;

        const result =
          safePlay(video);
        postState(true);

        return result;
      };

      const mediaPause = () => {
        const video =
          state.video ||
          findWatchVideo();

        if (!video) return false;

        attachVideo(video);

        state.explicitPause = true;
        state.wantsPlayback = false;
        state.userPauseUntil =
          Number.POSITIVE_INFINITY;
        state.transitionRecoveryUntil = 0;

        clearRecoveryTimers();

        try {
          nativePause.call(video);
        } catch (_) {
          return false;
        }
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

      const onPlay = () => {
        if (state.explicitPause) {
          try {
            nativePause.call(
              state.video
            );
          } catch (_) {}

          postState(true);
          return;
        }

        state.wantsPlayback = true;
        state.userPauseUntil = 0;

        configureWebAudioSession();
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

        const now = Date.now();

        if (state.systemInterruption) {
          clearRecoveryTimers();
          postState(true);
          return;
        }

        if (state.explicitPause) {
          state.wantsPlayback = false;
          state.transitionRecoveryUntil = 0;
          clearRecoveryTimers();
          postState(true);
          return;
        }

        if (
          now <= state.userPauseUntil ||
          !state.wantsPlayback
        ) {
          state.wantsPlayback = false;
          state.transitionRecoveryUntil = 0;
          clearRecoveryTimers();
        } else if (
          isBackgrounded() &&
          !video.ended
        ) {
          recoverPlayback(video);
        } else if (
          now <=
            state.transitionRecoveryUntil &&
          !video.ended
        ) {
          // A system background/PiP transition was armed before this pause.
          // Recover now, then retry again if the real visibility flips hidden.
          recoverPlayback(video);

          const waitForHidden = () => {
            if (
              isBackgrounded() &&
              state.wantsPlayback &&
              Date.now() >
                state.userPauseUntil &&
              !video.ended
            ) {
              recoverPlayback(video);
            }

            postState(true);
          };

          nativeDocumentAddEventListener(
            "visibilitychange",
            waitForHidden,
            { once: true }
          );
        } else {
          // Visible pause with no armed system transition is intentional.
          state.wantsPlayback = false;
          clearRecoveryTimers();
        }
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
        postState(false);
      };

      const onMetadata = () => {
        enforceInlinePlayback(
          state.video
        );
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
        postState(false);
      };

      function attachVideo(video) {
        if (
          !(video instanceof
            HTMLVideoElement)
        ) {
          return null;
        }

        const nextVideoID =
          currentVideoID();

        if (state.video === video) {
          const routeChanged =
            !!nextVideoID &&
            !!state.videoID &&
            nextVideoID !==
              state.videoID;

          if (routeChanged) {
            const keepBackgroundIntent =
              isBackgrounded() &&
              state.wantsPlayback;

            state.videoID =
              nextVideoID;
            state.lastKnownTime = 0;
            state.transitionRecoveryUntil = 0;
            clearRecoveryTimers();

            state.wantsPlayback =
              keepBackgroundIntent ||
              (
                !video.paused &&
                !video.ended
              );
          } else if (nextVideoID) {
            state.videoID =
              nextVideoID;
          }

          enforceInlinePlayback(video);
          return video;
        }

        const sameMedia =
          !state.videoID ||
          !nextVideoID ||
          state.videoID === nextVideoID;

        const preserveIntent =
          sameMedia &&
          state.wantsPlayback &&
          (
            isBackgrounded() ||
            Date.now() <=
              state.transitionRecoveryUntil
          );

        const preservePosition =
          sameMedia &&
          preserveIntent &&
          state.lastKnownTime > 1;

        detachVideo(state.video);

        state.video = video;
        state.videoID =
          nextVideoID ||
          state.videoID;

        try {
          video.setAttribute(
            "data-youtube-vcd-attached",
            "true"
          );
        } catch (_) {}

        enforceInlinePlayback(video);

        state.wantsPlayback =
          preserveIntent ||
          (
            !video.paused &&
            !video.ended
          );

        if (
          !preservePosition &&
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

        postState(true);

        return video;
      }

      // Do not let a hidden-page/site initiated pause defeat an already
      // established playback intent. Explicit app/lock-screen pause bypasses
      // this wrapper through nativePause after clearing wantsPlayback.
      HTMLMediaElement.prototype.pause =
        function(...args) {
          const isActiveVideo =
            this === state.video ||
            this.classList
              ?.contains(
                "html5-main-video"
              );

          const backgroundPause =
            isActiveVideo &&
            state.wantsPlayback &&
            !state.systemInterruption &&
            Date.now() >
              state.userPauseUntil &&
            isBackgrounded() &&
            !this.ended;

          if (backgroundPause) {
            return;
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

              if (state.explicitPause) {
                postState(true);
                return Promise.resolve();
              }

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

          state.transitionRecoveryUntil =
            Date.now() + 2500;

          configureWebAudioSession();

          if (
            !state.explicitPause &&
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
            isBackgrounded() &&
            Date.now() >
              state.userPauseUntil
          ) {
            recoverPlayback(video);
          }
          postState(true);

          return true;
        };

      const enterBackground = () => {
        state.nativeBackground = true;
        state.transitionRecoveryUntil =
          Date.now() + 2500;

        const video =
          state.video ||
          findWatchVideo();

        if (!video) {
          postState(true);
          return false;
        }

        attachVideo(video);
        configureWebAudioSession();

        if (
          state.wantsPlayback &&
          !state.explicitPause &&
          Date.now() >
            state.userPauseUntil
        ) {
          recoverPlayback(video);
        }
        postState(true);

        return true;
      };

      const resumeForeground = () => {
        state.nativeBackground = false;

        if (state.wantsPlayback) {
          state.transitionRecoveryUntil =
            Date.now() + 2500;
        }

        const video =
          state.video ||
          findWatchVideo();

        if (!video) return false;

        attachVideo(video);
        configureWebAudioSession();

        clearRecoveryTimers();

        if (
          state.wantsPlayback &&
          !video.ended &&
          Date.now() >
            state.userPauseUntil
        ) {
          // recoverPlayback also restores lastKnownTime if WebKit rebuilt the
          // MediaSource at position zero, even when the replacement element
          // has already started playing.
          recoverPlayback(video);
        }
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

        state.transitionRecoveryUntil =
          Date.now() + 1800;

        if (
          shouldResume &&
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

              // The WebKit presentation API handled the toggle. Without this,
              // the standards fallback below can immediately request PiP again.
              requested = true;
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

          if (
            typeof player
              .webkitRequestFullscreen ===
            "function"
          ) {
            player.webkitRequestFullscreen();
            return true;
          }
        } catch (_) {}

        return false;
      };

      const makeControlButton = (
        id,
        title,
        symbol,
        action
      ) => {
        let button =
          document.getElementById(id);

        if (button) return button;

        button =
          document.createElement("button");

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

        button.addEventListener(
          "click",
          (event) => {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
            action();
          },
          true
        );

        return button;
      };

      const ensureMediaControls = () => {
        const video =
          state.video ||
          findWatchVideo();

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
            makeControlButton(
              "__youtube_vcd_pip__",
              "Picture in Picture",
              "◱",
              requestPiP
            )
          );

          root.appendChild(
            makeControlButton(
              "__youtube_vcd_fullscreen__",
              "Fullscreen",
              "⛶",
              requestFullscreen
            )
          );

          (
            document.body ||
            document.documentElement
          )?.appendChild(root);
        }

        root.style.display = "flex";
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
        enterBackground,
        resumeForeground,

        beginSystemInterruption() {
          state.systemInterruption = true;
          clearRecoveryTimers();
          postState(true);
          return true;
        },

        endSystemInterruption() {
          state.systemInterruption = false;
          postState(true);
          return true;
        },

        keepAlive() {
          if (
            state.wantsPlayback &&
            !state.explicitPause &&
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
            explicitPause:
              state.explicitPause,
            realHidden:
              isBackgrounded(),
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
              "inline",
            readyState:
              video?.readyState ?? 0,
            networkState:
              video?.networkState ?? 0,
            inDOM:
              !!video &&
              document.contains(video)
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

      const recordPlayerControlIntent =
        (event) => {
          const target =
            event.target;

          if (
            !(target instanceof Element)
          ) {
            return;
          }

          const control =
            target.closest(
              [
                ".ytp-play-button",
                "button[aria-label^='Pause']",
                "button[aria-label^='Play']",
                "button[data-title-no-tooltip='Pause']",
                "button[data-title-no-tooltip='Play']"
              ].join(",")
            );

          if (!control) return;

          const video =
            state.video ||
            findWatchVideo();

          if (!video) return;

          attachVideo(video);

          if (
            !actionAllowed(
              "media-intent",
              260
            )
          ) {
            return;
          }

          const intent =
            (
              video.paused ||
              video.ended
            )
              ? "play"
              : "pause";

          if (intent === "play") {
            state.explicitPause = false;
            state.wantsPlayback = true;
            state.userPauseUntil = 0;
          } else {
            state.explicitPause = true;
            state.wantsPlayback = false;
            state.userPauseUntil =
              Number.POSITIVE_INFINITY;
            state.transitionRecoveryUntil = 0;
            clearRecoveryTimers();
          }

          try {
            window.webkit
              ?.messageHandlers
              ?.mediaIntent
              ?.postMessage({
                intent
              });
          } catch (_) {}
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
        "pointerdown",
        recordPlayerControlIntent,
        {
          capture: true,
          passive: true
        }
      );

      nativeDocumentAddEventListener(
        "touchstart",
        recordPlayerControlIntent,
        {
          capture: true,
          passive: true
        }
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

            ensureMediaControls();
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
        ensureMediaControls();
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
          ensureMediaControls();

          if (
            state.wantsPlayback &&
            isBackgrounded() &&
            Date.now() >
              state.userPauseUntil
          ) {
            recoverPlayback(
              state.video
            );
          }
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

    static let enterBackgroundCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      return control
        ? control.enterBackground()
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

    static let beginSystemInterruptionCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      return control
        ? control.beginSystemInterruption()
        : false;
    })();
    """#

    static let endSystemInterruptionCall = #"""
    (() => {
      const control =
        window.__YOUTUBE_VCD_MEDIA_CONTROL__;

      return control
        ? control.endSystemInterruption()
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

    static func restoreAfterReloadCall(
        seconds: Double,
        shouldPlay: Bool
    ) -> String {
        let safeSeconds =
            max(
                0,
                seconds
            )

        let playLiteral =
            shouldPlay
                ? "true"
                : "false"

        return """
        (() => {
          const control =
            window.__YOUTUBE_VCD_MEDIA_CONTROL__;

          if (!control) {
            return false;
          }

          const seeked =
            control.seekTo(\(safeSeconds));

          if (\(playLiteral)) {
            control.play();
          }

          return seeked;
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
