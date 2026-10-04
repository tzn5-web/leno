import SwiftUI

struct HomeView: View {
    @EnvironmentObject private var playerModel: PlayerModel
    @State private var urlText = ""

    var body: some View {
        List {
            Section("Player") {
                TextField("Direct HTTPS media URL", text: $urlText)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.URL)
                    .autocorrectionDisabled()

                Button {
                    playerModel.load(urlString: urlText)
                } label: {
                    Label("Load media", systemImage: "play.fill")
                }
                .disabled(URL(string: urlText)?.scheme?.hasPrefix("http") != true)
            }

            if playerModel.hasItem {
                Section {
                    PlayerView(player: playerModel.player)
                        .frame(minHeight: 220)
                        .listRowInsets(EdgeInsets())
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
                }
            }

            Section("Design") {
                Label("Background audio", systemImage: "waveform")
                Label("Lock Screen controls", systemImage: "lock")
                Label("Picture in Picture", systemImage: "pip")
                Label("No analytics or ad SDKs", systemImage: "hand.raised")
            }
        }
        .navigationTitle("Leno")
    }
}
