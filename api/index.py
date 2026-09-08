from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
import os
import traceback
from pathlib import Path

_root_dir = Path(__file__).resolve().parent.parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

# Try importing real app
try:
    from app.api.app import app
except Exception as _init_err:
    _init_tb = traceback.format_exc()
    print(f"CRITICAL APP IMPORT ERROR: {_init_tb}", file=sys.stderr)
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def catch_all(path_name: str):
        return {
            "error": "Application initialization failed",
            "traceback": _init_tb,
            "python_version": sys.version,
            "cwd": os.getcwd(),
            "sys_path": sys.path,
        }




