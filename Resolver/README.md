# VcdResolver 0.4.0-client

Backend-ul pentru YoutubeVcd 0.10.0. Resolverul face atât browsing nativ, cât
și rezolvarea/relay-ul streamurilor media.

## API pentru aplicație

- `GET /health`
- `GET /v1/home`
- `GET /v1/search?q=<text>`
- `GET /v1/channel/<UC...>`
- `GET /v1/thumb/<video-id>`
- `GET /v1/video/<video-id>`
- `GET|HEAD /v1/relay/<capability-token>`

Home folosește extractorul yt-dlp `:ytrec`, cu fallback la căutare normală.
Search folosește `ytsearch`. Channel folosește tab-ul `/videos`.

Live/upcoming sunt eliminate din feed deoarece relay-ul curent acceptă numai
media HTTP/HTTPS direct adresabilă; nu afișăm intenționat un clip pe care
playerul nu îl poate reda.

## Stack

- Python 3.12;
- yt-dlp 2026.08.19;
- yt-dlp-ejs 0.8.0;
- Deno 2.9.7;
- FastAPI / Uvicorn / httpx.

## Docker local

```bash
docker build -t vcd-resolver Resolver
docker run --rm -p 8085:8085 vcd-resolver
```

Pe iPhone folosește IP-ul LAN al PC-ului, de exemplu:

```
http://192.168.1.50:8085
```

Nu folosi `127.0.0.1` sau `localhost` pe iPhone.

## Public / VPS

Pentru Internet sunt obligatorii:

- HTTPS;
- `VCD_PUBLIC_BASE_URL`;
- `VCD_API_TOKEN`.

Exemplu:

```bash
docker run --rm -p 8085:8085 \
  -e VCD_API_TOKEN='schimba-ma' \
  -e VCD_PUBLIC_BASE_URL='https://resolver.example.com' \
  vcd-resolver
```

Clientul refuză bearer token pe HTTP și refuză redirect-uri API către altă
origine.

## Opțiuni

- `VCD_API_TOKEN`
- `VCD_PUBLIC_BASE_URL`
- `VCD_COOKIES_FILE`
- `VCD_RELAY_TTL` — implicit 21600 secunde
- `VCD_MAX_RELAY_ENTRIES` — implicit 1024
- `VCD_MAX_CONCURRENT_EXTRACTS` — implicit 2
- `VCD_MAX_VIDEO_HEIGHT` — implicit 1080
- `VCD_MAX_VIDEO_FPS` — implicit 30
- `VCD_BROWSE_LIMIT` — implicit 24, limitat la 8…50
- `VCD_UPSTREAM_READ_TIMEOUT` — implicit 45 secunde
- `YTDLP_TIMEOUT` — implicit 90 secunde
- `YTDLP_JS_RUNTIME` — implicit deno

## Cookies

Pentru conținut care cere sesiune se poate monta un cookies.txt Netscape și
seta `VCD_COOKIES_FILE`. Unele fluxuri YouTube pot cere în continuare un
PO-token provider; acest lucru depinde de YouTube/yt-dlp și nu este ascuns ca
funcționalitate garantată.

## Relay

Relay-ul păstrează URL-urile media upstream în server și expune către iPhone
doar capability URLs cu token aleator. Range este suportat, byte encoding este
`identity`, redirect-urile upstream sunt validate, iar destinațiile
loopback/private sunt refuzate.
