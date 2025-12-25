from fastapi import FastAPI, Request
from .proxy import proxy_request

app = FastAPI(title="Replica - Reverse Proxy")

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def handle(request: Request, path: str):
    return await proxy_request(request, path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
