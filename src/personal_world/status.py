from enum import Enum


class Status(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    UNKNOWN = "unknown"
    NEEDS_ATTENTION = "needs_attention"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    DISABLED = "disabled"
    NOT_CONFIGURED = "not_configured"

    def __str__(self) -> str:
        return self.value


RANK: dict[str, int] = {
    Status.HEALTHY.value: 0,
    Status.WARNING.value: 1,
    Status.UNKNOWN.value: 2,
    Status.NEEDS_ATTENTION.value: 3,
    Status.UNAVAILABLE.value: 4,
    Status.STALE.value: 5,
    Status.DISABLED.value: 6,
    Status.NOT_CONFIGURED.value: 7,
}


def worst(statuses: list[str]) -> str:
    if not statuses:
        return Status.HEALTHY.value
    ranked = [(RANK.get(s, 99), s) for s in statuses]
    ranked.sort(reverse=True)
    return ranked[0][1]
