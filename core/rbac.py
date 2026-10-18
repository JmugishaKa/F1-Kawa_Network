"""
Single source of truth for 'what can role R see/do'.

Everything in this file is the answer to Task 3's direct question: enforcement
lives HERE, not scattered across views and serializers as ad-hoc `if role ==`
checks. A view asks this module "give me the queryset for this role" or "what
precision does this role get"; a serializer asks it "mask or not". Adding a
fourth role next season means adding one entry to ROLE_RULES below and
wiring up its washing_station/queryset specifics if it needs scoping like
field_agent - it does not mean touching DeliveryViewSet, PlotViewSet, or any
serializer's field list. See DECISION_LOG.md.
"""
from rest_framework.permissions import BasePermission

from .models import Plot, UserProfile

Role = UserProfile.Role

# Declarative precision table: one row per role, read by views/serializers
# instead of each one hard-coding its own role checks.
ROLE_RULES = {
    Role.FIELD_AGENT: {
        "coordinate_precision": "full",
        "national_id": "masked",
        "delivery_scope": "own_station",
        "delivery_fields": "full",
        "audit_log_access": False,
    },
    Role.EXPORTER_PARTNER: {
        "coordinate_precision": "coarsened_sector",
        "national_id": "absent",
        "delivery_scope": "all_stations",
        "delivery_fields": "full",
        "audit_log_access": False,
    },
    Role.COMPLIANCE_AUDITOR: {
        "coordinate_precision": "full",
        "national_id": "absent",
        "delivery_scope": "all_stations",
        "delivery_fields": "metadata_only",  # no weight_kg / grade / client_ref
        "audit_log_access": True,
    },
}

# Delivery fields treated as "commercial terms" for the metadata_only view.
COMMERCIAL_DELIVERY_FIELDS = {"weight_kg", "grade", "client_ref"}


def get_role(user):
    if not user or not user.is_authenticated:
        return None
    profile = getattr(user, "profile", None)
    return profile.role if profile else None


def rules_for(user):
    role = get_role(user)
    return ROLE_RULES.get(role)


class HasKawaRole(BasePermission):
    """Authenticated AND has a recognised Kawa role. Covers the 'unauthenticated -> 401/403' row."""

    def has_permission(self, request, view):
        return get_role(request.user) is not None


def scope_plot_queryset(queryset, user):
    role = get_role(user)
    if role == Role.FIELD_AGENT:
        station = user.profile.washing_station_id
        return queryset.filter(washing_station_id=station) if station else queryset.none()
    return queryset  # exporter_partner and compliance_auditor see all plots


def scope_delivery_queryset(queryset, user):
    role = get_role(user)
    rule = ROLE_RULES.get(role)
    if rule is None:
        return queryset.none()
    if rule["delivery_scope"] == "own_station":
        station = user.profile.washing_station_id
        return queryset.filter(washing_station_id=station) if station else queryset.none()
    return queryset