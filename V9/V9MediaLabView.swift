import Foundation
import SwiftUI

struct V9MediaLabView:
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
    private var videoID =
        ""

    @State
    private var healthText =
        "Configurează IP-ul LAN al PC-ului sau un resolver HTTPS."

    @State
    private var busy =
        false

    @State
    private var errorText:
        String?

    private let resolver =
        VcdResolverClient()

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(
                    spacing:
                        18
                ) {
                    playerSurface

                    resolverPanel

                    playbackPanel

                    diagnosticPanel
                }
                .padding()
            }
            .navigationTitle(
                "V9 Media Lab"
            )
            .navigationBarTitleDisplayMode(
                .inline
            )
        }
        .onChange(
            of: scenePhase
        ) {
            _,
            newPhase in

            player.handleScenePhase(
                newPhase
            )
        }
        .onChange(
            of:
                resolverToken
        ) {
            _,
            newValue in

            ResolverTokenStore
                .save(
                    newValue
                )
        }
    }

    private var playerSurface:
        some View
    {
        ZStack {
            Color.black

            V9MPVPlayerView(
                service:
                    player
            )

            if !player.hasLoadedMedia {
                VStack(
                    spacing:
                        10
                ) {
                    Image(
                        systemName:
                            "play.rectangle.on.rectangle"
                    )
                    .font(
                        .system(
                            size: 42
                        )
                    )

                    Text(
                        "MPV persistent"
                    )
                    .font(
                        .headline
                    )

                    Text(
                        "Nu există WebKit sau AVPlayer în targetul V9."
                    )
                    .font(
                        .caption
                    )
                    .foregroundStyle(
                        .secondary
                    )
                }
                .foregroundStyle(
                    .white
                )
                .padding()
            }
        }
        .aspectRatio(
            16 / 9,
            contentMode:
                .fit
        )
        .clipShape(
            RoundedRectangle(
                cornerRadius:
                    16,
                style:
                    .continuous
            )
        )
    }

    private var resolverPanel:
        some View
    {
        VStack(
            alignment:
                .leading,
            spacing:
                12
        ) {
            Text(
                "VcdResolver"
            )
            .font(
                .headline
            )

            TextField(
                "https://resolver.example.com",
                text:
                    $endpoint
            )
            .textInputAutocapitalization(
                .never
            )
            .autocorrectionDisabled()
            .keyboardType(
                .URL
            )
            .textFieldStyle(
                .roundedBorder
            )

            SecureField(
                "Token resolver (opțional)",
                text:
                    $resolverToken
            )
            .textInputAutocapitalization(
                .never
            )
            .autocorrectionDisabled()
            .textFieldStyle(
                .roundedBorder
            )

            TextField(
                "YouTube video ID (11 caractere)",
                text:
                    $videoID
            )
            .textInputAutocapitalization(
                .never
            )
            .autocorrectionDisabled()
            .textFieldStyle(
                .roundedBorder
            )

            HStack {
                Button(
                    "Health"
                ) {
                    checkHealth()
                }

                Spacer()

                Button(
                    "Resolve + Play"
                ) {
                    resolveAndPlay()
                }
                .buttonStyle(
                    .borderedProminent
                )
                .disabled(
                    busy ||
                    videoID.count != 11 ||
                    endpoint
                        .trimmingCharacters(
                            in:
                                .whitespacesAndNewlines
                        )
                        .isEmpty
                )
            }

            Text(
                healthText
            )
            .font(
                .caption
            )
            .foregroundStyle(
                .secondary
            )
        }
        .padding()
        .background(
            .thinMaterial,
            in:
                RoundedRectangle(
                    cornerRadius:
                        16
                )
        )
    }

    private var playbackPanel:
        some View
    {
        VStack(
            spacing:
                12
        ) {
            HStack(
                spacing:
                    18
            ) {
                Button {
                    player.seek(
                        by:
                            -15
                    )
                } label: {
                    Image(
                        systemName:
                            "gobackward.15"
                    )
                }

                Button {
                    player.toggle()
                } label: {
                    Image(
                        systemName:
                            player.isPlaying
                                ? "pause.fill"
                                : "play.fill"
                    )
                    .font(
                        .title2
                    )
                }

                Button {
                    player.seek(
                        by:
                            15
                    )
                } label: {
                    Image(
                        systemName:
                            "goforward.15"
                    )
                }

                Button {
                    player.togglePiP()
                } label: {
                    Image(
                        systemName:
                            player.isPiPActive
                                ? "pip.exit"
                                : "pip.enter"
                    )
                }
                .accessibilityLabel(
                    "Picture in Picture"
                )
                .disabled(
                    !player
                        .isPiPPossible
                )
            }
            .buttonStyle(
                .bordered
            )
            .disabled(
                !player.hasLoadedMedia
            )

            if player.duration > 0 {
                ProgressView(
                    value:
                        min(
                            player.currentTime,
                            player.duration
                        ),
                    total:
                        player.duration
                )
            }

            Text(
                player.title
            )
            .font(
                .subheadline
                    .weight(
                        .semibold
                    )
            )
            .lineLimit(2)
        }
    }

    private var diagnosticPanel:
        some View
    {
        VStack(
            alignment:
                .leading,
            spacing:
                6
        ) {
            Text(
                "Diagnostic"
            )
            .font(
                .headline
            )

            Text(
                "State: \(player.stateDescription)"
            )

            Text(
                String(
                    format:
                        "Time: %.1f / %.1f",
                    player.currentTime,
                    player.duration
                )
            )

            Text(
                "Video relay: \(player.hasVideoRelay ? "DA" : "NU")"
            )

            Text(
                "Audio relay separat: \(player.hasAudioRelay ? "DA" : "NU")"
            )

            Text(
                "PiP posibil: \(player.isPiPPossible ? "DA" : "NU")"
            )

            Text(
                "PiP activ: \(player.isPiPActive ? "DA" : "NU")"
            )

            if let errorText {
                Text(
                    errorText
                )
                .foregroundStyle(
                    .red
                )
            }
        }
        .font(
            .caption
                .monospaced()
        )
        .frame(
            maxWidth:
                .infinity,
            alignment:
                .leading
        )
    }

    private func checkHealth() {
        guard !busy else {
            return
        }

        busy = true
        errorText = nil

        Task {
            defer {
                Task {
                    @MainActor in
                    busy = false
                }
            }

            do {
                let health =
                    try await resolver
                        .health(
                            endpoint:
                                endpoint
                        )

                await MainActor.run {
                    let runtime =
                        health.jsRuntime ??
                        "necunoscut"

                    let auth =
                        health.authRequired ==
                        true
                            ? "auth ON"
                            : "auth OFF"

                    let cap =
                        health.maxVideoHeight
                            .map {
                                height in

                                let fps =
                                    Int(
                                        health.maxVideoFPS ??
                                        0
                                    )

                                return fps > 0
                                    ? " • max \(height)p/\(fps)fps"
                                    : " • max \(height)p"
                            } ??
                        ""

                    healthText =
                        "OK • \(health.version) • \(runtime) • \(auth) • relay TTL \(health.relayTTL)s\(cap)"
                }
            } catch {
                await MainActor.run {
                    healthText =
                        "Resolver indisponibil"

                    errorText =
                        error.localizedDescription
                }
            }
        }
    }

    private func resolveAndPlay() {
        guard !busy else {
            return
        }

        busy = true
        errorText = nil

        Task {
            defer {
                Task {
                    @MainActor in
                    busy = false
                }
            }

            do {
                let endpointSnapshot =
                    endpoint

                let tokenSnapshot =
                    resolverToken

                let resolved =
                    try await resolver
                        .resolve(
                            videoID:
                                videoID,
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
                    errorText =
                        error.localizedDescription
                }
            }
        }
    }
}
