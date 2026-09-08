import os
import sys
import traceback
from pathlib import Path

# Add project root and current working dir to sys.path
_current_dir = Path(__file__).resolve().parent
_root_dir = _current_dir.parent
for p in [_root_dir, _current_dir, Path.cwd()]:
    str_p = str(p)
    if str_p not in sys.path:
        sys.path.insert(0, str_p)

try:
    from app.api.app import app
    try:
        from mangum import Mangum
        handler = Mangum(app, lifespan="off")
    except Exception:
        handler = app

except Exception as e:
    tb = traceback.format_exc()
    print(f"CRITICAL VERCEL INIT ERROR: {tb}", file=sys.stderr)

    async def fallback_app(scope, receive, send):
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
    app = fallback_app
    handler = fallback_app


