from decimal import Decimal

from django.core.management.base import BaseCommand

from core.models import PriceSchedule, Sector, WashingStation


class Command(BaseCommand):
    help = "Create a demo sector, station and price schedule (idempotent)."

    def handle(self, *args, **options):
        sector, _ = Sector.objects.get_or_create(name="Nyaruguru", defaults={"district": "Nyaruguru"})
        WashingStation.objects.get_or_create(name="Nyaruguru Washing Station", defaults={"sector": sector})
        for grade, price in (("A", "450.00"), ("B", "380.00"), ("C", "300.00")):
            PriceSchedule.objects.get_or_create(
                season="2026", grade=grade, defaults={"price_per_kg": Decimal(price)}
            )
        self.stdout.write(self.style.SUCCESS("Seeded demo data."))