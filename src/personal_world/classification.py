from enum import Enum

from pydantic import Field


class Classification(str, Enum):
    WORLD = "world"
    PRIVATE = "private"
    SECRET = "secret"  # nosec B105  # the classification enum member, not a credential


def meta(kind: str, exportable: bool = False) -> dict:
    """Field metadata: data classification and settings-export eligibility."""
    return {"classification": kind, "exportable": exportable}


def field_meta(field) -> tuple[str, bool]:
    extra = getattr(field, "json_schema_extra", None) or {}
    return extra.get("classification", "world"), bool(extra.get("exportable", False))


def secret_ref(name: str) -> Field:
    return Field(default=None, json_schema_extra=meta("secret"))
