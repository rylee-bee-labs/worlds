"""agent-sync project-sensor tests (providers/agent_sync.py + the
/api/projects/status endpoint).

Contract under test:
- agent-sync stays AUTHORITATIVE for project publication state; the
  sensor parses its documented play-nice/repo-status-v1 JSON and adds
  no Git computation of its own
- command absent / timeout / malformed output -> honest 'unavailable';
  Project Worlds continues normally
- one bad project record survives as its own honest record; the rest
  of the estate is never discarded
- remote UNKNOWN is preserved (safe_to_leave='unknown'), never
  converted to healthy or unhealthy
- closed vocabularies enforced; unknown values -> None / 'unknown',
  never guessed, never dropped
- exit code 1 from agent-sync is a valid "work to do" observation,
  NOT a provider failure (only agent_status.py exit-2/no-parse is)
- read-only: `agent-sync status --all --format json` argv only, no
  shell, never a mutation verb
- observation FRESHNESS is derived from agent-sync's observed_at
  (threshold = the product-wide lab_state 30-minute convention);
  state and freshness are separate dimensions — age never rewrites
  publish_state, and missing/invalid timestamps stay honestly
  'unknown'
"""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from personal_world.providers.agent_sync import (
    SCHEMA,
    AgentSyncProjectSensor,
)


def _record(project: str = "demo", **over) -> dict:
    """One well-formed repo-status-v1 record with per-test overrides."""
    base = {
        "schema": SCHEMA,
        "observed_at": "2026-09-12T12:48:38Z",
        "project": project,
        "path": f"/repos/{project}",
        "is_git_repo": True,
        "branch": "main",
        "local_head": "aaaaaaa",
        "remote_name": "origin",
        "remote_url": f"https://example.com/acme/{project}.git",
        "remote_head": "aaaaaaa",
        "publish_state": "match",
        "working_tree": {"staged": 0, "modified": 0, "untracked": 0,
                         "conflicted": 0},
        "play_nice": {"present": True, "revision": "0cee065",
                      "source_repository": "Rylee-Bee/play-nice-contracts"},
        "work_state": "working",
        "safe_to_leave": "yes",
    }
    base.update(over)
    return base


def _fake_run(stdout: str = "", returncode: int = 0, calls: list | None = None):
    """A subprocess.run replacement that records argv and replays a
    canned agent-sync answer."""
    calls = calls if calls is not None else []

    class P:
        pass

    def fake(cmd, **kwargs):
        calls.append(cmd)
        p = P()
        p.stdout = stdout
        p.returncode = returncode
        return p

    return fake, calls


class TestSensorHonestStates:
    """Every failure mode degrades to a structured state, never a
    crash, never a guessed record."""

    def test_missing_command_is_unavailable(self, monkeypatch):
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: None)
        r = AgentSyncProjectSensor().observe_projects()
        assert r.ok is False
        assert r.status == "unavailable"

    def test_timeout_is_unavailable_never_hangs(self, monkeypatch):
        def boom(cmd, **kw):
            raise subprocess.TimeoutExpired(cmd, 60)
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", boom)
        r = AgentSyncProjectSensor().observe_projects()
        assert r.ok is False
        assert r.status == "unavailable"

    def test_malformed_json_is_unavailable_not_partial(self, monkeypatch):
        fake, calls = _fake_run(stdout="this is not json at all")
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        r = AgentSyncProjectSensor().observe_projects()
        assert r.ok is False
        assert r.status == "unavailable"
        assert r.data is None

    def test_non_list_payload_is_unavailable(self, monkeypatch):
        fake, _ = _fake_run(stdout=json.dumps({"schema": SCHEMA}))
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        r = AgentSyncProjectSensor().observe_projects()
        assert r.ok is False
        assert r.status == "unavailable"

    def test_empty_registry_is_healthy_empty_list(self, monkeypatch):
        fake, _ = _fake_run(stdout="[]")
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        r = AgentSyncProjectSensor().observe_projects()
        assert r.ok is True
        assert r.data["projects"] == []

    def test_exit_one_is_a_valid_observation_not_failure(self, monkeypatch):
        """agent_status.py exits 1 when any project needs attention —
        the payload is still complete and honest. The sensor must
        serve it, not fail it."""
        records = [_record(), _record("wip", publish_state="diverged",
                                       safe_to_leave="no")]
        fake, _ = _fake_run(stdout=json.dumps(records), returncode=1)
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        r = AgentSyncProjectSensor().observe_projects()
        assert r.ok is True
        assert len(r.data["projects"]) == 2

    def test_one_bad_project_does_not_discard_the_rest(self, monkeypatch):
        good = _record("settled")
        errored = _record("broken", is_git_repo=False, branch=None,
                          local_head=None, remote_head=None,
                          publish_state=None, safe_to_leave="unknown",
                          error="observe_repo failed: boom")
        fake, _ = _fake_run(stdout=json.dumps([good, errored]))
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        r = AgentSyncProjectSensor().observe_projects()
        assert r.ok is True
        assert len(r.data["projects"]) == 2
        by_name = {p["project"]: p for p in r.data["projects"]}
        assert by_name["broken"]["error"] == "observe_repo failed: boom"
        assert by_name["broken"]["safe_to_leave"] == "unknown"

    def test_record_without_schema_marker_is_skipped_not_guessed(self, monkeypatch):
        alien = {"project": "alien", "not": "repo-status-v1"}
        good = _record("settled")
        fake, _ = _fake_run(stdout=json.dumps([good, alien]))
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        r = AgentSyncProjectSensor().observe_projects()
        names = [p["project"] for p in r.data["projects"]]
        assert names == ["settled"]


class TestNormalization:
    """The documented play-nice/repo-status-v1 shape maps onto the
    Project Worlds read-only model, honestly."""

    @pytest.fixture()
    def observed(self, monkeypatch):
        fake, calls = _fake_run(stdout=json.dumps([_record()]))
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        r = AgentSyncProjectSensor().observe_projects()
        assert r.ok is True
        return r.data

    def test_observed_at_is_carried(self, observed):
        assert observed["observed_at"] == "2026-09-12T12:48:38Z"

    def test_all_documented_fields_map(self, observed):
        p = observed["projects"][0]
        assert p["project"] == "demo"
        assert p["branch"] == "main"
        assert p["local_head"] == "aaaaaaa"
        assert p["remote_head"] == "aaaaaaa"
        assert p["publish_state"] == "match"
        assert p["working_tree"] == {"staged": 0, "modified": 0,
                                     "untracked": 0, "conflicted": 0}
        assert p["play_nice"]["present"] is True
        assert p["play_nice"]["revision"] == "0cee065"
        assert p["work_state"] == "working"
        assert p["safe_to_leave"] == "yes"

    def test_remote_unknown_is_preserved(self, monkeypatch):
        rec = _record("offline", remote_head=None, publish_state=None,
                      safe_to_leave="unknown")
        fake, _ = _fake_run(stdout=json.dumps([rec]))
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        r = AgentSyncProjectSensor().observe_projects()
        p = r.data["projects"][0]
        assert p["remote_head"] is None
        assert p["publish_state"] is None
        assert p["safe_to_leave"] == "unknown"  # never healthy/unhealthy

    def test_dirty_published_project_is_local_work_not_broken(self, monkeypatch):
        rec = _record("wip", working_tree={"staged": 0, "modified": 2,
                                           "untracked": 1, "conflicted": 0},
                     safe_to_leave="published-with-local-work")
        fake, _ = _fake_run(stdout=json.dumps([rec]))
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        r = AgentSyncProjectSensor().observe_projects()
        p = r.data["projects"][0]
        assert p["working_tree"]["modified"] == 2
        assert p["safe_to_leave"] == "published-with-local-work"

    @pytest.mark.parametrize("publish,state", [
        ("ahead", "no"),
        ("behind", "no"),
        ("diverged", "no"),
        ("match", "yes"),
    ])
    def test_publish_state_vocabulary(self, monkeypatch, publish, state):
        rec = _record(publish_state=publish, safe_to_leave=state)
        fake, _ = _fake_run(stdout=json.dumps([rec]))
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        r = AgentSyncProjectSensor().observe_projects()
        p = r.data["projects"][0]
        assert p["publish_state"] == publish
        assert p["safe_to_leave"] == state

    def test_non_main_branch_is_ordinary(self, monkeypatch):
        rec = _record("legacy", branch="master")
        fake, _ = _fake_run(stdout=json.dumps([rec]))
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        r = AgentSyncProjectSensor().observe_projects()
        assert r.data["projects"][0]["branch"] == "master"

    def test_play_nice_absent_is_honest(self, monkeypatch):
        rec = _record("plain", play_nice={"present": False})
        fake, _ = _fake_run(stdout=json.dumps([rec]))
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        r = AgentSyncProjectSensor().observe_projects()
        p = r.data["projects"][0]
        assert p["play_nice"]["present"] is False
        assert p["play_nice"]["revision"] is None

    def test_unknown_vocabulary_values_normalize_to_unknown(self, monkeypatch):
        rec = _record("weird", publish_state="sideways",
                      safe_to_leave="sure?", work_state="vibing")
        fake, _ = _fake_run(stdout=json.dumps([rec]))
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        r = AgentSyncProjectSensor().observe_projects()
        p = r.data["projects"][0]
        assert p["publish_state"] is None
        assert p["safe_to_leave"] == "unknown"
        assert p["work_state"] == "unknown"

    def test_bad_counts_coerce_to_zero_never_crash(self, monkeypatch):
        rec = _record("badcounts", working_tree={"staged": "lots",
                                                 "modified": None,
                                                 "untracked": -3})
        fake, _ = _fake_run(stdout=json.dumps([rec]))
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        r = AgentSyncProjectSensor().observe_projects()
        assert r.data["projects"][0]["working_tree"] == {
            "staged": 0, "modified": 0, "untracked": 0, "conflicted": 0}


class TestFreshness:
    """State and freshness are SEPARATE dimensions: age is derived from
    agent-sync's own observed_at and never rewrites publish_state.
    Threshold mirrors lab_state.FRESHNESS (the product-wide 30-minute
    freshness convention). Missing/invalid timestamps stay honestly
    'unknown' — no age is fabricated from a bad clock reading."""

    def _now(self):
        return datetime(2026, 9, 12, 15, 0, 0, tzinfo=timezone.utc)

    def test_fresh_under_threshold(self):
        from personal_world.providers.agent_sync import freshness
        now = self._now()
        f = freshness("2026-09-12T14:48:38Z", now=now)
        assert f == {"freshness": "fresh", "age_seconds": 682}

    def test_stale_above_threshold(self):
        from personal_world.providers.agent_sync import freshness
        now = self._now()
        f = freshness("2026-09-12T14:10:00Z", now=now)  # 50 min
        assert f["freshness"] == "stale"
        assert f["age_seconds"] == 3000

    def test_exact_threshold_is_fresh(self):
        from personal_world.providers.agent_sync import STALE_AFTER, freshness
        now = self._now()
        f = freshness("2026-09-12T14:30:00Z", now=now)  # exactly 30 min
        # exactly-at-threshold is NOT stale (strictly greater than)
        assert f["freshness"] == "fresh"
        assert f["age_seconds"] == int(STALE_AFTER.total_seconds())

    def test_missing_timestamp_is_unknown_not_stale(self):
        from personal_world.providers.agent_sync import freshness
        assert freshness(None) == {"freshness": "unknown", "age_seconds": None}
        assert freshness("") == {"freshness": "unknown", "age_seconds": None}

    def test_invalid_timestamp_is_unknown_not_stale(self):
        from personal_world.providers.agent_sync import freshness
        assert freshness("not-a-timestamp") == \
            {"freshness": "unknown", "age_seconds": None}

    def test_freshness_never_rewrites_state(self, monkeypatch):
        # stale observation of 'diverged' still reports 'diverged' —
        # the record's publish_state is untouched by the age math
        fake, _ = _fake_run(stdout=json.dumps([
            _record("split", publish_state="diverged",
                    remote_head="bbbbb", local_head="ccccc",
                    observed_at="2026-09-12T10:00:00Z"),
        ]))
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        result = AgentSyncProjectSensor().observe_projects()
        assert result.ok
        assert result.data["projects"][0]["publish_state"] == "diverged"
        assert result.data["freshness"] == "stale"

    def test_observe_projects_carries_freshness(self, monkeypatch):
        fake, _ = _fake_run(stdout=json.dumps([_record()]))
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        result = AgentSyncProjectSensor().observe_projects()
        assert result.ok
        assert result.data["observed_at"] == "2026-09-12T12:48:38Z"
        assert result.data["freshness"] in ("fresh", "stale")
        assert isinstance(result.data["age_seconds"], int)

    def test_threshold_matches_lab_state_convention(self):
        from personal_world.providers.agent_sync import STALE_AFTER
        from personal_world.providers.lab_state import FRESHNESS
        assert STALE_AFTER == FRESHNESS == timedelta(minutes=30)


class TestReadOnlyStructure:
    """The sensor is read-only by construction, like the gh CLI
    module before it: argv lists, no shell, no mutation verbs."""

    def test_invocation_is_status_all_json_argv_only(self, monkeypatch):
        fake, calls = _fake_run(stdout=json.dumps([_record()]))
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        AgentSyncProjectSensor().observe_projects()
        assert calls == [["/usr/bin/agent-sync", "status", "--all",
                          "--format", "json"]]

    def test_timeout_is_bounded(self):
        assert AgentSyncProjectSensor().timeout <= 60

    def test_no_mutation_verbs_in_module(self):
        src = Path("src/personal_world/providers/agent_sync.py").read_text()
        for verb in ("push", "commit", "rebase", "stash", "reset",
                     "clean", "merge"):
            assert f'"{verb}"' not in src, f"mutation verb {verb!r} in module"

    def test_no_shell_no_env_credential_access(self):
        src = Path("src/personal_world/providers/agent_sync.py").read_text()
        assert "shell=True" not in src
        assert "os.environ" not in src
        assert "open(" not in src


class TestObserveContract:
    def test_observe_unavailable_without_binary(self, monkeypatch):
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: None)
        assert AgentSyncProjectSensor().observe().ok is False

    def test_observe_healthy_with_binary(self, monkeypatch):
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        r = AgentSyncProjectSensor().observe()
        assert r.ok is True
        assert r.data == {"provider": "agent-sync"}


class TestEndpoint:
    """GET /api/projects/status through the real app."""

    def _client(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient

        from personal_world.api import create_app
        monkeypatch.setenv("PW_API_TOKEN", "t")
        return TestClient(create_app(tmp_path, tmp_path))

    def test_requires_auth(self, tmp_path, monkeypatch):
        client = self._client(tmp_path, monkeypatch)
        assert client.get("/api/projects/status").status_code == 401

    def test_serves_observation(self, tmp_path, monkeypatch):
        client = self._client(tmp_path, monkeypatch)
        fake, _ = _fake_run(stdout=json.dumps([_record("demo")]))
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        resp = client.get("/api/projects/status",
                          headers={"Authorization": "Bearer t"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["status"] == "healthy"
        assert body["data"]["projects"][0]["project"] == "demo"
        assert body["data"]["observed_at"] == "2026-09-12T12:48:38Z"

    def test_degrades_quietly_when_command_absent(self, tmp_path, monkeypatch):
        client = self._client(tmp_path, monkeypatch)
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: None)
        resp = client.get("/api/projects/status",
                          headers={"Authorization": "Bearer t"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["status"] == "unavailable"
        assert "agent-sync" in body["warnings"][0]

    def test_read_only_no_journal_side_effects(self, tmp_path, monkeypatch):
        client = self._client(tmp_path, monkeypatch)
        fake, _ = _fake_run(stdout=json.dumps([_record()]))
        monkeypatch.setattr("personal_world.providers.agent_sync._sync_binary",
                            lambda: "/usr/bin/agent-sync")
        monkeypatch.setattr(subprocess, "run", fake)
        before = (tmp_path / "journal.ndjson").exists()
        client.get("/api/projects/status", headers={"Authorization": "Bearer t"})
        after = (tmp_path / "journal.ndjson").exists()
        assert before == after  # a GET observed nothing into the journal
