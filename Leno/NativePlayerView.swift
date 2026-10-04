import AVFoundation
import SwiftUI
import UIKit

struct NativePlayerView: View {
    @ObservedObject var controller: NativePlaybackController
    @State private var controlsVisible = true

    var body: some View {
        ZStack {
            Color.black
                .ignoresSafeArea()

            NativePlayerSurface(controller: controller)
                .ignoresSafeArea()

            topAndBottomGradients

            switch controller.state {
            case .idle:
                EmptyView()

            case .resolving:
                resolvingOverlay

            case .ready:
                if controlsVisible {
                    controlsOverlay
                        .transition(.opacity)
                }

            case .failed(let message):
                failureOverlay(message: message)
            }
        }
        .contentShape(Rectangle())
        .onTapGesture {
            guard controller.state == .ready else { return }

            withAnimation(.easeInOut(duration: 0.18)) {
                controlsVisible.toggle()
            }
        }
        .statusBarHidden(true)
        .preferredColorScheme(.dark)
    }

    private var topAndBottomGradients: some View {
        VStack(spacing: 0) {
            LinearGradient(
                colors: [.black.opacity(0.72), .clear],
                startPoint: .top,
                endPoint: .bottom
            )
            .frame(height: 130)

            Spacer()

            LinearGradient(
                colors: [.clear, .black.opacity(0.78)],
                startPoint: .top,
                endPoint: .bottom
            )
            .frame(height: 190)
        }
        .ignoresSafeArea()
        .allowsHitTesting(false)
    }

    private var resolvingOverlay: some View {
        VStack(spacing: 14) {
            ProgressView()
                .tint(.white)
                .scaleEffect(1.15)

            Text("Pregătesc redarea")
                .font(.headline)

            Text("Se selectează streamul nativ optim…")
                .font(.caption)
                .foregroundStyle(.white.opacity(0.64))
        }
        .foregroundStyle(.white)
    }

    private var controlsOverlay: some View {
        VStack {
            HStack(spacing: 12) {
                Button {
                    controller.close()
                } label: {
                    Image(systemName: "xmark")
                        .font(.system(size: 16, weight: .bold))
                        .frame(width: 42, height: 42)
                        .background(.ultraThinMaterial, in: Circle())
                }

                Text(controller.title)
                    .font(.headline)
                    .lineLimit(1)

                Spacer()

                Button {
                    controller.requestPictureInPicture()
                } label: {
                    Image(
                        systemName: controller.isPiPActive
                            ? "pip.exit"
                            : "pip.enter"
                    )
                    .font(.system(size: 18, weight: .semibold))
                    .frame(width: 42, height: 42)
                    .background(.ultraThinMaterial, in: Circle())
                }
                .disabled(!controller.isPiPPossible)
                .opacity(controller.isPiPPossible ? 1 : 0.45)
            }
            .padding(.horizontal, 16)
            .padding(.top, 12)

            Spacer()

            VStack(spacing: 14) {
                Slider(
                    value: Binding(
                        get: { controller.currentTime },
                        set: { controller.seek(to: $0) }
                    ),
                    in: 0...max(controller.duration, 1)
                )
                .tint(.red)

                HStack {
                    Text(timeString(controller.currentTime))

                    Spacer()

                    Text(timeString(controller.duration))
                }
                .font(.caption.monospacedDigit())
                .foregroundStyle(.white.opacity(0.72))

                HStack(spacing: 28) {
                    Button {
                        controller.seek(by: -15)
                    } label: {
                        Image(systemName: "gobackward.15")
                    }

                    Button {
                        controller.togglePlayback()
                    } label: {
                        Image(
                            systemName: controller.isPlaying
                                ? "pause.fill"
                                : "play.fill"
                        )
                        .font(.system(size: 28, weight: .semibold))
                        .frame(width: 62, height: 62)
                        .background(.white, in: Circle())
                        .foregroundStyle(.black)
                    }

                    Button {
                        controller.seek(by: 15)
                    } label: {
                        Image(systemName: "goforward.15")
                    }
                }
                .font(.system(size: 24, weight: .semibold))
            }
            .padding(18)
            .background(
                .ultraThinMaterial,
                in: RoundedRectangle(
                    cornerRadius: 28,
                    style: .continuous
                )
            )
            .padding(.horizontal, 14)
            .padding(.bottom, 12)
        }
        .foregroundStyle(.white)
        .buttonStyle(.plain)
    }

    private func failureOverlay(message: String) -> some View {
        VStack(spacing: 18) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 42))
                .symbolRenderingMode(.hierarchical)

            VStack(spacing: 6) {
                Text("Clipul nu a pornit")
                    .font(.title3.weight(.bold))

                Text(message)
                    .font(.footnote)
                    .foregroundStyle(.white.opacity(0.68))
                    .multilineTextAlignment(.center)
                    .lineLimit(4)
            }

            HStack(spacing: 12) {
                Button("Închide") {
                    controller.close()
                }
                .buttonStyle(.bordered)

                Button("Reîncearcă") {
                    controller.retry()
                }
                .buttonStyle(.borderedProminent)
                .tint(.red)
            }
        }
        .foregroundStyle(.white)
        .padding(28)
        .frame(maxWidth: 380)
    }

    private func timeString(_ seconds: Double) -> String {
        guard seconds.isFinite, seconds >= 0 else { return "0:00" }

        let total = Int(seconds.rounded(.down))
        let hours = total / 3600
        let minutes = (total % 3600) / 60
        let secs = total % 60

        if hours > 0 {
            return String(format: "%d:%02d:%02d", hours, minutes, secs)
        }

        return String(format: "%d:%02d", minutes, secs)
    }
}

private struct NativePlayerSurface: UIViewRepresentable {
    @ObservedObject var controller: NativePlaybackController

    func makeUIView(context: Context) -> PlayerSurfaceUIView {
        let view = PlayerSurfaceUIView()
        controller.attach(playerLayer: view.playerLayer)
        return view
    }

    func updateUIView(
        _ uiView: PlayerSurfaceUIView,
        context: Context
    ) {
        uiView.playerLayer.player = controller.player
    }
}

private final class PlayerSurfaceUIView: UIView {
    override class var layerClass: AnyClass {
        AVPlayerLayer.self
    }

    var playerLayer: AVPlayerLayer {
        layer as! AVPlayerLayer
    }

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = .black
        playerLayer.videoGravity = .resizeAspect
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        backgroundColor = .black
        playerLayer.videoGravity = .resizeAspect
    }
}
