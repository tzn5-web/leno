import AVKit
import SwiftUI

struct NativePlayerView: View {
    @ObservedObject var controller: NativePlaybackController

    var body: some View {
        ZStack {
            Color.black
                .ignoresSafeArea()

            NativeAVPlayerController(
                player: controller.player
            )
            .ignoresSafeArea()

            switch controller.state {
            case .resolving(let message):
                loadingOverlay(message: message)

            case .failed(let message):
                failureOverlay(message: message)

            case .idle, .ready:
                EmptyView()
            }

            VStack {
                HStack {
                    Button {
                        controller.close()
                    } label: {
                        Image(systemName: "xmark")
                            .font(
                                .system(
                                    size: 16,
                                    weight: .bold
                                )
                            )
                            .foregroundStyle(.white)
                            .frame(width: 42, height: 42)
                            .background(
                                .black.opacity(0.58),
                                in: Circle()
                            )
                    }
                    .padding(.leading, 14)
                    .padding(.top, 8)

                    Spacer()
                }

                Spacer()
            }
        }
        .statusBarHidden(true)
        .preferredColorScheme(.dark)
    }

    private func loadingOverlay(
        message: String
    ) -> some View {
        VStack(spacing: 14) {
            ProgressView()
                .tint(.white)
                .controlSize(.large)

            Text(message)
                .font(.headline)
                .foregroundStyle(.white)

            if !controller.sourceLabel.isEmpty {
                Text(controller.sourceLabel)
                    .font(.caption)
                    .foregroundStyle(
                        .white.opacity(0.65)
                    )
            }
        }
        .padding(24)
        .background(
            .black.opacity(0.72),
            in: RoundedRectangle(
                cornerRadius: 18,
                style: .continuous
            )
        )
    }

    private func failureOverlay(
        message: String
    ) -> some View {
        VStack(spacing: 10) {
            Image(
                systemName:
                    "arrow.uturn.backward.circle"
            )
            .font(.largeTitle)

            Text("Revin la playerul YouTube")
                .font(.headline)

            Text(message)
                .font(.caption)
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)
        }
        .foregroundStyle(.white)
        .padding(22)
        .frame(maxWidth: 330)
        .background(
            .black.opacity(0.78),
            in: RoundedRectangle(
                cornerRadius: 18,
                style: .continuous
            )
        )
    }
}

private struct NativeAVPlayerController:
    UIViewControllerRepresentable
{
    let player: AVPlayer

    func makeUIViewController(
        context: Context
    ) -> AVPlayerViewController {
        let controller = AVPlayerViewController()

        controller.player = player
        controller.showsPlaybackControls = true
        controller.videoGravity = .resizeAspect
        controller.allowsPictureInPicturePlayback = true
        controller.canStartPictureInPictureAutomaticallyFromInline = true

        return controller
    }

    func updateUIViewController(
        _ uiViewController: AVPlayerViewController,
        context: Context
    ) {
        if uiViewController.player !== player {
            uiViewController.player = player
        }
    }
}
