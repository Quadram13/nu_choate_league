from __future__ import annotations

import uvicorn

from ..db import database_url
from ..paths import project_root


def run_server(*, host: str = "127.0.0.1", port: int = 8000, reload: bool = True) -> None:
    database_url()
    root = project_root()
    uvicorn.run(
        "nu_choate_league.web.app:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=[str(root / "src"), str(root / "hub")],
    )
