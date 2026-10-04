import SwiftUI

struct RootView: View {
    var body: some View {
        TabView {
            YouTubeView()
                .tabItem {
                    Label("YouTube", systemImage: "play.rectangle.fill")
                }

            NavigationStack {
                HomeView()
            }
            .tabItem {
                Label("Direct", systemImage: "waveform")
            }

            NavigationStack {
                AboutView()
            }
            .tabItem {
                Label("About", systemImage: "info.circle")
            }
        }
    }
}

private struct AboutView: View {
    var body: some View {
        List {
            Section("Leno") {
                Label("YouTube ad filtering enabled", systemImage: "shield.checkered")
                Label("Background audio", systemImage: "waveform")
                Label("Lock Screen controls", systemImage: "lock")
                Label("Picture in Picture", systemImage: "pip")
            }

            Section("Reliability") {
                Text("Automatic retry is enabled for navigation and WebKit process failures.")
                Text("A native direct-media player remains available as a fallback and diagnostic path.")
            }
        }
        .navigationTitle("About")
    }
}
