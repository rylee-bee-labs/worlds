"""Acceptance tests for personal_world.worlds.mapping: JSONPath subset + formats. No code execution."""
import pytest

from personal_world.worlds.mapping import MappingError, extract, format_value

DOC = {"a": {"b": 3, "c": [10, 20, 30]}, "items": [{"n": "x", "v": 1}, {"n": "y", "v": 2}], "z": None}


def test_extract_paths():
    assert extract(DOC, "$.a.b") == [3]
    assert extract(DOC, "$.a.c[1]") == [20]
    assert extract(DOC, "$.a.c[*]") == [10, 20, 30]
    assert extract(DOC, "$.items[*].n") == ["x", "y"]
    assert extract(DOC, "$.items[0].v") == [1]
    assert extract(DOC, "$.z") == [None]


def test_missing_is_empty_not_zero():
    assert extract(DOC, "$.nope") == []
    assert extract(DOC, "$.a.c[9]") == []
    assert extract(DOC, "$.a.b.c") == []


@pytest.mark.parametrize("bad", ["a.b", "$..a", "$.a[?(@.b>1)]", "$.a[1:2]", "$.a['b']", "$.a;drop", "$.a.__class__",
                                 "$.a[*][*]x", "", "$.", "$.a b", "$.a.(1+1)", "$[0]x", "$.a.c[-2]", "$.a.c[-0]"])
def test_unsupported_syntax_rejected(bad):
    with pytest.raises(MappingError):
        extract(DOC, bad)


def test_root_and_index_on_root_list():
    assert extract([1, 2], "$[1]") == [2]
    assert extract([1, 2], "$[*]") == [1, 2]
    assert extract(DOC, "$") == [DOC]


def test_does_not_execute_or_eval(monkeypatch):
    import builtins
    monkeypatch.setattr(builtins, "eval", lambda *a, **k: (_ for _ in ()).throw(AssertionError("eval used")))
    monkeypatch.setattr(builtins, "exec", lambda *a, **k: (_ for _ in ()).throw(AssertionError("exec used")))
    extract(DOC, "$.a.b")


def test_format_number_percent_bytes_duration_text():
    assert format_value(1234.5, "number", None) == "1,234.5"
    assert format_value(1234, "number", "files") == "1,234 files"
    assert format_value(0.256, "percent", None) == "25.6%"
    assert format_value(1536, "bytes", None) == "1.5 KiB"
    assert format_value(0, "bytes", None) == "0 B"
    assert format_value(3725, "duration", None) == "1h 2m"
    assert format_value(45, "duration", None) == "45s"
    assert format_value("hi", "text", None) == "hi"
    assert format_value(True, "text", None) == "yes"


def test_missing_and_bad_values_never_become_zero():
    assert format_value(None, "number", None) == "unknown"
    assert format_value("abc", "number", None) == "unknown"
    assert format_value(None, "text", None) == "unknown"
    assert format_value(True, "number", None) == "unknown"  # bool is not a number


def test_relative_time_is_deterministic_with_now():
    import datetime as dt
    now = dt.datetime(2026, 10, 1, 12, 0, tzinfo=dt.timezone.utc)
    assert format_value("2026-10-01T11:00:00Z", "relative_time", None, now=now) == "1 hour ago"
    assert format_value("2026-10-01T11:59:30Z", "relative_time", None, now=now) == "just now"
    assert format_value("2026-09-29T12:00:00Z", "relative_time", None, now=now) == "2 days ago"
    assert format_value("not a date", "relative_time", None, now=now) == "unknown"


def test_last_element_index():
    assert extract(DOC, "$.a.c[-1]") == [30]
    assert extract(DOC, "$.items[-1].n") == ["y"]
    assert extract({"l": []}, "$.l[-1]") == []          # an empty list has no last element
    assert extract(DOC, "$.a.b[-1]") == []              # not a list


def test_count_of_a_list():
    from personal_world.worlds.mapping import count_of, resolve

    def n(doc, path):
        return count_of(resolve(doc, path), path)

    assert n({"r": [1, 2, 3]}, "$.r") == 3
    assert n({"r": [1, 2, 3]}, "$.r[*]") == 3
    assert n({"r": []}, "$.r") == 0                      # an existing empty list is a real 0
    assert n({"r": []}, "$.r[*]") == 0
    assert n({"r": 5}, "$.r") is None                    # not a list: unknown, never 0
    assert n({"r": {"a": 1}}, "$.r") is None
    assert n({"x": 1}, "$.r") is None                    # missing: unknown, never 0
    assert n({"r": [[1, 2], [3]]}, "$.r[*]") == 2
