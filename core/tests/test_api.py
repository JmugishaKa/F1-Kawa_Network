import time
from decimal import Decimal
from unittest import mock

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from core import registry, tasks
from core.models import Delivery, Farmer, Plot, PriceSchedule, RiskCheckAttempt, Sector, WashingStation


class Base(APITestCase):
    def setUp(self):
        self.sector = Sector.objects.create(name="Nyaruguru")
        self.station = WashingStation.objects.create(name="Nyaruguru WS", sector=self.sector)
        self.farmer = Farmer.objects.create(full_name="Jean Claude", phone="0788123456")

    def make_plot(self, status=Plot.RiskStatus.PENDING, name="Hillside"):
        return Plot.objects.create(
            farmer=self.farmer, name=name, sector=self.sector, washing_station=self.station,
            area_hectares=Decimal("0.5"), risk_status=status,
        )


class FarmerTests(Base):
    def test_register_farmer(self):
        r = self.client.post("/api/farmers/", {"full_name": "Marie Uwase", "phone": "+250788000111"})
        self.assertEqual(r.status_code, 201)

    def test_validation_error_is_structured(self):
        r = self.client.post("/api/farmers/", {"full_name": "M", "phone": "abc"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"]["code"], "validation_error")
        self.assertIn("phone", r.json()["error"]["fields"])
        self.assertIn("full_name", r.json()["error"]["fields"])

    def test_duplicate_phone_rejected(self):
        r = self.client.post("/api/farmers/", {"full_name": "Someone", "phone": "0788123456"})
        self.assertEqual(r.status_code, 400)


class PlotTests(Base):
    payload = lambda self, **kw: {
        "farmer": self.farmer.pk, "name": "Hillside", "sector": self.sector.pk,
        "washing_station": self.station.pk, "area_hectares": "0.75", **kw,
    }

    @mock.patch("core.tasks.run_risk_check.apply_async")
    def test_plot_registration_queues_check_and_returns_pending(self, queued):
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post("/api/plots/", self.payload())
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertEqual(body["risk_status"], "pending")
        self.assertEqual(body["sector"], self.sector.pk)
        self.assertEqual(body["washing_station"], self.station.pk)
        queued.assert_called_once()

    def test_registration_does_not_wait_for_registry(self):
        with mock.patch("core.registry.check_plot", side_effect=lambda p: time.sleep(5)), \
             mock.patch("core.tasks.run_risk_check.apply_async"):
            start = time.monotonic()
            with self.captureOnCommitCallbacks(execute=True):
                r = self.client.post("/api/plots/", self.payload())
            self.assertEqual(r.status_code, 201)
            self.assertLess(time.monotonic() - start, 1.0)

    def test_broker_down_does_not_break_registration(self):
        with mock.patch("core.tasks.run_risk_check.apply_async", side_effect=ConnectionError("no broker")):
            with self.captureOnCommitCallbacks(execute=True):
                r = self.client.post("/api/plots/", self.payload())
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Plot.objects.get().risk_status, "pending")

    def test_requires_sector_and_station(self):
        r = self.client.post("/api/plots/", {"farmer": self.farmer.pk, "name": "X", "area_hectares": "1"})
        self.assertEqual(r.status_code, 400)
        fields = r.json()["error"]["fields"]
        self.assertIn("sector", fields)
        self.assertIn("washing_station", fields)

    def test_lat_without_lng_rejected(self):
        r = self.client.post("/api/plots/", self.payload(latitude="-2.5"))
        self.assertEqual(r.status_code, 400)

    def test_duplicate_plot_name_per_farmer(self):
        self.make_plot()
        r = self.client.post("/api/plots/", self.payload())
        self.assertEqual(r.status_code, 400)
        self.assertIn("name", r.json()["error"]["fields"])

    def test_list_and_filter(self):
        self.make_plot()
        r = self.client.get(f"/api/plots/?washing_station={self.station.pk}&risk_status=pending")
        self.assertEqual(r.json()["count"], 1)

    @mock.patch("core.tasks.run_risk_check.apply_async")
    def test_recheck_only_when_pending_or_failed(self, queued):
        failed = self.make_plot(Plot.RiskStatus.CHECK_FAILED)
        clear = self.make_plot(Plot.RiskStatus.CLEAR, name="Other")
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(f"/api/plots/{failed.pk}/recheck/").status_code, 202)
        self.assertEqual(self.client.post(f"/api/plots/{clear.pk}/recheck/").status_code, 409)
        queued.assert_called_once()


class RiskCheckTaskTests(Base):
    def test_success_records_attempt_and_updates_plot(self):
        plot = self.make_plot()
        with mock.patch("core.registry.check_plot", return_value=("clear", "ok")):
            self.assertIsNone(tasks.perform_risk_check(plot.pk))
        plot.refresh_from_db()
        self.assertEqual(plot.risk_status, "clear")
        self.assertIsNotNone(plot.risk_checked_at)
        self.assertEqual(plot.risk_attempts.get().outcome, "clear")

    def test_failure_records_attempt_and_backs_off(self):
        plot = self.make_plot()
        with mock.patch("core.registry.check_plot", side_effect=registry.RegistryUnavailable("down")):
            self.assertEqual(tasks.perform_risk_check(plot.pk, attempt=1), 60)
            self.assertEqual(tasks.perform_risk_check(plot.pk, attempt=2), 120)
        plot.refresh_from_db()
        self.assertEqual(plot.risk_status, "pending")
        self.assertEqual(RiskCheckAttempt.objects.filter(plot=plot, outcome="error").count(), 2)

    @override_settings(RISK_MAX_ATTEMPTS=3)
    def test_gives_up_after_max_attempts(self):
        plot = self.make_plot()
        with mock.patch("core.registry.check_plot", side_effect=registry.RegistryUnavailable("down")):
            self.assertIsNone(tasks.perform_risk_check(plot.pk, attempt=3))
        plot.refresh_from_db()
        self.assertEqual(plot.risk_status, "check_failed")

    def test_decided_plot_is_not_rechecked(self):
        plot = self.make_plot(Plot.RiskStatus.CLEAR)
        with mock.patch("core.registry.check_plot") as call:
            tasks.perform_risk_check(plot.pk)
        call.assert_not_called()

    def test_attempts_endpoint(self):
        plot = self.make_plot()
        with mock.patch("core.registry.check_plot", return_value=("flagged", "cleared")):
            tasks.perform_risk_check(plot.pk)
        r = self.client.get(f"/api/plots/{plot.pk}/risk-attempts/")
        self.assertEqual(r.json()[0]["outcome"], "flagged")


class DeliveryTests(Base):
    def post(self, plot, **kw):
        return self.client.post("/api/deliveries/", {"plot": plot.pk, "weight_kg": "42.5", "grade": "A", **kw})

    def test_record_delivery_carries_provenance(self):
        plot = self.make_plot(Plot.RiskStatus.CLEAR)
        r = self.post(plot)
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertEqual(body["plot"], plot.pk)
        self.assertEqual(body["farmer"], self.farmer.pk)
        self.assertEqual(body["sector"], self.sector.pk)
        self.assertEqual(body["washing_station"], self.station.pk)
        self.assertTrue(body["provenance_verified"])

    def test_unverified_plot_can_still_deliver_but_is_marked(self):
        for status in (Plot.RiskStatus.PENDING, Plot.RiskStatus.CHECK_FAILED):
            plot = self.make_plot(status, name=status)
            r = self.post(plot)
            self.assertEqual(r.status_code, 201)
            self.assertFalse(r.json()["provenance_verified"])
            self.assertEqual(r.json()["plot_risk_status"], status)

    def test_flagged_plot_is_blocked(self):
        r = self.post(self.make_plot(Plot.RiskStatus.FLAGGED))
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"]["code"], "plot_flagged")

    def test_validation(self):
        plot = self.make_plot()
        self.assertEqual(self.post(plot, weight_kg="-3").status_code, 400)
        self.assertEqual(self.post(plot, weight_kg="99999").status_code, 400)
        self.assertEqual(self.post(plot, grade="Z").status_code, 400)
        future = (timezone.now() + timezone.timedelta(days=1)).isoformat()
        self.assertEqual(self.post(plot, delivered_at=future).status_code, 400)
        self.assertEqual(self.client.post("/api/deliveries/", {"plot": 9999, "weight_kg": 1, "grade": "A"}).status_code, 400)

    def test_client_ref_makes_retries_idempotent(self):
        plot = self.make_plot()
        first = self.post(plot, client_ref="phone-1-0001")
        second = self.post(plot, client_ref="phone-1-0001")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(Delivery.objects.count(), 1)

    def test_feed_is_cursor_paginated_newest_first_and_compact(self):
        plot = self.make_plot(Plot.RiskStatus.CLEAR)
        for i in range(30):
            self.post(plot)
        r = self.client.get(f"/api/deliveries/?washing_station={self.station.pk}")
        body = r.json()
        self.assertEqual(len(body["results"]), 25)
        self.assertIsNotNone(body["next"])
        self.assertNotIn("count", body)
        ids = [d["id"] for d in body["results"]]
        self.assertEqual(ids, sorted(ids, reverse=True))
        self.assertEqual(set(body["results"][0]), {"id", "farmer_name", "plot_name", "weight_kg", "grade", "delivered_at", "verified"})
        page2 = self.client.get(body["next"]).json()
        self.assertEqual(len(page2["results"]), 5)
        self.assertFalse(set(ids) & {d["id"] for d in page2["results"]})

    def test_feed_query_count_is_constant(self):
        plot = self.make_plot(Plot.RiskStatus.CLEAR)
        for i in range(10):
            self.post(plot)
        with self.assertNumQueries(1):
            self.client.get("/api/deliveries/")


class PriceScheduleTests(Base):
    def test_price_schedule(self):
        for g, p in (("A", "450"), ("B", "380")):
            PriceSchedule.objects.create(season="2026", grade=g, price_per_kg=p)
        PriceSchedule.objects.create(season="2025", grade="A", price_per_kg="400", is_active=False)
        r = self.client.get("/api/price-schedule/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["season"], "2026")
        self.assertEqual(len(r.json()["prices"]), 2)

    def test_empty_schedule(self):
        self.assertEqual(self.client.get("/api/price-schedule/").json()["prices"], [])