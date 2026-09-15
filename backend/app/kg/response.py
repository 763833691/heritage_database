from __future__ import annotations

from typing import Any


def ok(data: Any = None, message: str = "success", code: int = 0) -> dict[str, Any]:
    return {"code": code, "message": message, "data": data if data is not None else {}}


def fail(message: str, data: Any = None, code: int = 1) -> dict[str, Any]:
    return {"code": code, "message": message, "data": data}
