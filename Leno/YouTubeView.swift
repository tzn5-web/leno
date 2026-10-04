import SwiftUI

struct YouTubeView: View {
    @StateObject private var session = YouTubeSession()
    @State private var searchText = ""
    @FocusState private var searchFocused: Bool
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        VStack(spacing: 0) {
            browserBar

            if session.isLoading {
                ProgressView(value: session.progress)
                    .progressViewStyle(.linear)
                    .frame(height: 2)
            }

            ZStack(alignment: .top) {
                YouTubeWebView(session: session)

                if case .recovering(let attempt) = session.state {
                    Label("Recovering \(attempt)/3", systemImage: "wrench.and.screwdriver")
                        .statusPill()
                        .padding(.top, 8)
                }

                if case .failed(let message) = session.state {
                    failureOverlay(message: message)
                }
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            if session.hasMedia {
                mediaBar
            }
        }
        .onChange(of: scenePhase) { _, newPhase in
            switch newPhase {
            case .active:
                session.applicationDidBecomeActive()
            case .background:
                session.applicationDidEnterBackground()
            default:
                break
            }
        }
    }

    private var browserBar: some View {
        HStack(spacing: 10) {
            Button {
                session.goBack()
            } label: {
                Image(systemName: "chevron.left")
            }
            .disabled(!session.canGoBack)
            .accessibilityLabel("Back")

            Button {
                session.goForward()
            } label: {
                Image(systemName: "chevron.right")
            }
            .disabled(!session.canGoForward)
            .accessibilityLabel("Forward")

            TextField("Search YouTube", text: $searchText)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .submitLabel(.search)
                .focused($searchFocused)
                .textFieldStyle(.roundedBorder)
                .onSubmit {
                    submitSearch()
                }

            Button {
                session.loadHome()
                searchFocused = false
            } label: {
                Image(systemName: "house.fill")
            }
            .accessibilityLabel("Home")

            Button {
                session.reload()
            } label: {
                Image(systemName: "arrow.clockwise")
            }
            .accessibilityLabel("Reload")
        }
        .font(.body.weight(.semibold))
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(.thinMaterial)
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

            Text(session.title)
                .font(.caption)
                .lineLimit(1)
                .foregroundStyle(.secondary)

            Spacer(minLength: 8)

            Button {
                session.requestPictureInPicture()
            } label: {
                Image(systemName: "pip")
            }
        }
        .font(.title3)
        .padding(.horizontal, 16)
        .frame(height: 52)
        .background(.ultraThinMaterial)
    }

    private func submitSearch() {
        let query = searchText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return }
        session.search(query)
        searchFocused = false
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
