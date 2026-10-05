import SwiftUI
import UIKit

@MainActor
final class V9MPVHostView:
    UIView
{
    func install(
        _ renderView:
            V9MPVRenderView
    ) {
        if renderView.superview !==
            self {
            renderView
                .removeFromSuperview()

            renderView.frame =
                bounds

            renderView.autoresizingMask = [
                .flexibleWidth,
                .flexibleHeight
            ]

            addSubview(
                renderView
            )
        } else {
            renderView.frame =
                bounds
        }
    }

    override func layoutSubviews() {
        super.layoutSubviews()

        subviews
            .compactMap {
                $0 as?
                    V9MPVRenderView
            }
            .forEach {
                $0.frame =
                    bounds
            }
    }
}

struct V9MPVPlayerView:
    UIViewRepresentable
{
    @ObservedObject
    var service:
        V9PlayerService

    final class Coordinator {
        let service:
            V9PlayerService

        let hostToken =
            UUID()

        init(
            service:
                V9PlayerService
        ) {
            self.service =
                service
        }
    }

    func makeCoordinator()
        -> Coordinator
    {
        Coordinator(
            service:
                service
        )
    }

    func makeUIView(
        context:
            Context
    ) -> V9MPVHostView {
        let host =
            V9MPVHostView()

        host.install(
            service
                .persistentRenderSurface()
        )

        service
            .setRenderSurfaceHosted(
                true,
                hostToken:
                    context
                        .coordinator
                        .hostToken
            )

        return host
    }

    func updateUIView(
        _ uiView:
            V9MPVHostView,
        context:
            Context
    ) {
        uiView.install(
            service
                .persistentRenderSurface()
        )

        service
            .setRenderSurfaceHosted(
                true,
                hostToken:
                    context
                        .coordinator
                        .hostToken
            )
    }

    static func dismantleUIView(
        _ uiView:
            V9MPVHostView,
        coordinator:
            Coordinator
    ) {
        coordinator
            .service
            .setRenderSurfaceHosted(
                false,
                hostToken:
                    coordinator
                        .hostToken
            )
    }
}
