"""Weekly brain update scheduler (Principle 12: local brains update weekly).

A zero-dependency daemon thread: it checks hourly and, if a week has passed
since the last update (or it never ran), runs ``engine.brains.weekly_update()``.
The last-run timestamp is persisted on disk so the cadence survives restarts
(important on Render, where the process can recycle).
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timedelta

_FMT = "%Y-%m-%d %H:%M:%S"


def _state_path(root: str) -> str:
    return os.path.join(root, "weekly_update.json")


def last_run(root: str) -> str | None:
    path = _state_path(root)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f).get("last_run")
        except Exception:
            return None
    return None


def due(root: str, every_days: int = 7) -> bool:
    lr = last_run(root)
    if not lr:
        return True
    try:
        return datetime.now() - datetime.strptime(lr, _FMT) >= timedelta(days=every_days)
    except Exception:
        return True


def run_if_due(engine, root: str, every_days: int = 7) -> dict | None:
    if not due(root, every_days):
        return None
    result = engine.brains.weekly_update()
    with open(_state_path(root), "w", encoding="utf-8") as f:
        json.dump({"last_run": result["at"], "result": result}, f, indent=2)
    return result


def status(root: str, every_days: int = 7) -> dict:
    return {"last_weekly_update": last_run(root), "due_now": due(root, every_days)}


def start_weekly_scheduler(engine, root: str, check_every_s: int = 3600) -> threading.Thread:
    """Start the daemon loop. Runs once on boot if overdue, then hourly checks."""
    def loop() -> None:
        while True:
            try:
                run_if_due(engine, root)
            except Exception:
                pass
            time.sleep(check_every_s)

    t = threading.Thread(target=loop, daemon=True, name="sb-weekly-update")
    t.start()
    return t
