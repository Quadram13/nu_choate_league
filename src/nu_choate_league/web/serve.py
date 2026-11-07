from __future__ import annotations

import sys

import uvicorn

from ..db import database_url
from ..paths import project_root


def run_server(*, host: str = "127.0.0.1", port: int = 8000, reload: bool = True) -> None:
    database_url()
    root = project_root()
    if reload and sys.platform == "win32":
        _terminate_worker_on_reload()
    uvicorn.run(
        "nu_choate_league.web.app:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=[str(root / "src"), str(root / "hub")],
    )


def _terminate_worker_on_reload() -> None:
    """On Windows, uvicorn reloads by sending CTRL_C_EVENT and joining the worker.

    That event does not stop the worker, so the reloader blocks in
    process.join() after "Reloading..." and the old process keeps serving.
    Terminate the worker instead. The reloader still owns the listening socket.
    """
    from uvicorn._subprocess import get_subprocess
    from uvicorn.supervisors.basereload import BaseReload

    def restart(self: BaseReload) -> None:
        self.process.terminate()
        self.process.join()
        self.process = get_subprocess(
            config=self.config,
            target=self.target,
            sockets=self.sockets,
        )
        self.process.start()

    BaseReload.restart = restart  # type: ignore[method-assign]
