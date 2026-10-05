import SwiftUI

struct V9MiniPlayerView:
    View
{
    @ObservedObject
    var player:
        V9PlayerService

    let openPlayer:
        () -> Void

    var body: some View {
        HStack(
            spacing:
                12
        ) {
            HStack(
                spacing:
                    10
            ) {
                ZStack {
                    Color.black

                    V9MPVPlayerView(
                        service:
                            player
                    )
                    .allowsHitTesting(
                        false
                    )

                    Color.clear
                        .contentShape(
                            Rectangle()
                        )
                        .onTapGesture {
                            openPlayer()
                        }
                }
                .frame(
                    width:
                        96,
                    height:
                        54
                )
                .clipShape(
                    RoundedRectangle(
                        cornerRadius:
                            8
                    )
                )

                Button {
                    openPlayer()
                } label: {
                    VStack(
                        alignment:
                            .leading,
                        spacing:
                            2
                    ) {
                        Text(
                            player.title
                        )
                        .font(
                            .subheadline
                                .weight(
                                    .semibold
                                )
                        )
                        .foregroundStyle(
                            .primary
                        )
                        .lineLimit(
                            1
                        )

                        Text(
                            V9VideoFormatting
                                .duration(
                                    player.currentTime
                                )
                        )
                        .font(
                            .caption2
                                .monospacedDigit()
                        )
                        .foregroundStyle(
                            .secondary
                        )
                    }
                }
                .buttonStyle(
                    .plain
                )
            }

            Spacer()

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
                    .title3
                )
            }

            Button {
                openPlayer()
            } label: {
                Image(
                    systemName:
                        "chevron.up"
                )
            }
        }
        .padding(
            .horizontal,
            14
        )
        .padding(
            .vertical,
            10
        )
        .background(
            .ultraThinMaterial
        )
        .overlay(
            alignment:
                .top
        ) {
            if player.duration > 0 {
                GeometryReader {
                    geometry in

                    Rectangle()
                        .fill(
                            .primary
                        )
                        .frame(
                            width:
                                geometry.size.width *
                                min(
                                    1,
                                    max(
                                        0,
                                        player.currentTime /
                                        player.duration
                                    )
                                ),
                            height:
                                2
                        )
                }
                .frame(
                    height:
                        2
                )
            }
        }
    }
}

struct V9PlayerSheet:
    View
{
    @ObservedObject
    var player:
        V9PlayerService

    @Environment(\.dismiss)
    private var dismiss

    var body: some View {
        NavigationStack {
            VStack(
                spacing:
                    18
            ) {
                ZStack {
                    Color.black

                    V9MPVPlayerView(
                        service:
                            player
                    )
                }
                .aspectRatio(
                    16 / 9,
                    contentMode:
                        .fit
                )

                VStack(
                    alignment:
                        .leading,
                    spacing:
                        14
                ) {
                    Text(
                        player.title
                    )
                    .font(
                        .title3
                            .weight(
                                .semibold
                            )
                    )
                    .lineLimit(
                        3
                    )

                    if player.duration > 0 {
                        Slider(
                            value:
                                Binding(
                                    get: {
                                        min(
                                            player.currentTime,
                                            player.duration
                                        )
                                    },
                                    set: {
                                        value in

                                        player.seek(
                                            to:
                                                value
                                        )
                                    }
                                ),
                            in:
                                0...max(
                                    1,
                                    player.duration
                                )
                        )

                        HStack {
                            Text(
                                V9VideoFormatting
                                    .duration(
                                        player.currentTime
                                    )
                            )

                            Spacer()

                            Text(
                                V9VideoFormatting
                                    .duration(
                                        player.duration
                                    )
                            )
                        }
                        .font(
                            .caption
                                .monospacedDigit()
                        )
                        .foregroundStyle(
                            .secondary
                        )
                    }

                    HStack {
                        Spacer()

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

                        Spacer()

                        Button {
                            player.toggle()
                        } label: {
                            Image(
                                systemName:
                                    player.isPlaying
                                        ? "pause.circle.fill"
                                        : "play.circle.fill"
                            )
                            .font(
                                .system(
                                    size:
                                        54
                                )
                            )
                        }

                        Spacer()

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

                        Spacer()

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
                        .disabled(
                            !player.isPiPPossible
                        )

                        Spacer()
                    }
                    .font(
                        .title2
                    )

                    if case .failed(
                        let message
                    ) =
                        player.state {
                        Text(
                            message
                        )
                        .foregroundStyle(
                            .red
                        )
                        .font(
                            .footnote
                        )
                    }
                }
                .padding(
                    .horizontal
                )

                Spacer(
                    minLength:
                        0
                )
            }
            .navigationTitle(
                "Redare"
            )
            .navigationBarTitleDisplayMode(
                .inline
            )
            .toolbar {
                ToolbarItem(
                    placement:
                        .topBarTrailing
                ) {
                    Button(
                        "Închide"
                    ) {
                        dismiss()
                    }
                }
            }
        }
        .presentationDragIndicator(
            .visible
        )
    }
}

struct V9SettingsSummaryView:
    View
{
    let endpoint:
        String

    let openSettings:
        () -> Void

    var body: some View {
        NavigationStack {
            Form {
                Section(
                    "YoutubeVcd"
                ) {
                    Text(
                        "Home, Search, canale și rezolvarea streamurilor rulează direct pe iPhone. Playerul persistent, background audio, lock-screen controls și Picture in Picture folosesc același motor MPV."
                    )
                }

                Section(
                    "Fallback opțional"
                ) {
                    LabeledContent(
                        "VcdResolver"
                    ) {
                        Text(
                            endpoint.isEmpty
                                ? "Dezactivat"
                                : endpoint
                        )
                        .lineLimit(
                            1
                        )
                    }

                    Button(
                        endpoint.isEmpty
                            ? "Adaugă fallback resolver"
                            : "Configurează fallback resolver"
                    ) {
                        openSettings()
                    }

                    Text(
                        "Resolverul extern nu este necesar pentru folosirea normală. Este utilizat doar dacă rezolvarea nativă a unui videoclip eșuează."
                    )
                    .font(
                        .footnote
                    )
                    .foregroundStyle(
                        .secondary
                    )
                }
            }
            .navigationTitle(
                "Setări"
            )
        }
    }
}

struct V9ResolverSettingsView:
    View
{
    @Binding
    var endpoint:
        String

    @Binding
    var resolverToken:
        String

    let resolver:
        VcdResolverClient

    @Environment(\.dismiss)
    private var dismiss

    @State
    private var checking =
        false

    @State
    private var status =
        "Opțional. Lasă gol pentru funcționare complet nativă."

    @State
    private var statusOK =
        false

    var body: some View {
        NavigationStack {
            Form {
                Section(
                    "Fallback VcdResolver"
                ) {
                    TextField(
                        "http://192.168.1.50:8085",
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

                    SecureField(
                        "Token (doar pentru HTTPS public)",
                        text:
                            $resolverToken
                    )
                    .textInputAutocapitalization(
                        .never
                    )
                    .autocorrectionDisabled()

                    Button {
                        check()
                    } label: {
                        if checking {
                            ProgressView()
                        } else {
                            Text(
                                "Testează conexiunea"
                            )
                        }
                    }
                    .disabled(
                        checking ||
                        endpoint
                            .trimmingCharacters(
                                in:
                                    .whitespacesAndNewlines
                            )
                            .isEmpty
                    )

                    Label(
                        status,
                        systemImage:
                            statusOK
                                ? "checkmark.circle.fill"
                                : "info.circle"
                    )
                    .foregroundStyle(
                        statusOK
                            ? .green
                            : .secondary
                    )
                }

                Section(
                    "Când îl folosești"
                ) {
                    Text(
                        "YoutubeVcd încearcă întotdeauna mai întâi rezolvarea nativă pe iPhone. Acest endpoint este fallback."
                    )

                    Text(
                        "Dacă fallback-ul rulează pe PC, folosește IP-ul LAN al PC-ului, de exemplu http://192.168.1.50:8085."
                    )
                    .font(
                        .caption
                    )
                }
            }
            .navigationTitle(
                "Fallback resolver"
            )
            .toolbar {
                ToolbarItem(
                    placement:
                        .confirmationAction
                ) {
                    Button(
                        "Gata"
                    ) {
                        dismiss()
                    }
                }
            }
        }
    }

    private func check() {
        guard !checking
        else {
            return
        }

        checking =
            true

        statusOK =
            false

        Task {
            defer {
                Task {
                    @MainActor in

                    checking =
                        false
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
                    statusOK =
                        health.ok

                    status =
                        "Conectat • \(health.version)"
                }
            } catch {
                await MainActor.run {
                    status =
                        error.localizedDescription
                }
            }
        }
    }
}
