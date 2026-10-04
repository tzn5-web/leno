import SwiftUI

struct RootView: View {
    var body: some View {
        TabView {
            NavigationStack {
                HomeView()
            }
            .tabItem {
                Label("Home", systemImage: "house")
            }

            NavigationStack {
                SearchView()
            }
            .tabItem {
                Label("Search", systemImage: "magnifyingglass")
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

private struct SearchView: View {
    var body: some View {
        ContentUnavailableView(
            "Search provider not connected",
            systemImage: "magnifyingglass",
            description: Text("The player is ready. A lawful media provider can be connected here without changing playback architecture.")
        )
        .navigationTitle("Search")
    }
}

private struct LibraryView: View {
    var body: some View {
        ContentUnavailableView(
            "Library is empty",
            systemImage: "rectangle.stack",
            description: Text("Saved and recent items will appear here.")
        )
        .navigationTitle("Library")
    }
}
