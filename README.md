# Replica

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Docker](https://img.shields.io/badge/docker-ready-blue)

Replica is a lightweight, Python-based reverse proxy. It mirrors content from a target origin, sanitizes headers to keep downstream proxies happy, and handles on-the-fly text replacement. It includes an in-memory TTL cache for static assets and HTML to ensure high performance.

## Features

*   **Smart Proxying:** Forward requests to any target origin with minimal overhead.
*   **In-Memory Caching:** Built-in TTL caching for static files and HTML.
*   **Header Sanitization:** Automatically cleans headers to prevent conflicts with Cloudflare or other edge proxies.
*   **Dynamic Content:** Perform regex-based text replacements on the fly.
*   **JS Injection:** Easily inject custom JavaScript into the `<body>` of proxied HTML pages.

## Quick Start (Docker)

The easiest way to deploy Replica is pulling the pre-built image directly from the GitHub Container Registry.

### 1. Run via GHCR

You don't need to clone the repo to run the proxy. Just create a `.env` file (see [Configuration](#configuration-reference)) and run:

```bash
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  --name replica \
  ghcr.io/sarperavci/replica:latest
```

### 2. Build from Source

If you prefer to build the image yourself or use Docker Compose:

```bash
# Clone the repo
git clone https://github.com/sarperavci/replica.git
cd replica

# Build and run
docker compose up --build
```

## Configuration Reference

Replica is configured entirely via environment variables.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `TARGET_ORIGIN` | `https://example.com` | The upstream site you want to proxy. |
| `REPLACEMENTS` | `[]` | JSON string of rules. Use `"to": "MY_HOST"` to dynamically map to your origin. |
| `CACHE_TTL_STATIC` | (Internal Default) | Time-to-live (seconds) for static files. |
| `CACHE_TTL_HTML` | (Internal Default) | Time-to-live (seconds) for HTML content. |
| `INJECT_JS` | `None` | String of JavaScript to inject before `</body>`. |
| `INJECT_JS_FILE` | `None` | Path to a local JS file. If set, this overrides `INJECT_JS`. |


## Local Development

Follow these steps to set up a local environment for debugging or contributing.

### 1. Environment Setup

```bash
# Create a virtual environment
python3.10 -m venv .venv

# Activate it
source .venv/bin/activate
# Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file in the root directory:

```bash
cp .env.example .env
```

Ensure the variables (especially `TARGET_ORIGIN`) are set correctly for your local testing.

### 3. Running the Server

**Standard Run:**
Since `replica` is a package, run it as a module:

```bash
python -m replica
```

**Development Mode (Hot Reload):**
For active development, use Uvicorn directly to reload on code changes:

```bash
uvicorn replica.main:app --reload --host 127.0.0.1 --port 8000
```

## License

MIT License. See [LICENSE](LICENSE) for details.

## Contributing

Pull requests are welcome. If you find a bug or want to suggest a feature, please open an issue.