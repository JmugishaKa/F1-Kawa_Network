import logging
import time

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import registry
from .models import Plot, RiskCheckAttempt

logger = logging.getLogger(__name__)


def perform_risk_check(plot_id, attempt=1):
    plot = Plot.objects.filter(pk=plot_id).first()
    if plot is None or plot.risk_status in (Plot.RiskStatus.CLEAR, Plot.RiskStatus.FLAGGED):
        #this check is important than I first thought- without it a retried
        # celery message could re-run the check on a plot that is already been cleared or flagged, which would be bad.
        return None

    started = time.monotonic()
    try:
        outcome, detail = registry.check_plot(plot)
    except Exception as exc:
        _record(plot, attempt, RiskCheckAttempt.Outcome.ERROR, str(exc), started)
        if attempt >= settings.RISK_MAX_ATTEMPTS:
            plot.risk_status = Plot.RiskStatus.CHECK_FAILED
            plot.save(update_fields=["risk_status"])
            logger.error("risk check gave up for plot %s after %s attempts", plot_id, attempt)
            return None
        #exponential backoff: the brief says the registry can be down for hours, 
        # So I dont want to retry every minutes and hammer it.
        delay = settings.RISK_RETRY_BASE_SECONDS * 2 ** (attempt - 1)
        logger.warning("risk check attempt %s failed for plot %s; retrying in %ss", attempt, plot_id, delay)
        return delay

    _record(plot, attempt, outcome, detail, started)
    plot.risk_status = outcome
    plot.risk_checked_at = timezone.now()
    plot.save(update_fields=["risk_status", "risk_checked_at"])
    logger.info("risk check for plot %s -> %s (attempt %s)", plot_id, outcome, attempt)
    return None


def _record(plot, attempt, outcome, detail, started):
    RiskCheckAttempt.objects.create(
        plot=plot, attempt=attempt, outcome=outcome, detail=detail[:255],
        duration_ms=int((time.monotonic() - started) * 1000),
    )


@shared_task(bind=True, name="core.run_risk_check")
def run_risk_check(self, plot_id, attempt=1):
    delay = perform_risk_check(plot_id, attempt)
    if delay is not None:
        raise self.retry(args=(plot_id, attempt + 1), countdown=delay, max_retries=None)


def enqueue_risk_check(plot_id):
    def _send():
        try:
            run_risk_check.apply_async(args=(plot_id,), retry=False)
        except Exception:
            logger.exception("could not queue risk check for plot %s; left pending", plot_id)

    transaction.on_commit(_send)