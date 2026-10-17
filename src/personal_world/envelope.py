from typing import Any

from pydantic import BaseModel, Field

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_DENIED = 2
EXIT_DRIFT = 3


class Result(BaseModel):
    ok: bool
    status: str
    changed: bool = False
    warnings: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    data: Any = None


def ok(status: str = "healthy", **kwargs: Any) -> Result:
    return Result(ok=True, status=status, **kwargs)


def fail(status: str = "unhealthy", **kwargs: Any) -> Result:
    kwargs.setdefault("warnings", [])
    return Result(ok=False, status=status, **kwargs)
