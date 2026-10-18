"""Staging Scenario 2: stale price schedule after a mid-season update.

Adapted setup: this project's price schedule is a real PriceSchedule table
row, not an in-code dict (see ADR.md Task 4 - caching was deliberately NOT
chosen, specifically to avoid this class of staleness bug). Assertions are
unchanged from the original scenario; only the mechanism for "update the
underlying schedule" changed to match this project's actual persistence.
"""
from decimal import Decimal

import pytest

from core.models import PriceSchedule


@pytest.mark.django_db
def test_price_schedule_reflects_update_within_documented_window(as_role):
    client = as_role("exporter_user")

    row, _ = PriceSchedule.objects.get_or_create(
        season="2026", grade="A", defaults={"price_per_kg": Decimal("450.00")}
    )

    before = client.get("/api/price-schedule/")
    assert before.status_code == 200, before.content
    prices = {p["grade"]: p["price_per_kg"] for p in before.json()["prices"]}
    original_price_a = Decimal(prices["A"])

    updated_price_a = original_price_a + 37
    row.price_per_kg = updated_price_a
    row.save()

    after = client.get("/api/price-schedule/")
    assert after.status_code == 200, after.content
    served = {p["grade"]: p["price_per_kg"] for p in after.json()["prices"]}
    served_price_a = Decimal(served["A"])

    assert served_price_a == updated_price_a, (
        "price-schedule endpoint served a stale value after a mid-season update -- "
        f"expected {updated_price_a}, got {served_price_a}"
    )