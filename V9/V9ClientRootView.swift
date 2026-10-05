import Foundation
import SwiftUI

struct V9ClientRootView:
    View
{
    @EnvironmentObject
    private var player:
        V9PlayerService

    @Environment(\.scenePhase)
    private var scenePhase

    @AppStorage(
        "v9.resolver.endpoint"
    )
    private var endpoint =
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

    private let resolver =
        VcdResolverClient()

    var body: some View {
        TabView {
            V9HomeFeedView(
                resolver:
                    resolver,
                endpoint:
                    endpoint,
                resolverToken:
                    resolverToken,
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
                resolver:
                    resolver,
                endpoint:
                    endpoint,
                resolverToken:
                    resolverToken,
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
                    endpoint,
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
                    $endpoint,
                resolverToken:
                    $resolverToken,
                resolver:
                    resolver
            )
        }
        .task {
            if endpoint
                .trimmingCharacters(
                    in:
                        .whitespacesAndNewlines
                )
                .isEmpty {
                showSettings =
                    true
            }
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
        let endpointSnapshot =
            endpoint

        let tokenSnapshot =
            resolverToken

        guard !endpointSnapshot
            .trimmingCharacters(
                in:
                    .whitespacesAndNewlines
            )
            .isEmpty
        else {
            showSettings =
                true
            return
        }

        showPlayer =
            true

        Task {
            do {
                let resolved =
                    try await resolver
                        .resolve(
                            videoID:
                                video.id,
                            endpoint:
                                endpointSnapshot,
                            bearerToken:
                                tokenSnapshot
                        )

                await MainActor.run {
                    player.load(
                        resolved,
                        refreshProvider:
                            {
                                id in

                                try await resolver
                                    .resolve(
                                        videoID:
                                            id,
                                        endpoint:
                                            endpointSnapshot,
                                        bearerToken:
                                            tokenSnapshot
                                    )
                            }
                    )
                }
            } catch {
                await MainActor.run {
                    player
                        .reportExternalFailure(
                            error
                                .localizedDescription
                        )
                }
            }
        }
    }
}
