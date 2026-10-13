import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def seeded_db(db):
    """Runs the F2 fixture command so field_agent_user/exporter_user/auditor_user exist."""
    call_command("seed_rbac_fixtures")


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def as_role(seeded_db, api_client):
    """Returns an APIClient force-logged-in as the named seed user.

    Matches F2_CONTRACT.md: the hidden checks authenticate directly as each
    fixture user and never go through the login views.
    """

    def _as_role(username):
        user = User.objects.get(username=username)
        api_client.force_login(user)
        return api_client

    return _as_role
