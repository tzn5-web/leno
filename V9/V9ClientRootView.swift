import Foundation
import SwiftUI

@MainActor
struct V9ClientRootView:
    View
{
    @EnvironmentObject
    private var player:
        V9PlayerService

    @Environment(\.scenePhase)
    private var scenePhase

    @StateObject
    private var native =
        V9NativeYouTubeClient()

    @AppStorage(
        "v9.resolver.endpoint"
    )
    private var fallbackEndpoint =
        ""

    @State
    private var resolverToken =
        ResolverTokenStore
            .load()

    @State
    private var showSettings =
        false

    @State
    private var showPlayer =
        false

    @State
    private var clientError:
        String?

    @State
    private var resolvingVideoID:
        String?

    private let resolver =
        VcdResolverClient()

    var body: some View {
        TabView {
            V9HomeFeedView(
                native:
                    native,
                play:
                    play
            )
            .tabItem {
                Label(
                    "Acasă",
                    systemImage:
                        "house.fill"
                )
            }

            V9SearchView(
                native:
                    native,
                play:
                    play
            )
            .tabItem {
                Label(
                    "Caută",
                    systemImage:
                        "magnifyingglass"
                )
            }

            V9SettingsSummaryView(
                endpoint:
                    fallbackEndpoint,
                openSettings:
                    {
                        showSettings =
                            true
                    }
            )
            .tabItem {
                Label(
                    "Setări",
                    systemImage:
                        "gearshape.fill"
                )
            }
        }
        .safeAreaInset(
            edge:
                .bottom,
            spacing:
                0
        ) {
            if player
                .hasLoadedMedia {
                V9MiniPlayerView(
                    player:
                        player,
                    openPlayer:
                        {
                            showPlayer =
                                true
                        }
                )
            }
        }
        .overlay {
            if resolvingVideoID !=
                nil {
                ZStack {
                    Color.black
                        .opacity(
                            0.18
                        )
                        .ignoresSafeArea()

                    ProgressView(
                        "Pregătesc videoclipul…"
                    )
                    .padding(
                        20
                    )
                    .background(
                        .regularMaterial,
                        in:
                            RoundedRectangle(
                                cornerRadius:
                                    16
                            )
                    )
                }
            }
        }
        .sheet(
            isPresented:
                $showPlayer
        ) {
            V9PlayerSheet(
                player:
                    player
            )
        }
        .sheet(
            isPresented:
                $showSettings
        ) {
            V9ResolverSettingsView(
                endpoint:
                    $fallbackEndpoint,
                resolverToken:
                    $resolverToken,
                resolver:
                    resolver
            )
        }
        .alert(
            "Nu pot reda videoclipul",
            isPresented:
                Binding(
                    get: {
                        clientError !=
                            nil
                    },
                    set: {
                        visible in

                        if !visible {
                            clientError =
                                nil
                        }
                    }
                )
        ) {
            Button(
                "OK",
                role:
                    .cancel
            ) {
                clientError =
                    nil
            }
        } message: {
            Text(
                clientError ??
                "Eroare necunoscută."
            )
        }
        .onChange(
            of:
                scenePhase
        ) {
            _,
            phase in

            player
                .handleScenePhase(
                    phase
                )
        }
        .onChange(
            of:
                resolverToken
        ) {
            _,
            value in

            ResolverTokenStore
                .save(
                    value
                )
        }
    }

    private func play(
        _ video:
            BrowseVideo
    ) {
        guard resolvingVideoID ==
                nil
        else {
            return
        }

        let endpointSnapshot =
            fallbackEndpoint

        let tokenSnapshot =
            resolverToken

        resolvingVideoID =
            video.id

        Task {
            defer {
                resolvingVideoID =
                    nil
            }

            do {
                let resolved =
                    try await resolveVideo(
                        id:
                            video.id,
                        fallbackEndpoint:
                            endpointSnapshot,
                        token:
                            tokenSnapshot
                    )

                player.load(
                    resolved,
                    refreshProvider:
                        {
                            id in

                            try await resolveRefresh(
                                id:
                                    id,
                                fallbackEndpoint:
                                    endpointSnapshot,
                                token:
                                    tokenSnapshot
                            )
                        }
                )

                showPlayer =
                    true
            } catch {
                clientError =
                    error
                        .localizedDescription
            }
        }
    }

    private func resolveVideo(
        id:
            String,
        fallbackEndpoint:
            String,
        token:
            String
    ) async throws
        -> ResolvedVideo
    {
        do {
            return try await native
                .resolve(
                    videoID:
                        id
                )
        } catch {
            let endpoint =
                fallbackEndpoint
                    .trimmingCharacters(
                        in:
                            .whitespacesAndNewlines
                    )

            guard !endpoint
                .isEmpty
            else {
                throw error
            }

            return try await resolver
                .resolve(
                    videoID:
                        id,
                    endpoint:
                        endpoint,
                    bearerToken:
                        token
                )
        }
    }
    private func resolveRefresh(
        id:
            String,
        fallbackEndpoint:
            String,
        token:
            String
    ) async throws
        -> ResolvedVideo
    {
        let endpoint =
            fallbackEndpoint
                .trimmingCharacters(
                    in:
                        .whitespacesAndNewlines
                )

        // A refresh is requested only after the currently loaded media has
        // already failed. If an optional resolver exists, try its independent
        // extraction path first instead of repeatedly returning the same
        // native CDN route.
        if !endpoint.isEmpty {
            do {
                return try await resolver
                    .resolve(
                        videoID:
                            id,
                        endpoint:
                            endpoint,
                        bearerToken:
                            token
                    )
            } catch {
                // Keep the app autonomous even if the optional backend is
                // unavailable.
            }
        }

        return try await native
            .resolve(
                videoID:
                    id
            )
    }

}
