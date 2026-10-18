from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from core.models import AccessLogEntry, Delivery, Farmer, Plot, Sector, UserProfile, WashingStation

User = get_user_model()


class Base(APITestCase):
    def setUp(self):
        self.sector_a = Sector.objects.create(name="SectorA")
        self.sector_b = Sector.objects.create(name="SectorB")
        self.station_a = WashingStation.objects.create(name="StationA", sector=self.sector_a)
        self.station_b = WashingStation.objects.create(name="StationB", sector=self.sector_b)
        self.farmer = Farmer.objects.create(full_name="Jean Claude", phone="0788100001", national_id="1198880012345678")

        self.plot_a1 = self._plot("A1", self.sector_a, self.station_a, "-2.700000", "29.500000")
        self.plot_a2 = self._plot("A2", self.sector_a, self.station_a, "-2.701000", "29.501000")
        self.plot_b1 = self._plot("B1", self.sector_b, self.station_b, "-2.600000", "29.750000")

        self.delivery_a = Delivery.objects.create(
            plot=self.plot_a1, washing_station=self.station_a, weight_kg=Decimal("40.00"),
            grade="A", delivered_at="2026-01-01T10:00:00Z", plot_risk_status=Plot.RiskStatus.CLEAR,
        )
        self.delivery_b = Delivery.objects.create(
            plot=self.plot_b1, washing_station=self.station_b, weight_kg=Decimal("25.50"),
            grade="B", delivered_at="2026-01-01T11:00:00Z", plot_risk_status=Plot.RiskStatus.CLEAR,
        )

        self.agent = self._user("agent1", UserProfile.Role.FIELD_AGENT, self.station_a)
        self.exporter = self._user("exporter1", UserProfile.Role.EXPORTER_PARTNER)
        self.auditor = self._user("auditor1", UserProfile.Role.COMPLIANCE_AUDITOR)

    def _plot(self, name, sector, station, lat, lng):
        return Plot.objects.create(
            farmer=self.farmer, name=name, sector=sector, washing_station=station,
            area_hectares=Decimal("0.5"), latitude=Decimal(lat), longitude=Decimal(lng),
            risk_status=Plot.RiskStatus.CLEAR,
        )

    def _user(self, username, role, station=None):
        user = User.objects.create_user(username=username, password="pass12345")
        UserProfile.objects.create(user=user, role=role, washing_station=station)
        return user

    def login_as(self, user):
        self.client.force_login(user)


class UnauthenticatedTests(Base):
    def test_deliveries_require_auth(self):
        self.assertIn(self.client.get("/api/deliveries/").status_code, (401, 403))

    def test_plots_require_auth(self):
        self.assertIn(self.client.get("/api/plots/").status_code, (401, 403))

    def test_farmers_require_auth(self):
        self.assertIn(self.client.get("/api/farmers/").status_code, (401, 403))


class FieldAgentTests(Base):
    def setUp(self):
        super().setUp()
        self.login_as(self.agent)

    def test_sees_only_own_station_deliveries(self):
        r = self.client.get("/api/deliveries/")
        ids = {d["id"] for d in r.json()["results"]}
        self.assertEqual(ids, {self.delivery_a.pk})

    def test_sees_only_own_station_plots_with_full_coordinates_and_plot_code(self):
        r = self.client.get("/api/plots/")
        body = r.json()["results"]
        ids = {p["id"] for p in body}
        self.assertEqual(ids, {self.plot_a1.pk, self.plot_a2.pk})
        a1 = next(p for p in body if p["id"] == self.plot_a1.pk)
        self.assertEqual(str(a1["latitude"]), "-2.700000")
        self.assertEqual(a1["plot_code"], "A1")

    def test_farmer_national_id_is_masked_to_last_four(self):
        r = self.client.get(f"/api/farmers/{self.farmer.pk}/")
        self.assertEqual(r.json()["national_id"], "************5678")

    def test_cannot_read_audit_log(self):
        r = self.client.get("/api/access-log/")
        self.assertEqual(r.json()["results"], [])


class ExporterPartnerTests(Base):
    def setUp(self):
        super().setUp()
        self.login_as(self.exporter)

    def test_sees_all_stations_deliveries(self):
        r = self.client.get("/api/deliveries/")
        ids = {d["id"] for d in r.json()["results"]}
        self.assertEqual(ids, {self.delivery_a.pk, self.delivery_b.pk})

    def test_sees_all_plots_with_coarsened_coordinates(self):
        r = self.client.get("/api/plots/")
        body = {p["id"]: p for p in r.json()["results"]}
        self.assertEqual(set(body), {self.plot_a1.pk, self.plot_a2.pk, self.plot_b1.pk})
        self.assertEqual(body[self.plot_a1.pk]["latitude"], body[self.plot_a2.pk]["latitude"])
        self.assertEqual(body[self.plot_a1.pk]["longitude"], body[self.plot_a2.pk]["longitude"])
        self.assertNotEqual(body[self.plot_a1.pk]["latitude"], body[self.plot_b1.pk]["latitude"])
        self.assertNotEqual(str(body[self.plot_a1.pk]["latitude"]), "-2.700000")

    def test_national_id_field_is_absent_not_null(self):
        r = self.client.get(f"/api/farmers/{self.farmer.pk}/")
        self.assertNotIn("national_id", r.json())

    def test_cannot_read_audit_log(self):
        r = self.client.get("/api/access-log/")
        self.assertEqual(r.json()["results"], [])


class ComplianceAuditorTests(Base):
    def setUp(self):
        super().setUp()
        self.login_as(self.auditor)

    def test_sees_all_stations_metadata_only_deliveries(self):
        r = self.client.get("/api/deliveries/")
        body = r.json()["results"]
        self.assertEqual({d["id"] for d in body}, {self.delivery_a.pk, self.delivery_b.pk})
        for d in body:
            self.assertNotIn("weight_kg", d)
            self.assertNotIn("grade", d)
            self.assertIn("washing_station", d)  # metadata, not commercial - still visible

    def test_sees_all_plots_with_full_coordinates(self):
        r = self.client.get("/api/plots/")
        body = {p["id"]: p for p in r.json()["results"]}
        self.assertEqual(str(body[self.plot_a1.pk]["latitude"]), "-2.700000")
        self.assertEqual(str(body[self.plot_b1.pk]["latitude"]), "-2.600000")

    def test_national_id_field_is_absent(self):
        r = self.client.get(f"/api/farmers/{self.farmer.pk}/")
        self.assertNotIn("national_id", r.json())

    def test_can_read_audit_log(self):
        self.client.get("/api/plots/")
        r = self.client.get("/api/access-log/")
        self.assertGreater(len(r.json()["results"]), 0)


class AuditTrailTests(Base):
    def test_viewing_plot_coordinates_is_logged_without_storing_them(self):
        self.login_as(self.agent)
        self.client.get(f"/api/plots/{self.plot_a1.pk}/")
        entry = AccessLogEntry.objects.filter(
            object_type="plot", object_id=self.plot_a1.pk, action=AccessLogEntry.Action.VIEW_PLOT_COORDINATES
        ).latest("id")
        self.assertEqual(entry.precision, "full")
        self.assertEqual(entry.role, UserProfile.Role.FIELD_AGENT)
        self.assertFalse(hasattr(entry, "latitude"))

    def test_exporter_view_is_logged_as_coarsened(self):
        self.login_as(self.exporter)
        self.client.get(f"/api/plots/{self.plot_a1.pk}/")
        entry = AccessLogEntry.objects.filter(
            object_type="plot", object_id=self.plot_a1.pk, action=AccessLogEntry.Action.VIEW_PLOT_COORDINATES
        ).latest("id")
        self.assertEqual(entry.precision, "coarsened_sector")

    def test_viewing_farmer_identity_is_logged(self):
        self.login_as(self.agent)
        self.client.get(f"/api/farmers/{self.farmer.pk}/")
        entry = AccessLogEntry.objects.filter(
            object_type="farmer", object_id=self.farmer.pk, action=AccessLogEntry.Action.VIEW_FARMER_IDENTITY
        ).latest("id")
        self.assertEqual(entry.precision, "masked")


class SeedFixturesTests(APITestCase):
    """Verifies seed_rbac_fixtures matches docs/autograding/F2_CONTRACT.md exactly."""

    def test_seed_command_is_idempotent(self):
        from django.core.management import call_command
        call_command("seed_rbac_fixtures")
        counts_first = (User.objects.count(), Plot.objects.count(), Delivery.objects.count())
        call_command("seed_rbac_fixtures")
        counts_second = (User.objects.count(), Plot.objects.count(), Delivery.objects.count())
        self.assertEqual(counts_first, counts_second)

    def test_seeded_users_match_contract(self):
        from django.core.management import call_command
        call_command("seed_rbac_fixtures")

        agent = User.objects.get(username="field_agent_user")
        self.assertTrue(agent.check_password("GraderPass123!"))
        self.assertEqual(agent.profile.role, UserProfile.Role.FIELD_AGENT)
        self.assertEqual(agent.profile.washing_station.name, "Nyaruguru")

        exporter = User.objects.get(username="exporter_user")
        self.assertEqual(exporter.profile.role, UserProfile.Role.EXPORTER_PARTNER)
        self.assertIsNone(exporter.profile.washing_station)

        auditor = User.objects.get(username="auditor_user")
        self.assertEqual(auditor.profile.role, UserProfile.Role.COMPLIANCE_AUDITOR)

    def test_seeded_farmer_matches_contract(self):
        from django.core.management import call_command
        call_command("seed_rbac_fixtures")
        farmer = Farmer.objects.get(member_number="KWA-F-SEED-01")
        self.assertEqual(farmer.full_name, "Uwimana Béatrice")
        self.assertEqual(farmer.national_id, "1198770123456789")
        self.assertEqual(farmer.national_id_masked[-4:], "6789")

    def test_seeded_plots_match_contract(self):
        from django.core.management import call_command
        call_command("seed_rbac_fixtures")
        expected = {
            "KWA-SEED-K1": ("Kigoma", "Nyaruguru", "-2.540000", "29.710000"),
            "KWA-SEED-K2": ("Kigoma", "Nyaruguru", "-2.660000", "29.790000"),
            "KWA-SEED-M1": ("Mbazi", "Kamonyi", "-2.510000", "29.520000"),
            "KWA-SEED-M2": ("Mbazi", "Kamonyi", "-2.900000", "29.900000"),
        }
        for code, (sector, station, lat, lng) in expected.items():
            plot = Plot.objects.get(name=code)
            self.assertEqual(plot.sector.name, sector)
            self.assertEqual(plot.washing_station.name, station)
            self.assertEqual(str(plot.latitude), lat)
            self.assertEqual(str(plot.longitude), lng)

    def test_seeded_deliveries_match_contract(self):
        from django.core.management import call_command
        call_command("seed_rbac_fixtures")
        k1 = Plot.objects.get(name="KWA-SEED-K1")
        m1 = Plot.objects.get(name="KWA-SEED-M1")
        self.assertTrue(Delivery.objects.filter(plot=k1, washing_station__name="Nyaruguru").exists())
        self.assertTrue(Delivery.objects.filter(plot=m1, washing_station__name="Kamonyi").exists())

    def test_field_agent_sees_only_nyaruguru_plots_via_api(self):
        from django.core.management import call_command
        call_command("seed_rbac_fixtures")
        self.client.force_login(User.objects.get(username="field_agent_user"))
        r = self.client.get("/api/plots/")
        codes = {p["plot_code"] for p in r.json()["results"]}
        self.assertEqual(codes, {"KWA-SEED-K1", "KWA-SEED-K2"})

    def test_exporter_coarsened_coordinates_are_not_rounded_stored_values(self):
        """Mirrors the F2 Contract's strictest check: no rounding of the real
        coordinate, at any precision from 0 to 6 decimals, should match."""
        from django.core.management import call_command
        call_command("seed_rbac_fixtures")
        self.client.force_login(User.objects.get(username="exporter_user"))
        r = self.client.get("/api/plots/")
        by_code = {p["plot_code"]: p for p in r.json()["results"]}
        k1_lat = str(by_code["KWA-SEED-K1"]["latitude"])
        stored = Decimal("-2.540000")
        for places in range(7):
            self.assertNotEqual(Decimal(k1_lat), round(stored, places))
        self.assertEqual(by_code["KWA-SEED-K1"]["latitude"], by_code["KWA-SEED-K2"]["latitude"])
        self.assertNotEqual(by_code["KWA-SEED-K1"]["latitude"], by_code["KWA-SEED-M1"]["latitude"])