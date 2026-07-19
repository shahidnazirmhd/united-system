"""Process entrypoint: wires the webhook server, client instances, and
handler registry together at process start, per
HRMS_Folder_Structure.md section 3.7.

`create_app` (webhook/server.py) does the actual composition (every client
and service constructed exactly once, in its `lifespan` context manager);
this file's only remaining job is to build the ASGI `app` object uvicorn
serves and to provide a `python -m src.main` local-run path. In production
this module is instead pointed to directly by uvicorn/gunicorn
(`src.main:app`) — see Dockerfile's CMD.
"""
from __future__ import annotations

import uvicorn

from src.config import get_settings
from src.webhook.server import create_app

settings = get_settings()
app = create_app(settings)


def run() -> None:
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8080,
        reload=not settings.is_production,
        log_config=None,  # this service configures its own JSON logging (logging_config.py); uvicorn's default
        # colored console formatter would otherwise fight with it for control of the root logger.
    )


if __name__ == "__main__":
    run()
