"""
Vercel Serverless Entrypoint for ARM Starosta.
"""
import sys
import traceback

try:
    from app.api.app import app
except Exception as e:
    tb = traceback.format_exc()
    print(f"CRITICAL VERCEL INIT ERROR: {tb}", file=sys.stderr)

    async def app(scope, receive, send):
        if scope["type"] == "http":
            body = f"Serverless Startup Exception:\n\n{tb}".encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", str(len(body)).encode("utf-8")),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })

# Vercel ASGI Handler
handler = app

