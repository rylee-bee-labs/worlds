"""C1.3 query templates: a closed set, rendered in UTC, query values only."""
import datetime as dt

import pytest

from personal_world.worlds.models import Request
from personal_world.worlds.templates import check_query_value, render_query, render_value

NOW = dt.datetime(2026, 10, 1, 23, 30, 5, tzinfo=dt.timezone.utc)


def test_renders_the_closed_set_in_utc():
    assert render_value("{today}", NOW) == "2026-10-01"
    assert render_value("{today+7d}", NOW) == "2026-10-08"
    assert render_value("{today-30d}", NOW) == "2026-09-01"
    assert render_value("{today+0d}", NOW) == "2026-10-01"
    assert render_value("{now}", NOW) == "2026-10-01T23:30:05Z"
    assert render_value("from {today} to {today+1d}", NOW) == "from 2026-10-01 to 2026-10-02"
    assert render_value("plain", NOW) == "plain"


def test_a_late_evening_in_another_zone_is_still_the_utc_day():
    east = dt.datetime(2026, 10, 2, 5, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))  # 21:00 UTC on the 1st
    assert render_value("{today}", east) == "2026-10-01"


def test_render_query_renders_every_value():
    assert render_query({"start": "{today}", "end": "{today+7d}", "k": "v"}, NOW) == {"start": "2026-10-01", "end": "2026-10-08", "k": "v"}


@pytest.mark.parametrize("bad", ["{tomorrow}", "{today+367d}", "{today+d}", "{today*2}", "{ today }", "{{today}}", "{today", "today}",
                                 "{today+7days}", "{env:SECRET}", "{}", "{now+1d}", "{TODAY}"])
def test_unknown_or_malformed_templates_are_refused_at_save_time(bad):
    with pytest.raises(ValueError):
        check_query_value(bad)


def test_366_days_is_the_limit():
    assert check_query_value("{today+366d}") == "{today+366d}"
    assert check_query_value("{today-366d}") == "{today-366d}"


def _req(**kw):
    return Request(id="p.r", provider="p", path="/x", **kw)


def test_the_request_model_validates_query_values_only():
    _req(query={"start": "{today}"})
    with pytest.raises(ValueError):
        _req(query={"start": "{yesterday}"})
    # never templated in the path
    with pytest.raises(ValueError):
        Request(id="p.r", provider="p", path="/x/{today}")
