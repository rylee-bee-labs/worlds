"""Journal gate: a narrow, closed-enum door onto the private Journal.

Design (owner decision, 2026-09-27): the existing hard wall stays
EXACTLY as strict as it is today — ``_require_person`` in ``api.py``
still flatly refuses every agent principal on ``/api/journal*`` and
``/api/recall``, unconditionally, regardless of scope. This module is
an ADDITIONAL narrow door, reached only through the ``journal_gate``
confining scope (see ``api.CONFINING_SCOPES``): an agent holding that
scope may ask a closed-enum question ("does the journal relate to X
lately?") and gets back a closed-enum answer. It never gets retrieval
results, entry text, or free-form output.

The retrieval step and the model step are both deliberately
replaceable and untrusted:

- ``retrieve`` is a relevance filter, not the security boundary — it
  decides what the model stand-in gets to look at.
- ``mock_model`` stands in for a real model (a later step wires one
  in). Nothing about the security property depends on this function
  being trustworthy.
- ``_validate`` is the actual boundary. It structurally cannot pass
  through anything but the closed Answer schema, and separately
  rejects any answer that shares a long run of words with a retrieved
  entry's real text — this catches a model (mock or real) that tries
  to leak verbatim content through an enum-shaped field. On any
  failure anywhere, the gate collapses to ``unsure`` and count "0" —
  never an exception, never partial output.
"""

from __future__ import annotations

import json as _json
import urllib.error as _urlerr
import urllib.request as _urlreq
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from .classification import Classification
from .journal import Journal
from .model import JournalEvent, JournalKind
from .url_safety import http_urlopen


class Ask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ask: Literal["relates_to", "written_lately"]
    topic: str = Field(max_length=80)
    window_days: Literal[7, 30, 90]


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: Literal["yes", "no", "unsure"]
    strength: Literal["weak", "strong"] | None = None
    when: Literal["this_week", "this_month", "older"] | None = None
    count: Literal["0", "1-2", "3-9", "10+"]


UNSURE = Answer(answer="unsure", strength=None, when=None, count="0")


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)


#: Kinds excluded from the gate's retrieval corpus entirely. SECURITY
#: holds the gate's own audit trail (see ``_record_audit`` in api.py) —
#: without this exclusion, asking about a topic would also match past
#: audit entries that happen to mention that topic, a feedback loop
#: that has nothing to do with the person's actual journal content.
_NON_CONTENT_KINDS = frozenset({JournalKind.SECURITY.value})


def _window_events(journal: Journal, window_days: int) -> list[JournalEvent]:
    """Current (non-superseded), non-secret, content-kind entries
    inside the window.

    Secret-classified rows are excluded defensively even though nothing
    in this codebase currently classifies journal entries as SECRET —
    a gate over private memory should not assume that stays true.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    total = sum(1 for _ in journal.events())
    out = []
    for e in journal.current_events(n=max(total, 1), exclude_kinds=_NON_CONTENT_KINDS):
        if e.classification == Classification.SECRET:
            continue
        if _aware(e.ts) >= cutoff:
            out.append(e)
    return out


_STOPWORDS = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "is", "was"}


def retrieve(topic: str, journal: Journal, window_days: int) -> list[JournalEvent]:
    """Deliberately dumb word-overlap retrieval — a relevance filter
    for the model stand-in, never the security boundary."""
    topic_words = {w.lower() for w in topic.split() if len(w) > 2} - _STOPWORDS
    if not topic_words:
        return []
    hits = []
    for e in _window_events(journal, window_days):
        text_words = {w.lower().strip(".,!?;:\"'") for w in e.summary.split()}
        if topic_words & text_words:
            hits.append(e)
    return hits


def mock_model(ask: Ask, hits: list[JournalEvent]) -> dict[str, Any]:
    """Deterministic stand-in for a real model. No I/O, no network.

    Turns retrieval hits into a closed-enum-shaped dict using only
    counts and dates — it never reads entry text. Used when no real
    model endpoint is configured (dev/test/degraded mode). The
    validator downstream enforces the schema regardless of what any
    model (mock or real) returns.
    """
    n = len(hits)
    if n == 0:
        return {"answer": "no", "strength": None, "when": None, "count": "0"}
    count = "1-2" if n <= 2 else "3-9" if n <= 9 else "10+"
    newest = max(hits, key=lambda e: e.ts)
    age_days = (datetime.now(timezone.utc) - _aware(newest.ts)).days
    when = "this_week" if age_days <= 7 else "this_month" if age_days <= 30 else "older"
    strength = "strong" if n >= 3 else "weak"
    return {"answer": "yes", "strength": strength, "when": when, "count": count}


_MODEL_SYSTEM_PROMPT = """You are a narrow classifier for a private journal gate.

You are given a topic-ask and a small set of journal-entry snippets that
already matched a keyword search. Decide, from those snippets ONLY, how
to answer the ask.

Respond with ONLY a single JSON object, no other text, no markdown
fences, matching exactly this shape:
{"answer": "yes"|"no"|"unsure", "strength": "weak"|"strong"|null, "when": "this_week"|"this_month"|"older"|null, "count": "0"|"1-2"|"3-9"|"10+"}

Rules:
- NEVER quote, repeat, or paraphrase any entry's wording in your output.
- NEVER include any field or text outside the exact JSON shape above.
- If you are not confident, answer "unsure"."""


def real_model(
    ask: Ask,
    hits: list[JournalEvent],
    *,
    base_url: str,
    model: str,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Call a local, OpenAI-chat-completions-compatible model.

    Runs on the estate's existing on-LAN resident model server — the
    same trust boundary mem0-mcp already sends journal-adjacent
    content to for memory extraction; this is not a new place private
    content goes. Nothing about the security property depends on this
    function being trustworthy: ``_validate`` enforces the closed
    schema and the leak check against whatever this returns, exactly
    as it does for ``mock_model``. Any network failure, timeout, or
    unparseable response returns the closed "unsure" shape — never an
    exception, never a partial or free-text result.
    """
    if not hits:
        return {"answer": "no", "strength": None, "when": None, "count": "0"}
    snippets = "\n".join(f"- {e.summary}" for e in hits[:20])
    user_prompt = (
        f'ask="{ask.ask}" topic="{ask.topic}" window_days={ask.window_days}\n'
        f"matched snippets:\n{snippets}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _MODEL_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": 120,
    }
    req = _urlreq.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=_json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
        method="POST",
    )
    try:
        with http_urlopen(req, timeout=timeout) as resp:
            body = _json.loads(resp.read().decode("utf-8"))
        text = body["choices"][0]["message"]["content"]
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end < start:
            return UNSURE.model_dump()
        return _json.loads(text[start : end + 1])
    except (_urlerr.URLError, TimeoutError, OSError, KeyError, IndexError, ValueError):
        return UNSURE.model_dump()


def _shares_long_run(candidate: str, hits: list[JournalEvent], run_len: int = 5) -> bool:
    """True if ``candidate`` shares ``run_len``+ consecutive words with
    any retrieved entry's real text. The leak check, independent of
    what a model claims its output means."""
    cand_words = candidate.lower().split()
    if len(cand_words) < run_len:
        return False
    windows = {
        tuple(cand_words[i : i + run_len])
        for i in range(len(cand_words) - run_len + 1)
    }
    for e in hits:
        entry_words = e.summary.lower().split()
        for i in range(len(entry_words) - run_len + 1):
            if tuple(entry_words[i : i + run_len]) in windows:
                return True
    return False


def _validate(raw: dict[str, Any], hits: list[JournalEvent]) -> Answer:
    try:
        answer = Answer.model_validate(raw)
    except Exception:
        return UNSURE
    for value in (answer.answer, answer.strength, answer.when, answer.count):
        if isinstance(value, str) and _shares_long_run(value, hits):
            return UNSURE
    return answer


class Denylist(BaseModel):
    """The owner's "never answer about..." list. Checked before
    retrieval or any model call — a blocked ask never reaches the
    model at all, real or mock."""

    model_config = ConfigDict(extra="forbid")

    blocked_agents: list[str] = Field(default_factory=list)
    blocked_topics: list[str] = Field(default_factory=list)


def load_denylist(path) -> Denylist:
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        return Denylist()
    try:
        return Denylist.model_validate(_json.loads(p.read_text()))
    except Exception:
        return Denylist()


def save_denylist(path, denylist: Denylist) -> None:
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_json.dumps(denylist.model_dump(), indent=2))


def _denylisted(ask: Ask, caller_id: str, denylist: Denylist) -> bool:
    if caller_id in denylist.blocked_agents:
        return True
    topic_lower = ask.topic.lower()
    return any(t.lower() in topic_lower for t in denylist.blocked_topics if t)


def gate(
    ask_raw: dict[str, Any],
    journal: Journal,
    *,
    model_fn: Callable[[Ask, list[JournalEvent]], dict[str, Any]] = mock_model,
    denylist: Denylist | None = None,
    caller_id: str = "",
) -> dict[str, Any]:
    """The whole gate in one call. Any failure anywhere — a malformed
    Ask, a denylisted caller/topic, a malformed model answer, or a
    detected leak — collapses to ``unsure``, never an exception and
    never partial/free-text output.
    """
    try:
        ask = Ask.model_validate(ask_raw)
    except Exception:
        return UNSURE.model_dump()
    if denylist is not None and _denylisted(ask, caller_id, denylist):
        return UNSURE.model_dump()
    hits = retrieve(ask.topic, journal, ask.window_days)
    raw = model_fn(ask, hits)
    return _validate(raw, hits).model_dump()
