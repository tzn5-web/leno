# VcdResolver V9.2

Resolver separat pentru YoutubeVcd V9.2. Extracția YouTube rămâne în afara IPA-ului, iar iPhone-ul primește URL-uri de relay controlate de resolver.

## Stack validat

- yt-dlp 2026.08.19 + yt-dlp-ejs 0.8.0.
- Deno 2.9.7 ca runtime JavaScript.
- Python 3.12 în container.
- Relay HTTP cu GET/HEAD, Range și timeout finit.
- TTL glisant pentru tokenurile folosite activ.
- Refresh serializat per stream la upstream 403/404/410.
- Limită implicită de 1024 relay-uri active.
- Selecție conservatoare H.264/AAC când există.
- Cookie file opțional pentru conținut care necesită sesiune.
- Token opțional pentru endpoint-ul de resolve.

## Limită intenționată în V9.2

V9.2 acceptă doar streamuri media directe cu protocol HTTP/HTTPS. Playlisturile HLS/m3u8 și formatele cu liste de fragmente sunt refuzate în loc să lase URL-uri upstream să ajungă pe iPhone.

Asta înseamnă că unele livestreamuri nu sunt încă suportate. Un relay HLS dedicat trebuie să rescrie fiecare segment, EXT-X-KEY și EXT-X-MAP înainte să putem declara live-ul sigur și complet.

## Docker local

```bash
docker build -t vcd-resolver .
docker run --rm -p 8085:8085 vcd-resolver
```

Pe iPhone, folosește IP-ul LAN al PC-ului, de exemplu:

```
http://192.168.1.50:8085
```

Nu folosi `127.0.0.1` sau `localhost` pe iPhone; acestea indică telefonul însuși.

## VPS / Internet

Pentru un resolver public folosește HTTPS. Clientul V9.2 refuză:

- HTTP public în afara rețelei locale.
- trimiterea bearer token-ului prin HTTP necriptat.

Exemplu container:

```bash
docker run --rm -p 8085:8085 \
  -e VCD_API_TOKEN='schimba-ma' \
  -e VCD_PUBLIC_BASE_URL='https://resolver.example.com' \
  vcd-resolver
```

Reverse proxy-ul HTTPS trebuie să trimită traficul către portul 8085.

## Cookies opționale

Pentru videoclipuri care cer autentificare poți monta un fișier Netscape cookies:

```bash
docker run --rm -p 8085:8085 \
  -v "$PWD/cookies.txt:/run/secrets/youtube-cookies.txt:ro" \
  -e VCD_COOKIES_FILE='/run/secrets/youtube-cookies.txt' \
  vcd-resolver
```

Cookies nu garantează conținutul members-only/age-restricted: unele cazuri YouTube pot necesita și PO Token provider configurat în yt-dlp.

## Variabile

- `VCD_API_TOKEN`: protejează endpoint-ul de resolve.
- `VCD_PUBLIC_BASE_URL`: URL public folosit în relay URLs când resolverul e în spatele unui reverse proxy.
- `VCD_COOKIES_FILE`: cale opțională către cookies.txt.
- `VCD_RELAY_TTL`: TTL relay, implicit 21600 secunde.
- `VCD_MAX_RELAY_ENTRIES`: implicit 1024.
- `VCD_UPSTREAM_READ_TIMEOUT`: implicit 45 secunde.
- `YTDLP_TIMEOUT`: timeout extracție, implicit 90 secunde.
- `YTDLP_JS_RUNTIME`: implicit deno.

## API

Health:

```
GET /health
```

Resolve:

```
GET /v1/video/<11-character-video-id>
Authorization: Bearer <token>   # doar dacă VCD_API_TOKEN este setat
```

Relay:

```
GET|HEAD /v1/relay/<capability-token>
Range: bytes=...
```

Relay tokenurile sunt capability URLs greu de ghicit; URL-ul media upstream nu este returnat de endpoint-ul de resolve.
