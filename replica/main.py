import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from .proxy import proxy_request
from .config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("replica.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup validation
    errors = settings.validate()
    if errors:
        for err in errors:
            logger.error(err)
        logger.error("Startup validation failed — exiting")
        sys.exit(2)

    settings.print_diagnostics()
    yield

app = FastAPI(
    title="Replica - Reverse Proxy",
    redoc_url=None,
    docs_url=None,
    openapi_url=None,
    lifespan=lifespan
)

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def handle(request: Request, path: str):
    return await proxy_request(request, path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
