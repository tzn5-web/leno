import SwiftUI

struct V9HomeFeedView:
    View
{
    let resolver:
        VcdResolverClient

    let endpoint:
        String

    let resolverToken:
        String

    let play:
        (BrowseVideo) -> Void

    @State
    private var items:
        [BrowseVideo] = []

    @State
    private var loading =
        false

    @State
    private var errorText:
        String?

    var body: some View {
        NavigationStack {
            Group {
                if endpoint
                    .trimmingCharacters(
                        in:
                            .whitespacesAndNewlines
                    )
                    .isEmpty {
                    ContentUnavailableView(
                        "Configurează resolverul",
                        systemImage:
                            "network.slash",
                        description:
                            Text(
                                "Deschide Setări și introdu adresa VcdResolver."
                            )
                    )
                } else if loading &&
                          items.isEmpty {
                    ProgressView(
                        "Încarc videoclipurile…"
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
                        resolver:
                            resolver,
                        endpoint:
                            endpoint,
                        resolverToken:
                            resolverToken,
                        play:
                            play
                    )
                    .refreshable {
                        await load()
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
                            await load()
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
            .task(
                id:
                    endpoint
            ) {
                await load()
            }
        }
    }

    @MainActor
    private func load()
        async
    {
        guard !loading,
              !endpoint
                .trimmingCharacters(
                    in:
                        .whitespacesAndNewlines
                )
                .isEmpty
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
            let result =
                try await resolver
                    .home(
                        endpoint:
                            endpoint,
                        bearerToken:
                            resolverToken
                    )

            items =
                result.items

            if items.isEmpty {
                errorText =
                    "Resolverul nu a întors videoclipuri."
            }
        } catch {
            errorText =
                error.localizedDescription
        }
    }
}

struct V9SearchView:
    View
{
    let resolver:
        VcdResolverClient

    let endpoint:
        String

    let resolverToken:
        String

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
                        resolver:
                            resolver,
                        endpoint:
                            endpoint,
                        resolverToken:
                            resolverToken,
                        play:
                            play
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
                    await search()
                }
            }
        }
    }

    @MainActor
    private func search()
        async
    {
        let trimmed =
            query.trimmingCharacters(
                in:
                    .whitespacesAndNewlines
            )

        guard !loading,
              trimmed.count >= 2,
              !endpoint
                .trimmingCharacters(
                    in:
                        .whitespacesAndNewlines
                )
                .isEmpty
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
            let result =
                try await resolver
                    .search(
                        query:
                            trimmed,
                        endpoint:
                            endpoint,
                        bearerToken:
                            resolverToken
                    )

            items =
                result.items

            if items.isEmpty {
                errorText =
                    "Niciun rezultat."
            }
        } catch {
            errorText =
                error.localizedDescription
        }
    }
}

struct V9VideoFeed:
    View
{
    let items:
        [BrowseVideo]

    let resolver:
        VcdResolverClient

    let endpoint:
        String

    let resolverToken:
        String

    let play:
        (BrowseVideo) -> Void

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
                        resolver:
                            resolver,
                        endpoint:
                            endpoint,
                        resolverToken:
                            resolverToken,
                        play:
                            play
                    )
                }
            }
            .padding(
                .vertical,
                8
            )
        }
    }
}

struct V9VideoCard:
    View
{
    let video:
        BrowseVideo

    let resolver:
        VcdResolverClient

    let endpoint:
        String

    let resolverToken:
        String

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
                              duration > 0 {
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
                       !video.channel.isEmpty {
                        NavigationLink {
                            V9ChannelView(
                                channelID:
                                    channelID,
                                initialTitle:
                                    video.channel,
                                resolver:
                                    resolver,
                                endpoint:
                                    endpoint,
                                resolverToken:
                                    resolverToken,
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

                    if let views =
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

struct V9ChannelView:
    View
{
    let channelID:
        String

    let initialTitle:
        String

    let resolver:
        VcdResolverClient

    let endpoint:
        String

    let resolverToken:
        String

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
    private var errorText:
        String?

    init(
        channelID:
            String,
        initialTitle:
            String,
        resolver:
            VcdResolverClient,
        endpoint:
            String,
        resolverToken:
            String,
        play:
            @escaping (BrowseVideo) -> Void
    ) {
        self.channelID =
            channelID

        self.initialTitle =
            initialTitle

        self.resolver =
            resolver

        self.endpoint =
            endpoint

        self.resolverToken =
            resolverToken

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
                    resolver:
                        resolver,
                    endpoint:
                        endpoint,
                    resolverToken:
                        resolverToken,
                    play:
                        play
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
            await load()
        }
    }

    @MainActor
    private func load()
        async
    {
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
            let result =
                try await resolver
                    .channel(
                        channelID:
                            channelID,
                        endpoint:
                            endpoint,
                        bearerToken:
                            resolverToken
                    )

            title =
                result.title

            items =
                result.items
        } catch {
            errorText =
                error.localizedDescription
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

        if hours > 0 {
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
