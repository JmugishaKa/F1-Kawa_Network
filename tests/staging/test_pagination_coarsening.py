"""Staging Scenario 1: coordinate precision leaking under pagination.

Spec (08-kawa-contracts-and-deltas.md): authenticate as exporter_partner and
walk every page of GET /api/plots/, asserting coarsened coordinates hold on
every page -- not just the first page or the detail view. Fails when
coarsening is applied by a code path that only covers page one.
"""

from decimal import Decimal
from urllib.parse import urlsplit

import pytest

from core.models import Farmer, Plot, Sector, WashingStation

PAGE_SIZE = 50  # config/pagination.py StandardPagination.page_size


def _next_path(body):
    next_url = body.get("next") if isinstance(body, dict) else None
    if not next_url:
        return None
    parsed = urlsplit(next_url)
    return parsed.path + (("?" + parsed.query) if parsed.query else "")


def _results(body):
    return body["results"] if isinstance(body, dict) and "results" in body else body


@pytest.mark.django_db
def test_coarsened_coordinates_hold_on_every_page(as_role):
    client = as_role("exporter_user")
    farmer = Farmer.objects.first()
    assert farmer is not None, "seed_rbac_fixtures did not create the seed farmer"

    kigoma = Sector.objects.get(name="Kigoma")
    mbazi = Sector.objects.get(name="Mbazi")
    nyaruguru = WashingStation.objects.get(name="Nyaruguru")
    kamonyi = WashingStation.objects.get(name="Kamonyi")

    for i in range(2 * PAGE_SIZE):
        sector = kigoma if i % 2 == 0 else mbazi
        station = nyaruguru if sector == kigoma else kamonyi
        Plot.objects.create(
            farmer=farmer,
            name=f"KWA-STAGING-{i:03d}",
            sector=sector,
            washing_station=station,
            latitude=Decimal("-2.000000") + Decimal(i) / Decimal(1000),
            longitude=Decimal("29.000000") + Decimal(i) / Decimal(1000),
            area_hectares=Decimal("1.00"),
        )

    seen_by_sector: dict[str, set[tuple[str, str]]] = {}
    pages_walked = 0
    path = "/api/plots/"

    while path:
        response = client.get(path)
        assert response.status_code == 200, response.content
        body = response.json()
        results = _results(body)
        assert results, f"page {pages_walked + 1} returned no results"

        for returned in results:
            raw = Plot.objects.get(name=returned["plot_code"])
            returned_point = (str(returned["latitude"]), str(returned["longitude"]))
            raw_point = (str(raw.latitude), str(raw.longitude))
            assert returned_point != raw_point, (
                f"plot {returned['plot_code']} on page {pages_walked + 1} returned its raw "
                "stored coordinate to exporter_partner instead of a coarsened one"
            )
            seen_by_sector.setdefault(raw.sector_id, set()).add(returned_point)

        pages_walked += 1
        path = _next_path(body)

    assert pages_walked >= 2, (
        "fixture data did not force pagination -- test setup bug, not a grading signal "
        f"(only walked {pages_walked} page(s) at PAGE_SIZE={PAGE_SIZE})"
    )

    for sector, points in seen_by_sector.items():
        assert len(points) == 1, (
            f"plots in sector {sector!r} returned {len(points)} distinct coarsened points "
            "across pages instead of one consistent point per sector"
        )

    all_points = {p for points in seen_by_sector.values() for p in points}
    assert len(all_points) == len(seen_by_sector), (
        "two different sectors coarsened to the same point -- coarsening must be per-sector"
    )
