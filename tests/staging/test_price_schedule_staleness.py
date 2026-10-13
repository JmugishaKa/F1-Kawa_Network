"""Staging Scenario 2: stale price schedule after a mid-season update.

Spec (08-kawa-contracts-and-deltas.md): read GET /api/price-schedule/,
update the underlying schedule, re-read, and assert the new value is served
within the invalidation window documented in the student's own README.md.
Fails when a cache was added in F1 with no invalidation path -- F1 only
requires that caching exist, not that it invalidates correctly.

This project's README documents "a static in-code dict, not cached... no
cache to invalidate" -- so the invalidation window is immediate, and the
test asserts the very next read reflects the update.
"""

import pytest

from core import views as core_views


@pytest.mark.django_db
def test_price_schedule_reflects_update_within_documented_window(as_role):
    client = as_role("exporter_user")

    before = client.get("/api/price-schedule/")
    assert before.status_code == 200, before.content
    original_price_a = before.json()["prices_per_kg"]["A"]

    updated_price_a = original_price_a + 37
    core_views.PRICE_SCHEDULE["prices_per_kg"]["A"] = updated_price_a
    try:
        after = client.get("/api/price-schedule/")
        assert after.status_code == 200, after.content
        served_price_a = after.json()["prices_per_kg"]["A"]

        assert served_price_a == updated_price_a, (
            "price-schedule endpoint served a stale value after a mid-season update -- the "
            f"README's documented invalidation window (immediate, no cache) was not honoured: "
            f"expected {updated_price_a}, got {served_price_a}"
        )
    finally:
        core_views.PRICE_SCHEDULE["prices_per_kg"]["A"] = original_price_a
