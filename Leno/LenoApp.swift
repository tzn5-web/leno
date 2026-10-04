import SwiftUI

@main
struct LenoApp: App {
    @StateObject private var playerModel = PlayerModel()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(playerModel)
        }
    }
}
