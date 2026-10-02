import random
import time

import requests
from django.conf import settings


class RegistryUnavailable(Exception):
    pass


def check_plot(plot):
    if settings.RISK_REGISTRY_MOCK:
        return _mock_check(plot)
    try:
        resp = requests.post(
            settings.RISK_REGISTRY_URL,
            json={"plot_id": plot.pk, "lat": str(plot.latitude), "lng": str(plot.longitude)},
            timeout=settings.RISK_REGISTRY_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise RegistryUnavailable(str(exc)) from exc
    if data.get("recently_cleared"):
        return "flagged", "registry: recently cleared land"
    return "clear", "registry: no clearing detected"


def _mock_check(plot):
    time.sleep(random.uniform(settings.RISK_REGISTRY_MOCK_DELAY_MIN, settings.RISK_REGISTRY_MOCK_DELAY_MAX))
    roll = random.random()
    if roll < settings.RISK_REGISTRY_MOCK_FAILURE_RATE:
        raise RegistryUnavailable("mock registry: service unavailable")
    if random.random() < settings.RISK_REGISTRY_MOCK_FLAG_RATE:
        return "flagged", "mock registry: recently cleared land"
    return "clear", "mock registry: no clearing detected"