import SwiftUI

struct V9MediaLabView:
    View
{
    @EnvironmentObject
    private var player:
        V9PlayerService

    @AppStorage(
        "v9.resolver.endpoint"
    )
    private var endpoint =
        "http://127.0.0.1:8085"

    @State
    private var videoID =
        ""

    @State
    private var healthText =
        "Resolver neverificat"

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
                    videoID.count != 11
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
                    healthText =
                        "OK • \(health.version) • relay TTL \(health.relayTTL)s"
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
                let resolved =
                    try await resolver
                        .resolve(
                            videoID:
                                videoID,
                            endpoint:
                                endpoint
                        )

                await MainActor.run {
                    player.load(
                        resolved
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
