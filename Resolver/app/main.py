from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

APP_VERSION = "0.2.0-lab"
TOKEN_TTL_SECONDS = int(os.getenv("VCD_RELAY_TTL", "21600"))
YTDLP_BIN = os.getenv("YTDLP_BIN", "yt-dlp")
YTDLP_TIMEOUT = int(os.getenv("YTDLP_TIMEOUT", "90"))
YTDLP_JS_RUNTIME = os.getenv("YTDLP_JS_RUNTIME", "deno").strip() or "deno"
API_TOKEN = os.getenv("VCD_API_TOKEN", "").strip()
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


relay_entries: dict[str, RelayEntry] = {}
relay_lock = asyncio.Lock()


def cleanup_entries() -> None:
    now = time.time()
    expired = [
        token
        for token, entry in relay_entries.items()
        if entry.expires_at <= now
    ]
    for token in expired:
        relay_entries.pop(token, None)


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


def choose_formats(
    info: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    formats = [
        f
        for f in info.get("formats", [])
        if f.get("url")
    ]

    video_only = [
        f for f in formats
        if f.get("vcodec") not in (None, "none")
        and f.get("acodec") in (None, "none")
    ]

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
        if f.get("url")
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

    url = f"https://www.youtube.com/watch?v={video_id}"
    proc = await asyncio.create_subprocess_exec(
        YTDLP_BIN,
        "--dump-single-json",
        "--no-playlist",
        "--skip-download",
        "--no-warnings",
        "--js-runtimes",
        YTDLP_JS_RUNTIME,
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=YTDLP_TIMEOUT,
        )
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise HTTPException(status_code=504, detail="yt-dlp timeout")

    if proc.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace")[-1200:]
        raise HTTPException(status_code=502, detail=f"yt-dlp failed: {detail}")

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"invalid yt-dlp json: {exc}")


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


def forwarded_request_headers(request: Request) -> dict[str, str]:
    forwarded: dict[str, str] = {}

    for source, target in [
        ("range", "Range"),
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
) -> tuple[httpx.AsyncClient, httpx.Response]:
    headers = dict(entry.headers)
    headers.update(forwarded_request_headers(request))

    client = httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(30.0, read=None),
    )

    upstream = await client.send(
        client.build_request(
            request.method,
            entry.url,
            headers=headers,
        ),
        stream=True,
    )

    return client, upstream


async def close_upstream(
    client: httpx.AsyncClient,
    upstream: httpx.Response,
) -> None:
    await upstream.aclose()
    await client.aclose()


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "version": APP_VERSION,
        "relay_ttl": TOKEN_TTL_SECONDS,
        "js_runtime": YTDLP_JS_RUNTIME,
        "auth_required": bool(API_TOKEN),
    }


@app.get("/v1/video/{video_id}")
async def video(video_id: str, request: Request) -> dict[str, Any]:
    require_api_token(request)

    info = await extract_video(video_id)
    video_format, audio_format = choose_formats(info)

    if video_format is None:
        raise HTTPException(status_code=502, detail="no playable stream")

    base = str(request.base_url).rstrip("/")
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
        "thumbnail": info.get("thumbnail"),
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

    client, upstream = await send_upstream(entry, request)

    if upstream.status_code in REFRESHABLE_UPSTREAM_STATUS:
        await close_upstream(client, upstream)

        try:
            await refresh_relay_entry(entry)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"stream refresh failed: {type(exc).__name__}",
            ) from exc

        client, upstream = await send_upstream(entry, request)

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
        "cache-control",
    ]:
        value = upstream.headers.get(key)
        if value:
            response_headers[key] = value

    if entry.content_type and "content-type" not in response_headers:
        response_headers["content-type"] = entry.content_type

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
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await close_upstream(client, upstream)

    return StreamingResponse(
        iterator(),
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=None,
    )
