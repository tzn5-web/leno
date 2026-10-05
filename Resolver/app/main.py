from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import re
import secrets
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

APP_VERSION = "0.3.0-lab"
TOKEN_TTL_SECONDS = int(os.getenv("VCD_RELAY_TTL", "21600"))
YTDLP_BIN = os.getenv("YTDLP_BIN", "yt-dlp")
YTDLP_TIMEOUT = int(os.getenv("YTDLP_TIMEOUT", "90"))
YTDLP_JS_RUNTIME = os.getenv("YTDLP_JS_RUNTIME", "deno").strip() or "deno"
API_TOKEN = os.getenv("VCD_API_TOKEN", "").strip()
PUBLIC_BASE_URL = os.getenv("VCD_PUBLIC_BASE_URL", "").strip().rstrip("/")
COOKIES_FILE = os.getenv("VCD_COOKIES_FILE", "").strip()
MAX_RELAY_ENTRIES = max(32, int(os.getenv("VCD_MAX_RELAY_ENTRIES", "1024")))
MAX_CONCURRENT_EXTRACTS = max(1, int(os.getenv("VCD_MAX_CONCURRENT_EXTRACTS", "2")))
MAX_VIDEO_HEIGHT = max(360, int(os.getenv("VCD_MAX_VIDEO_HEIGHT", "1080")))
MAX_VIDEO_FPS = max(24.0, float(os.getenv("VCD_MAX_VIDEO_FPS", "30")))
UPSTREAM_READ_TIMEOUT = max(10.0, float(os.getenv("VCD_UPSTREAM_READ_TIMEOUT", "45")))
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
REFRESHABLE_UPSTREAM_STATUS = {403, 404, 410}

app = FastAPI(
    title="VcdResolver",
    version=APP_VERSION,
)


@dataclass
class RelayEntry:
    url: str
    headers: dict[str, str]
    expires_at: float
    content_type: str | None
    video_id: str
    format_id: str
    stream_kind: str
    generation: int = 0
    refresh_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


relay_entries: dict[str, RelayEntry] = {}
relay_lock = asyncio.Lock()
extraction_semaphore = asyncio.Semaphore(MAX_CONCURRENT_EXTRACTS)


def cleanup_entries() -> None:
    now = time.time()
    expired = [
        token
        for token, entry in relay_entries.items()
        if entry.expires_at <= now
    ]
    for token in expired:
        relay_entries.pop(token, None)


def enforce_relay_capacity() -> None:
    overflow = len(relay_entries) - MAX_RELAY_ENTRIES + 1
    if overflow <= 0:
        return

    oldest = sorted(
        relay_entries.items(),
        key=lambda item: item[1].expires_at,
    )

    for token, _ in oldest[:overflow]:
        relay_entries.pop(token, None)


def is_local_network_host(host: str) -> bool:
    value = host.strip().lower().strip("[]")

    if value == "localhost" or value.endswith(".local") or "." not in value:
        return True

    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False

    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
    )


def resolved_public_base(request: Request) -> str:
    if PUBLIC_BASE_URL:
        try:
            parsed = httpx.URL(PUBLIC_BASE_URL)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail="VCD_PUBLIC_BASE_URL is invalid",
            ) from exc

        host = parsed.host or ""
        scheme = parsed.scheme.decode() if isinstance(parsed.scheme, bytes) else str(parsed.scheme)

        if scheme not in {"http", "https"} or not host:
            raise HTTPException(
                status_code=500,
                detail="VCD_PUBLIC_BASE_URL must be an absolute http(s) URL",
            )

        if scheme == "http" and not is_local_network_host(host):
            raise HTTPException(
                status_code=500,
                detail="public VCD_PUBLIC_BASE_URL must use https",
            )

        if not is_local_network_host(host) and not API_TOKEN:
            raise HTTPException(
                status_code=500,
                detail="public VCD_PUBLIC_BASE_URL requires VCD_API_TOKEN",
            )

        return PUBLIC_BASE_URL

    host = request.url.hostname or ""
    peer_host = request.client.host if request.client else ""

    # request.base_url is derived from the incoming Host header. A remote
    # caller can spoof Host, so LAN mode requires both the advertised host and
    # the actual peer (or trusted proxy-derived client) to be local/private.
    if (
        not is_local_network_host(host)
        or not peer_host
        or not is_local_network_host(peer_host)
    ):
        raise HTTPException(
            status_code=500,
            detail="set VCD_PUBLIC_BASE_URL and VCD_API_TOKEN for non-LAN deployments",
        )

    return str(request.base_url).rstrip("/")


def require_api_token(request: Request) -> None:
    if not API_TOKEN:
        return

    expected = f"Bearer {API_TOKEN}"
    supplied = request.headers.get("authorization", "")
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="resolver authorization required")


async def create_relay_entry(
    *,
    video_id: str,
    format_info: dict[str, Any],
    stream_kind: str,
) -> str:
    token = secrets.token_urlsafe(24)
    content_type = format_info.get("mime_type")

    async with relay_lock:
        cleanup_entries()
        enforce_relay_capacity()
        relay_entries[token] = RelayEntry(
            url=str(format_info["url"]),
            headers=normalized_headers(format_info),
            expires_at=time.time() + TOKEN_TTL_SECONDS,
            content_type=str(content_type) if content_type else None,
            video_id=video_id,
            format_id=str(format_info.get("format_id") or ""),
            stream_kind=stream_kind,
        )

    return token


def is_relayable_format(format_info: dict[str, Any]) -> bool:
    raw_url = str(format_info.get("url") or "")
    if not raw_url:
        return False

    protocol = str(format_info.get("protocol") or "").lower()
    if protocol and protocol not in {"http", "https"}:
        return False

    try:
        parsed = httpx.URL(raw_url)
    except Exception:
        return False

    scheme = str(parsed.scheme).lower()
    host = str(parsed.host or "")

    if scheme not in {"http", "https"} or not host:
        return False

    # yt-dlp is the only source of upstream URLs, but never let a malformed
    # extraction turn the relay into a local-network/loopback fetcher.
    if is_local_network_host(host):
        return False

    # Fragment/manifest protocols need URL rewriting for every nested segment.
    # Until that dedicated relay exists, never leak those upstream URLs to iOS.
    if format_info.get("fragments"):
        return False

    return True


def choose_formats(
    info: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    formats = [
        f
        for f in info.get("formats", [])
        if is_relayable_format(f)
    ]

    video_only = [
        f for f in formats
        if f.get("vcodec") not in (None, "none")
        and f.get("acodec") in (None, "none")
    ]

    def constrain_video(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not candidates:
            return candidates

        within_height = [
            f for f in candidates
            if int(f.get("height") or 0) <= MAX_VIDEO_HEIGHT
        ]
        if within_height:
            candidates = within_height

        within_fps = [
            f for f in candidates
            if float(f.get("fps") or 0) <= MAX_VIDEO_FPS
        ]
        if within_fps:
            candidates = within_fps

        return candidates

    video_only = constrain_video(video_only)

    audio_only = [
        f for f in formats
        if f.get("acodec") not in (None, "none")
        and f.get("vcodec") in (None, "none")
    ]

    muxed = [
        f for f in formats
        if f.get("vcodec") not in (None, "none")
        and f.get("acodec") not in (None, "none")
    ]
    muxed = constrain_video(muxed)

    def video_score(f: dict[str, Any]) -> tuple[int, int, int, float]:
        height = int(f.get("height") or 0)
        codec = str(f.get("vcodec") or "").lower()
        ext = str(f.get("ext") or "").lower()

        h264 = codec.startswith("avc1") or "h264" in codec
        mp4 = ext == "mp4"
        compatibility = 3 if (h264 and mp4) else 2 if h264 else 1

        bitrate = float(f.get("tbr") or 0)
        return (compatibility, height, 1 if mp4 else 0, bitrate)

    def audio_score(f: dict[str, Any]) -> tuple[int, int, float]:
        codec = str(f.get("acodec") or "").lower()
        ext = str(f.get("ext") or "").lower()

        aac = "mp4a" in codec or "aac" in codec
        m4a = ext in {"m4a", "mp4"}
        compatibility = 3 if (aac and m4a) else 2 if aac else 1

        bitrate = float(f.get("abr") or f.get("tbr") or 0)
        return (compatibility, 1 if m4a else 0, bitrate)

    if video_only and audio_only:
        return max(video_only, key=video_score), max(audio_only, key=audio_score)

    if muxed:
        return max(muxed, key=video_score), None

    return None, None


def normalized_headers(format_info: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}

    http_headers = format_info.get("http_headers") or {}
    for key, value in http_headers.items():
        if value is None:
            continue

        if key.lower() in {
            "user-agent",
            "referer",
            "origin",
            "cookie",
        }:
            headers[str(key)] = str(value)

    return headers


def format_matches_kind(format_info: dict[str, Any], stream_kind: str) -> bool:
    has_video = format_info.get("vcodec") not in (None, "none")
    has_audio = format_info.get("acodec") not in (None, "none")

    if stream_kind == "video":
        return has_video and not has_audio

    if stream_kind == "audio":
        return has_audio and not has_video

    return has_video and has_audio


def select_refresh_format(
    info: dict[str, Any],
    entry: RelayEntry,
) -> dict[str, Any] | None:
    formats = [
        f
        for f in info.get("formats", [])
        if is_relayable_format(f)
    ]

    for candidate in formats:
        if (
            str(candidate.get("format_id") or "") == entry.format_id
            and format_matches_kind(candidate, entry.stream_kind)
        ):
            return candidate

    video, audio = choose_formats(info)

    if entry.stream_kind == "audio":
        return audio

    if entry.stream_kind == "video":
        if audio is not None:
            return video
        return None

    if audio is None:
        return video

    return None


async def extract_video(video_id: str) -> dict[str, Any]:
    if not VIDEO_ID_RE.fullmatch(video_id):
        raise HTTPException(status_code=400, detail="invalid video id")

    async with extraction_semaphore:
        url = f"https://www.youtube.com/watch?v={video_id}"

        arguments = [
            YTDLP_BIN,
            "--dump-single-json",
            "--no-playlist",
            "--skip-download",
            "--no-warnings",
            "--js-runtimes",
            YTDLP_JS_RUNTIME,
        ]

        if COOKIES_FILE:
            if not os.path.isfile(COOKIES_FILE):
                raise HTTPException(
                    status_code=500,
                    detail="VCD_COOKIES_FILE does not exist",
                )

            arguments.extend(
                [
                    "--cookies",
                    COOKIES_FILE,
                ]
            )

        arguments.append(url)

        proc = await asyncio.create_subprocess_exec(
            *arguments,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=YTDLP_TIMEOUT,
            )
        except asyncio.CancelledError:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
            raise
        except TimeoutError:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
            raise HTTPException(status_code=504, detail="yt-dlp timeout")

        if proc.returncode != 0:
            diagnostic = stderr.decode("utf-8", errors="replace")[-1200:]
            print(
                f"yt-dlp failed for {video_id}: {diagnostic}",
                file=sys.stderr,
            )
            raise HTTPException(
                status_code=502,
                detail="yt-dlp extraction failed",
            )

        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            print(
                f"yt-dlp returned invalid JSON for {video_id}: {exc}",
                file=sys.stderr,
            )
            raise HTTPException(
                status_code=502,
                detail="invalid yt-dlp response",
            ) from exc


async def refresh_relay_entry(entry: RelayEntry) -> None:
    info = await extract_video(entry.video_id)
    refreshed_format = select_refresh_format(info, entry)

    if refreshed_format is None:
        raise HTTPException(
            status_code=502,
            detail=f"could not refresh {entry.stream_kind} stream",
        )

    content_type = refreshed_format.get("mime_type")
    entry.url = str(refreshed_format["url"])
    entry.headers = normalized_headers(refreshed_format)
    entry.content_type = str(content_type) if content_type else None
    entry.format_id = str(refreshed_format.get("format_id") or "")
    entry.expires_at = time.time() + TOKEN_TTL_SECONDS
    entry.generation += 1


def forwarded_request_headers(
    request: Request,
    *,
    include_conditionals: bool,
) -> dict[str, str]:
    forwarded: dict[str, str] = {}

    range_value = request.headers.get("range")
    if range_value:
        forwarded["Range"] = range_value

    if include_conditionals:
        for source, target in [
            ("if-range", "If-Range"),
            ("if-none-match", "If-None-Match"),
            ("if-modified-since", "If-Modified-Since"),
        ]:
            value = request.headers.get(source)
            if value:
                forwarded[target] = value

    return forwarded


async def send_upstream(
    entry: RelayEntry,
    request: Request,
    *,
    include_conditionals: bool = True,
) -> tuple[httpx.AsyncClient, httpx.Response]:
    headers = dict(entry.headers)

    # Range semantics and Content-Length must describe the original media
    # bytes, not a transparently compressed HTTP representation.
    headers["Accept-Encoding"] = "identity"

    headers.update(
        forwarded_request_headers(
            request,
            include_conditionals=include_conditionals,
        )
    )

    client = httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(
            30.0,
            read=UPSTREAM_READ_TIMEOUT,
        ),
    )

    try:
        upstream = await client.send(
            client.build_request(
                request.method,
                entry.url,
                headers=headers,
            ),
            stream=True,
        )
    except httpx.TimeoutException as exc:
        await client.aclose()
        raise HTTPException(
            status_code=504,
            detail="upstream media timeout",
        ) from exc
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(
            status_code=502,
            detail="upstream media transport failed",
        ) from exc

    return client, upstream


async def close_upstream(
    client: httpx.AsyncClient,
    upstream: httpx.Response,
) -> None:
    await upstream.aclose()
    await client.aclose()


@app.get("/health")
async def health() -> dict[str, Any]:
    async with relay_lock:
        cleanup_entries()
        active_relay_entries = len(relay_entries)

    return {
        "ok": True,
        "version": APP_VERSION,
        "relay_ttl": TOKEN_TTL_SECONDS,
        "js_runtime": YTDLP_JS_RUNTIME,
        "auth_required": bool(API_TOKEN),
        "cookies_configured": bool(COOKIES_FILE),
        "public_base_configured": bool(PUBLIC_BASE_URL),
        "max_relay_entries": MAX_RELAY_ENTRIES,
        "max_concurrent_extracts": MAX_CONCURRENT_EXTRACTS,
        "max_video_height": MAX_VIDEO_HEIGHT,
        "max_video_fps": MAX_VIDEO_FPS,
        "active_relay_entries": active_relay_entries,
    }


@app.get("/v1/video/{video_id}")
async def video(video_id: str, request: Request) -> dict[str, Any]:
    require_api_token(request)

    # Validate deployment/origin before starting an expensive yt-dlp process.
    base = resolved_public_base(request)

    info = await extract_video(video_id)
    video_format, audio_format = choose_formats(info)

    if video_format is None:
        detail = (
            "live/HLS or fragmented stream is not yet supported by the V9.2 relay"
            if info.get("is_live")
            else "no directly relayable HTTP/HTTPS stream is available"
        )
        raise HTTPException(
            status_code=502,
            detail=detail,
        )

    split_streams = audio_format is not None

    async def make_stream(
        format_info: dict[str, Any] | None,
        stream_kind: str,
    ) -> dict[str, Any] | None:
        if format_info is None:
            return None

        token = await create_relay_entry(
            video_id=video_id,
            format_info=format_info,
            stream_kind=stream_kind,
        )

        return {
            "relayURL": f"{base}/v1/relay/{token}",
            "formatID": str(format_info.get("format_id") or ""),
            "container": str(format_info.get("ext") or ""),
            "videoCodec": None
            if format_info.get("vcodec") in (None, "none")
            else str(format_info.get("vcodec")),
            "audioCodec": None
            if format_info.get("acodec") in (None, "none")
            else str(format_info.get("acodec")),
            "height": format_info.get("height"),
            "fps": format_info.get("fps"),
            "bitrate": format_info.get("tbr"),
        }

    return {
        "videoID": video_id,
        "title": str(info.get("title") or "YouTube"),
        "duration": info.get("duration"),
        # Never hand raw upstream thumbnail URLs to the client. A future
        # metadata UI can add a dedicated image relay/cache.
        "thumbnail": None,
        "video": await make_stream(
            video_format,
            "video" if split_streams else "muxed",
        ),
        "audio": await make_stream(audio_format, "audio"),
        "expiresIn": TOKEN_TTL_SECONDS,
    }


@app.api_route("/v1/relay/{token}", methods=["GET", "HEAD"])
async def relay(token: str, request: Request) -> Response:
    async with relay_lock:
        cleanup_entries()
        entry = relay_entries.get(token)

        if entry is not None:
            # Sliding lease: an actively used playback token remains valid.
            entry.expires_at = time.time() + TOKEN_TTL_SECONDS

    if entry is None:
        raise HTTPException(status_code=404, detail="relay token expired or unknown")

    generation = entry.generation

    client, upstream = await send_upstream(entry, request)

    if upstream.status_code in REFRESHABLE_UPSTREAM_STATUS:
        await close_upstream(client, upstream)

        async with entry.refresh_lock:
            try:
                # Another concurrent Range request may already have refreshed
                # this relay while we were waiting for the lock.
                if entry.generation == generation:
                    await refresh_relay_entry(entry)
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"stream refresh failed: {type(exc).__name__}",
                ) from exc

        client, upstream = await send_upstream(
            entry,
            request,
            include_conditionals=False,
        )

    if upstream.status_code >= 400:
        status = upstream.status_code
        await close_upstream(client, upstream)
        raise HTTPException(
            status_code=status,
            detail="upstream media request failed",
        )

    response_headers: dict[str, str] = {}

    for key in [
        "accept-ranges",
        "content-range",
        "content-length",
        "content-type",
        "etag",
        "last-modified",
        "content-encoding",
    ]:
        value = upstream.headers.get(key)
        if value:
            response_headers[key] = value

    if entry.content_type and "content-type" not in response_headers:
        response_headers["content-type"] = entry.content_type

    # Relay URLs are bearer-like capabilities. Never invite reverse proxies,
    # browsers or shared caches to retain the media response by token URL.
    response_headers["cache-control"] = "private, no-store"
    response_headers["x-content-type-options"] = "nosniff"

    if request.method == "HEAD":
        status = upstream.status_code
        await close_upstream(client, upstream)
        return Response(
            status_code=status,
            headers=response_headers,
            media_type=None,
        )

    async def iterator():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await close_upstream(client, upstream)

    return StreamingResponse(
        iterator(),
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=None,
    )
