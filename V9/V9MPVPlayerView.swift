import SwiftUI
import UIKit

struct V9MPVPlayerView:
    UIViewControllerRepresentable
{
    @ObservedObject
    var service:
        V9PlayerService

    func makeUIViewController(
        context: Context
    ) -> UIViewController {
        V9MPVViewController(
            service:
                service
        )
    }

    func updateUIViewController(
        _ uiViewController:
            UIViewController,
        context: Context
    ) {}
}

final class V9MPVViewController:
    UIViewController
{
    private let service:
        V9PlayerService

    private let metalLayer =
        V9MetalLayer()

    init(
        service:
            V9PlayerService
    ) {
        self.service =
            service

        super.init(
            nibName:
                nil,
            bundle:
                nil
        )
    }

    @available(
        *,
        unavailable
    )
    required init?(
        coder: NSCoder
    ) {
        nil
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        view.backgroundColor =
            .black

        metalLayer.frame =
            view.bounds

        metalLayer.contentsScale =
            UIScreen.main
                .nativeScale

        metalLayer.framebufferOnly =
            true

        metalLayer.backgroundColor =
            UIColor.black
                .cgColor

        view.layer.addSublayer(
            metalLayer
        )

        service.attach(
            metalLayer:
                metalLayer
        )
    }

    override func viewDidLayoutSubviews() {
        super
            .viewDidLayoutSubviews()

        metalLayer.frame =
            view.bounds

        metalLayer.drawableSize =
            CGSize(
                width:
                    max(
                        2,
                        view.bounds.width *
                        metalLayer.contentsScale
                    ),
                height:
                    max(
                        2,
                        view.bounds.height *
                        metalLayer.contentsScale
                    )
            )
    }
}
