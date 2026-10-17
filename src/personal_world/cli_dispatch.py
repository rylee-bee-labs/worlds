"""The manifest-bound CLI surface — owner decision #19.

Decision #19: *everything the product can do has a simple CLI wrapper and
an API route, and both derive from the same source, so a small agent or
bot does not have to think — it just files things the right way.*

The single source is ``api_manifest.py`` (the same table ``GET
/api/manifest`` serves as ``endpoints``). Every wrapper in this module
declares the manifest id(s) it files, and its ``kind``/``gate`` are READ
FROM THAT TABLE — never restated here. An id that does not exist fails at
import, loudly, the way ``api_manifest.Endpoint`` does. ``personal-world
api-manifest`` prints the joined table: every endpoint row carries the
shell command that files it (or ``null``), plus explicit coverage counts,
so the map states its own completeness instead of implying it.

Three commands are added to ``personal-world``:

* ``api-manifest`` — the bot's map (endpoints + CLI wrappers + coverage).
* ``api <METHOD> <path>`` — the generic authenticated escape hatch
  against a running local backend. Any row in the map is callable, so a
  capability with no friendly wrapper is still reachable.
* ``do <noun> <verb>`` — the friendly wrappers, one verb each.

``do`` is a group rather than bare top-level nouns because ``cli.py``
already owns ``status``, ``journal``, ``prefs``, ``manifest`` and
``history`` with pre-decision-#19 semantics that existing tests pin
(``tests/test_framework.py::test_core_only_cli_status_and_manifest``
asserts the exact shape of ``manifest``; ``tests/test_prefs.py::
TestCliPrefs`` asserts ``prefs set`` mutates immediately). This module is
additive and clobbers nothing. Retiring the legacy verbs onto this
surface is an owner decision, not a lane-local one.

Transports (both about what they need):

* ``service`` — the default. The wrapper calls the SAME canonical service
  function the API handler calls (``prefs.set_prefs``,
  ``Journal.supersede``, ``Scheduler.add``, ``NativeDiscovery``,
  ``ProposalStore``, ``TemplateRegistry``, ``OIDCService`` …). No HTTP
  server required, matching ``docs/ARCHITECTURE.md`` ("The CLI does not
  require an HTTP server").
* ``http`` — ``api`` and ``do chat send``. Chat's composition (world
  context, brain templates, tool loop, proposal extraction, transcript)
  lives only in ``api.py``'s handler; re-implementing it here is exactly
  the divergence decision #19 forbids, so those two go to the backend. An
  unreachable backend answers ``unavailable`` (exit 3) — never a guess,
  never a fabricated reply.

WRITE SAFETY (the part a bot must not have to think about):

* A write wrapper **files a durable proposal** by default and mutates
  nothing. It prints ``proposal_id`` and exits 4.
* Acting requires BOTH ``--approve`` and the step-up credential in the
  environment (``PW_STEP_UP_TOKEN``), which must resolve — through
  ``identity.resolve_principal``, the same single entry point the API uses — to
  the calling principal. A bare flag never mutates anything.
* Reads need no approval.
* ``--approve`` files the proposal first, then approves it through
  ``ProposalStore.approve`` (server-held evidence: actor, time, method)
  and executes it. The durable record survives either way, so there is
  always an audit of what was asked and what was done.

EXIT CODES (this module's contract; ``envelope.EXIT_OK``/``EXIT_ERROR``
are reused, the rest are defined here because ``envelope.EXIT_DENIED=2``
predates this surface and ``cli.py``'s legacy commands keep their own
mapping):

    0  ok — the command did what it says (``changed``/``data.mutated``
       say whether it mutated anything)
    1  error — refused, invalid state, not found, unexpected failure
    2  usage — bad arguments (argparse's own code for a usage error)
    3  not_configured / unavailable — nothing is wired, or the backend or
       a provider cannot be reached
    4  gated — nothing was mutated; a human must approve (a proposal was
       filed, or ``--approve``/the step-up credential is missing, or the
       surface is person-only). Exit 4 is NOT an error.

Every command prints the ``envelope.Result`` JSON with ``--json`` and a
short human rendering without it. Statuses are accurate, in the established
free-form style (``healthy``, ``not_configured``, ``unavailable``,
``proposed``, ``needs_approval``, ``needs_step_up``, ``denied``,
``person_only``, ``not_found``, ``invalid_args``, ``unsupported``,
``unhealthy``).

``ok`` and exit 4 together carry one distinction worth knowing:

* ``ok=true`` + exit 4 (``proposed``, ``needs_approval``) — the command
  did its DEFAULT job: it filed a proposal or showed the dry-run. Nothing
  was mutated (``data.mutated=false``); a human can approve it.
* ``ok=false`` + exit 4 (``needs_step_up``, ``person_only``, ``denied``) —
  the requested mutation was REFUSED. Nothing was mutated either.

KNOWN LIMITS (stated, not hidden — see ``docs/CLI-REFERENCE.md``):

* ``ProposalStore`` and ``Scheduler`` cache their JSON file in memory at
  construction. A backend that is ALREADY RUNNING will not see a proposal
  or reminder this CLI files until it restarts, and its own next write can
  drop it. This CLI always reads the file fresh, so its own view is
  correct. Closing the gap needs a create/reload route in
  ``api.py``/``tool_registry.py`` (out of this lane).
* ``cli.*`` proposal types are executed by this module's actor table.
  ``POST /api/proposals/{id}/execute`` answers ``unsupported`` for them,
  visibly, never silently.
* In-process writes make the CLI a second writer of ``world.json`` /
  ``reminders.json`` alongside a running backend (the documented
  multi-writer gap in ``docs/repo/WIRING-READINESS.md``). Write wrappers
  say so in ``warnings``.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any, Callable

from .api_manifest import ENDPOINTS, GATES, KINDS, endpoint_manifest
from .envelope import EXIT_ERROR, EXIT_OK, Result, fail, ok
from .url_safety import http_urlopen

# ── Exit codes ───────────────────────────────────────────────────────
#: bad arguments (argparse uses 2 for a usage error; we agree with it)
EXIT_USAGE = 2
#: nothing is wired, or the backend/provider cannot be reached
EXIT_UNAVAILABLE = 3
#: nothing was mutated; a human must approve (NOT an error)
EXIT_NEEDS_APPROVAL = 4

#: status → exit code. Anything absent falls back to EXIT_OK (ok results)
#: or EXIT_ERROR (failures). ``proposed``/``needs_*`` map to 4 even though
#: the Result is ok=True: the command succeeded at its default intent
#: (file, don't mutate) and the caller must know nothing changed.
EXIT_BY_STATUS: dict[str, int] = {
    "invalid_args": EXIT_USAGE,
    "usage": EXIT_USAGE,
    "not_configured": EXIT_UNAVAILABLE,
    "unavailable": EXIT_UNAVAILABLE,
    "proposed": EXIT_NEEDS_APPROVAL,
    "needs_approval": EXIT_NEEDS_APPROVAL,
    "needs_step_up": EXIT_NEEDS_APPROVAL,
    "person_only": EXIT_NEEDS_APPROVAL,
    "denied": EXIT_NEEDS_APPROVAL,
    "refused": EXIT_NEEDS_APPROVAL,
    "unauthenticated": EXIT_NEEDS_APPROVAL,
    "unauthorized": EXIT_NEEDS_APPROVAL,
    "forbidden": EXIT_NEEDS_APPROVAL,
    "expired": EXIT_NEEDS_APPROVAL,
}

# ── Names and environment ────────────────────────────────────────────
#: Top-level group holding the friendly wrappers. A group (not bare
#: nouns) because cli.py already owns status/journal/prefs/manifest/
#: history — see the module docstring.
DISPATCH_GROUP = "do"
MANIFEST_COMMAND = "api-manifest"
API_COMMAND = "api"

TOKEN_ENV = "PW_API_TOKEN"  # nosec B105  # the NAME of the env var holding the token
#: A different credential to act as (multi mode: an agent-scoped token).
CLI_TOKEN_ENV = "PW_CLI_TOKEN"  # nosec B105  # the NAME of the env var holding the token
#: The step-up credential. Never a flag: an explicit env credential that
#: must resolve to the calling principal, mirroring POST /api/auth/step-up.
STEP_UP_ENV = "PW_STEP_UP_TOKEN"
BASE_ENV = "PW_API_BASE"
SESSION_ENV = "PW_SESSION"
IDENTITY_MODE_ENV = "PW_IDENTITY_MODE"
DEFAULT_BASE = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT = 30.0

_ROW_BY_ID = {row.id: row for row in ENDPOINTS}

#: Proposal types ``ProposalStore.execute`` already owns (created by the
#: chat tool loop). They route to the store, never to a CLI actor, so the
#: canonical executor stays the only one for brain-proposed writes.
STORE_EXECUTABLE = frozenset(
    {"journal_write", "world_intent", "world_fact", "reminder", "reconciler_apply"}
)


def exit_for(result: Result) -> int:
    """The documented exit code for one envelope."""
    if result.ok:
        return EXIT_BY_STATUS.get(result.status, EXIT_OK)
    return EXIT_BY_STATUS.get(result.status, EXIT_ERROR)


# ── Declarative action table ─────────────────────────────────────────


@dataclass(frozen=True)
class Arg:
    """One argparse argument for a wrapper."""

    flags: tuple[str, ...]
    kw: dict[str, Any]


def A(*flags: str, **kw: Any) -> Arg:
    return Arg(flags=flags, kw=kw)


@dataclass(frozen=True)
class Action:
    """One ``do <noun> <verb>`` wrapper, bound to manifest ids.

    ``kind`` and ``gate`` are DERIVED from ``api_manifest`` — the single
    source — never restated here, so a route's kind or gate change shows
    up in the CLI without an edit and cannot drift.

    Two flags describe how a WRITE wrapper behaves:

    * ``mutates`` (default) — files a durable proposal by default and acts
      only on ``--approve`` + the step-up credential.
    * ``direct`` — the trust-boundary commands themselves (approving or
      rejecting a proposal): there is nothing to propose, so the default
      is an explicit dry-run and acting needs the same two keys.
    * ``mutates=False, direct=False`` on a kind=write row — a write that
      mutates no world state (``chat send``: a model invocation that can
      journal and create proposals of its own). Documented per action.
    """

    noun: str
    verb: str
    help: str
    run: Callable[["Ctx"], Result]
    ids: tuple[str, ...] = ()
    mutates: bool = True
    direct: bool = False
    person_only: bool = False
    transport: str = "service"
    args: tuple[Arg, ...] = ()
    note: str | None = None

    @property
    def command(self) -> str:
        if self.verb:
            return f"personal-world {DISPATCH_GROUP} {self.noun} {self.verb}"
        return f"personal-world {self.noun}"

    @property
    def rows(self) -> tuple[Any, ...]:
        return tuple(_ROW_BY_ID[i] for i in self.ids)

    @property
    def kind(self) -> str:
        """Read from the manifest: write if ANY bound row is a write."""
        return "write" if any(r.kind == "write" for r in self.rows) else "read"

    @property
    def gate(self) -> str:
        """The strictest gate among the bound manifest rows."""
        gates = [row.gate for row in self.rows] or ["none"]
        return sorted(gates, key=GATES.index)[-1]

    @property
    def files_proposal(self) -> bool:
        return self.kind == "write" and self.mutates and not self.direct

    @property
    def needs_approval(self) -> bool:
        """Whether ``--approve`` + the step-up credential gate this action."""
        return self.kind == "write" and (self.mutates or self.direct)

    @property
    def route(self) -> str:
        return ", ".join(f"{r.method} {r.path}" for r in self.rows) or "(any)"

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "command": self.command,
            "noun": self.noun,
            "verb": self.verb,
            "help": self.help,
            "ids": list(self.ids),
            "kind": self.kind,
            "gate": self.gate,
            "auth": ", ".join(sorted({r.auth for r in self.rows})) or "authenticated",
            "transport": self.transport,
            "route": self.route,
            "person_only": self.person_only,
            "needs_approval": self.needs_approval,
            "files_proposal": self.files_proposal,
        }
        if self.note:
            out["note"] = self.note
        return out


# ── The dispatch context ─────────────────────────────────────────────


class Ctx:
    """Everything a wrapper needs, built lazily.

    Constructed from the ``(world, registry, journal, args)`` tuple
    ``cli.py`` hands every command. Expensive pieces (the api-shaped
    registry, the scheduler, the proposal store, the principal) are only
    built by the commands that ask for them, so ``do auth status`` never
    pays for provider construction.
    """

    def __init__(self, args: Any, world: Any, registry: Any, journal: Any) -> None:
        self.args = args
        self._world0 = world
        self._registry0 = registry
        self._journal0 = journal
        self.data_dir = Path(getattr(args, "data_dir", None) or "./data")
        self.config_dir = Path(getattr(args, "config_dir", None) or "./config")

    # -- output -------------------------------------------------------
    @property
    def as_json(self) -> bool:
        # ``do --json <noun> <verb>`` and ``do <noun> <verb> --json`` both
        # work: the group flag uses a distinct dest because a subparser's
        # defaults overwrite the parent namespace.
        return bool(getattr(self.args, "json", False)) or bool(
            getattr(self.args, "do_json", False)
        )

    # -- identity / credentials ---------------------------------------
    @cached_property
    def identity_mode(self) -> str:
        return os.environ.get(IDENTITY_MODE_ENV, "single")

    @cached_property
    def identity_store(self):
        from .identity import IdentityStore

        return IdentityStore(self.data_dir)

    @cached_property
    def instance_token(self) -> str | None:
        """The instance credential. ``<data_dir>/.env`` wins over the
        environment, mirroring ``api._reconcile_boot_token``: the token a
        human created through first-run setup outranks deployment env."""
        env_file = self.data_dir / ".env"
        if env_file.is_file():
            try:
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("#"):
                        continue
                    if line.startswith(f"{TOKEN_ENV}="):
                        value = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if value:
                            return value
            except OSError:
                pass
        return os.environ.get(TOKEN_ENV) or None

    @property
    def instance_token_source(self) -> str:
        env_file = self.data_dir / ".env"
        if env_file.is_file():
            try:
                text = env_file.read_text(encoding="utf-8")
            except OSError:
                text = ""
            for line in text.splitlines():
                line = line.strip()
                if not line.startswith("#") and line.startswith(f"{TOKEN_ENV}="):
                    if line.split("=", 1)[1].strip().strip('"').strip("'"):
                        return str(env_file)
        if os.environ.get(TOKEN_ENV):
            return f"{TOKEN_ENV} env"
        return "none"

    @cached_property
    def cli_token(self) -> str | None:
        """The credential this invocation acts as."""
        return os.environ.get(CLI_TOKEN_ENV) or self.instance_token

    @cached_property
    def principal(self):
        """The canonical Principal for this invocation, or None.

        Resolved through ``identity.resolve_principal`` — the one entry point.
        None means "no credential store is configured": the CLI still has
        the local owner's filesystem authority (as every existing
        ``cli.py`` write does), but writes report that.
        """
        from .identity import NoPrincipalError, resolve_principal

        try:
            return resolve_principal(
                self.cli_token,
                self.identity_store,
                self.identity_mode,
                self.instance_token,
            )
        except NoPrincipalError:
            return None
        except Exception:
            return None

    @property
    def actor_id(self) -> str:
        return self.principal.id if self.principal is not None else "local-cli"

    def path(self, kind: str) -> Path:
        """The caller's own file for one state kind (decision #13)."""
        from .identity import principal_scoped_path

        return principal_scoped_path(
            self.data_dir, self.principal, kind, mode=self.identity_mode
        )

    # -- state --------------------------------------------------------
    @cached_property
    def world(self):
        wp = self.path("world")
        if self._world0 is not None and wp == self.data_dir / "world.json":
            return self._world0
        from .app import load_world

        return load_world(wp)

    @property
    def world_path(self) -> Path:
        return self.path("world")

    @cached_property
    def journal(self):
        from .journal import Journal

        jp = self.path("journal")
        legacy = getattr(self._journal0, "path", None)
        if self._journal0 is not None and legacy == jp:
            return self._journal0
        return Journal(jp)

    @cached_property
    def registry(self):
        """The registry built the way ``create_app`` builds it.

        ``cli.py``'s own build omits vault/journal/data_dir, which is the
        divergence ``docs/repo/WIRING-READINESS.md`` records for the CLI.
        This surface answers capability questions the way ``GET
        /api/status`` does.
        """
        from .app import build_registry
        from .providers.registry import Registry
        from .vault import Vault

        return build_registry(
            self.world,
            Registry(),
            self.config_dir,
            vault=Vault(self.data_dir / "vault.enc"),
            journal=self.journal,
            data_dir=self.data_dir,
        )

    @cached_property
    def scheduler(self):
        from .scheduler import Scheduler

        # notifier=None on purpose: firing and delivery belong to the
        # running backend's scheduler thread, not to a short-lived CLI.
        return Scheduler(self.path("reminders"), journal=self.journal, notifier=None)

    @cached_property
    def store(self):
        """The proposal store owning the caller's tree (decision #13).

        ``proposal_store_for`` returns the same instance-global store the
        API and the chat tool loop use when the path is the legacy one, so
        a proposal filed here is a proposal they can approve.
        """
        from .tool_registry import proposal_store_for

        return proposal_store_for(self.path("proposals"), journal=self.journal)

    # -- gates --------------------------------------------------------
    def person_gate(self, action: Action) -> Result | None:
        """Mirror ``api._require_person``: agents are refused, fail closed."""
        if not action.person_only:
            return None
        p = self.principal
        if p is not None and p.kind == "agent":
            return fail(
                "person_only",
                warnings=[
                    f"{action.command} is a person-only surface; an agent "
                    "principal is refused even with a valid token"
                ],
                data={"mutated": False, "principal": p.id, "kind": p.kind},
            )
        return None

    def step_up_gate(self, action: Action) -> Result | None:
        """The in-process analogue of ``require_step_up``.

        Same rules, same entry point: a person, re-presenting a credential that
        resolves to the same principal. No bare flags.
        """
        p = self.principal
        if p is not None and p.kind == "agent":
            return fail(
                "person_only",
                warnings=[
                    "step-up is person-only: an agent files proposals and a "
                    "person approves them"
                ],
                data={"mutated": False, "principal": p.id},
            )
        presented = os.environ.get(STEP_UP_ENV)
        if not presented:
            return fail(
                "needs_step_up",
                warnings=[
                    f"{action.command} mutates state: pass --approve AND "
                    f"export {STEP_UP_ENV}=<instance token> (the credential "
                    "is re-presented, never implied by a flag)"
                ],
                data={
                    "mutated": False,
                    "action": f"{action.noun} {action.verb}".strip(),
                    "route": action.route,
                    "gate": action.gate,
                },
            )
        if p is None and not self.instance_token:
            return fail(
                "not_configured",
                warnings=[
                    "no instance credential is configured, so a step-up "
                    "credential cannot be verified: run first-run setup or "
                    f"export {TOKEN_ENV}"
                ],
                data={"mutated": False},
            )
        from .identity import NoPrincipalError, resolve_principal

        try:
            elevated = resolve_principal(
                presented,
                self.identity_store,
                self.identity_mode,
                self.instance_token,
            )
        except NoPrincipalError:
            elevated = None
        except Exception:
            elevated = None
        if elevated is None:
            return fail(
                "denied",
                warnings=[
                    f"{STEP_UP_ENV} was rejected: it does not resolve to a "
                    "principal through identity resolution"
                ],
                data={"mutated": False},
            )
        if p is not None and elevated.id != p.id:
            return fail(
                "denied",
                warnings=[
                    f"{STEP_UP_ENV} resolves to a different principal "
                    f"({elevated.id}) than the caller ({p.id}); an elevation "
                    "is never issued across identities"
                ],
                data={"mutated": False},
            )
        return None

    # -- the uniform write path ---------------------------------------
    def write(
        self,
        action: Action,
        proposal_type: str,
        record: dict[str, Any],
        description: str,
    ) -> Result:
        """File, and act only on explicit approval + step-up credential.

        ``record`` is the human/agent-readable statement of what was
        asked; it is stored verbatim in the durable proposal so the
        review surface (and ``do proposals get``) shows exactly what will
        happen.
        """
        gate = self.person_gate(action)
        if gate is not None:
            return gate

        if not bool(getattr(self.args, "approve", False)):
            filed = self._file(action, proposal_type, record, description)
            if not filed.ok:
                return filed
            pid = (filed.data or {}).get("proposal_id")
            return ok(
                "proposed",
                changed=False,
                warnings=[
                    "nothing was mutated: the write is filed as a pending "
                    "proposal awaiting a person's approval"
                ],
                actions=[
                    f"review: personal-world {DISPATCH_GROUP} proposals get {pid} --json",
                    f"act:    {action.command} <same args> --approve  "
                    f"(requires {STEP_UP_ENV})",
                    f"or:     personal-world {DISPATCH_GROUP} proposals execute "
                    f"{pid} --approve",
                ],
                data={**(filed.data or {}), "mutated": False},
            )

        gate = self.step_up_gate(action)
        if gate is not None:
            return gate

        filed = self._file(action, proposal_type, record, description)
        if not filed.ok:
            return filed
        pid = (filed.data or {}).get("proposal_id")
        approved = self.store.approve(pid, self.actor_id, journal=self.journal)
        if not approved.ok:
            return approved
        return self.execute(pid)

    def direct_write(
        self,
        action: Action,
        description: str,
        act: Callable[[], Result],
        preview: dict[str, Any] | None = None,
    ) -> Result:
        """For the trust-boundary commands themselves (proposals
        approve/reject/execute): there is nothing to propose, so the
        default is an explicit dry-run and acting needs the same two keys.
        """
        gate = self.person_gate(action)
        if gate is not None:
            return gate
        if not bool(getattr(self.args, "approve", False)):
            return ok(
                "needs_approval",
                changed=False,
                warnings=[
                    "nothing was mutated: pass --approve AND export "
                    f"{STEP_UP_ENV}=<instance token> to perform this action"
                ],
                data={
                    "mutated": False,
                    "action": description,
                    "route": action.route,
                    "gate": action.gate,
                    **(preview or {}),
                },
            )
        gate = self.step_up_gate(action)
        if gate is not None:
            return gate
        return act()

    def _file(
        self,
        action: Action,
        proposal_type: str,
        record: dict[str, Any],
        description: str,
    ) -> Result:
        """Create the durable proposal (same store the API/chat use)."""
        payload = {
            "type": proposal_type,
            "origin": "cli",
            "cli_command": action.command,
            "requested_by": self.actor_id,
            # The manifest row this proposal corresponds to: the durable
            # record names the API action, so CLI and API cannot drift.
            "route": {
                "ids": list(action.ids),
                "gate": action.gate,
                "kind": action.kind,
            },
            "args": record,
        }
        res = self.store.propose(payload, self.journal, description)
        if not res.ok:
            return res
        data = dict(res.data or {})
        data["mutated"] = False
        data["description"] = description
        return ok(res.status, data=data)

    def execute(self, proposal_id: str) -> Result:
        """Execute an APPROVED proposal.

        Brain-proposed types go to ``ProposalStore.execute`` (the canonical
        executor). ``cli.*`` types go to this module's actor table, which
        calls the same service functions the API handlers call.
        """
        p = self.store.get(proposal_id)
        if p is None:
            return fail("not_found", warnings=[f"proposal '{proposal_id}' not found"])
        if p.get("status") != "approved":
            return fail(
                "invalid_state",
                warnings=[
                    f"proposal is {p.get('status')}, not approved. Only "
                    "proposals approved through the trusted owner path can "
                    "be executed."
                ],
            )
        ptype = p.get("type")
        if ptype in STORE_EXECUTABLE:
            r = self.store.execute(
                self.journal,
                self.world,
                proposal_id,
                self.scheduler,
                world_path=self.world_path,
            )
            return r.model_copy(update={"changed": bool(r.ok)})

        actor = CLI_ACTORS.get(ptype or "")
        if actor is None:
            return fail(
                "unsupported",
                warnings=[
                    f"no executor for proposal type '{ptype}'; nothing was "
                    "applied and the proposal stays approved"
                ],
                data={"proposal_id": proposal_id, "type": ptype, "mutated": False},
            )
        from .world import MutationDenied

        try:
            r = actor(self, p)
        except MutationDenied as exc:
            # A cemented policy refuses every non-user mutation path, the
            # CLI included. Refusal, not a crash — and nothing changed.
            r = fail("denied", warnings=[str(exc)])
        except Exception as exc:  # failure, never a fake success
            r = fail("unhealthy", warnings=[f"execute failed: {exc}"])
        self._mark(proposal_id, "executed" if r.ok else "failed", r)
        if r.ok:
            data = dict(r.data or {})
            data.setdefault("proposal_id", proposal_id)
            data.setdefault("type", ptype)
            data["mutated"] = True
            r = r.model_copy(update={"changed": True, "data": data})
        else:
            data = dict(r.data or {})
            data["mutated"] = False
            data.setdefault("proposal_id", proposal_id)
            r = r.model_copy(update={"data": data})
        return r

    def _mark(self, proposal_id: str, status: str, result: Result) -> None:
        """Record the terminal status through the store's own atomic write.

        ``ProposalStore`` has no public "mark executed" for a type it does
        not own, so the CLI actor path uses the store's persistence entry point
        directly (no logic duplicated: the actor did the work, the store
        keeps the audit). Extending ``ProposalStore.execute`` in
        ``tool_registry.py`` is the clean fix and belongs to that module's
        lane.
        """
        try:
            with self.store.lock:
                entry = self.store.proposals.get(proposal_id)
                if entry is None:
                    return
                entry["status"] = status
                entry["executed_via"] = "cli"
                entry["executed_at"] = time.time()
                if not result.ok:
                    entry["execution_warnings"] = list(result.warnings)
                self.store._persist_locked()
        except Exception:  # nosec B110  # see below: a persist failure must not change the answer
            # Persistence failure must never fake a successful execution:
            # the action already happened and its own result is returned.
            pass

    # -- http transport -----------------------------------------------
    @property
    def base_url(self) -> str:
        return (
            getattr(self.args, "base", None) or os.environ.get(BASE_ENV) or DEFAULT_BASE
        ).rstrip("/")

    @property
    def timeout(self) -> float:
        try:
            return float(getattr(self.args, "timeout", None) or DEFAULT_TIMEOUT)
        except (TypeError, ValueError):
            return DEFAULT_TIMEOUT

    def http(self, method: str, path: str, data: Any = None) -> Result:
        """One authenticated call to the local backend, envelope in/out."""
        url = self.base_url + path
        headers = {
            "Accept": "application/json",
            "User-Agent": "personal-world-cli-dispatch",
        }
        token = self.cli_token
        if token:
            headers["Authorization"] = f"Bearer {token}"
        session = os.environ.get(SESSION_ENV)
        if session:
            # An explicit session id, only when the operator supplies it:
            # a browser session credential is never picked out of
            # sessions.json implicitly.
            headers["Cookie"] = f"pw_session={session}"
        body: bytes | None = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        # Deliberately NOT sending X-PW-StepUp: that header is delegated
        # proxy trust, and this CLI has no proxy to delegate from.
        request = urllib.request.Request(
            url, data=body, method=method.upper(), headers=headers
        )
        where = {"method": method.upper(), "path": path, "base": self.base_url}
        try:
            with http_urlopen(request, timeout=self.timeout) as resp:
                code = int(getattr(resp, "status", 200) or 200)
                raw = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            code = exc.code
            try:
                raw = exc.read().decode("utf-8", "replace")
            except Exception:
                raw = ""
        except urllib.error.URLError as exc:
            return fail(
                "unavailable",
                warnings=[
                    f"cannot reach the backend at {self.base_url}: {exc.reason}",
                    "start it (uvicorn personal_world.api:app --port 8000) or "
                    f"point {BASE_ENV} at the right instance",
                ],
                data={**where, "mutated": False},
            )
        except (TimeoutError, OSError) as exc:
            return fail(
                "unavailable",
                warnings=[
                    f"call to {self.base_url}{path} failed: {type(exc).__name__}: {exc}"
                ],
                data={**where, "mutated": False},
            )
        return _result_from_http(code, raw, where)

    # -- write-side warnings ------------------------------------------
    @staticmethod
    def multi_writer_warning(filename: str) -> str:
        return (
            f"{filename} was written in-process; a backend that is already "
            f"running keeps its own copy of {filename} in memory and can "
            "overwrite this change (documented multi-writer gap). Restart "
            "the backend, or file the same change through "
            "`personal-world api`."
        )


def _result_from_http(code: int, raw: str, where: dict[str, Any]) -> Result:
    """Map one HTTP response onto the envelope,."""
    body: Any
    try:
        body = json.loads(raw) if raw.strip() else None
    except ValueError:
        body = raw[:4000] if raw else None

    if 200 <= code < 300:
        if isinstance(body, dict) and "ok" in body:
            # The API speaks this envelope already: pass it through
            # verbatim so a bot sees exactly what a browser sees.
            return Result(
                ok=bool(body.get("ok")),
                status=str(body.get("status") or "healthy"),
                changed=bool(body.get("changed", False)),
                warnings=[str(w) for w in (body.get("warnings") or [])],
                actions=[str(a) for a in (body.get("actions") or [])],
                data=body.get("data"),
            )
        return ok("healthy", data={"http_status": code, "body": body})

    status_by_code = {
        400: "invalid_args",
        401: "unauthenticated",
        403: "denied",
        404: "not_found",
        405: "invalid_args",
        409: "invalid_state",
        422: "invalid_args",
        503: "not_configured",
    }
    status = status_by_code.get(code, "unhealthy")
    warnings: list[str] = []
    data: dict[str, Any] = {"http_status": code, "mutated": False, **where}
    if isinstance(body, dict):
        if isinstance(body.get("status"), str):
            status = body["status"]
        detail = body.get("detail")
        if detail is not None:
            warnings.append(
                detail if isinstance(detail, str) else json.dumps(detail)[:1000]
            )
        data["body"] = body
    elif body is not None:
        data["body"] = body
        warnings.append(str(body)[:1000])
    if not warnings:
        warnings.append(f"HTTP {code} from {where['method']} {where['path']}")
    return fail(status, warnings=warnings, data=data)


def _slug(text: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return out[:48] or "item"


# ── Read wrappers ────────────────────────────────────────────────────


def _world_status(ctx: Ctx) -> Result:
    """Mirrors GET /api/status exactly: summary + capability statuses + actors."""
    registry = ctx.registry
    summary = ctx.world.summary()
    summary["capabilities"] = registry.status_map()
    summary["actors"] = [a.model_dump(mode="json") for a in registry.actors()]
    return ok("healthy", data=summary)


def _world_actors(ctx: Ctx) -> Result:
    return ok(
        "healthy", data=[a.model_dump(mode="json") for a in ctx.registry.actors()]
    )


def _capabilities_list(ctx: Ctx) -> Result:
    """Mirrors the ``data`` half of GET /api/manifest."""
    return ok("healthy", data=ctx.registry.manifest())


def _capabilities_health(ctx: Ctx) -> Result:
    """Mirrors the ``data.capabilities`` half of GET /api/status."""
    from .status import worst

    status_map = ctx.registry.status_map()
    statuses = [str(v.get("status")) for v in status_map.values()]
    counts: dict[str, int] = {}
    for s in statuses:
        counts[s] = counts.get(s, 0) + 1
    warnings = [
        f"{cap}: {v.get('status')}"
        + (f" — {v['warnings'][0]}" if v.get("warnings") else "")
        for cap, v in sorted(status_map.items())
        if not v.get("ok")
    ]
    overall = worst(statuses) if statuses else "healthy"
    data = {"capabilities": status_map, "counts": counts, "worst": overall}
    if bool(getattr(ctx.args, "strict", False)):
        # --strict turns this into a monitoring check: the envelope's own
        # ok/status become the verdict instead of mirroring the API.
        healthy = all(v.get("ok") for v in status_map.values())
        return (ok if healthy else fail)(overall, warnings=warnings, data=data)
    # Default mirrors GET /api/status: ok=True, per-capability truth in data.
    return ok(
        "healthy",
        warnings=warnings,
        data=data,
        actions=[
            f"{len(status_map)} capabilities: "
            + ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        ],
    )


def _journal_list(ctx: Ctx) -> Result:
    """Mirrors GET /api/journal: the calm view, each chain's current version."""
    events = ctx.journal.current_events(int(getattr(ctx.args, "n", 20) or 20))
    return ok("healthy", data=[e.model_dump(mode="json") for e in events])


def _journal_history(ctx: Ctx) -> Result:
    ts = str(getattr(ctx.args, "ts", "") or "").strip()
    if not ts:
        return fail("invalid_args", warnings=["--ts is required"])
    entry = ctx.journal.by_ts(ts)
    if entry is None:
        # Same status the API returns for a missing entry.
        return fail("not_configured", warnings=[f"no journal entry found at {ts}"])
    chain = ctx.journal.history_of(entry)
    return ok("healthy", data={"entries": [e.model_dump(mode="json") for e in chain]})


def _journal_audit(ctx: Ctx) -> Result:
    from .journal import AuditRenderer

    return ok("healthy", data={"text": AuditRenderer().render(ctx.journal)})


def _reminders_list(ctx: Ctx) -> Result:
    reminders = ctx.scheduler.list_reminders()
    return ok("healthy", data=[r.model_dump(mode="json") for r in reminders])


def _proposals_list(ctx: Ctx) -> Result:
    status = getattr(ctx.args, "status", None)
    return ok("healthy", data=ctx.store.list(status))


def _proposals_get(ctx: Ctx) -> Result:
    pid = str(getattr(ctx.args, "proposal_id", "") or "")
    p = ctx.store.get(pid)
    if p is None:
        return fail("not_found", warnings=[f"proposal '{pid}' not found"])
    return ok("healthy", data=p)


def _prefs_get(ctx: Ctx) -> Result:
    from . import prefs

    return ok("healthy", data=prefs.get_prefs(ctx.world))


def _prefs_schema(ctx: Ctx) -> Result:
    """Mirrors GET /api/prefs/schema: the writable vocabulary.

    Rendered by ``prefs.spec_schema`` — the same function the API uses, so
    the two surfaces cannot drift (``companion_id`` in particular is a row
    with no closed list: the vocabulary is the person's own crew).
    """
    from . import prefs

    return ok(
        "healthy",
        data={
            key: prefs.spec_schema(spec) for key, spec in prefs.PREFS.items()
        },
    )


def _projects_status(ctx: Ctx) -> Result:
    """Mirrors GET /api/projects/status (the agent-sync estate sensor)."""
    from .providers.agent_sync import AgentSyncProjectSensor

    return AgentSyncProjectSensor().observe_projects()


def _search_paths(ctx: Ctx) -> list[str]:
    from .source_control import configured_search_paths

    return configured_search_paths(ctx.config_dir)


def _projects_repos(ctx: Ctx) -> Result:
    from .source_control import status_all

    paths = _search_paths(ctx)
    if not paths:
        return fail(
            "not_configured",
            warnings=["no source_control search paths configured"],
        )
    return ok("healthy", data={"repositories": status_all(paths)})


def _projects_history(ctx: Ctx) -> Result:
    from .source_control import discover_repositories, repository_history

    paths = _search_paths(ctx)
    if not paths:
        return fail(
            "not_configured",
            warnings=["no source_control search paths configured"],
        )
    repos = [e for e in discover_repositories(paths) if e["is_repository"]]
    if not repos:
        return fail(
            "not_configured",
            warnings=["no git repositories found in configured search paths"],
        )
    limit = int(getattr(ctx.args, "limit", 20) or 20)
    wanted = str(getattr(ctx.args, "repo", "") or "").strip()
    if wanted:
        repos = [r for r in repos if r["name"] == wanted]
        if not repos:
            return fail(
                "not_found",
                warnings=[
                    f"repository '{wanted}' not found in configured search paths"
                ],
            )
    if len(repos) == 1:
        return ok(
            "healthy",
            data={
                "repo": repos[0]["name"],
                "commits": repository_history(repos[0]["path"], limit),
            },
        )
    return ok(
        "healthy",
        data={
            "history": {r["name"]: repository_history(r["path"], limit) for r in repos}
        },
    )


def _templates_list(ctx: Ctx) -> Result:
    from .template_registry import TemplateRegistry

    registry = TemplateRegistry(ctx.config_dir, ctx.data_dir)
    if bool(getattr(ctx.args, "public", False)):
        # Mirrors GET /api/templates (currently uncurated in api_manifest):
        # id/surface/role/description only, no template bodies.
        return ok("healthy", data={"templates": registry.list_public()})
    return ok("healthy", data={"templates": registry.list_templates()})


def _auth_status(ctx: Ctx) -> Result:
    """Credential + principal + step-up readiness. Never prints a secret."""
    from .identity import dev_bypass_enabled

    p = ctx.principal
    presented = os.environ.get(STEP_UP_ENV)
    step_up_ok = False
    reason = "no step-up credential presented"
    if presented:
        from .identity import NoPrincipalError, resolve_principal

        try:
            elevated = resolve_principal(
                presented,
                ctx.identity_store,
                ctx.identity_mode,
                ctx.instance_token,
            )
            step_up_ok = p is None or elevated.id == p.id
            reason = (
                "credential resolves to the calling principal"
                if step_up_ok
                else f"credential resolves to {elevated.id}, not the caller"
            )
        except NoPrincipalError:
            reason = "credential does not resolve to a principal"
        except Exception as exc:
            reason = f"credential could not be verified ({type(exc).__name__})"
    elif not ctx.instance_token:
        reason = "no instance credential is configured"
    return ok(
        "healthy",
        data={
            "identity_mode": ctx.identity_mode,
            "credential": {
                "configured": ctx.instance_token is not None,
                "source": ctx.instance_token_source,
            },
            "principal": (
                {
                    "id": p.id,
                    "kind": p.kind,
                    "display_name": p.display_name,
                    "scopes": list(p.scopes),
                    "source": p.source,
                }
                if p is not None
                else None
            ),
            "step_up": {
                "env": STEP_UP_ENV,
                "credential_present": bool(presented),
                "authorized": step_up_ok,
                "reason": reason,
            },
            "dev_bypass": dev_bypass_enabled(),
            "data_dir": str(ctx.data_dir),
            "config_dir": str(ctx.config_dir),
            "backend_base": ctx.base_url,
        },
        actions=[f"writes need: --approve AND {STEP_UP_ENV}=<instance token>"],
    )


def _auth_session(ctx: Ctx) -> Result:
    """The browser-session store, without ever printing a session id.

    Read-only on purpose: ``SessionStore.get()`` touches and rewrites the
    file, so this walks the loaded records instead.
    """
    from .auth import SessionStore

    store = SessionStore(ctx.data_dir)
    now = time.time()
    rows = []
    for session in list(getattr(store, "_sessions", {}).values()):
        rows.append(
            {
                "principal_id": session.principal_id,
                "auth_method": session.auth_method,
                "created_at": session.created_at,
                "last_active": session.last_active,
                "age_seconds": max(0, int(now - session.last_active)),
                "valid": session.is_valid(),
                "has_step_up": session.has_step_up(session.principal_id),
            }
        )
    rows.sort(key=lambda r: r["created_at"])
    return ok(
        "healthy",
        data={
            "count": len(rows),
            "sessions": rows,
            "session_ids_exposed": False,
            "note": "session ids are credentials and are never printed",
        },
    )


def _oidc_status(ctx: Ctx) -> Result:
    """The same four-state report GET /api/auth/oidc/status gives."""
    from .oidc import OIDCService

    report = OIDCService(ctx.config_dir).status()
    return Result(
        ok=bool(report.get("ok")),
        status=str(report.get("status") or "unhealthy"),
        warnings=[str(w) for w in (report.get("warnings") or [])],
        data=report.get("data"),
    )


def _chat_send(ctx: Ctx) -> Result:
    """HTTP transport: chat's composition lives only in api.py."""
    message = str(getattr(ctx.args, "message", "") or "").strip()
    if not message:
        return fail("invalid_args", warnings=["--message is required"])
    payload: dict[str, Any] = {"message": message, "history": []}
    surface = getattr(ctx.args, "surface", None)
    if surface:
        payload["context"] = {"route": f"/{str(surface).lstrip('/')}"}
    return ctx.http("POST", "/api/chat", payload)


# ── Write actors (cli.* proposal types) ──────────────────────────────
#
# Each actor calls the SAME canonical service function the matching API
# handler calls. Nothing here re-implements domain logic; these are the
# act step of propose → approve → act for the types ProposalStore does
# not own (see STORE_EXECUTABLE).


def _act_journal_write(ctx: Ctx, p: dict[str, Any]) -> Result:
    from .model import JournalKind

    text = str((p.get("args") or {}).get("text") or "")
    ctx.journal.record(kind=JournalKind.OBSERVATION, summary=text, source="cli")
    return ok("healthy", data={"written": len(text), "source": "cli"})


def _act_journal_supersede(ctx: Ctx, p: dict[str, Any]) -> Result:
    """Append-only correction, with the API's idempotent-retry semantics."""
    args = p.get("args") or {}
    ts = str(args.get("supersedes") or "")
    corrected = str(args.get("text") or "")
    reason = args.get("reason") or None
    old = ctx.journal.by_ts(ts)
    if old is None:
        return fail("not_found", warnings=[f"no journal entry found at {ts}"])
    for later in ctx.journal.events():
        if later.supersedes == old.ts:
            if later.summary == corrected:
                return ok(
                    "healthy",
                    data={
                        "current": later.model_dump(mode="json"),
                        "superseded": old.model_dump(mode="json"),
                        "already_applied": True,
                    },
                )
            return fail(
                "invalid_state",
                warnings=[
                    f"entry at {ts} was already superseded by a different "
                    "correction — correct the current entry instead"
                ],
            )
    try:
        # proposed_by is free text in journal.supersede; the API coerces
        # unknown values to "the Journal screen", which would be a false claim
        # here. The audit line's trailing "approved by the owner via the
        # Journal screen" is journal.py's own template wording.
        current, audit = ctx.journal.supersede(
            ts, corrected, reason, proposed_by="the Personal World CLI"
        )
    except (KeyError, ValueError) as exc:
        return fail("unavailable", warnings=[str(exc)])
    return ok(
        "healthy",
        data={
            "current": current.model_dump(mode="json"),
            "superseded": old.model_dump(mode="json"),
            "audit": audit.model_dump(mode="json"),
            "already_applied": False,
        },
    )


def _act_prefs_set(ctx: Ctx, p: dict[str, Any]) -> Result:
    from . import prefs
    from .app import save_world

    args = p.get("args") or {}
    key = str(args.get("key") or "")
    raw = args.get("value")
    try:
        data = prefs.set_prefs(ctx.world, {key: prefs.coerce_value(key, raw)})
    except prefs.PrefsValueError as exc:
        return fail("rejected", warnings=[str(exc)])
    save_world(ctx.world, ctx.world_path)
    return ok(
        "updated",
        warnings=[Ctx.multi_writer_warning("world.json")],
        data={"key": key, "prefs": data, "persisted": "world.json"},
    )


def _act_world_write(ctx: Ctx, p: dict[str, Any]) -> Result:
    """intent / fact / policy — the same writes POST /api/world/* make."""
    from .app import save_world
    from .model import Fact, Intent, Policy, PolicyEffect, Provenance

    args = p.get("args") or {}
    kind = str(args.get("kind") or "")
    key = str(args.get("key") or "")
    provenance = Provenance(source="cli")
    try:
        if kind == "intent":
            ctx.world.set_intent(
                Intent(key=key, value=args.get("value"), provenance=provenance)
            )
        elif kind == "fact":
            ctx.world.record_fact(
                Fact(key=key, value=args.get("value"), provenance=provenance)
            )
        elif kind == "policy":
            ctx.world.set_policy(
                Policy(
                    key=key,
                    effect=PolicyEffect(str(args.get("effect") or "allow")),
                    provenance=provenance,
                )
            )
        else:
            return fail("unsupported", warnings=[f"unknown world write '{kind}'"])
    except ValueError as exc:
        return fail("rejected", warnings=[str(exc)])
    save_world(ctx.world, ctx.world_path)
    return ok(
        "updated",
        warnings=[Ctx.multi_writer_warning("world.json")],
        data={"kind": kind, "key": key, "persisted": "world.json"},
    )


def _act_reminder_add(ctx: Ctx, p: dict[str, Any]) -> Result:
    from .scheduler import Reminder

    args = p.get("args") or {}
    reminder = Reminder(
        id=str(args.get("id") or f"cli-{int(time.time())}"),
        text=str(args.get("text") or ""),
        cron_hour=args.get("cron_hour"),
        cron_minute=args.get("cron_minute"),
        cron_day=args.get("cron_day"),
    )
    r = ctx.scheduler.add(reminder)
    if not r.ok:
        return r
    return ok(
        "healthy",
        warnings=[Ctx.multi_writer_warning("reminders.json")],
        data={"id": reminder.id, "text": reminder.text, "persisted": "reminders.json"},
    )


def _act_source_refresh(ctx: Ctx, p: dict[str, Any]) -> Result:
    """The act step of the Projects propose → approve → act workflow."""
    from .model import JournalKind
    from .source_control import discover_repositories, repository_status

    repo = str((p.get("args") or {}).get("repo") or "")
    paths = _search_paths(ctx)
    if not paths:
        return fail(
            "not_configured",
            warnings=["no source_control search paths configured"],
        )
    matches = [
        e
        for e in discover_repositories(paths)
        if e["is_repository"] and e["name"] == repo
    ]
    if not matches:
        ctx.journal.record(
            JournalKind.FAILURE,
            f"proposed repository status refresh rejected: repository "
            f"'{repo}' not found in configured search paths",
            source="cli",
        )
        return fail(
            "not_configured",
            warnings=[f"repository '{repo}' not found in configured search paths"],
        )
    status = repository_status(matches[0]["path"])
    if status.get("error"):
        ctx.journal.record(
            JournalKind.FAILURE,
            f"repository status refresh ran for '{repo}' but git reported: "
            f"{status['error']}",
            source="cli",
        )
        return fail("unavailable", warnings=[str(status["error"])])
    bits = [
        f"branch {status.get('branch') or 'unknown'}",
        "uncommitted changes" if status.get("dirty") else "clean",
    ]
    if status.get("ahead") or status.get("behind"):
        bits.append(
            f"{status.get('ahead') or 0} ahead / {status.get('behind') or 0} behind"
        )
    ctx.journal.record(
        JournalKind.PROVIDER_ACTION,
        f"approved action: repository status refresh for '{repo}' (proposed "
        f"by the CLI, approved explicitly, executed by the native git "
        f"baseline) — {', '.join(bits)}",
        source="cli",
    )
    return ok("healthy", data={"repo": repo, "status": status})


#: proposal type → act step. Keys are this module's own vocabulary; the
#: store's own types stay with ``ProposalStore.execute``.
CLI_ACTORS: dict[str, Callable[[Ctx, dict[str, Any]], Result]] = {
    "cli.journal_write": _act_journal_write,
    "cli.journal_supersede": _act_journal_supersede,
    "cli.prefs_set": _act_prefs_set,
    "cli.world_write": _act_world_write,
    "cli.reminder_add": _act_reminder_add,
    "cli.source_refresh": _act_source_refresh,
}


# ── Write wrappers (each is 1-5 lines: validate, then ctx.write) ─────


def _journal_write(ctx: Ctx) -> Result:
    text = str(getattr(ctx.args, "text", "") or "").strip()
    if not text or len(text) > 2000:
        return fail("invalid_args", warnings=["--text must be 1-2000 chars"])
    return ctx.write(
        _ACTION_BY_KEY["journal write"],
        "cli.journal_write",
        {"text": text},
        f"Write journal entry: {text[:100]}",
    )


def _journal_supersede(ctx: Ctx) -> Result:
    ts = str(getattr(ctx.args, "ts", "") or "").strip()
    text = str(getattr(ctx.args, "text", "") or "").strip()
    reason = str(getattr(ctx.args, "reason", "") or "").strip()
    if not ts or not text:
        return fail("invalid_args", warnings=["--ts and --text are required"])
    if len(text) > 2000:
        return fail("invalid_args", warnings=["--text must be 1-2000 chars"])
    return ctx.write(
        _ACTION_BY_KEY["journal supersede"],
        "cli.journal_supersede",
        {"supersedes": ts, "text": text, "reason": reason or None},
        f"Correct journal entry {ts}: {text[:80]}",
    )


def _reminders_add(ctx: Ctx) -> Result:
    text = str(getattr(ctx.args, "text", "") or "").strip()
    if not text:
        return fail("invalid_args", warnings=["--text is required"])
    rid = str(getattr(ctx.args, "id", "") or "").strip() or f"cli-{int(time.time())}"
    day = getattr(ctx.args, "day", None)
    if day and str(day).lower() not in (
        "mon",
        "tue",
        "wed",
        "thu",
        "fri",
        "sat",
        "sun",
    ):
        return fail(
            "invalid_args",
            warnings=["--day must be one of mon tue wed thu fri sat sun"],
        )
    record = {
        "id": rid,
        "text": text,
        "cron_hour": getattr(ctx.args, "hour", None),
        "cron_minute": getattr(ctx.args, "minute", None),
        "cron_day": str(day).lower() if day else None,
    }
    return ctx.write(
        _ACTION_BY_KEY["reminders add"],
        "cli.reminder_add",
        record,
        f"Add reminder '{text[:80]}'",
    )


def _prefs_set(ctx: Ctx) -> Result:
    from . import prefs

    key = str(getattr(ctx.args, "key", "") or "")
    raw = getattr(ctx.args, "value", None)
    if not key or raw is None:
        return fail("invalid_args", warnings=["KEY and VALUE are required"])
    # Validate at FILE time against the same specs the API validates with,
    # so a bad value is a usage error (exit 2) rather than a proposal that
    # can only fail later. Read-only: the world is not touched here.
    spec = prefs.PREFS.get(key)
    if spec is None:
        return fail(
            "invalid_args",
            warnings=[
                f"unknown preference {key!r} (see `personal-world "
                f"{DISPATCH_GROUP} prefs schema`)"
            ],
        )
    try:
        spec.validate(prefs.coerce_value(key, raw))
    except prefs.PrefsValueError as exc:
        return fail("invalid_args", warnings=[str(exc)])
    return ctx.write(
        _ACTION_BY_KEY["prefs set"],
        "cli.prefs_set",
        {"key": key, "value": raw},
        f"Set preference {key}={raw}",
    )


def _world_write(ctx: Ctx, kind: str) -> Result:
    key = str(getattr(ctx.args, "key", "") or "").strip()
    if not key:
        return fail("invalid_args", warnings=["--key is required"])
    record: dict[str, Any] = {"kind": kind, "key": key}
    if kind == "policy":
        effect = str(getattr(ctx.args, "effect", "") or "").strip().lower()
        if effect not in ("allow", "deny"):
            return fail("invalid_args", warnings=["--effect must be 'allow' or 'deny'"])
        record["effect"] = effect
        description = f"Set policy '{key}' = {effect}"
    else:
        record["value"] = getattr(ctx.args, "value", None)
        description = f"Set {kind} '{key}'"
    action = _ACTION_BY_KEY[f"world {kind}"]
    return ctx.write(action, "cli.world_write", record, description)


def _world_intent(ctx: Ctx) -> Result:
    return _world_write(ctx, "intent")


def _world_fact(ctx: Ctx) -> Result:
    return _world_write(ctx, "fact")


def _world_policy(ctx: Ctx) -> Result:
    return _world_write(ctx, "policy")


def _projects_propose_refresh(ctx: Ctx) -> Result:
    repo = str(getattr(ctx.args, "repo", "") or "").strip()
    if not repo:
        return fail("invalid_args", warnings=["--repo is required"])
    return ctx.write(
        _ACTION_BY_KEY["projects propose-refresh"],
        "cli.source_refresh",
        {"repo": repo},
        f"Refresh repository status for '{repo}'",
    )


def _proposals_decide(ctx: Ctx, decision: str) -> Result:
    pid = str(getattr(ctx.args, "proposal_id", "") or "")
    if not pid:
        return fail("invalid_args", warnings=["PROPOSAL_ID is required"])
    action = _ACTION_BY_KEY[f"proposals {decision}"]
    existing = ctx.store.get(pid)
    if existing is None:
        return fail("not_found", warnings=[f"proposal '{pid}' not found"])

    def act() -> Result:
        r = getattr(ctx.store, decision)(pid, ctx.actor_id, journal=ctx.journal)
        if r.ok:
            data = dict(r.data or {})
            data["mutated"] = True
            r = r.model_copy(update={"changed": True, "data": data})
        return r

    return ctx.direct_write(
        action,
        f"{decision} proposal {pid}",
        act,
        preview={"proposal_id": pid, "proposal": existing},
    )


def _proposals_approve(ctx: Ctx) -> Result:
    return _proposals_decide(ctx, "approve")


def _proposals_reject(ctx: Ctx) -> Result:
    return _proposals_decide(ctx, "reject")


def _proposals_execute(ctx: Ctx) -> Result:
    pid = str(getattr(ctx.args, "proposal_id", "") or "")
    if not pid:
        return fail("invalid_args", warnings=["PROPOSAL_ID is required"])
    action = _ACTION_BY_KEY["proposals execute"]
    existing = ctx.store.get(pid)
    if existing is None:
        return fail("not_found", warnings=[f"proposal '{pid}' not found"])

    def act() -> Result:
        return ctx.execute(pid)

    return ctx.direct_write(
        action,
        f"execute approved proposal {pid}",
        act,
        preview={
            "proposal_id": pid,
            "proposal": existing,
            "executor": (
                "ProposalStore.execute"
                if existing.get("type") in STORE_EXECUTABLE
                else "cli actor"
            ),
        },
    )


# ── The wrapper table ────────────────────────────────────────────────

APPROVE_HELP = (
    "act now instead of only filing: files the proposal, approves it as "
    "you, then executes it. ALSO requires the step-up credential in "
    "$PW_STEP_UP_TOKEN (a flag alone never mutates anything)."
)

ACTIONS: tuple[Action, ...] = (
    # -- world --------------------------------------------------------
    Action(
        noun="world",
        verb="status",
        ids=("API-003",),
        help="world summary + capability statuses + actors (read-only)",
        run=_world_status,
    ),
    Action(
        noun="world",
        verb="actors",
        ids=("API-014",),
        help="staff-directory view of every registered provider (read-only)",
        run=_world_actors,
    ),
    Action(
        noun="world",
        verb="intent",
        ids=("API-075",),
        help="file an intent write (propose by default)",
        run=_world_intent,
        args=(
            A("--key", required=True, help="intent key"),
            A("--value", help="intent value"),
        ),
    ),
    Action(
        noun="world",
        verb="fact",
        ids=("API-076-fact",),
        help="file a fact write (propose by default)",
        run=_world_fact,
        args=(
            A("--key", required=True, help="fact key"),
            A("--value", help="observed value"),
        ),
    ),
    Action(
        noun="world",
        verb="policy",
        ids=("API-076-policy",),
        help="file a policy write (propose by default; cemented policies still refuse)",
        run=_world_policy,
        args=(
            A("--key", required=True, help="policy key"),
            A("--effect", required=True, help="allow | deny"),
        ),
    ),
    # -- journal ------------------------------------------------------
    Action(
        noun="journal",
        verb="list",
        ids=("API-005",),
        person_only=True,
        help="current version of each journal chain (read-only)",
        run=_journal_list,
        args=(A("-n", type=int, default=20, help="how many entries (default 20)"),),
    ),
    Action(
        noun="journal",
        verb="history",
        ids=("API-008",),
        person_only=True,
        help="full correction chain for one entry, oldest first (read-only)",
        run=_journal_history,
        args=(A("--ts", required=True, help="entry timestamp"),),
    ),
    Action(
        noun="journal",
        verb="audit",
        ids=("API-009",),
        person_only=True,
        help="audit-log rendering of the journal (read-only)",
        run=_journal_audit,
    ),
    Action(
        noun="journal",
        verb="write",
        ids=("API-006",),
        person_only=True,
        help="file a journal note (propose by default; nothing is written without --approve)",
        run=_journal_write,
        args=(A("--text", required=True, help="1-2000 chars"),),
    ),
    Action(
        noun="journal",
        verb="supersede",
        ids=("API-007",),
        person_only=True,
        help="file an append-only correction (propose by default)",
        run=_journal_supersede,
        args=(
            A("--ts", required=True, help="timestamp of the entry to correct"),
            A("--text", required=True, help="the corrected text (1-2000 chars)"),
            A("--reason", help="why the correction is needed"),
        ),
    ),
    # -- reminders ----------------------------------------------------
    Action(
        noun="reminders",
        verb="list",
        ids=("API-067-get",),
        help="list reminders (read-only)",
        run=_reminders_list,
    ),
    Action(
        noun="reminders",
        verb="add",
        ids=("API-067-add",),
        help="file a reminder (propose by default)",
        run=_reminders_add,
        args=(
            A("--text", required=True, help="reminder text"),
            A("--id", help="reminder id (default cli-<epoch>)"),
            A("--hour", type=int, help="fire at this hour (0-23)"),
            A("--minute", type=int, help="fire at this minute (0-59)"),
            A("--day", help="mon|tue|wed|thu|fri|sat|sun (default every day)"),
        ),
    ),
    # -- proposals ----------------------------------------------------
    Action(
        noun="proposals",
        verb="list",
        ids=("PROP-list",),
        help="list proposals, newest last (read-only)",
        run=_proposals_list,
        args=(A("--status", help="filter: pending|approved|rejected|executed|failed"),),
    ),
    Action(
        noun="proposals",
        verb="get",
        ids=("PROP-get",),
        help="one proposal in full (read-only)",
        run=_proposals_get,
        args=(A("proposal_id", help="proposal id"),),
    ),
    Action(
        noun="proposals",
        verb="approve",
        ids=("PROP-approve",),
        direct=True,
        help="owner approval of a pending proposal (dry-run without --approve)",
        run=_proposals_approve,
        args=(A("proposal_id", help="proposal id"),),
        note="This IS the human trust boundary: the default is a dry-run "
        "showing exactly what will be approved.",
    ),
    Action(
        noun="proposals",
        verb="reject",
        ids=("PROP-reject",),
        direct=True,
        help="reject a pending proposal (dry-run without --approve)",
        run=_proposals_reject,
        args=(A("proposal_id", help="proposal id"),),
    ),
    Action(
        noun="proposals",
        verb="execute",
        ids=("PROP-execute",),
        direct=True,
        help="execute an APPROVED proposal (dry-run without --approve)",
        run=_proposals_execute,
        args=(A("proposal_id", help="proposal id"),),
        note="Refuses anything not already approved; approval evidence is "
        "server-held and cannot be forged by a caller.",
    ),
    # -- prefs --------------------------------------------------------
    Action(
        noun="prefs",
        verb="get",
        ids=("API-030-get",),
        person_only=True,
        help="effective presentation preferences (read-only)",
        run=_prefs_get,
    ),
    Action(
        noun="prefs",
        verb="schema",
        ids=("API-031",),
        help="the writable preference vocabulary and floors (read-only)",
        run=_prefs_schema,
    ),
    Action(
        noun="prefs",
        verb="set",
        ids=("API-030-put",),
        person_only=True,
        help="file a preference change (propose by default; minimum accessibility settings enforced)",
        run=_prefs_set,
        args=(
            A("key", help="preference key (see `do prefs schema`)"),
            A("value", help="new value"),
        ),
    ),
    # -- projects -----------------------------------------------------
    Action(
        noun="projects",
        verb="status",
        ids=("API-079",),
        help="project-estate status from the agent-sync sensor (read-only)",
        run=_projects_status,
        note="Honest 'unavailable' when the optional agent-sync binary is "
        "absent — the product stays useful without it.",
    ),
    Action(
        noun="projects",
        verb="repos",
        ids=("API-033",),
        help="native git status for every configured repository (read-only)",
        run=_projects_repos,
    ),
    Action(
        noun="projects",
        verb="history",
        ids=("API-034",),
        help="native git commit history, newest first (read-only)",
        run=_projects_history,
        args=(
            A("--repo", help="one repository name (default: all)"),
            A("--limit", type=int, default=20, help="commits per repo (default 20)"),
        ),
    ),
    Action(
        noun="projects",
        verb="propose-refresh",
        ids=("API-035",),
        help="file an approved repository status refresh (propose by default)",
        run=_projects_propose_refresh,
        args=(A("--repo", required=True, help="repository name"),),
    ),
    # -- capabilities -------------------------------------------------
    Action(
        noun="capabilities",
        verb="list",
        ids=("API-015",),
        help="capability/provider manifest — what exists, what is active (read-only)",
        run=_capabilities_list,
    ),
    Action(
        noun="capabilities",
        verb="health",
        ids=("API-003",),
        help="per-capability health, the same map GET /api/status returns",
        run=_capabilities_health,
        args=(
            A(
                "--strict",
                action="store_true",
                help="make the envelope's ok/status the verdict (for monitoring)",
            ),
        ),
        note="Bound to API-003 because GET /api/status is where "
        "`data.capabilities` lives.",
    ),
    # -- chat ---------------------------------------------------------
    Action(
        noun="chat",
        verb="send",
        ids=("API-010",),
        # API-010 is kind=write in the manifest, so this wrapper inherits
        # that — but a chat is a model invocation, not a world mutation, so
        # it files no proposal of its own. Any write the model wants goes
        # into the same durable proposal store, reviewed the same way.
        mutates=False,
        transport="http",
        help="send a message to the companion (needs a running backend)",
        run=_chat_send,
        args=(
            A("--message", required=True, help="the message"),
            A("--surface", help="UI route context, e.g. lab or journal"),
            A(
                "--base",
                help=f"backend base URL (default ${BASE_ENV} or {DEFAULT_BASE})",
            ),
            A("--timeout", type=float, help="seconds (default 30)"),
        ),
        note="HTTP transport by design: chat's composition (context, "
        "templates, tool loop, transcript) lives only in api.py, and "
        "duplicating it here is the divergence decision #19 forbids. "
        "The route is kind=write because it can journal a "
        "recommendation and create proposals of its own — it does not "
        "mutate world state, so it needs no proposal of its own.",
    ),
    # -- templates ----------------------------------------------------
    Action(
        noun="templates",
        verb="list",
        ids=("API-077-templates",),
        help="brain templates on disk (read-only)",
        run=_templates_list,
        args=(
            A(
                "--public",
                action="store_true",
                help="id/surface/role/description only, no template bodies",
            ),
        ),
    ),
    # -- auth ---------------------------------------------------------
    Action(
        noun="auth",
        verb="status",
        ids=("AUTH-009-session",),
        help="credential, principal and step-up readiness (never prints a secret)",
        run=_auth_status,
        args=(
            A(
                "--base",
                help=f"backend base URL (default ${BASE_ENV} or {DEFAULT_BASE})",
            ),
        ),
    ),
    Action(
        noun="auth",
        verb="session",
        ids=("AUTH-009-session",),
        help="browser-session store summary; session ids are never printed",
        run=_auth_session,
    ),
    Action(
        noun="oidc",
        verb="status",
        ids=("AUTH-009-oidc-config",),
        help="OIDC wiring state: not_configured | configured | unreachable | misconfigured",
        run=_oidc_status,
        note="Performs live provider discovery when configured, exactly as "
        "the API does; 'not_configured' is a healthy state (exit 3 "
        "means 'nothing to talk to', not 'broken').",
    ),
)

#: "noun verb" → Action, so a handler can name its own action.
_ACTION_BY_KEY: dict[str, Action] = {f"{a.noun} {a.verb}": a for a in ACTIONS}


def _check_bindings() -> None:
    """Import-time invariants — fail loudly, never ship a broken map.

    * every wrapper names real ``api_manifest`` rows (a typo is a
      KeyError turned into a clear message);
    * no two wrappers claim the same ``noun verb``;
    * only a kind=write row can be gated behind ``--approve`` (a read
      never proposes, and a write that mutates nothing must say so in its
      ``note`` rather than being silently unguarded).
    """
    seen: set[tuple[str, str]] = set()
    for action in ACTIONS + TOP_LEVEL:
        key = (action.noun, action.verb)
        if key in seen:
            raise ValueError(f"duplicate dispatch action: {action.command}")
        seen.add(key)
        for manifest_id in action.ids:
            if manifest_id not in _ROW_BY_ID:
                raise ValueError(
                    f"{action.command}: '{manifest_id}' is not an "
                    "api_manifest endpoint id — the CLI map and the API map "
                    "must share one source"
                )
        if action.needs_approval and action.kind != "write":
            raise ValueError(f"{action.command}: only a write can need approval")
        if action.kind == "write" and not action.needs_approval and not action.note:
            raise ValueError(
                f"{action.command}: a write that needs no approval must "
                "document why in its note"
            )


# ── The map ──────────────────────────────────────────────────────────


def _cli_index() -> dict[tuple[str, str], list[str]]:
    """(METHOD, path) → the shell commands that file it."""
    index: dict[tuple[str, str], list[str]] = {}
    for action in ACTIONS:
        for row in action.rows:
            index.setdefault((row.method, row.path), []).append(action.command)
    return index


def _verified_manifest(ctx: Ctx, verify: bool) -> tuple[dict[str, Any], list[str]]:
    """``endpoint_manifest`` over the live route table when possible.

    Falls back to the curated table with ``present: null`` (meaning "not
    verified in this invocation") — never ``present: false``, which would
    claim a route is absent when we simply did not look.
    """
    warnings: list[str] = []
    routes: Any = None
    if verify:
        try:
            from .api import create_app

            routes = list(create_app(ctx.data_dir, ctx.config_dir).routes)
        except Exception as exc:
            warnings.append(
                "route table not verified in this invocation "
                f"({type(exc).__name__}: {exc}); 'present' is null, not false"
            )
    else:
        warnings.append(
            "route table not verified (--no-verify); 'present' is null, not false"
        )
    if routes is None:
        rows = []
        for row in ENDPOINTS:
            out = {
                "id": row.id,
                "method": row.method,
                "path": row.path,
                "capability": row.capability,
                "kind": row.kind,
                "gate": row.gate,
                "auth": row.auth,
                "present": None,
            }
            if row.note:
                out["note"] = row.note
            rows.append(out)
        return (
            {
                "source": "src/personal_world/api_manifest.py (curated table, "
                "not verified against a live route table)",
                "vocabulary": {"kind": list(KINDS), "gate": list(GATES)},
                "endpoints": rows,
                "uncurated": [],
                "coverage": {
                    "curated": len(rows),
                    "curated_present": None,
                    "uncurated": None,
                    "complete": None,
                },
                "writes_without_elevation": [],
                "curated_but_not_registered": [],
            },
            warnings,
        )
    return endpoint_manifest(routes), warnings


def _manifest_payload(ctx: Ctx) -> Result:
    verify = not bool(getattr(ctx.args, "no_verify", False))
    payload, warnings = _verified_manifest(ctx, verify)
    index = _cli_index()
    for row in payload["endpoints"] + payload["uncurated"]:
        row["cli"] = index.get((row["method"], row["path"]), [])

    # Coverage is computed over the WHOLE table, before any filter, so the
    # map's claim about itself never depends on how it was sliced.
    curated = list(payload["endpoints"])
    uncurated = list(payload["uncurated"])
    covered = [r for r in curated if r.get("cli")]
    gaps = [f"{r['method']} {r['path']}" for r in curated if not r.get("cli")]
    payload["cli"] = {
        "group": DISPATCH_GROUP,
        "commands": [a.to_dict() for a in ACTIONS],
        "generic": [
            {
                "command": f"personal-world {API_COMMAND} <METHOD> <path>",
                "ids": [],
                "kind": "read|write",
                "gate": "per row",
                "transport": "http",
                "help": "the escape hatch: any row in this map is callable",
            },
            {
                "command": f"personal-world {MANIFEST_COMMAND}",
                "ids": ["API-015"],
                "kind": "read",
                "gate": "none",
                "transport": "service",
                "help": "print this map",
            },
        ],
        "coverage": {
            "wrappers": len(ACTIONS),
            "curated_rows": len(curated),
            "rows_with_wrapper": len(covered),
            "rows_without_wrapper": gaps,
            "uncurated_rows": len(uncurated),
            "complete": not gaps and not uncurated,
        },
    }

    capability = getattr(ctx.args, "capability", None)
    writes_only = bool(getattr(ctx.args, "writes", False))
    gaps_only = bool(getattr(ctx.args, "gaps", False))

    def keep(row: dict[str, Any]) -> bool:
        if capability and row.get("capability") != capability:
            return False
        if writes_only and row.get("kind") != "write":
            return False
        if gaps_only and row.get("cli"):
            return False
        return True

    payload["endpoints"] = [r for r in curated if keep(r)]
    payload["uncurated"] = [r for r in uncurated if keep(r)]
    return ok(
        "healthy",
        warnings=warnings,
        actions=[
            f"{len(covered)}/{len(curated)} curated rows have a friendly "
            f"wrapper; every row is callable through `personal-world {API_COMMAND}`"
        ],
        data=payload,
    )


def _api_call(ctx: Ctx) -> Result:
    method = str(getattr(ctx.args, "method", "") or "").strip().upper()
    path = str(getattr(ctx.args, "path", "") or "").strip()
    if method not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
        return fail(
            "invalid_args",
            warnings=[f"unsupported method '{method}'"],
        )
    if not path.startswith("/"):
        return fail(
            "invalid_args",
            warnings=["path must start with '/' (e.g. /api/status)"],
        )
    data: Any = None
    raw = getattr(ctx.args, "data", None)
    if raw:
        text = raw
        if text.startswith("@"):
            try:
                text = Path(text[1:]).read_text(encoding="utf-8")
            except OSError as exc:
                return fail(
                    "invalid_args", warnings=[f"cannot read --data file: {exc}"]
                )
        try:
            data = json.loads(text)
        except ValueError as exc:
            return fail("invalid_args", warnings=[f"--data must be valid JSON: {exc}"])
    return ctx.http(method, path, data)


#: The two top-level commands that are not `do <noun> <verb>` wrappers.
TOP_LEVEL: tuple[Action, ...] = (
    Action(
        noun=MANIFEST_COMMAND,
        verb="",
        ids=("API-015",),
        help="the bot's map: every endpoint, its gate, and the command that files it",
        run=_manifest_payload,
        args=(
            A("--capability", help="only this capability"),
            A("--writes", action="store_true", help="only kind=write rows"),
            A("--gaps", action="store_true", help="only rows with no CLI wrapper"),
            A(
                "--no-verify",
                action="store_true",
                help="skip building the app to verify routes (present=null)",
            ),
        ),
    ),
    Action(
        noun=API_COMMAND,
        verb="",
        ids=(),
        help="generic authenticated call against the local backend (the escape hatch)",
        run=_api_call,
        transport="http",
        args=(
            A("method", help="GET|POST|PUT|PATCH|DELETE"),
            A("path", help="route path, e.g. /api/status or '/api/journal?n=5'"),
            A("--data", help="JSON body, or @file.json"),
            A(
                "--base",
                help=f"backend base URL (default ${BASE_ENV} or {DEFAULT_BASE})",
            ),
            A("--timeout", type=float, help="seconds (default 30)"),
        ),
        note="Credential: $PW_API_TOKEN, else <data_dir>/.env, else "
        "$PW_SESSION as a browser-session cookie. X-PW-StepUp is never "
        "sent. A local backend grants step-up to a true-loopback peer "
        "(the documented local-owner exception), so prefer `do` for "
        "writes: it files a durable proposal instead.",
    ),
)


def _list_payload(ctx: Ctx) -> Result:
    """`personal-world do` with no noun: what you can file, and how."""
    rows = [a.to_dict() for a in ACTIONS]
    return ok(
        "healthy",
        actions=[
            "reads need nothing; writes file a proposal and exit 4",
            f"to act: add --approve AND export {STEP_UP_ENV}=<instance token>",
            f"the full map: personal-world {MANIFEST_COMMAND} --json",
        ],
        data={"group": DISPATCH_GROUP, "commands": rows, "count": len(rows)},
    )


_LIST_ACTION = Action(
    noun=DISPATCH_GROUP,
    verb="",
    ids=(),
    help="list every wrapper, its manifest id, kind and gate",
    run=_list_payload,
)


# The whole table now exists: check it against the one source of truth.
_check_bindings()


# ── Output ───────────────────────────────────────────────────────────


def _table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> list[str]:
    def cell(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple)):
            return ", ".join(str(v) for v in value)
        return str(value)

    cells = [[cell(r.get(key)) for key, _ in columns] for r in rows]
    widths = [
        max([len(title)] + [len(c[i]) for c in cells]) if cells else len(title)
        for i, (_, title) in enumerate(columns)
    ]
    out = ["  ".join(title.ljust(widths[i]) for i, (_, title) in enumerate(columns))]
    out.append("  ".join("-" * w for w in widths))
    for c in cells:
        out.append("  ".join(c[i].ljust(widths[i]) for i in range(len(columns))))
    return out


def _human(result: Result) -> list[str]:
    lines = [f"{result.status}: {'ok' if result.ok else 'not ok'}"]
    for w in result.warnings:
        lines.append(f"  ! {w}")
    for a in result.actions:
        lines.append(f"  * {a}")
    data = result.data
    if isinstance(data, dict) and "endpoints" in data:
        lines += _table(
            data.get("endpoints") or [],
            [
                ("id", "ID"),
                ("method", "METHOD"),
                ("path", "PATH"),
                ("capability", "CAPABILITY"),
                ("kind", "KIND"),
                ("gate", "GATE"),
                ("cli", "CLI WRAPPER"),
            ],
        )
        coverage = (data.get("cli") or {}).get("coverage") or {}
        if coverage:
            lines.append(
                f"  {coverage.get('rows_with_wrapper')}/"
                f"{coverage.get('curated_rows')} curated rows have a wrapper; "
                f"{coverage.get('uncurated_rows')} live rows are uncurated"
            )
        return lines
    if (
        isinstance(data, dict)
        and "commands" in data
        and isinstance(data["commands"], list)
    ):
        lines += _table(
            data["commands"],
            [
                ("command", "COMMAND"),
                ("kind", "KIND"),
                ("gate", "GATE"),
                ("route", "FILES"),
                ("help", "WHAT IT DOES"),
            ],
        )
        return lines
    if data is not None:
        lines.append(json.dumps(data, indent=2, default=str))
    return lines


def _emit(result: Result, as_json: bool) -> int:
    if as_json:
        print(result.model_dump_json(indent=2))
    else:
        for line in _human(result):
            print(line)
    return exit_for(result)


# ── Dispatch entry point ─────────────────────────────────────────────


def _dispatch(world: Any, registry: Any, journal: Any, args: Any) -> int:
    """The single ``fn`` every parser in this module sets.

    ``cli.py`` calls ``args.fn(world, registry, journal, args)`` and
    catches only ``MutationDenied``; this catches everything else so a bot
    gets an envelope and an exit code, never a traceback.
    """
    action: Action | None = getattr(args, "action", None)
    ctx = Ctx(args, world, registry, journal)
    if action is None:
        return _emit(fail("invalid_args", warnings=["nothing to do"]), ctx.as_json)
    try:
        result = action.run(ctx)
    except SystemExit:
        raise
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        return EXIT_ERROR
    except Exception as exc:
        from .world import MutationDenied

        if isinstance(exc, MutationDenied):
            # A cemented policy refuses every non-user mutation path, the
            # CLI included. Refused (ok=false) and exit 4: nothing changed.
            result = fail(
                "denied",
                warnings=[str(exc)],
                data={"mutated": False},
            )
        else:
            result = fail(
                "unhealthy",
                warnings=[f"{action.command} failed: {type(exc).__name__}: {exc}"],
                data={"mutated": False},
            )
    if not isinstance(result, Result):  # a handler returned a dict,
        result = ok("healthy", data=result)
    return _emit(result, ctx.as_json)


_WRITE_FLAGS: tuple[Arg, ...] = (
    A("--approve", action="store_true", help=APPROVE_HELP),
)
