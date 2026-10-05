#!/usr/bin/env python3
import json
import sys

target = sys.argv[-1] if len(sys.argv) > 1 else ""

video_a = {
    "id": "dQw4w9WgXcQ",
    "title": "Test Video A",
    "channel": "Test Channel",
    "uploader": "Test Channel",
    "channel_id": "UCaaaaaaaaaaaaaaaaaaaaaa",
    "duration": 213,
    "view_count": 123456,
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
}
video_b = {
    "id": "9bZkp7q19f0",
    "title": "Test Video B",
    "channel": "Second Channel",
    "uploader": "Second Channel",
    "channel_id": "UCbbbbbbbbbbbbbbbbbbbbbb",
    "duration": 252,
    "view_count": 987654,
    "url": "https://www.youtube.com/watch?v=9bZkp7q19f0",
}

if target.startswith("ytsearch") or target == ":ytrec" or "/channel/" in target:
    print(json.dumps({
        "id": "browse",
        "title": "Browse",
        "entries": [video_a, video_b],
    }))
    raise SystemExit(0)

video_id = target.split("v=")[-1][:11]
print(json.dumps({
    "id": video_id,
    "title": "Resolved Test Video",
    "duration": 213,
    "formats": [
        {
            "format_id": "137",
            "url": "https://example.invalid/video.mp4",
            "protocol": "https",
            "vcodec": "avc1.640028",
            "acodec": "none",
            "ext": "mp4",
            "height": 1080,
            "fps": 30,
            "tbr": 4500,
            "http_headers": {"User-Agent": "test"},
        },
        {
            "format_id": "140",
            "url": "https://example.invalid/audio.m4a",
            "protocol": "https",
            "vcodec": "none",
            "acodec": "mp4a.40.2",
            "ext": "m4a",
            "abr": 128,
            "http_headers": {"User-Agent": "test"},
        },
    ],
}))
