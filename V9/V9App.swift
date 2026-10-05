import SwiftUI

@main
struct YoutubeVcdV9App: App {
    @StateObject private var player =
        V9PlayerService()

    var body: some Scene {
        WindowGroup {
            V9ClientRootView()
                .environmentObject(
                    player
                )
        }
    }
}
