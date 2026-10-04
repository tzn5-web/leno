import SwiftUI

struct RootView: View {
    var body: some View {
        TabView {
            NavigationStack {
                HomeView()
            }
            .tabItem {
                Label("Player", systemImage: "play.rectangle")
            }

            NavigationStack {
                YouTubeBrowserView()
            }
            .tabItem {
                Label("YouTube", systemImage: "play.square")
            }

            NavigationStack {
                LibraryView()
            }
            .tabItem {
                Label("Library", systemImage: "rectangle.stack")
            }
        }
    }
}

private struct LibraryView: View {
    var body: some View {
        ContentUnavailableView(
            "Library is empty",
            systemImage: "rectangle.stack",
            description: Text("Saved and recent native-player items will appear here.")
        )
        .navigationTitle("Library")
    }
}
