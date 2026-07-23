<h1 align="center">Replica</h1>

<p align="center">
  <strong>Mirror any website through your own origin — with a browser-grade TLS<br>fingerprint, clean headers, live content rewriting, and a built-in cache.</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue.svg">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green.svg">
  <img alt="Docker" src="https://img.shields.io/badge/docker-ready-blue.svg">
</p>

Replica is a lightweight reverse proxy. Point it at a target site and it serves a working mirror of that site from your own host — the pages load, the assets resolve, and the links stay on your domain. You can rewrite text on the way through, drop in your own JavaScript, and let a built-in cache keep it fast.

## Why Replica

- **Mirror a site under your own domain.** Set one target and Replica serves the whole site from your host, with links and URLs rewritten so visitors never leave your domain.
- **Reaches sites that block plain proxies.** Requests are made to look like they come from a real browser, so origins behind anti-bot protection load instead of returning a challenge.
- **Rewrite the content.** Apply your own find-and-replace rules to any text on the page — swap names, labels, or URLs across the whole mirror.
- **Inject your own JavaScript.** Add a script to every page — inline or from a file — to change behavior, add analytics, or tweak the UI.
- **Fast by default.** Pages and assets are cached in memory with sensible TTLs, so repeat visits are served instantly without hitting the origin.
- **Clean, drop-in deployment.** A single container, configured entirely through environment variables. Run it and it works.

## How it works

Replica is a single ASGI app. Every request matches one catch-all route and flows through `proxy_request`: build the upstream URL from `TARGET_ORIGIN` + the incoming path, sanitize the request headers, fetch upstream through a pooled impersonating client, sanitize and rewrite the response, apply replacements and JS injection to text bodies, then cache and return it. On startup the app validates its configuration and exits if anything is wrong, so a misconfigured deploy fails loudly instead of silently proxying to the wrong place.

```
client ──▶ Replica ──▶ [ cache? ] ──▶ curl-impersonate (chrome/firefox) ──▶ TARGET_ORIGIN
        ◀──         ◀── rewrite headers · rewrite URLs · replacements · inject JS ◀──
```

## Quick start (Docker)

The fastest way to run Replica is the pre-built image from GHCR — no clone required.

```bash
# minimal: just point it at a target
docker run -d -p 8000:8000 \
  --env TARGET_ORIGIN="https://example.com" \
  --name replica \
  ghcr.io/sarperavci/replica:latest
```

For anything beyond a target origin, put your settings in a `.env` file (see [Configuration](#configuration)) and pass it in:

```bash
docker run -d -p 8000:8000 --env-file .env --name replica ghcr.io/sarperavci/replica:latest
```

Then open <http://localhost:8000>. To build the image yourself:

```bash
git clone https://github.com/sarperavci/replica.git
cd replica
docker compose up --build
```

## Configuration

Replica is configured entirely through environment variables (or a local `.env` file, loaded automatically). Invalid values are reported at startup and abort the boot.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `TARGET_ORIGIN` | `https://example.com` | Upstream site to mirror. Must be a valid `http(s)` URL. A base path is preserved. |
| `REPLACEMENTS` | `{}` | JSON object of `{"find": "replace"}` rules applied to text responses (case-insensitive, literal). Use `"replace"` = `"MY_HOST"` to insert the request's host. |
| `CACHE_TTL_STATIC` | `86400` | TTL in seconds for cached static assets (images, CSS, JS, fonts). |
| `CACHE_TTL_HTML` | `300` | TTL in seconds for cached HTML and other text responses. |
| `INJECT_JS` | *(none)* | JavaScript to inject into every HTML page. Wrapped in `<script>` automatically. |
| `INJECT_JS_FILE` | *(none)* | Path to a JS file to inject. Overrides `INJECT_JS` when set and readable. |
| `INJECT_JS_LOCATION` | `body` | Where to inject: `head` (before `</head>`) or `body` (before `</body>`). |

The target-to-your-host URL rewriting is always applied and cannot be disabled — any `REPLACEMENTS` rule that would clash with it is ignored so the mapping stays correct.

### Example `.env`

```bash
TARGET_ORIGIN=https://news.ycombinator.com
REPLACEMENTS='{"Hacker News": "My News", "footer": "MY_HOST"}'
CACHE_TTL_HTML=60
INJECT_JS_LOCATION=head
INJECT_JS='console.log("served through Replica");'
```

## Local development

Replica targets **Python 3.10+**.

```bash
# 1. Environment
python3.10 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# 2. Configuration
cp .env.example .env               # then edit TARGET_ORIGIN etc.

# 3. Run
uvicorn replica.main:app --host 0.0.0.0 --port 8000

# ...or with hot reload while developing
uvicorn replica.main:app --reload --host 127.0.0.1 --port 8000
```

## Known limitations

- **Google and similar targets aren't supported.** Sites with advanced bot detection need handling Replica doesn't implement.
- **No WebSocket support.** Only HTTP/HTTPS is proxied; WebSocket upgrades will fail.
- **Cache is in-memory and per-process.** It isn't shared across replicas and is lost on restart.

## Contributing

Pull requests are welcome. If you hit a bug or want a feature, open an issue first so we can talk it through.

## License

MIT. See [LICENSE](LICENSE).
