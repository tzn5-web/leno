import SwiftUI

struct YouTubeView: View {
    @StateObject private var session = YouTubeSession()

    var body: some View {
        ZStack(alignment: .top) {
            YouTubeWebView(session: session)
                .ignoresSafeArea()

            if shouldShowStatus {
                statusPill
                    .padding(.top, 8)
            }

            if case .failed(let message) = session.state {
                failureOverlay(message: message)
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            if session.isPlaying {
                mediaBar
            }
        }
    }

    private var shouldShowStatus: Bool {
        switch session.state {
        case .loading, .recovering:
            return true
        default:
            return false
        }
    }

    @ViewBuilder
    private var statusPill: some View {
        switch session.state {
        case .loading:
            Label("Loading YouTube", systemImage: "arrow.triangle.2.circlepath")
                .statusPill()
        case .recovering(let attempt):
            Label("Recovering \(attempt)/3", systemImage: "wrench.and.screwdriver")
                .statusPill()
        default:
            EmptyView()
        }
    }

    private var mediaBar: some View {
        HStack(spacing: 18) {
            Button {
                session.seek(by: -15)
            } label: {
                Image(systemName: "gobackward.15")
            }

            Button {
                session.togglePlayback()
            } label: {
                Image(systemName: session.isPlaying ? "pause.fill" : "play.fill")
            }

            Button {
                session.seek(by: 15)
            } label: {
                Image(systemName: "goforward.15")
            }

            Spacer()

            Button {
                session.requestPictureInPicture()
            } label: {
                Image(systemName: "pip")
            }
        }
        .font(.title3)
        .padding(.horizontal, 18)
        .frame(height: 50)
        .background(.ultraThinMaterial)
    }

    private func failureOverlay(message: String) -> some View {
        VStack(spacing: 14) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)

            Text("YouTube did not load correctly")
                .font(.headline)

            Text(message)
                .font(.footnote)
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)

            Button("Reload") {
                session.reloadFromHome()
            }
            .buttonStyle(.borderedProminent)
        }
        .padding(24)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 18))
        .padding(24)
    }
}

private extension View {
    func statusPill() -> some View {
        self
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 12)
            .padding(.vertical, 7)
            .background(.regularMaterial, in: Capsule())
    }
}
