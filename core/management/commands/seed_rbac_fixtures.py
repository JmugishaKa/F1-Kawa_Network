"""
This intends to create the exact fixtures that will fulfill F2 Contract's checks.

Every value here is copied from docs/autograding/F2_CONTRACT.md's fixture
table, not invented. If the contract ever changes, this SEED_DATA dict is
the only thing that would need some editing - the logic below just applies
whatever is in it.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Delivery, Farmer, Plot, Sector, UserProfile, WashingStation

User = get_user_model()

GRADER_PASSWORD = "GraderPass123!"

SEED_DATA = {
    "sectors": {"kigoma": "Kigoma", "mbazi": "Mbazi"},
    "stations": {"nyaruguru": ("Nyaruguru", "kigoma"), "kamonyi": ("Kamonyi", "mbazi")},
    "farmer": {
        "full_name": "Uwimana Béatrice",
        "phone": "+250780000099",
        "national_id": "1198770123456789",  # last four: 6789
        "member_number": "KWA-F-SEED-01",
        "cooperative": "",
    },
    "plots": [
        # plot_code, sector key, station key, lat, lng
        {"plot_code": "KWA-SEED-K1", "sector": "kigoma", "station": "nyaruguru", "lat": "-2.540000", "lng": "29.710000"},
        {"plot_code": "KWA-SEED-K2", "sector": "kigoma", "station": "nyaruguru", "lat": "-2.660000", "lng": "29.790000"},
        {"plot_code": "KWA-SEED-M1", "sector": "mbazi", "station": "kamonyi", "lat": "-2.510000", "lng": "29.520000"},
        {"plot_code": "KWA-SEED-M2", "sector": "mbazi", "station": "kamonyi", "lat": "-2.900000", "lng": "29.900000"},
    ],
    "deliveries": [
        {"plot_code": "KWA-SEED-K1", "weight_kg": "38.50", "grade": "A"},
        {"plot_code": "KWA-SEED-M1", "weight_kg": "25.00", "grade": "B"},
    ],
    # field_agent_user is scoped to this station key.
    "field_agent_station": "nyaruguru",
}


class Command(BaseCommand):
    help = "Create the fixed users/farmer/plots/deliveries the F2 autograder checks against (idempotent)."

    def handle(self, *args, **options):
        sectors = {key: self._sector(name) for key, name in SEED_DATA["sectors"].items()}
        stations = {
            key: self._station(name, sectors[sector_key])
            for key, (name, sector_key) in SEED_DATA["stations"].items()
        }

        farmer_data = SEED_DATA["farmer"]
        farmer, _ = Farmer.objects.get_or_create(
            phone=farmer_data["phone"],
            defaults={
                "full_name": farmer_data["full_name"],
                "national_id": farmer_data["national_id"],
                "member_number": farmer_data["member_number"],
                "cooperative": farmer_data["cooperative"],
            },
        )

        plots_by_code = {}
        for p in SEED_DATA["plots"]:
            plot, _ = Plot.objects.get_or_create(
                name=p["plot_code"],
                farmer=farmer,
                defaults={
                    "sector": sectors[p["sector"]],
                    "washing_station": stations[p["station"]],
                    "area_hectares": Decimal("0.5"),
                    "latitude": Decimal(p["lat"]),
                    "longitude": Decimal(p["lng"]),
                    "risk_status": Plot.RiskStatus.CLEAR,
                    "risk_checked_at": timezone.now(),
                },
            )
            plots_by_code[p["plot_code"]] = plot

        for d in SEED_DATA["deliveries"]:
            plot = plots_by_code[d["plot_code"]]
            Delivery.objects.get_or_create(
                plot=plot,
                weight_kg=Decimal(d["weight_kg"]),
                grade=d["grade"],
                defaults={
                    "washing_station": plot.washing_station,
                    "delivered_at": timezone.now(),
                    "plot_risk_status": plot.risk_status,
                },
            )

        self._create_user("field_agent_user", UserProfile.Role.FIELD_AGENT,
                           washing_station=stations[SEED_DATA["field_agent_station"]])
        self._create_user("exporter_user", UserProfile.Role.EXPORTER_PARTNER)
        self._create_user("auditor_user", UserProfile.Role.COMPLIANCE_AUDITOR)

        self.stdout.write(self.style.SUCCESS(
            "Seeded RBAC fixtures: 3 users, 1 farmer, "
            f"{len(SEED_DATA['plots'])} plots, {len(SEED_DATA['deliveries'])} deliveries."
        ))

    def _sector(self, name):
        sector, _ = Sector.objects.get_or_create(name=name)
        return sector

    def _station(self, name, sector):
        station, _ = WashingStation.objects.get_or_create(name=name, defaults={"sector": sector})
        return station

    def _create_user(self, username, role, washing_station=None):
        user, created = User.objects.get_or_create(username=username)
        user.set_password(GRADER_PASSWORD)
        user.save()
        UserProfile.objects.update_or_create(user=user, defaults={"role": role, "washing_station": washing_station})