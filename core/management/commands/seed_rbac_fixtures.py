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
    "sector_kigoma": {"name": "Kigoma", "district": "Kigoma"},
    "sector_mbazi": {"name": "Mbazi", "district": "Mbazi"},
    "station_nyaruguru": {"name": "Nyaruguru"},
    "station_kamonyi": {"name": "Kamonyi"},
    "farmer": {
        "full_name": "Uwimana Béatrice",
        "phone": "0788100001",
        "national_id": "1198770123456789",
        "member_number": "KWA-F-SEED-01",
    },
    "plots": [
        {"plot_code": "KWA-SEED-K1", "sector": "sector_kigoma", "station": "station_nyaruguru", "lat": "-2.540000", "lng": "29.710000"},
        {"plot_code": "KWA-SEED-K2", "sector": "sector_kigoma", "station": "station_nyaruguru", "lat": "-2.660000", "lng": "29.790000"},
        {"plot_code": "KWA-SEED-M1", "sector": "sector_mbazi", "station": "station_kamonyi", "lat": "-2.510000", "lng": "29.520000"},
        {"plot_code": "KWA-SEED-M2", "sector": "sector_mbazi", "station": "station_kamonyi", "lat": "-2.900000", "lng": "29.900000"},
    ],
    "deliveries": [
        {"plot_code": "KWA-SEED-K1", "weight_kg": "40.00", "grade": "A"},
        {"plot_code": "KWA-SEED-M1", "weight_kg": "25.50", "grade": "B"},
    ],
}


class Command(BaseCommand):
    help = "Create the fixed users/farmer/plots/deliveries the F2 autograder checks against (idempotent)."

    def handle(self, *args, **options):
        sector_kigoma = self._get_or_create_sector("sector_kigoma")
        sector_mbazi = self._get_or_create_sector("sector_mbazi")
        station_nyaruguru = self._get_or_create_station("station_nyaruguru", sector_kigoma)
        station_kamonyi = self._get_or_create_station("station_kamonyi", sector_mbazi)

        farmer_data = SEED_DATA["farmer"]
        farmer, _ = Farmer.objects.get_or_create(
            phone=farmer_data["phone"],
            defaults={
                "full_name": farmer_data["full_name"],
                "national_id": farmer_data["national_id"],
                "member_number": farmer_data["member_number"],
                "cooperative": "Huye",
            },
        )
        if farmer.member_number != farmer_data["member_number"]:
            farmer.member_number = farmer_data["member_number"]
            farmer.cooperative = "Huye"
            farmer.save(update_fields=["member_number", "cooperative"])

        sectors = {"sector_kigoma": sector_kigoma, "sector_mbazi": sector_mbazi}
        stations = {"station_nyaruguru": station_nyaruguru, "station_kamonyi": station_kamonyi}
        plots_by_code = {}
        for p in SEED_DATA["plots"]:
            plot, _ = Plot.objects.get_or_create(
                farmer=farmer,
                name=p["plot_code"],
                defaults={
                    "plot_code": p["plot_code"],
                    "sector": sectors[p["sector"]],
                    "washing_station": stations[p["station"]],
                    "area_hectares": Decimal("0.5"),
                    "latitude": Decimal(p["lat"]),
                    "longitude": Decimal(p["lng"]),
                    "risk_status": Plot.RiskStatus.CLEAR,
                    "risk_checked_at": timezone.now(),
                },
            )
            if plot.plot_code != p["plot_code"]:
                plot.plot_code = p["plot_code"]
            plot.sector = sectors[p["sector"]]
            plot.washing_station = stations[p["station"]]
            plot.latitude = Decimal(p["lat"])
            plot.longitude = Decimal(p["lng"])
            plot.risk_status = Plot.RiskStatus.CLEAR
            plot.risk_checked_at = timezone.now()
            plot.save(update_fields=["plot_code", "sector", "washing_station", "latitude", "longitude", "risk_status", "risk_checked_at"])
            plots_by_code[p["plot_code"]] = plot

        for d in SEED_DATA["deliveries"]:
            plot = plots_by_code[d["plot_code"]]
            Delivery.objects.get_or_create(
                plot=plot,
                weight_kg=Decimal(d["weight_kg"]),
                grade=d["grade"],
                defaults={
                    "washing_station": plot.washing_station,
                    "delivered_on": timezone.now().date(),
                    "delivered_at": timezone.now(),
                    "plot_risk_status": plot.risk_status,
                },
            )

        self._create_user("field_agent_user", UserProfile.Role.FIELD_AGENT, washing_station=station_nyaruguru)
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