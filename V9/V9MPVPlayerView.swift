import SwiftUI
import UIKit

struct V9MPVPlayerView:
    UIViewRepresentable
{
    @ObservedObject
    var service:
        V9PlayerService

    func makeUIView(
        context: Context
    ) -> V9MPVRenderView {
        let view =
            V9MPVRenderView()

        service.attach(
            renderView:
                view
        )

        return view
    }

    func updateUIView(
        _ uiView:
            V9MPVRenderView,
        context: Context
    ) {}
}
