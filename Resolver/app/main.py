from __future__ import annotations

import asyncio
import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

APP_VERSION = "0.1.0-lab"
TOKEN_TTL_SECONDS = int(os.getenv("VCD_RELAY_TTL", "1800"))
YTDLP_BIN = os.getenv("YTDLP_BIN", "yt-dlp")
YTDLP_TIMEOUT = int(os.getenv("YTDLP_TIMEOUT", "90"))

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


async def create_relay_entry(
    url: str,
    headers: dict[str, str] | None,
    content_type: str | None,
) -> str:
    token = secrets.token_urlsafe(24)
    async with relay_lock:
        cleanup_entries()
        relay_entries[token] = RelayEntry(
            url=url,
            headers=headers or {},
            expires_at=time.time() + TOKEN_TTL_SECONDS,
            content_type=content_type,
        )
    return token


def choose_formats(info: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
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

        # First Media Lab goal is reliability, not maximum codec efficiency.
        # Prefer an MP4/H.264 path that VideoToolbox handles broadly on iPhone.
        h264 = codec.startswith("avc1") or "h264" in codec
        mp4 = ext == "mp4"
        compatibility = 3 if (h264 and mp4) else 2 if h264 else 1

        bitrate = float(f.get("tbr") or 0)
        return (compatibility, height, 1 if mp4 else 0, bitrate)

    def audio_score(f: dict[str, Any]) -> tuple[int, int, float]:
        codec = str(f.get("acodec") or "").lower()
        ext = str(f.get("ext") or "").lower()

        # Prefer AAC/M4A first so the first device tests use the most
        # conservative iOS audio path. Opus remains a fallback for MPV.
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


async def extract_video(video_id: str) -> dict[str, Any]:
    if len(video_id) != 11:
        raise HTTPException(status_code=400, detail="invalid video id")

    url = f"https://www.youtube.com/watch?v={video_id}"
    proc = await asyncio.create_subprocess_exec(
        YTDLP_BIN,
        "--dump-single-json",
        "--no-playlist",
        "--skip-download",
        "--no-warnings",
        "--js-runtimes",
        "node",
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
        raise HTTPException(status_code=504, detail="yt-dlp timeout")

    if proc.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace")[-1000:]
        raise HTTPException(status_code=502, detail=f"yt-dlp failed: {detail}")

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"invalid yt-dlp json: {exc}")


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "version": APP_VERSION,
        "relay_ttl": TOKEN_TTL_SECONDS,
    }


@app.get("/v1/video/{video_id}")
async def video(video_id: str, request: Request) -> dict[str, Any]:
    info = await extract_video(video_id)
    video_format, audio_format = choose_formats(info)

    if video_format is None:
        raise HTTPException(status_code=502, detail="no playable stream")

    base = str(request.base_url).rstrip("/")

    async def make_stream(format_info: dict[str, Any] | None) -> dict[str, Any] | None:
        if format_info is None:
            return None

        content_type = format_info.get("mime_type")
        token = await create_relay_entry(
            str(format_info["url"]),
            normalized_headers(format_info),
            str(content_type) if content_type else None,
        )

        return {
            "relayURL": f"{base}/v1/relay/{token}",
            "formatID": str(format_info.get("format_id") or ""),
            "container": str(format_info.get("ext") or ""),
            "videoCodec": None if format_info.get("vcodec") in (None, "none") else str(format_info.get("vcodec")),
            "audioCodec": None if format_info.get("acodec") in (None, "none") else str(format_info.get("acodec")),
            "height": format_info.get("height"),
            "fps": format_info.get("fps"),
            "bitrate": format_info.get("tbr"),
        }

    return {
        "videoID": video_id,
        "title": str(info.get("title") or "YouTube"),
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail"),
        "video": await make_stream(video_format),
        "audio": await make_stream(audio_format),
        "expiresIn": TOKEN_TTL_SECONDS,
    }


@app.get("/v1/relay/{token}")
async def relay(token: str, request: Request) -> StreamingResponse:
    async with relay_lock:
        cleanup_entries()
        entry = relay_entries.get(token)

    if entry is None:
        raise HTTPException(status_code=404, detail="relay token expired or unknown")

    headers = dict(entry.headers)

    range_header = request.headers.get("range")
    if range_header:
        headers["Range"] = range_header

    client = httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(30.0, read=None),
    )

    upstream = await client.send(
        client.build_request(
            "GET",
            entry.url,
            headers=headers,
        ),
        stream=True,
    )

    if upstream.status_code >= 400:
        await upstream.aclose()
        await client.aclose()
        raise HTTPException(
            status_code=upstream.status_code,
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
    ]:
        value = upstream.headers.get(key)
        if value:
            response_headers[key] = value

    if entry.content_type and "content-type" not in response_headers:
        response_headers["content-type"] = entry.content_type

    async def iterator():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        iterator(),
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=None,
    )
