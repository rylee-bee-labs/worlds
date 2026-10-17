"""Provider configuration schemas for the Connections & Providers UI.

Each capability/provider exposes a config_schema that the frontend
renders as a form — no bespoke React code per provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConfigField:
    """A single configuration field for a provider."""
    key: str
    label: str
    type: str  # text, url, secret, select, boolean
    required: bool = False
    description: str = ""
    placeholder: str = ""
    options: list[dict[str, str]] = field(default_factory=list)
    secret_ref: bool = False  # field stores a Vault reference, not a value

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "key": self.key,
            "label": self.label,
            "type": self.type,
            "required": self.required,
        }
        if self.description:
            d["description"] = self.description
        if self.placeholder:
            d["placeholder"] = self.placeholder
        if self.options:
            d["options"] = self.options
        if self.secret_ref:
            d["secret_ref"] = True
        return d


@dataclass
class ProviderSchema:
    """Configuration schema for a provider/adapter."""
    id: str
    display_name: str
    capability: str
    description: str
    adapter_type: str  # e.g. "plex", "sonarr", "ics", "webhook", "ntfy"
    config_fields: list[ConfigField] = field(default_factory=list)
    can_test: bool = True
    multiple: bool = True  # can have multiple instances

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "capability": self.capability,
            "description": self.description,
            "adapter_type": self.adapter_type,
            "config_fields": [f.to_dict() for f in self.config_fields],
            "can_test": self.can_test,
            "multiple": self.multiple,
        }


@dataclass
class CapabilitySchema:
    """Full schema for a capability: available providers, active config."""
    capability: str
    display_name: str
    description: str
    icon: str
    providers: list[ProviderSchema]
    needs_setup: bool = False
    help_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "providers": [p.to_dict() for p in self.providers],
            "needs_setup": self.needs_setup,
            "help_text": self.help_text,
        }


# ── Provider schemas ──────────────────────────────────────────────

def _media_providers() -> list[ProviderSchema]:
    return [
        ProviderSchema(
            id="plex",
            display_name="Plex",
            capability="media",
            description="Plex Media Server",
            adapter_type="plex",
            config_fields=[
                ConfigField("base_url", "Server URL", "url", required=True,
                            placeholder="http://plex.local:32400"),
                ConfigField("token", "Token", "secret", required=True,
                            secret_ref=True,
                            description="Stored in Vault"),
            ],
        ),
        ProviderSchema(
            id="sonarr",
            display_name="Sonarr",
            capability="media",
            description="TV show management",
            adapter_type="sonarr",
            config_fields=[
                ConfigField("base_url", "Server URL", "url", required=True,
                            placeholder="http://sonarr.local:8989"),
                ConfigField("api_key", "API Key", "secret", required=True,
                            secret_ref=True),
            ],
        ),
        ProviderSchema(
            id="radarr",
            display_name="Radarr",
            capability="media",
            description="Movie management",
            adapter_type="radarr",
            config_fields=[
                ConfigField("base_url", "Server URL", "url", required=True,
                            placeholder="http://radarr.local:7878"),
                ConfigField("api_key", "API Key", "secret", required=True,
                            secret_ref=True),
            ],
        ),
        ProviderSchema(
            id="lidarr",
            display_name="Lidarr",
            capability="media",
            description="Music management",
            adapter_type="lidarr",
            config_fields=[
                ConfigField("base_url", "Server URL", "url", required=True,
                            placeholder="http://lidarr.local:8686"),
                ConfigField("api_key", "API Key", "secret", required=True,
                            secret_ref=True),
            ],
        ),
    ]


def _calendar_providers() -> list[ProviderSchema]:
    return [
        ProviderSchema(
            id="ics",
            display_name="ICS Feed",
            capability="calendar",
            description="iCalendar URL feed",
            adapter_type="ics",
            config_fields=[
                ConfigField("name", "Name", "text", required=True,
                            placeholder="My Calendar"),
                ConfigField("url", "URL", "url", required=True,
                            placeholder="https://calendar.google.com/.../basic.ics"),
            ],
        ),
        ProviderSchema(
            id="caldav",
            display_name="CalDAV",
            capability="calendar",
            description="CalDAV server",
            adapter_type="caldav",
            config_fields=[
                ConfigField("name", "Name", "text", required=True,
                            placeholder="Work Calendar"),
                ConfigField("server_url", "Server URL", "url", required=True,
                            placeholder="https://caldav.example.com"),
                ConfigField("username", "Username", "text",
                            placeholder="user@example.com"),
                ConfigField("password", "Password", "secret", secret_ref=True),
            ],
            can_test=False,
        ),
    ]


def _notifications_providers() -> list[ProviderSchema]:
    return [
        ProviderSchema(
            id="webhook",
            display_name="Webhook",
            capability="notifications",
            description="Generic HTTP webhook",
            adapter_type="webhook",
            config_fields=[
                ConfigField("name", "Name", "text", required=True,
                            placeholder="My Webhook"),
                ConfigField("url", "URL", "url", required=True,
                            placeholder="https://hooks.example.com/..."),
                ConfigField("headers", "Headers (JSON)", "text",
                            placeholder='{"Authorization": "Bearer ..."}'),
            ],
        ),
        ProviderSchema(
            id="ntfy",
            display_name="ntfy",
            capability="notifications",
            description="ntfy push notifications",
            adapter_type="ntfy",
            config_fields=[
                ConfigField("name", "Name", "text", required=True,
                            placeholder="Phone"),
                ConfigField("topic", "Topic", "text", required=True,
                            placeholder="my-world-alerts"),
                ConfigField("server", "Server", "url",
                            placeholder="https://ntfy.sh"),
                ConfigField("token", "Token", "secret", secret_ref=True,
                            description="Optional auth token (stored in Vault)"),
            ],
        ),
    ]


def _updates_providers() -> list[ProviderSchema]:
    return [
        ProviderSchema(
            id="github_release",
            display_name="GitHub Release",
            capability="update_discovery",
            description="Watch GitHub releases",
            adapter_type="github_release",
            config_fields=[
                ConfigField("name", "Name", "text", required=True,
                            placeholder="Personal World"),
                ConfigField("repository", "Repository", "text", required=True,
                            placeholder="Rylee-Bee/personal-world"),
                ConfigField("current_version", "Current version", "text",
                            placeholder="1.0.0"),
            ],
        ),
        ProviderSchema(
            id="version_url",
            display_name="Version URL",
            capability="update_discovery",
            description="Check a URL for version info",
            adapter_type="version_url",
            config_fields=[
                ConfigField("name", "Name", "text", required=True,
                            placeholder="My Service"),
                ConfigField("url", "Version URL", "url", required=True,
                            placeholder="https://service.example/version.json"),
            ],
            can_test=False,
        ),
    ]


def _auth_providers() -> list[ProviderSchema]:
    return [
        ProviderSchema(
            id="oidc",
            display_name="OIDC / SSO",
            capability="auth",
            description="OpenID Connect identity provider",
            adapter_type="oidc",
            config_fields=[
                ConfigField("display_name", "Display name", "text",
                            placeholder="My Identity Provider"),
                ConfigField("issuer_url", "Issuer URL", "url", required=True,
                            placeholder="https://auth.example.com"),
                ConfigField("client_id", "Client ID", "text", required=True),
                ConfigField("client_secret", "Client secret", "secret",
                            required=True, secret_ref=True),
                ConfigField("scopes", "Scopes", "text",
                            placeholder="openid profile email"),
            ],
            can_test=True,
            multiple=False,
        ),
    ]


def _reasoning_providers() -> list[ProviderSchema]:
    return [
        ProviderSchema(
            id="ollama",
            display_name="Ollama",
            capability="reasoning",
            description="Local Ollama instance",
            adapter_type="ollama",
            config_fields=[
                ConfigField("base_url", "Server URL", "url", required=True,
                            placeholder="http://ollama:11434"),
                ConfigField("model", "Model", "text", required=True,
                            placeholder="qwen3:1.7b"),
                ConfigField("timeout", "Timeout (seconds)", "text",
                            placeholder="120"),
            ],
            can_test=True,
            multiple=False,
        ),
        ProviderSchema(
            id="openai_compat",
            display_name="OpenAI-compatible",
            capability="reasoning",
            description="OpenAI-compatible API",
            adapter_type="openai_compat",
            config_fields=[
                ConfigField("base_url", "API URL", "url", required=True),
                ConfigField("model", "Model", "text", required=True),
                ConfigField("api_key", "API Key", "secret", secret_ref=True),
            ],
            can_test=False,
            multiple=False,
        ),
        ProviderSchema(
            id="openai",
            display_name="OpenAI",
            capability="reasoning",
            description="OpenAI API",
            adapter_type="openai",
            config_fields=[
                ConfigField("model", "Model", "text", required=True,
                            placeholder="gpt-4o"),
                ConfigField("api_key", "API Key", "secret", required=True,
                            secret_ref=True),
            ],
            can_test=False,
            multiple=False,
        ),
        ProviderSchema(
            id="anthropic",
            display_name="Anthropic",
            capability="reasoning",
            description="Anthropic Claude API",
            adapter_type="anthropic",
            config_fields=[
                ConfigField("model", "Model", "text", required=True,
                            placeholder="claude-sonnet-5"),
                ConfigField("api_key", "API Key", "secret", required=True,
                            secret_ref=True),
            ],
            can_test=False,
            multiple=False,
        ),
    ]


# ── Full capability schemas ────────────────────────────────────────

CAPABILITY_SCHEMAS: dict[str, CapabilitySchema] = {
    "media": CapabilitySchema(
        capability="media",
        display_name="Media",
        description="Movies, TV shows, music",
        icon="icon-world-content-story",
        providers=_media_providers(),
        needs_setup=True,
        help_text="Connect a media server to see your library.",
    ),
    "calendar": CapabilitySchema(
        capability="calendar",
        display_name="Calendar",
        description="Calendar events and schedules",
        icon="icon-system-device-theme",
        providers=_calendar_providers(),
        needs_setup=True,
        help_text="Add a calendar source to see upcoming events.",
    ),
    "notifications": CapabilitySchema(
        capability="notifications",
        display_name="Notifications",
        description="Push notifications and alerts",
        icon="icon-status-feedback-notification",
        providers=_notifications_providers(),
        needs_setup=True,
        help_text="Add a notification destination to receive alerts.",
    ),
    "update_discovery": CapabilitySchema(
        capability="update_discovery",
        display_name="Updates",
        description="Version and update discovery",
        icon="icon-system-action-refresh",
        providers=_updates_providers(),
        needs_setup=True,
        help_text="Add something to watch for updates.",
    ),
    "auth": CapabilitySchema(
        capability="auth",
        display_name="Authentication",
        description="Sign-in and identity",
        icon="icon-system-device-accessibility",
        providers=_auth_providers(),
        needs_setup=False,
        help_text="Local login is always available. OIDC adds single sign-on.",
    ),
    "reasoning": CapabilitySchema(
        capability="reasoning",
        display_name="Reasoning",
        description="AI reasoning provider",
        icon="icon-world-content-world",
        providers=_reasoning_providers(),
        needs_setup=False,
        help_text="Choose an AI provider for the assistant.",
    ),
}


def get_capability_schemas() -> list[dict[str, Any]]:
    """Return all capability schemas for the UI."""
    return [cs.to_dict() for cs in CAPABILITY_SCHEMAS.values()]


def get_capability_schema(capability: str) -> dict[str, Any] | None:
    """Return schema for a single capability."""
    cs = CAPABILITY_SCHEMAS.get(capability)
    return cs.to_dict() if cs else None
