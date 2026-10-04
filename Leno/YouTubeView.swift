import SwiftUI

struct YouTubeView: View {
    @StateObject private var session =
        YouTubeSession()

    @ObservedObject var playback:
        NativePlaybackController

    var body: some View {
        ZStack {
            YouTubeWebView(session: session)
                .ignoresSafeArea(
                    .container,
                    edges: .bottom
                )

            if session.state == .idle ||
               session.isLoading {
                HomeLoadingView()
                    .transition(.opacity)
                    .allowsHitTesting(false)
            }

            if case .recovering(let attempt) =
                session.state {
                recoveryPill(attempt: attempt)
            }

            if case .failed(let message) =
                session.state {
                failureOverlay(
                    message: message
                )
            }
        }
        .background(Color(.systemBackground))
        .onAppear {
            session.onVideoSelected = {
                videoID in
                playback.open(videoID: videoID)
            }

            playback.onWebFallback = {
                videoID in
                session.loadVideoInWeb(
                    videoID: videoID
                )
            }
        }
        .fullScreenCover(
            isPresented: Binding(
                get: {
                    playback.isPresented
                },
                set: { presented in
                    if !presented {
                        playback.close()
                    }
                }
            )
        ) {
            NativePlayerView(
                controller: playback
            )
        }
    }

    private func recoveryPill(
        attempt: Int
    ) -> some View {
        VStack {
            HStack(spacing: 8) {
                ProgressView()
                    .controlSize(.small)

                Text(
                    "Reconectare… \(attempt)/3"
                )
                .font(
                    .caption.weight(.semibold)
                )
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 9)
            .background(
                .ultraThinMaterial,
                in: Capsule()
            )
            .shadow(radius: 12, y: 5)

            Spacer()
        }
        .padding(.top, 10)
    }

    private func failureOverlay(
        message: String
    ) -> some View {
        ZStack {
            Color(.systemBackground)
                .ignoresSafeArea()

            VStack(spacing: 18) {
                Image(
                    systemName:
                        "wifi.exclamationmark"
                )
                .font(
                    .system(
                        size: 42,
                        weight: .semibold
                    )
                )
                .symbolRenderingMode(
                    .hierarchical
                )

                VStack(spacing: 6) {
                    Text(
                        "YouTube nu s-a încărcat"
                    )
                    .font(
                        .title3.weight(.bold)
                    )

                    Text(message)
                        .font(.footnote)
                        .foregroundStyle(
                            .secondary
                        )
                        .multilineTextAlignment(
                            .center
                        )
                        .lineLimit(3)
                }

                Button {
                    session.reloadFromHome()
                } label: {
                    Label(
                        "Reîncearcă",
                        systemImage:
                            "arrow.clockwise"
                    )
                    .font(.headline)
                    .frame(
                        maxWidth: .infinity
                    )
                    .padding(
                        .vertical,
                        12
                    )
                }
                .buttonStyle(
                    .borderedProminent
                )
                .tint(.red)
            }
            .padding(24)
            .frame(maxWidth: 360)
        }
    }
}

private struct HomeLoadingView: View {
    var body: some View {
        ZStack {
            Color(.systemBackground)
                .ignoresSafeArea()

            ScrollView {
                VStack(spacing: 22) {
                    loadingHeader

                    ForEach(
                        0..<3,
                        id: \.self
                    ) { _ in
                        loadingCard
                    }
                }
                .padding(.bottom, 80)
            }
            .scrollDisabled(true)
        }
    }

    private var loadingHeader: some View {
        HStack(spacing: 10) {
            RoundedRectangle(
                cornerRadius: 7,
                style: .continuous
            )
            .fill(.red)
            .frame(
                width: 34,
                height: 24
            )
            .overlay {
                Image(
                    systemName:
                        "play.fill"
                )
                .font(
                    .system(
                        size: 10,
                        weight: .black
                    )
                )
                .foregroundStyle(.white)
            }

            Text("YoutubeVcd")
                .font(
                    .system(
                        size: 20,
                        weight: .bold,
                        design: .rounded
                    )
                )

            Spacer()

            Circle()
                .fill(
                    .secondary.opacity(0.14)
                )
                .frame(
                    width: 34,
                    height: 34
                )
                .overlay {
                    Image(
                        systemName:
                            "magnifyingglass"
                    )
                    .font(
                        .system(
                            size: 15,
                            weight: .semibold
                        )
                    )
                    .foregroundStyle(
                        .secondary
                    )
                }
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
    }

    private var loadingCard: some View {
        VStack(
            alignment: .leading,
            spacing: 12
        ) {
            RoundedRectangle(
                cornerRadius: 14,
                style: .continuous
            )
            .fill(
                .secondary.opacity(0.12)
            )
            .aspectRatio(
                16 / 9,
                contentMode: .fit
            )

            HStack(
                alignment: .top,
                spacing: 12
            ) {
                Circle()
                    .fill(
                        .secondary.opacity(0.12)
                    )
                    .frame(
                        width: 38,
                        height: 38
                    )

                VStack(
                    alignment: .leading,
                    spacing: 7
                ) {
                    RoundedRectangle(
                        cornerRadius: 5
                    )
                    .fill(
                        .secondary.opacity(0.12)
                    )
                    .frame(height: 13)

                    RoundedRectangle(
                        cornerRadius: 5
                    )
                    .fill(
                        .secondary.opacity(0.09)
                    )
                    .frame(
                        width: 180,
                        height: 11
                    )
                }

                Spacer()
            }
        }
        .padding(.horizontal, 12)
    }
}
