import SwiftUI

struct RootView: View {
    @StateObject private var playback =
        NativePlaybackController()

    var body: some View {
        YouTubeView(playback: playback)
    }
}
