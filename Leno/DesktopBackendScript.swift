import Foundation

enum DesktopBackendScript {
    static let source = #"""
    (() => {
      "use strict";

      if (window.__YOUTUBE_VCD_DESKTOP_BACKEND_V5__) return;
      window.__YOUTUBE_VCD_DESKTOP_BACKEND_V5__ = true;

      const nativeSetTimeout =
        window.setTimeout.bind(window);

      const nativeSetInterval =
        window.setInterval.bind(window);

      const DESKTOP_HOST =
        "www.youtube.com";

      const desktopState =
        window.__YOUTUBE_VCD_DESKTOP_STATE__ = {
          active: false,
          mediaSessionShielded: false,
          host: location.hostname
        };

      const ensureViewport = () => {
        try {
          let viewport =
            document.querySelector(
              'meta[name="viewport"]'
            );

          if (!viewport) {
            viewport =
              document.createElement(
                "meta"
              );

            viewport.name =
              "viewport";

            (
              document.head ||
              document.documentElement
            )?.appendChild(viewport);
          }

          viewport.content =
            "width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover";
        } catch (_) {}
      };

      const normalizeCurrentURL = () => {
        try {
          const url =
            new URL(location.href);

          const host =
            url.hostname.toLowerCase();

          if (
            host === "m.youtube.com" ||
            host === "youtube.com"
          ) {
            url.hostname =
              DESKTOP_HOST;
          }

          if (
            url.hostname === "youtu.be"
          ) {
            const id =
              url.pathname
                .split("/")
                .filter(Boolean)[0];

            if (id) {
              url.hostname =
                DESKTOP_HOST;

              url.pathname =
                "/watch";

              url.searchParams.set(
                "v",
                id
              );
            }
          }

          const path =
            url.pathname;

          const contentRoute =
            path === "/" ||
            path === "/watch" ||
            path.startsWith(
              "/shorts/"
            ) ||
            path.startsWith(
              "/live/"
            ) ||
            path.startsWith(
              "/feed/"
            ) ||
            path === "/results" ||
            path === "/playlist" ||
            path.startsWith(
              "/channel/"
            ) ||
            path.startsWith(
              "/@"
            );

          if (contentRoute) {
            url.searchParams.set(
              "app",
              "desktop"
            );

            url.searchParams.set(
              "persist_app",
              "1"
            );
          }

          if (
            url.href !==
            location.href
          ) {
            location.replace(
              url.href
            );

            return true;
          }
        } catch (_) {}

        return false;
      };

      const isAppPromotionURL = (
        value
      ) => {
        const text =
          String(
            value || ""
          ).trim();

        return (
          /^(?:youtube|vnd\.youtube|itms-apps|itms-services):/i.test(
            text
          ) ||
          /apps\.apple\.com|itunes\.apple\.com/i.test(
            text
          )
        );
      };

      const stopAppPromotionClick = (
        event
      ) => {
        try {
          const target =
            event.target;

          if (
            !(target instanceof Element)
          ) {
            return;
          }

          const link =
            target.closest(
              "a[href]"
            );

          if (
            link instanceof
              HTMLAnchorElement &&
            isAppPromotionURL(
              link.href
            )
          ) {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
          }
        } catch (_) {}
      };

      document.addEventListener(
        "click",
        stopAppPromotionClick,
        true
      );

      document.addEventListener(
        "auxclick",
        stopAppPromotionClick,
        true
      );

      // Native MPRemoteCommandCenter + MPNowPlayingInfoCenter own system
      // transport. The YouTube page is not allowed to install a second
      // remote-command layer.
      const disablePageMediaSession = () => {
        let session = null;
        let proto = null;

        try {
          session =
            navigator.mediaSession;

          proto =
            session
              ? Object.getPrototypeOf(
                  session
                )
              : null;
        } catch (_) {
          return;
        }

        if (!session || !proto) {
          return;
        }

        try {
          if (
            typeof proto
              .setActionHandler ===
              "function" &&
            !proto
              .__youtubeVcdSetActionHandlerBlocked
          ) {
            Object.defineProperty(
              proto,
              "__youtubeVcdSetActionHandlerBlocked",
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
            session.setActionHandler =
              function() {
                return undefined;
              };

            desktopState.mediaSessionShielded =
              true;
          } catch (_) {}
        }

        try {
          if (
            typeof proto
              .setPositionState ===
              "function" &&
            !proto
              .__youtubeVcdSetPositionStateBlocked
          ) {
            Object.defineProperty(
              proto,
              "__youtubeVcdSetPositionStateBlocked",
              {
                configurable: false,
                enumerable: false,
                writable: false,
                value: true
              }
            );

            Object.defineProperty(
              proto,
              "setPositionState",
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
            session.setPositionState =
              function() {
                return undefined;
              };
          } catch (_) {}
        }

        for (
          const property of
          [
            "metadata",
            "playbackState"
          ]
        ) {
          try {
            const descriptor =
              Object.getOwnPropertyDescriptor(
                proto,
                property
              );

            if (
              !descriptor?.set
            ) {
              continue;
            }

            Object.defineProperty(
              proto,
              property,
              {
                configurable:
                  descriptor
                    .configurable,
                enumerable:
                  descriptor
                    .enumerable,
                get:
                  descriptor
                    .get
                    ? function() {
                        return descriptor
                          .get
                          .call(this);
                      }
                    : undefined,
                set() {}
              }
            );
          } catch (_) {}
        }
      };

      const installDesktopShellStyle =
        () => {
          if (
            document.getElementById(
              "__youtube_vcd_desktop_shell_v5__"
            )
          ) {
            return;
          }

          const style =
            document.createElement(
              "style"
            );

          style.id =
            "__youtube_vcd_desktop_shell_v5__";

          style.textContent = [
            "html,body{width:100%!important;min-width:0!important;max-width:100vw!important;overflow-x:hidden!important;}",
            "ytd-app,#content,#page-manager{width:100%!important;min-width:0!important;max-width:100vw!important;}",
            "ytd-mini-guide-renderer,ytd-masthead #voice-search-button,ytd-masthead #buttons ytd-button-renderer,ytd-masthead ytd-topbar-menu-button-renderer,ytd-masthead #end #buttons,ytd-miniplayer,ytd-player-minimized,ytd-banner-promo-renderer,ytd-statement-banner-renderer,[class*='app-promo'],[class*='open-app']{display:none!important;visibility:hidden!important;}",
            "ytd-masthead{position:sticky!important;top:0!important;width:100%!important;min-width:0!important;z-index:2020!important;}",
            "ytd-masthead #container{min-width:0!important;padding-left:max(10px,env(safe-area-inset-left))!important;padding-right:max(10px,env(safe-area-inset-right))!important;}",
            "ytd-masthead #center{flex:1 1 auto!important;min-width:0!important;max-width:none!important;}",
            "ytd-masthead #search{min-width:0!important;}",
            "ytd-guide-renderer,#guide{max-width:min(86vw,340px)!important;}",
            "tp-yt-app-drawer#guide{z-index:2500!important;}",
            "ytd-watch-flexy,ytd-watch-grid,ytd-browse,ytd-search{width:100%!important;min-width:0!important;max-width:100vw!important;}",
            "ytd-watch-flexy #columns,ytd-watch-flexy #primary,ytd-watch-flexy #secondary,ytd-watch-grid #columns{width:100%!important;min-width:0!important;max-width:100%!important;}",
            "ytd-watch-flexy #columns{display:block!important;padding:0!important;}",
            "ytd-watch-flexy #primary{margin:0!important;padding:0 10px 18px!important;}",
            "ytd-watch-flexy #secondary{margin:0!important;padding:0 10px 28px!important;}",
            "ytd-watch-flexy #player-container-outer,ytd-watch-flexy #player-container-inner,ytd-watch-flexy #player-container,#movie_player,.html5-video-player,.html5-video-container,video.html5-main-video{max-width:100vw!important;}",
            "ytd-watch-flexy #player-container-outer{width:100vw!important;margin-left:-10px!important;margin-right:-10px!important;}",
            "ytd-watch-flexy #player-container-inner,ytd-watch-flexy #player-container,#movie_player,.html5-video-player,.html5-video-container{width:100%!important;}",
            "video.html5-main-video{object-fit:contain!important;}",
            "ytd-rich-grid-renderer #contents,ytd-two-column-browse-results-renderer #primary,ytd-section-list-renderer,ytd-item-section-renderer,ytd-search #contents{width:100%!important;min-width:0!important;max-width:100%!important;}",
            "ytd-rich-grid-renderer{--ytd-rich-grid-items-per-row:1!important;--ytd-rich-grid-posts-per-row:1!important;--ytd-rich-grid-game-cards-per-row:1!important;padding:0 10px!important;}",
            "ytd-rich-item-renderer,ytd-video-renderer,ytd-compact-video-renderer,ytd-grid-video-renderer{width:100%!important;min-width:0!important;max-width:100%!important;}",
            "ytd-video-renderer #dismissible,ytd-video-renderer #content,ytd-video-renderer #meta,ytd-compact-video-renderer #dismissible{min-width:0!important;max-width:100%!important;}",
            "#chips-wrapper,ytd-feed-filter-chip-bar-renderer{max-width:100vw!important;overflow-x:auto!important;scrollbar-width:none!important;}",
            "#chips-wrapper::-webkit-scrollbar{display:none!important;}"
          ].join("");

          (
            document.head ||
            document.documentElement
          )?.appendChild(style);
        };

      const reconcileDesktopShell = () => {
        ensureViewport();
        disablePageMediaSession();
        installDesktopShellStyle();

        desktopState.active =
          location.hostname ===
          DESKTOP_HOST;

        desktopState.host =
          location.hostname;

        try {
          document.documentElement
            ?.setAttribute(
              "data-youtube-vcd-desktop",
              "true"
            );
        } catch (_) {}
      };

      if (normalizeCurrentURL()) {
        return;
      }

      reconcileDesktopShell();

      let reconcileScheduled = false;

      const scheduleReconcile = () => {
        if (reconcileScheduled) {
          return;
        }

        reconcileScheduled = true;

        nativeSetTimeout(
          () => {
            reconcileScheduled = false;
            reconcileDesktopShell();
          },
          120
        );
      };

      const observer =
        new MutationObserver(
          scheduleReconcile
        );

      const start = () => {
        reconcileDesktopShell();

        if (
          document.documentElement
        ) {
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

      nativeSetTimeout(
        reconcileDesktopShell,
        0
      );

      nativeSetTimeout(
        reconcileDesktopShell,
        250
      );

      nativeSetTimeout(
        reconcileDesktopShell,
        900
      );

      document.addEventListener(
        "yt-navigate-finish",
        () => {
          scheduleReconcile();
        },
        true
      );

      nativeSetInterval(
        reconcileDesktopShell,
        3000
      );
    })();
    """#
}
