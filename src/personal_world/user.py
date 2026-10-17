"""User model: per-person world isolation.

Each user gets their own world, journal, preferences, vault, and
companion theme pack. Shared infrastructure (homelab providers) is
global. The user model is minimal — just enough to partition state,
never to profile or track.

The user owns their world. The world owns the truth.
"""

from pathlib import Path

from pydantic import BaseModel, Field

from .model import Accessibility


def _default_root() -> Path:
    import os
    return Path(os.environ.get("PW_DATA_DIR", "/data"))


class User(BaseModel):
    """A person in the Personal World system."""

    id: str
    name: str
    display_name: str | None = None
    companion: str = "world-keeper"
    accessibility: Accessibility = Field(default_factory=Accessibility)
    vault_enabled: bool = True

    root: Path = Field(default_factory=lambda: _default_root())

    @property
    def data_dir(self) -> Path:
        # Root is an explicit field (PW_DATA_DIR default) so callers can
        # thread the app's real data dir without env luck; the per-user
        # shape under it never changes.
        return self.root / "users" / self.id

    @property
    def world_path(self) -> Path:
        return self.data_dir / "world.json"

    @property
    def journal_path(self) -> Path:
        return self.data_dir / "journal.ndjson"

    @property
    def vault_path(self) -> Path:
        return self.data_dir / "vault.enc"

    @property
    def prefs_path(self) -> Path:
        return self.data_dir / "prefs.json"


class UserManager:
    """Manages user registration and lookup.

    Users are stored as individual YAML files under the users
    directory. The first user to register becomes the owner.
    """

    def __init__(self, users_dir: Path) -> None:
        self.users_dir = users_dir
        self._users: dict[str, User] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self.users_dir.exists():
            for path in self.users_dir.glob("*.json"):
                try:
                    import json

                    data = json.loads(path.read_text())
                    user = User.model_validate(data)
                    self._users[user.id] = user
                except Exception:  # nosec B112  # skip this user file, load the rest
                    continue
        self._loaded = True

    def get(self, user_id: str) -> User | None:
        self._ensure_loaded()
        return self._users.get(user_id)

    def create(self, user: User) -> User:
        """Register a new user."""
        self._ensure_loaded()
        self.users_dir.mkdir(parents=True, exist_ok=True)
        self._users[user.id] = user
        (self.users_dir / f"{user.id}.json").write_text(
            user.model_dump_json(indent=2)
        )
        user.data_dir.mkdir(parents=True, exist_ok=True)
        return user

    def list_users(self) -> list[User]:
        self._ensure_loaded()
        return list(self._users.values())
