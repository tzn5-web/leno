import SwiftUI

struct HomeView: View {
    @EnvironmentObject private var playerModel: PlayerModel
    @State private var urlText = ""

    var body: some View {
        List {
            Section("Player") {
                TextField("Direct HTTP(S) media URL", text: $urlText)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.URL)
                    .autocorrectionDisabled()
                    .onSubmit(load)

                Button(action: load) {
                    Label("Load media", systemImage: "play.fill")
                }
                .disabled(!isValidURL)
            }

            if playerModel.hasItem {
                Section {
                    PlayerView(player: playerModel.player)
                        .frame(minHeight: 220)
                        .listRowInsets(EdgeInsets())
                }

                Section("Status") {
                    LabeledContent("Playback", value: playerModel.phase.label)

                    if let error = playerModel.errorMessage {
                        Text(error)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }

                    if case .failed = playerModel.phase {
                        Button {
                            playerModel.retry()
                        } label: {
                            Label("Retry", systemImage: "arrow.clockwise")
                        }
                    }
                }

                Section("Playback") {
                    HStack {
                        Button {
                            playerModel.seek(by: -15)
                        } label: {
                            Label("Back 15", systemImage: "gobackward.15")
                        }

                        Spacer()

                        Button {
                            playerModel.togglePlayback()
                        } label: {
                            Label(
                                playerModel.isPlaying ? "Pause" : "Play",
                                systemImage: playerModel.isPlaying ? "pause.fill" : "play.fill"
                            )
                        }

                        Spacer()

                        Button {
                            playerModel.seek(by: 15)
                        } label: {
                            Label("Forward 15", systemImage: "goforward.15")
                        }
                    }
                    .buttonStyle(.borderless)

                    Button(role: .destructive) {
                        playerModel.clear()
                        urlText = ""
                    } label: {
                        Label("Close media", systemImage: "xmark.circle")
                    }
                }
            }

            Section("Core") {
                Label("Background audio", systemImage: "waveform")
                Label("Lock Screen controls", systemImage: "lock")
                Label("Picture in Picture", systemImage: "pip")
                Label("Automatic playback recovery", systemImage: "arrow.triangle.2.circlepath")
                Label("No analytics or third-party ad SDKs", systemImage: "hand.raised")
            }
        }
        .navigationTitle("Leno")
    }

    private var isValidURL: Bool {
        guard let url = URL(string: urlText.trimmingCharacters(in: .whitespacesAndNewlines)),
              let scheme = url.scheme?.lowercased() else { return false }
        return scheme == "http" || scheme == "https"
    }

    private func load() {
        guard isValidURL else { return }
        playerModel.load(urlString: urlText)
    }
}