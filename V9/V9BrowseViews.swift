import SwiftUI

@MainActor
struct V9HomeFeedView:
    View
{
    @ObservedObject
    var native:
        V9NativeYouTubeClient

    let play:
        (BrowseVideo) -> Void

    @State
    private var items:
        [BrowseVideo] = []

    @State
    private var loading =
        false

    @State
    private var loadingMore =
        false

    @State
    private var hasMore =
        false

    @State
    private var errorText:
        String?

    var body: some View {
        NavigationStack {
            Group {
                if loading &&
                   items.isEmpty {
                    ProgressView(
                        "Încarc YouTube…"
                    )
                } else if let errorText,
                          items.isEmpty {
                    ContentUnavailableView(
                        "Home indisponibil",
                        systemImage:
                            "exclamationmark.triangle",
                        description:
                            Text(
                                errorText
                            )
                    )
                } else {
                    V9VideoFeed(
                        items:
                            items,
                        native:
                            native,
                        play:
                            play,
                        hasMore:
                            hasMore,
                        loadingMore:
                            loadingMore,
                        loadMore:
                            loadMore
                    )
                    .refreshable {
                        await load(
                            reset:
                                true
                        )
                    }
                }
            }
            .navigationTitle(
                "YoutubeVcd"
            )
            .toolbar {
                ToolbarItem(
                    placement:
                        .topBarTrailing
                ) {
                    Button {
                        Task {
                            await load(
                                reset:
                                    true
                            )
                        }
                    } label: {
                        Image(
                            systemName:
                                "arrow.clockwise"
                        )
                    }
                    .disabled(
                        loading
                    )
                }
            }
            .task {
                if items.isEmpty {
                    await load(
                        reset:
                            true
                    )
                }
            }
        }
    }

    private func load(
        reset:
            Bool
    ) async {
        guard !loading
        else {
            return
        }

        loading =
            true

        errorText =
            nil

        defer {
            loading =
                false
        }

        do {
            let page =
                try await native
                    .home(
                        reset:
                            reset
                    )

            items =
                page.items

            hasMore =
                page.hasMore

            if items.isEmpty {
                errorText =
                    "YouTube nu a întors videoclipuri."
            }
        } catch {
            errorText =
                error.localizedDescription
        }
    }

    private func loadMore()
        async
    {
        guard hasMore,
              !loadingMore,
              !loading
        else {
            return
        }

        loadingMore =
            true

        defer {
            loadingMore =
                false
        }

        do {
            let page =
                try await native
                    .home(
                        reset:
                            false
                    )

            items =
                page.items

            hasMore =
                page.hasMore
        } catch {
            // Keep the already-loaded feed visible if a continuation fails.
            hasMore =
                true
        }
    }
}

@MainActor
struct V9SearchView:
    View
{
    @ObservedObject
    var native:
        V9NativeYouTubeClient

    let play:
        (BrowseVideo) -> Void

    @State
    private var query =
        ""

    @State
    private var items:
        [BrowseVideo] = []

    @State
    private var loading =
        false

    @State
    private var loadingMore =
        false

    @State
    private var hasMore =
        false

    @State
    private var errorText:
        String?

    var body: some View {
        NavigationStack {
            Group {
                if query
                    .trimmingCharacters(
                        in:
                            .whitespacesAndNewlines
                    )
                    .isEmpty &&
                   items.isEmpty {
                    ContentUnavailableView(
                        "Caută pe YouTube",
                        systemImage:
                            "magnifyingglass",
                        description:
                            Text(
                                "Scrie titlul, canalul sau subiectul dorit."
                            )
                    )
                } else if loading &&
                          items.isEmpty {
                    ProgressView(
                        "Caut…"
                    )
                } else if let errorText,
                          items.isEmpty {
                    ContentUnavailableView(
                        "Căutarea a eșuat",
                        systemImage:
                            "exclamationmark.triangle",
                        description:
                            Text(
                                errorText
                            )
                    )
                } else {
                    V9VideoFeed(
                        items:
                            items,
                        native:
                            native,
                        play:
                            play,
                        hasMore:
                            hasMore,
                        loadingMore:
                            loadingMore,
                        loadMore:
                            loadMore
                    )
                }
            }
            .navigationTitle(
                "Caută"
            )
            .searchable(
                text:
                    $query,
                placement:
                    .navigationBarDrawer(
                        displayMode:
                            .always
                    ),
                prompt:
                    "Caută pe YouTube"
            )
            .onSubmit(
                of:
                    .search
            ) {
                Task {
                    await search(
                        reset:
                            true
                    )
                }
            }
        }
    }

    private func search(
        reset:
            Bool
    ) async {
        let trimmed =
            query.trimmingCharacters(
                in:
                    .whitespacesAndNewlines
            )

        guard !loading,
              trimmed.count >=
                2
        else {
            return
        }

        loading =
            true

        errorText =
            nil

        defer {
            loading =
                false
        }

        do {
            let page =
                try await native
                    .search(
                        query:
                            trimmed,
                        reset:
                            reset
                    )

            items =
                page.items

            hasMore =
                page.hasMore

            if items.isEmpty {
                errorText =
                    "Niciun rezultat."
            }
        } catch {
            errorText =
                error.localizedDescription
        }
    }

    private func loadMore()
        async
    {
        guard hasMore,
              !loadingMore,
              !loading
        else {
            return
        }

        let trimmed =
            query.trimmingCharacters(
                in:
                    .whitespacesAndNewlines
            )

        guard trimmed.count >=
                2
        else {
            return
        }

        loadingMore =
            true

        defer {
            loadingMore =
                false
        }

        do {
            let page =
                try await native
                    .search(
                        query:
                            trimmed,
                        reset:
                            false
                    )

            items =
                page.items

            hasMore =
                page.hasMore
        } catch {
            hasMore =
                true
        }
    }
}

@MainActor
struct V9VideoFeed:
    View
{
    let items:
        [BrowseVideo]

    @ObservedObject
    var native:
        V9NativeYouTubeClient

    let play:
        (BrowseVideo) -> Void

    let hasMore:
        Bool

    let loadingMore:
        Bool

    let loadMore:
        () async -> Void

    var body: some View {
        ScrollView {
            LazyVStack(
                spacing:
                    22
            ) {
                ForEach(
                    items
                ) {
                    video in

                    V9VideoCard(
                        video:
                            video,
                        native:
                            native,
                        play:
                            play
                    )
                }

                if hasMore {
                    ProgressView()
                        .padding(
                            24
                        )
                        .onAppear {
                            guard !loadingMore
                            else {
                                return
                            }

                            Task {
                                await loadMore()
                            }
                        }
                }
            }
            .padding(
                .vertical,
                8
            )
        }
    }
}

@MainActor
struct V9VideoCard:
    View
{
    let video:
        BrowseVideo

    @ObservedObject
    var native:
        V9NativeYouTubeClient

    let play:
        (BrowseVideo) -> Void

    var body: some View {
        VStack(
            alignment:
                .leading,
            spacing:
                10
        ) {
            Button {
                play(
                    video
                )
            } label: {
                ZStack(
                    alignment:
                        .bottomTrailing
                ) {
                    AsyncImage(
                        url:
                            video.thumbnailURL
                    ) {
                        phase in

                        switch phase {
                        case .success(
                            let image
                        ):
                            image
                                .resizable()
                                .scaledToFill()

                        default:
                            Rectangle()
                                .fill(
                                    .quaternary
                                )
                                .overlay {
                                    Image(
                                        systemName:
                                            "play.rectangle.fill"
                                    )
                                    .font(
                                        .largeTitle
                                    )
                                    .foregroundStyle(
                                        .secondary
                                    )
                                }
                        }
                    }
                    .frame(
                        maxWidth:
                            .infinity
                    )
                    .aspectRatio(
                        16 / 9,
                        contentMode:
                            .fill
                    )
                    .clipped()

                    if video.isLive {
                        Text(
                            "LIVE"
                        )
                        .font(
                            .caption2
                                .bold()
                        )
                        .padding(
                            .horizontal,
                            6
                        )
                        .padding(
                            .vertical,
                            4
                        )
                        .background(
                            .red,
                            in:
                                RoundedRectangle(
                                    cornerRadius:
                                        4
                                )
                        )
                        .foregroundStyle(
                            .white
                        )
                        .padding(
                            8
                        )
                    } else if let duration =
                                video.duration,
                              duration >
                                0 {
                        Text(
                            V9VideoFormatting
                                .duration(
                                    duration
                                )
                        )
                        .font(
                            .caption2
                                .monospacedDigit()
                                .bold()
                        )
                        .padding(
                            .horizontal,
                            5
                        )
                        .padding(
                            .vertical,
                            3
                        )
                        .background(
                            .black
                                .opacity(
                                    0.75
                                ),
                            in:
                                RoundedRectangle(
                                    cornerRadius:
                                        4
                                )
                        )
                        .foregroundStyle(
                            .white
                        )
                        .padding(
                            8
                        )
                    }
                }
            }
            .buttonStyle(
                .plain
            )

            VStack(
                alignment:
                    .leading,
                spacing:
                    5
            ) {
                Button {
                    play(
                        video
                    )
                } label: {
                    Text(
                        video.title
                    )
                    .font(
                        .headline
                    )
                    .foregroundStyle(
                        .primary
                    )
                    .multilineTextAlignment(
                        .leading
                    )
                    .lineLimit(
                        2
                    )
                }
                .buttonStyle(
                    .plain
                )

                HStack(
                    spacing:
                        6
                ) {
                    if let channelID =
                            video.channelID,
                       !video.channel
                        .isEmpty {
                        NavigationLink {
                            V9ChannelView(
                                channelID:
                                    channelID,
                                initialTitle:
                                    video.channel,
                                native:
                                    native,
                                play:
                                    play
                            )
                        } label: {
                            Text(
                                video.channel
                            )
                        }
                    } else if !video
                        .channel
                        .isEmpty {
                        Text(
                            video.channel
                        )
                    }

                    if let viewsText =
                            video.viewCountText,
                       !viewsText
                        .isEmpty {
                        Text(
                            "•"
                        )

                        Text(
                            viewsText
                        )
                    } else if let views =
                                video.viewCount {
                        Text(
                            "•"
                        )

                        Text(
                            V9VideoFormatting
                                .views(
                                    views
                                )
                        )
                    }
                }
                .font(
                    .subheadline
                )
                .foregroundStyle(
                    .secondary
                )
            }
            .padding(
                .horizontal
            )
        }
    }
}

@MainActor
struct V9ChannelView:
    View
{
    let channelID:
        String

    let initialTitle:
        String

    @ObservedObject
    var native:
        V9NativeYouTubeClient

    let play:
        (BrowseVideo) -> Void

    @State
    private var title:
        String

    @State
    private var items:
        [BrowseVideo] = []

    @State
    private var loading =
        false

    @State
    private var loadingMore =
        false

    @State
    private var hasMore =
        false

    @State
    private var errorText:
        String?

    init(
        channelID:
            String,
        initialTitle:
            String,
        native:
            V9NativeYouTubeClient,
        play:
            @escaping (BrowseVideo) -> Void
    ) {
        self.channelID =
            channelID

        self.initialTitle =
            initialTitle

        self.native =
            native

        self.play =
            play

        _title =
            State(
                initialValue:
                    initialTitle
            )
    }

    var body: some View {
        Group {
            if loading &&
               items.isEmpty {
                ProgressView(
                    "Încarc canalul…"
                )
            } else if let errorText,
                      items.isEmpty {
                ContentUnavailableView(
                    "Canal indisponibil",
                    systemImage:
                        "exclamationmark.triangle",
                    description:
                        Text(
                            errorText
                        )
                )
            } else {
                V9VideoFeed(
                    items:
                        items,
                    native:
                        native,
                    play:
                        play,
                    hasMore:
                        hasMore,
                    loadingMore:
                        loadingMore,
                    loadMore:
                        loadMore
                )
            }
        }
        .navigationTitle(
            title
        )
        .navigationBarTitleDisplayMode(
            .inline
        )
        .task {
            if items.isEmpty {
                await load(
                    reset:
                        true
                )
            }
        }
    }

    private func load(
        reset:
            Bool
    ) async {
        guard !loading
        else {
            return
        }

        loading =
            true

        errorText =
            nil

        defer {
            loading =
                false
        }

        do {
            let page =
                try await native
                    .channel(
                        channelID:
                            channelID,
                        reset:
                            reset
                    )

            title =
                page.title

            items =
                page.items

            hasMore =
                page.hasMore
        } catch {
            errorText =
                error.localizedDescription
        }
    }

    private func loadMore()
        async
    {
        guard hasMore,
              !loadingMore,
              !loading
        else {
            return
        }

        loadingMore =
            true

        defer {
            loadingMore =
                false
        }

        do {
            let page =
                try await native
                    .channel(
                        channelID:
                            channelID,
                        reset:
                            false
                    )

            title =
                page.title

            items =
                page.items

            hasMore =
                page.hasMore
        } catch {
            hasMore =
                true
        }
    }
}

enum V9VideoFormatting
{
    static func duration(
        _ seconds:
            Double
    ) -> String {
        let total =
            max(
                0,
                Int(
                    seconds.rounded()
                )
            )

        let hours =
            total /
            3600

        let minutes =
            (
                total %
                3600
            ) /
            60

        let remaining =
            total %
            60

        if hours >
            0 {
            return String(
                format:
                    "%d:%02d:%02d",
                hours,
                minutes,
                remaining
            )
        }

        return String(
            format:
                "%d:%02d",
            minutes,
            remaining
        )
    }

    static func views(
        _ value:
            Int
    ) -> String {
        let number =
            Double(
                max(
                    0,
                    value
                )
            )

        if number >=
            1_000_000_000 {
            return String(
                format:
                    "%.1f mld. viz.",
                number /
                1_000_000_000
            )
        }

        if number >=
            1_000_000 {
            return String(
                format:
                    "%.1f mil. viz.",
                number /
                1_000_000
            )
        }

        if number >=
            1_000 {
            return String(
                format:
                    "%.1f K viz.",
                number /
                1_000
            )
        }

        return "\(value) viz."
    }
}
