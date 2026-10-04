# VcdResolver Media Lab

Minimal V9 resolver for the first native playback laboratory.

## What it proves

- YouTube extraction happens off-device.
- Raw upstream media URLs do not leave the resolver.
- iPhone requests media through the resolver relay.
- HTTP Range is forwarded, so libmpv can seek.
- Separate video/audio streams can be handed to a single MPV instance.
- Resolver can be updated independently from the IPA.

## Run

```bash
docker build -t vcd-resolver .
docker run --rm -p 8085:8085 vcd-resolver
```

Health:

```
GET /health
```

Resolve:

```
GET /v1/video/<11-character-video-id>
```

The response returns relay URLs rather than raw googlevideo URLs.

This is a laboratory implementation. Authentication, persistent cache,
multi-user credentials and production hardening come after playback gates pass.
