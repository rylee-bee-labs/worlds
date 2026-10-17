"""Workbench spike proof suite (ADR-0003/0006 thin slice, backend only).

Fake podman via PATH-injected shim scripts in tmp_path (the estate
subprocess-faking idiom, cf. tests/test_safe_commit.py fake-uv). The
shim RECORDS its argv and environment so the security floor is proven,
not asserted:

- disabled by default: capability reports not_configured, nothing runs
- allowlist refusal (empty allowlist fails closed; unlisted names,
  option-injection and shell-metacharacter names are denied)
- argv-without-shell: the recorded invocation is exactly
  [podman, exec, <container>, *argv] — metacharacters stay literal
- no env passthrough: the client runs with an explicitly empty env;
  a planted secret never reaches the invocation
- no mount flags before the container name (host paths stay mounted-out)
- timeout kill: bounded, recorded as state=timeout
- event envelope: one journal TASK row per execution — event_id,
  task_id, state, payload, correlation_id on the existing journal
- degraded status when podman is missing: 'unavailable: <reason>',
  never a fake list
"""

import json
import os
import time
from pathlib import Path

import pytest

from personal_world.app import build_registry
from personal_world.journal import Journal
from personal_world.model import JournalKind
from personal_world.providers.registry import Registry
from personal_world.providers.workbench import (
    ALLOWLIST_ENV,
    WORKBENCH_ENV,
    WorkbenchPodman,
)
from personal_world.world import World

# The shim is deliberately built from shell BUILTINS only (printf,
# read, test, while): run_task/list_environments launch it with an
# explicitly EMPTY environment, so there is no PATH for the script to
# resolve external commands through. '#!/bin/sh' is resolved by the
# kernel, not by PATH.
SHIM = """#!/bin/sh
# fake podman for the workbench spike — records argv + env, then
# emulates: ps -> payload file; 'die' in argv -> exit 7;
# 'hang' in argv -> builtin busy-loop (killed by the timeout).
# The leak/taskbox markers are BUILTIN checks so the env-isolation
# proof cannot pass vacuously if the external `env` command were
# unavailable under the empty PATH.
printf '%s\\n' "$@" > "{log}/args"
env > "{log}/env"
if [ -n "$PW_FAKE_SECRET" ]; then printf 'leak\\n' > "{log}/leak"; fi
if [ "$TASKBOX" = "yes" ]; then printf 'seen\\n' > "{log}/taskbox"; fi
if [ "$1" = "ps" ]; then
  while IFS= read -r line; do printf '%s\\n' "$line"; done < "{payload}"
  exit 0
fi
for a in "$@"; do
  if [ "$a" = "die" ]; then
    printf 'boom\\n' >&2
    exit 7
  fi
  if [ "$a" = "hang" ]; then
    while : ; do : ; done
  fi
done
printf 'task-out\\n'
printf 'task-err\\n' >&2
exit 0
"""

GOOD_PS = json.dumps(
    [
        {"Id": "abc123def456789", "Names": "ai-distrobox",
         "Image": "distrobox-fedora", "State": "running"},
        {"Id": "ffeeddccbbaa1122", "Names": ["two-name-box"],
         "State": "stopped"},  # Image missing on purpose
    ]
) + "\n"


def _install_podman(tmp_path, monkeypatch, payload="[]\n"):
    """PATH-inject the fake podman; return the log dir where the shim
    records each invocation."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir(exist_ok=True)
    log_dir = tmp_path / "shimlog"
    log_dir.mkdir(exist_ok=True)
    payload_file = tmp_path / "ps.json"
    payload_file.write_text(payload)
    shim = bin_dir / "podman"
    shim.write_text(
        SHIM.format(log=str(log_dir), payload=str(payload_file))
    )
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    return log_dir


def _wipe_shimlog(log_dir: Path) -> None:
    for f in log_dir.glob("*"):
        f.unlink()


def _provider(tmp_path, *, allow=("ai-distrobox",), **cfg) -> WorkbenchPodman:
    config = {"allowed_containers": list(allow)} if allow is not None else {}
    config.update(cfg)
    return WorkbenchPodman(config=config, journal=Journal(tmp_path / "journal.ndjson"))


def _journal_rows(tmp_path) -> list[dict]:
    path = tmp_path / "journal.ndjson"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """The spike is off by default: never let the developer's real
    PW_WORKBENCH leak into a 'disabled' proof."""
    monkeypatch.delenv(WORKBENCH_ENV, raising=False)
    monkeypatch.delenv(ALLOWLIST_ENV, raising=False)


# ── 1. disabled by default ──────────────────────────────────────────


class TestDisabledByDefault:
    def test_capability_reports_not_configured_via_registry(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "connections.json").write_text(json.dumps({"connections": []}))
        reg = build_registry(World(), Registry(), config_dir, data_dir=tmp_path)
        r = reg.observe("workbench")
        assert r.ok is False
        # honest 'off', exactly like every other unconnected capability
        assert r.status == "not_configured"
        assert any("workbench" in w for w in r.warnings)

    def test_run_task_refuses_and_records_security_event(self, tmp_path, monkeypatch):
        _install_podman(tmp_path, monkeypatch)
        wb = _provider(tmp_path)  # allowlist configured, but env gate OFF
        r = wb.run_task("ai-distrobox", ["true"])
        assert r.ok is False
        assert r.status == "not_configured"
        assert not (tmp_path / "shimlog" / "args").exists(), "nothing may execute"
        kinds = [row["kind"] for row in _journal_rows(tmp_path)]
        assert kinds == [JournalKind.SECURITY.value]


# ── 2. allowlist / fail-closed refusals ─────────────────────────────


class TestAllowlistFailClosed:
    @pytest.fixture
    def wb(self, tmp_path, monkeypatch):
        monkeypatch.setenv(WORKBENCH_ENV, "1")
        _install_podman(tmp_path, monkeypatch)
        return _provider(tmp_path, allow=None)  # no config allowlist

    def test_empty_allowlist_refuses_everything(self, wb, tmp_path):
        assert wb.allowlist() == []
        r = wb.run_task("ai-distrobox", ["echo", "hi"])
        assert r.ok is False and r.status == "denied"
        assert not (tmp_path / "shimlog" / "args").exists(), "refusal must not execute"
        kinds = [row["kind"] for row in _journal_rows(tmp_path)]
        assert kinds == [JournalKind.SECURITY.value]

    def test_unlisted_container_refused(self, tmp_path, monkeypatch):
        monkeypatch.setenv(WORKBENCH_ENV, "1")
        _install_podman(tmp_path, monkeypatch)
        wb = _provider(tmp_path, allow=("allowed-box",))
        r = wb.run_task("other-box", ["echo", "hi"])
        assert r.ok is False and r.status == "denied"
        assert not (tmp_path / "shimlog" / "args").exists()

    def test_env_var_allowlist_is_honored(self, tmp_path, monkeypatch):
        monkeypatch.setenv(WORKBENCH_ENV, "1")
        monkeypatch.setenv(ALLOWLIST_ENV, "ai-distrobox, backup-box")
        _install_podman(tmp_path, monkeypatch)
        wb = _provider(tmp_path, allow=None)  # config absent -> env fallback
        assert wb.allowlist() == ["ai-distrobox", "backup-box"]
        assert wb.run_task("ai-distrobox", ["true"]).ok is True

    @pytest.mark.parametrize(
        "name",
        [
            "-lead-dash-option",       # option injection into podman exec
            "box; rm -rf /",           # shell metacharacters
            "box|tee /etc/x",
            "path/../escape",          # path-shaped names
            "two words",
            "",
            "Ünicode-box",             # outside the explicit charset
        ],
    )
    def test_container_name_shape_enforced(self, wb, name, tmp_path):
        assert wb.run_task(name, ["true"]).status == "denied"
        assert not (tmp_path / "shimlog" / "args").exists()


# ── 3. argv never touches a shell ───────────────────────────────────


class TestArgvWithoutShell:
    @pytest.fixture
    def wb(self, tmp_path, monkeypatch):
        monkeypatch.setenv(WORKBENCH_ENV, "1")
        _install_podman(tmp_path, monkeypatch)
        return _provider(tmp_path)

    def test_invocation_is_exactly_podman_exec_container_argv(self, wb, tmp_path):
        _wipe_shimlog(tmp_path / "shimlog")
        r = wb.run_task("ai-distrobox", ["echo", "a > b", "*", "$(whoami)"])
        assert r.ok, r.warnings
        recorded = (tmp_path / "shimlog" / "args").read_text().splitlines()
        assert recorded == ["exec", "ai-distrobox", "echo", "a > b", "*", "$(whoami)"]
        # metacharacters stayed literal: no redirect target, no glob spill
        assert not (tmp_path / "b").exists()
        assert not (tmp_path / "shimlog" / "stdout").exists()

    def test_shell_string_argv_refused(self, wb, tmp_path):
        r = wb.run_task("ai-distrobox", "echo hi | tee /etc/passwd")
        assert r.ok is False and r.status == "denied"
        assert any("shell" in w for w in r.warnings)
        assert not (tmp_path / "shimlog" / "args").exists()

    def test_empty_and_nonstring_argv_refused(self, wb):
        assert wb.run_task("ai-distrobox", []).status == "denied"
        assert wb.run_task("ai-distrobox", ["ok", 42]).status == "denied"
        assert wb.run_task("ai-distrobox", ["a\x00b"]).status == "denied"

    def test_no_mount_flags_before_the_container(self, wb, tmp_path):
        """Even argv items that LOOK like podman flags are passed to the
        COMMAND (after the container name) — host mounts stay impossible."""
        _wipe_shimlog(tmp_path / "shimlog")
        wb.run_task("ai-distrobox", ["-v", "/host:/container", "--privileged"])
        recorded = (tmp_path / "shimlog" / "args").read_text().splitlines()
        assert recorded[:2] == ["exec", "ai-distrobox"]
        assert recorded.index("ai-distrobox") == 1, "container must precede all argv"


# ── 4. env isolation ────────────────────────────────────────────────


class TestNoEnvPassthrough:
    def test_client_runs_with_empty_env_and_host_secrets_stay_home(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv(WORKBENCH_ENV, "1")
        monkeypatch.setenv("PW_FAKE_SECRET", "do-not-leak-9f3a")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_do-not-leak")
        _install_podman(tmp_path, monkeypatch)
        wb = _provider(tmp_path)
        assert wb.run_task("ai-distrobox", ["true"]).ok
        log = tmp_path / "shimlog"
        # builtin -n check inside the shim: the secret variable was not
        # even VISIBLE to the process (not vacuous if `env` failed)
        assert not (log / "leak").exists()
        env_seen = (log / "env").read_text()
        for needle in ("do-not-leak-9f3a", "PW_FAKE_SECRET", "ghp_do-not-leak",
                       "GITHUB_TOKEN"):
            assert needle not in env_seen

    def test_env_is_opt_in_via_config(self, tmp_path, monkeypatch):
        monkeypatch.setenv(WORKBENCH_ENV, "1")
        monkeypatch.setenv("PW_FAKE_SECRET", "do-not-leak-9f3a")
        _install_podman(tmp_path, monkeypatch)
        wb = _provider(tmp_path, podman_env={"TASKBOX": "yes"})
        assert wb.run_task("ai-distrobox", ["true"]).ok
        log = tmp_path / "shimlog"
        assert (log / "taskbox").exists(), "allowlisted env must arrive"
        assert not (log / "leak").exists(), "nothing else may"


# ── 5. timeout kill ─────────────────────────────────────────────────


class TestTimeoutKill:
    def test_hang_is_killed_and_recorded(self, tmp_path, monkeypatch):
        monkeypatch.setenv(WORKBENCH_ENV, "1")
        _install_podman(tmp_path, monkeypatch)
        wb = _provider(tmp_path)
        started = time.monotonic()
        r = wb.run_task("ai-distrobox", ["hang"], timeout=0.5)
        elapsed = time.monotonic() - started
        assert r.ok is False
        assert r.status == "timeout"
        assert elapsed < 15, f"timeout must bound the task, took {elapsed:.1f}s"
        rows = _journal_rows(tmp_path)
        task = rows[-1]
        assert task["kind"] == JournalKind.TASK.value
        assert task["state"] == "timeout"
        assert task["payload"]["exit_code"] is None  # never fabricated


# ── 6. event envelope on the journal (ADR-0006) ─────────────────────


class TestEventEnvelope:
    def test_completion_writes_one_task_row_with_the_envelope(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv(WORKBENCH_ENV, "1")
        _install_podman(tmp_path, monkeypatch)
        wb = _provider(tmp_path)
        r = wb.run_task("ai-distrobox", ["echo", "hi"], correlation_id="corr-77")
        assert r.ok
        rows = _journal_rows(tmp_path)
        assert len(rows) == 1, "one journal row per execution — existing journal"
        row = rows[0]
        # envelope fields (ADR-0006 Decision 1) mapped onto the journal:
        assert row["kind"] == JournalKind.TASK.value          # subject/type
        assert row["ts"]                                       # timestamp (existing)
        assert row["provenance"]["source"] == "workbench"      # source (existing)
        assert row["event_id"]
        assert row["task_id"] == r.data["task_id"]
        assert row["state"] == "completed"
        assert row["correlation_id"] == "corr-77"
        assert row["payload"]["argv"] == ["echo", "hi"]
        assert row["payload"]["container"] == "ai-distrobox"
        assert row["payload"]["exit_code"] == 0
        # readable without the payload, for the audit renderer
        assert "ai-distrobox" in row["summary"]
        # journal still loads through the shared model
        fresh = Journal(tmp_path / "journal.ndjson")
        assert [e.task_id for e in fresh.events()] == [row["task_id"]]

    def test_nonzero_exit_is_recorded_not_raised(self, tmp_path, monkeypatch):
        monkeypatch.setenv(WORKBENCH_ENV, "1")
        _install_podman(tmp_path, monkeypatch)
        wb = _provider(tmp_path)
        r = wb.run_task("ai-distrobox", ["die"])
        assert r.ok is False and r.status == "failed"
        assert r.data["exit_code"] == 7
        row = _journal_rows(tmp_path)[-1]
        assert row["kind"] == JournalKind.TASK.value
        assert row["state"] == "failed"
        assert row["payload"]["exit_code"] == 7

    def test_run_task_refuses_when_no_journal_wired(self, tmp_path, monkeypatch):
        """Unauditable work does not run: journal is part of the floor."""
        monkeypatch.setenv(WORKBENCH_ENV, "1")
        _install_podman(tmp_path, monkeypatch)
        wb = WorkbenchPodman(config={"allowed_containers": ["ai-distrobox"]})
        r = wb.run_task("ai-distrobox", ["true"])
        assert r.ok is False and r.status == "unavailable"
        assert any("journal" in w for w in r.warnings)
        assert not (tmp_path / "shimlog" / "args").exists()


# ── 7. degraded status when podman is missing ───────────────────────


class TestDegradedWithoutPodman:
    @pytest.fixture
    def no_podman_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv(WORKBENCH_ENV, "1")
        empty = tmp_path / "emptybin"
        empty.mkdir()
        monkeypatch.setenv("PATH", str(empty))

    def test_observe_reports_unavailable_with_reason(self, tmp_path, no_podman_path):
        wb = _provider(tmp_path)
        r = wb.observe()
        assert r.ok is False
        assert r.status == "unavailable"
        assert any(w.startswith("unavailable:") for w in r.warnings)

    def test_list_environments_never_fakes_a_list(self, tmp_path, no_podman_path):
        wb = _provider(tmp_path)
        r = wb.list_environments()
        assert r.ok is False and r.status == "unavailable"
        assert r.data is None, "no environments key on failure"

    def test_unparseable_ps_output_degrades_not_guessed(self, tmp_path, monkeypatch):
        monkeypatch.setenv(WORKBENCH_ENV, "1")
        _install_podman(tmp_path, monkeypatch, payload="this is not json\n")
        wb = _provider(tmp_path)
        r = wb.list_environments()
        assert r.ok is False and r.status == "unavailable"
        assert any("unavailable:" in w for w in r.warnings)

    def test_run_task_without_podman_makes_no_journal_claim(
        self, tmp_path, no_podman_path
    ):
        wb = _provider(tmp_path)
        r = wb.run_task("ai-distrobox", ["true"])
        assert r.ok is False and r.status == "unavailable"
        assert _journal_rows(tmp_path) == [], "nothing ran -> no TASK event"


# ── 8. happy path + registry integration ────────────────────────────


class TestEnabledRegistration:
    def test_list_environments_parses_and_normalises(self, tmp_path, monkeypatch):
        monkeypatch.setenv(WORKBENCH_ENV, "1")
        _install_podman(tmp_path, monkeypatch, payload=GOOD_PS)
        wb = _provider(tmp_path)
        r = wb.list_environments()
        assert r.ok
        envs = r.data["environments"]
        assert [e["name"] for e in envs] == ["ai-distrobox", "two-name-box"]
        # missing Image stays None — never invented
        assert envs[1]["image"] is None
        assert envs[0]["status"] == "running"

    def test_observe_healthy_lists_environments_and_actions(self, tmp_path, monkeypatch):
        monkeypatch.setenv(WORKBENCH_ENV, "1")
        _install_podman(tmp_path, monkeypatch, payload=GOOD_PS)
        wb = _provider(tmp_path)
        r = wb.observe()
        assert r.ok and r.status == "healthy"
        assert r.actions == ["list_environments", "run_task"]
        assert [e["name"] for e in r.data["environments"]] == [
            "ai-distrobox", "two-name-box",
        ]

    def test_registry_picks_the_provider_up_when_enabled(self, tmp_path, monkeypatch):
        monkeypatch.setenv(WORKBENCH_ENV, "1")
        _install_podman(tmp_path, monkeypatch, payload=GOOD_PS)
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "connections.json").write_text(json.dumps({"connections": []}))
        reg = build_registry(World(), Registry(), config_dir,
                             journal=Journal(tmp_path / "j.ndjson"), data_dir=tmp_path)
        p = reg.provider_for("workbench")
        assert p is not None and p.name == "workbench-podman"
        assert p.writes == "exec"
        assert reg.observe("workbench").status == "healthy"
        assert "workbench" in reg.manifest()
