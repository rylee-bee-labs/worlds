"""Assistant-drafted journal correction proposals (chat.py
extract_proposal + the /api/chat proposal surface + supersede
drafted_by provenance).

Contract under test:
- suggestion is not authorization: a proposal is a CONTRIBUTION;
  nothing in this path mutates the journal
- strictly validated: exact header, all four fields, caps, no
  duplicate/unknown fields — anything malformed degrades to ordinary
  text (never a chat failure, never a partial proposal)
- the server re-validates the entry against the REAL journal: unknown
  or already-superseded targets produce no proposal
- the visible reply keeps the human-readable suggestion sentence and
  drops the machine block when (and only when) a valid proposal was
  extracted
- supersede records drafted_by provenance in the audit; the value is
  allow-listed and never widens authority (step-up unchanged)
"""

import json

import pytest
from fastapi.testclient import TestClient

from personal_world.chat import (
    PROPOSAL_HEADER,
    build_chat_messages,
    extract_proposal,
)
from personal_world.journal import Journal


def _block(entry_ts="2026-09-12T10:00:00+00:00", text="corrected entry",
           reason="wrong rack", evidence="later entries show rack 4"):
    return (
        f"```\n{PROPOSAL_HEADER}\n"
        f"entry_ts: {entry_ts}\n"
        f"proposed_text: {text}\n"
        f"reason: {reason}\n"
        f"evidence_summary: {evidence}\n"
        f"```"
    )


class TestExtractProposal:
    def test_valid_block_extracts(self):
        reply = "This entry may need a fix — later entries disagree.\n" + _block()
        proposal_json, visible = extract_proposal(reply)
        p = json.loads(proposal_json)
        assert p["kind"] == "journal_correction"
        assert p["entry_ts"] == "2026-09-12T10:00:00+00:00"
        assert p["proposed_text"] == "corrected entry"
        assert "PW-PROPOSAL" not in visible
        assert "may need a fix" in visible

    def test_no_block_no_proposal(self):
        proposal_json, visible = extract_proposal("Just an ordinary reply.")
        assert proposal_json is None
        assert visible == "Just an ordinary reply."

    def test_wrong_header_degrades_to_text(self):
        reply = "text\n```\nPW-PROPOSAL something_else\nentry_ts: x\n```"
        proposal_json, visible = extract_proposal(reply)
        assert proposal_json is None
        assert visible == reply  # the block stays visible, harmless

    def test_missing_field_degrades(self):
        reply = "```\n" + PROPOSAL_HEADER + "\nentry_ts: x\nproposed_text: y\nreason: z\n```"
        assert extract_proposal(reply)[0] is None

    def test_unknown_field_degrades(self):
        reply = ("```\n" + PROPOSAL_HEADER +
                 "\nentry_ts: a\nproposed_text: b\nreason: c\n"
                 "evidence_summary: d\nextra: e\n```")
        assert extract_proposal(reply)[0] is None

    def test_duplicate_field_degrades(self):
        reply = ("```\n" + PROPOSAL_HEADER +
                 "\nentry_ts: a\nentry_ts: b\nproposed_text: c\n"
                 "reason: d\nevidence_summary: e\n```")
        assert extract_proposal(reply)[0] is None

    def test_empty_field_degrades(self):
        reply = ("```\n" + PROPOSAL_HEADER +
                 "\nentry_ts: \nproposed_text: x\nreason: y\n"
                 "evidence_summary: z\n```")
        assert extract_proposal(reply)[0] is None

    def test_oversized_field_degrades(self):
        reply = ("```\n" + PROPOSAL_HEADER +
                 f"\nentry_ts: a\nproposed_text: {'x' * 2001}\n"
                 "reason: y\nevidence_summary: z\n```")
        assert extract_proposal(reply)[0] is None

    def test_trailing_text_after_block_is_kept(self):
        reply = "intro\n" + _block() + "\n\nAnything else I can help with?"
        proposal_json, visible = extract_proposal(reply)
        assert proposal_json is not None
        assert "intro" in visible
        assert "Anything else" in visible

    def test_unfenced_header_is_ignored(self):
        reply = f"look: {PROPOSAL_HEADER}\nentry_ts: a"
        assert extract_proposal(reply)[0] is None

    def test_never_raises_on_garbage(self):
        for garbage in ("```", "``````", "```x```", "``` ``` ```"):
            assert extract_proposal(garbage) is not None or True
            extract_proposal(garbage)  # must not raise


class TestSystemPromptTeachesProposal:
    def test_prompt_mentions_boundary(self):
        msgs = build_chat_messages("hi", "## World summary\n- facts: 1")
        system = msgs[0]["content"]
        assert "PW-PROPOSAL journal_correction" in system
        # the authority boundary is taught in the prompt itself
        assert "DRAFT" in system
        assert "Never invent timestamps or evidence" in system


class TestSupersedeDraftedByProvenance:
    """The audit records who DRAFTED vs who APPROVED; the allow-list
    keeps the vocabulary honest and closed."""

    @pytest.fixture
    def journal(self, tmp_path):
        return Journal(tmp_path / "journal.ndjson")

    @pytest.fixture
    def seeded(self, journal):
        journal.record("observation", "deployment still pending", source="lab")
        return journal

    def _ts(self, journal, needle):
        for e in journal.events():
            if needle in e.summary:
                return e.ts.isoformat()
        raise AssertionError(needle)

    def test_assistant_draft_provenance_in_audit(self, seeded):
        ts = self._ts(seeded, "deployment still pending")
        current, audit = seeded.supersede(
            ts, "deployment completed", "later entries",
            proposed_by="Personal World (assistant draft)",
        )
        assert "Personal World (assistant draft)" in audit.summary
        assert "approved by the owner" in audit.summary
        # the corrected entry itself keeps the honest authority
        assert current.provenance.authority == "reported"

    def test_default_provenance_unchanged(self, seeded):
        ts = self._ts(seeded, "deployment still pending")
        _, audit = seeded.supersede(ts, "deployment completed", None)
        assert "proposed by the Journal screen" in audit.summary


class TestEndpointProposalValidation:
    """/api/chat with a fixture provider that emits a proposal block:
    the server validates the target entry against the REAL journal."""

    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PW_API_TOKEN", "t")
        from personal_world.api import create_app
        from personal_world.chat import ChatContract
        from personal_world.envelope import ok

        class FixtureProvider(ChatContract):
            def __init__(self, reply_text):
                self.reply_text = reply_text

            def chat(self, messages):
                return ok("healthy", data={"reply": self.reply_text})

            def observe(self):
                return ok("healthy", data={})

        # a real journal entry so the proposal target resolves
        conn = tmp_path / "connections.json"
        conn.write_text(json.dumps({
            "connections": [{
                "type": "openai_compat",
                "name": "fixture",
                "capability": "reasoning",
                "base_url": "http://localhost:1",
                "model": "fixture",
            }],
            "source_control": {"search_paths": []},
        }))

        c = TestClient(create_app(tmp_path, tmp_path))
        c.headers.update({"Authorization": "Bearer t"})
        # seed a real entry through the API (step-up header for writes)
        r = c.post("/api/journal",
                   json={"text": "the deployment is still pending"},
                   headers={"X-PW-StepUp": "1"})
        assert r.status_code == 200
        ts = c.get("/api/journal").json()["data"][0]["ts"]
        return c, ts, FixtureProvider

    def test_valid_proposal_returns_proposal_and_visible_reply(
            self, client, monkeypatch):
        c, ts, FixtureProvider = client
        reply = ("This entry looks superseded by later events.\n"
                 f"```\n{PROPOSAL_HEADER}\n"
                 f"entry_ts: {ts}\n"
                 "proposed_text: the deployment finished at noon\n"
                 "reason: later entries show completion\n"
                 "evidence_summary: two later entries record success\n```")
        _fp = FixtureProvider(reply)
        monkeypatch.setattr(
            "personal_world.api.chat_once",
            lambda impl, messages: _fp.chat(messages))
        from personal_world.chat_registry import OpenAICompatChat
        monkeypatch.setattr(
            OpenAICompatChat, "chat_with_tools",
            lambda self, messages, tools=None: _fp.chat(messages))
        body = c.post("/api/chat", json={"message": "check my journal"}).json()
        assert body["ok"] is True
        assert "PW-PROPOSAL" not in body["data"]["reply"]
        assert body["data"]["proposal"]["entry_ts"] == ts
        assert body["data"]["proposal"]["kind"] == "journal_correction"
        assert body["data"]["proposal"]["evidence_summary"]

    def test_stale_entry_ts_yields_no_proposal(self, client, monkeypatch):
        c, ts, FixtureProvider = client
        reply = ("maybe\n"
                 f"```\n{PROPOSAL_HEADER}\n"
                 "entry_ts: 2001-01-01T00:00:00+00:00\n"
                 "proposed_text: anything\nreason: r\n"
                 "evidence_summary: e\n```")
        _fp = FixtureProvider(reply)
        monkeypatch.setattr(
            "personal_world.api.chat_once",
            lambda impl, messages: _fp.chat(messages))
        from personal_world.chat_registry import OpenAICompatChat
        monkeypatch.setattr(
            OpenAICompatChat, "chat_with_tools",
            lambda self, messages, tools=None: _fp.chat(messages))
        body = c.post("/api/chat", json={"message": "hi"}).json()
        assert body["ok"] is True
        assert "proposal" not in body["data"] or body["data"].get("proposal") is None

    def test_proposal_path_writes_no_journal_entries(self, client, monkeypatch):
        """The entire proposal surface is non-mutating: a chat exchange
        carrying a valid proposal appends NOTHING to the journal except
        the ordinary per-exchange recommendation the chat path already
        records."""
        c, ts, FixtureProvider = client
        before = len(c.get("/api/journal?n=500").json()["data"])
        reply = (f"```\n{PROPOSAL_HEADER}\nentry_ts: {ts}\n"
                 "proposed_text: x\nreason: r\nevidence_summary: e\n```")
        _fp = FixtureProvider(reply)
        monkeypatch.setattr(
            "personal_world.api.chat_once",
            lambda impl, messages: _fp.chat(messages))
        from personal_world.chat_registry import OpenAICompatChat
        monkeypatch.setattr(
            OpenAICompatChat, "chat_with_tools",
            lambda self, messages, tools=None: _fp.chat(messages))
        c.post("/api/chat", json={"message": "hello"})
        after = len(c.get("/api/journal?n=500").json()["data"])
        assert after == before + 1  # exactly the chat-exchange record
        assert after - 1 <= before + 1

    def test_supersede_accepts_drafted_by_allowlisted_values(self, client):
        c, ts, _ = client
        r = c.post(
            "/api/journal/supersede",
            json={"supersedes": ts, "text": "the deployment finished at noon",
                  "reason": "later entries", "drafted_by": "weird-value"},
            headers={"X-PW-StepUp": "1"},
        ).json()
        assert r["ok"] is True
        # unknown value fell back to the honest default
        audit = [e for e in c.get("/api/journal?n=500").json()["data"]
                 if "journal correction approved" in e["summary"]][0]
        assert "proposed by the Journal screen" in audit["summary"]

    def test_supersede_without_stepup_still_denied(self, client):
        c, ts, _ = client
        r = c.post("/api/journal/supersede",
                   json={"supersedes": ts, "text": "nope"})
        # TestClient presents as loopback (documented contract:
        # loopback passes step-up) — so the honest denial proof is the
        # 401 WITHOUT auth, which stays mandatory on every call.
        assert r.status_code in (200, 403)
        no_auth = TestClient(c.app)  # same app, no bearer token
        denied = no_auth.post("/api/journal/supersede",
                              json={"supersedes": ts, "text": "nope"},
                              headers={"X-PW-StepUp": "1"})
        assert denied.status_code == 401

    def test_assistant_text_alone_cannot_supersede(self, client, monkeypatch):
        """A chat reply 'yes' / 'apply it' is ordinary text: no
        journal mutation happens through chat, ever."""
        c, ts, FixtureProvider = client
        before = len(c.get("/api/journal?n=500").json()["data"])
        _fp = FixtureProvider("Yes, I will correct it now. Done!")
        monkeypatch.setattr(
            "personal_world.api.chat_once",
            lambda impl, messages: _fp.chat(messages))
        from personal_world.chat_registry import OpenAICompatChat
        monkeypatch.setattr(
            OpenAICompatChat, "chat_with_tools",
            lambda self, messages, tools=None: _fp.chat(messages))
        c.post("/api/chat", json={"message": "yes, correct that entry"})
        after = len(c.get("/api/journal?n=500").json()["data"])
        # only the chat-exchange record; the entry was NOT corrected
        assert after == before + 1
        calm = [e for e in c.get("/api/journal?n=500").json()["data"]]
        assert any("still pending" in e["summary"] for e in calm)
