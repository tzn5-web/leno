# VcdResolver V9

Resolver separat pentru YoutubeVcd V9. Extracția YouTube rămâne în afara IPA-ului, iar iPhone-ul primește doar URL-uri de relay controlate de resolver.

## Ce repară versiunea 0.2

- yt-dlp 2026.08.19 + yt-dlp-ejs 0.8.0.
- Deno 2.9.7 ca runtime JavaScript suportat pentru challenge-urile YouTube.
- Relay HTTP cu Range și HEAD.
- TTL glisant: un stream folosit activ nu expiră doar pentru că sesiunea depășește TTL-ul inițial.
- Re-extracție automată dacă upstream-ul răspunde 403/404/410.
- Refolosirea aceluiași format când este posibil, cu fallback compatibil H.264/AAC.
- Token opțional pentru endpoint-ul de rezolvare prin `VCD_API_TOKEN`.

## Docker

```bash
docker build -t vcd-resolver .
docker run --rm -p 8085:8085 vcd-resolver
```

Cu autentificare pentru un VPS:

```bash
docker run --rm -p 8085:8085 \
  -e VCD_API_TOKEN='schimba-ma' \
  vcd-resolver
```

Health:

```
GET /health
```

Resolve:

```
GET /v1/video/<11-character-video-id>
Authorization: Bearer <token>   # doar dacă VCD_API_TOKEN este setat
```

## Foarte important pe iPhone

`127.0.0.1` și `localhost` înseamnă iPhone-ul însuși. Pentru resolverul rulat pe PC folosește IP-ul LAN al PC-ului, de exemplu `http://192.168.1.50:8085`. Pentru acces din afara casei folosește un endpoint HTTPS.

Relay-ul folosește tokenuri greu de ghicit și nu expune URL-urile upstream în răspunsul clientului.
