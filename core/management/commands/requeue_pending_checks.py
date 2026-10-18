from django.core.management.base import BaseCommand

from core.models import Plot
from core.tasks import enqueue_risk_check


class Command(BaseCommand):
    help = "Re-queue risk checks for plots still pending (e.g. the broker was down at registration)."

    def handle(self, *args, **options):
        ids = list(Plot.objects.filter(risk_status=Plot.RiskStatus.PENDING).values_list("pk", flat=True))
        for pk in ids:
            enqueue_risk_check(pk)
        self.stdout.write(f"Queued {len(ids)} pending plot(s).")