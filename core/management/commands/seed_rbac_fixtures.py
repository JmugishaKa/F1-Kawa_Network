"""
Creates the fixed users/farmer/plots/deliveries the F2 autograder checks against.

*** PLACEHOLDER VALUES ***
The assignment says: "Copy the F2 Contract's table exactly, including the
plot_code values, or the grading checks cannot find your fixtures." We do not
have that contract yet (GitHub Classroom was down when this was written) - so
every value below is a reasonable guess, clearly isolated in SEED_DATA at the
top of this file. Once you have docs/autograding/F2_CONTRACT.md, this is the
only place that needs editing: swap the values in SEED_DATA to match the
contract's table exactly, nothing else in this file should need to change.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Delivery, Farmer, Plot, Sector, UserProfile, WashingStation

User = get_user_model()

GRADER_PASSWORD = "GraderPass123!"

SEED_DATA = {
    "sector": {"name": "Nyaruguru", "district": "Nyaruguru"},
    "other_sector": {"name": "Huye", "district": "Huye"},  # second sector, so coarsening is actually testable
    "station": {"name": "Nyaruguru Washing Station"},
    "other_station": {"name": "Huye Washing Station"},
    "farmer": {"full_name": "Jean Claude", "phone": "0788100001", "national_id": "1198880012345678"},
    "plots": [
        # plot_code, sector key, station key, lat, lng
        {"plot_code": "PLOT-001", "sector": "sector", "station": "station", "lat": "-2.700000", "lng": "29.500000"},
        {"plot_code": "PLOT-002", "sector": "sector", "station": "station", "lat": "-2.701000", "lng": "29.501000"},
        {"plot_code": "PLOT-003", "sector": "other_sector", "station": "other_station", "lat": "-2.600000", "lng": "29.750000"},
        {"plot_code": "PLOT-004", "sector": "other_sector", "station": "other_station", "lat": "-2.601000", "lng": "29.751000"},
    ],
    "deliveries": [
        # plot_code, weight_kg, grade
        {"plot_code": "PLOT-001", "weight_kg": "40.00", "grade": "A"},
        {"plot_code": "PLOT-003", "weight_kg": "25.50", "grade": "B"},
    ],
}


class Command(BaseCommand):
    help = "Create the fixed users/farmer/plots/deliveries the F2 autograder checks against (idempotent)."

    def handle(self, *args, **options):
        sector = self._get_or_create_sector("sector")
        other_sector = self._get_or_create_sector("other_sector")
        station = self._get_or_create_station("station", sector)
        other_station = self._get_or_create_station("other_station", other_sector)

        farmer_data = SEED_DATA["farmer"]
        farmer, _ = Farmer.objects.get_or_create(
            phone=farmer_data["phone"],
            defaults={"full_name": farmer_data["full_name"], "national_id": farmer_data["national_id"]},
        )

        sectors = {"sector": sector, "other_sector": other_sector}
        stations = {"station": station, "other_station": other_station}
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

        self._create_user("field_agent_user", UserProfile.Role.FIELD_AGENT, washing_station=station)
        self._create_user("exporter_user", UserProfile.Role.EXPORTER_PARTNER)
        self._create_user("auditor_user", UserProfile.Role.COMPLIANCE_AUDITOR)

        self.stdout.write(self.style.SUCCESS(
            "Seeded RBAC fixtures: 3 users, 1 farmer, "
            f"{len(SEED_DATA['plots'])} plots, {len(SEED_DATA['deliveries'])} deliveries."
        ))

    def _get_or_create_sector(self, key):
        data = SEED_DATA[key]
        sector, _ = Sector.objects.get_or_create(name=data["name"], defaults={"district": data["district"]})
        return sector

    def _get_or_create_station(self, key, sector):
        data = SEED_DATA[key]
        station, _ = WashingStation.objects.get_or_create(name=data["name"], defaults={"sector": sector})
        return station

    def _create_user(self, username, role, washing_station=None):
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.set_password(GRADER_PASSWORD)
            user.save()
        else:
            # Idempotent: a second run must not error, and should still leave
            # the password/role correct even if something else changed them.
            user.set_password(GRADER_PASSWORD)
            user.save(update_fields=["password"])
        UserProfile.objects.update_or_create(
            user=user, defaults={"role": role, "washing_station": washing_station}
        )