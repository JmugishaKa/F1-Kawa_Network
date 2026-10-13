"""Staging Scenario 3: deliveries stranded on a failed risk check.

Spec (08-kawa-contracts-and-deltas.md): register a plot with the external
registry forced to fail, record a delivery against it, then assert the
delivery reaches a state that can be assigned to an export lot or is
explicitly rejected with a reason. Fails when the async flow has no failure
path, leaving the delivery indefinitely in its initial state.

Written against the contract, not against this reference implementation's
current fields: as of this session, core/tasks.check_deforestation_risk is a
documented stub that never calls an external registry and always marks the
risk check "unknown" -- there is no registry-failure path yet, and Delivery
has no status field at all. This test is expected to FAIL against the
current reference (see 08-kawa-contracts-and-deltas.md's recorded staging
verification) -- that is real open Summative-stage work, not a test bug.
"""

import pytest

from core.models import Farmer

STATUS_LIKE_FIELDS = {"status", "state", "export_status", "risk_check_status", "rejection_reason"}


@pytest.mark.django_db
def test_delivery_reaches_an_observable_state_after_failed_risk_check(as_role, settings):
    # Points any real registry integration at an address that will refuse
    # the connection, forcing a failure. Inert against implementations that
    # don't yet read this setting -- see module docstring.
    settings.REGISTRY_API_URL = "http://127.0.0.1:1/unreachable-registry"

    client = as_role("field_agent_user")
    farmer = Farmer.objects.first()
    assert farmer is not None, "seed_rbac_fixtures did not create the seed farmer"

    plot_response = client.post(
        "/api/plots/",
        {
            "farmer": farmer.id,
            "plot_code": "KWA-STAGING-RISK-01",
            "sector": "Nyaruguru",
            "washing_station": "Nyaruguru",
            "latitude": "-2.550000",
            "longitude": "29.720000",
            "area_hectares": "1.00",
        },
    )
    assert plot_response.status_code == 201, plot_response.content
    plot_id = plot_response.json()["id"]

    delivery_response = client.post(
        "/api/deliveries/",
        {
            "plot": plot_id,
            "washing_station": "Nyaruguru",
            "weight_kg": "10.00",
            "grade": "A",
            "delivered_on": "2026-09-01",
        },
    )
    assert delivery_response.status_code == 201, delivery_response.content
    delivery_data = delivery_response.json()

    present = STATUS_LIKE_FIELDS & set(delivery_data.keys())
    assert present, (
        "delivery response carries no field indicating whether it can be assigned to an "
        f"export lot or was explicitly rejected (checked for {sorted(STATUS_LIKE_FIELDS)}, "
        f"got fields {sorted(delivery_data.keys())}) -- a delivery against a plot whose risk "
        "check failed is stranded with no observable state"
    )
