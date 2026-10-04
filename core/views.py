from django.contrib.auth import authenticate, login, logout
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AccessLogEntry, Delivery, Farmer, Plot, PriceSchedule, Sector, WashingStation
from .pagination import DeliveryFeedPagination, StandardPagination
from .rbac import HasKawaRole, Role, get_role, scope_delivery_queryset, scope_plot_queryset
from .serializers import (
    AccessLogEntrySerializer, DeliveryFeedSerializer, DeliverySerializer, FarmerSerializer,
    PlotSerializer, PriceSerializer, RiskCheckAttemptSerializer, SectorSerializer,
    WashingStationSerializer,
)
from .tasks import enqueue_risk_check


class SectorViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Sector.objects.all()
    serializer_class = SectorSerializer


class WashingStationViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = WashingStation.objects.all()
    serializer_class = WashingStationSerializer
    filterset_fields = ["sector"]


class FarmerViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin,
                    mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Farmer.objects.all()
    serializer_class = FarmerSerializer
    pagination_class = StandardPagination
    search_fields = ["full_name", "phone"]
    # Who may REGISTER a farmer is unscoped by the F2 matrix (it only specifies
    # national_id visibility) - deliberately left open; see DECISION_LOG.md.


class PlotViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin,
                  mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Plot.objects.select_related("farmer", "sector", "washing_station")
    serializer_class = PlotSerializer
    pagination_class = StandardPagination
    filterset_fields = ["farmer", "sector", "washing_station", "risk_status"]

    def get_permissions(self):
        # Matrix governs reads; registration/rechecking are unscoped (see DECISION_LOG.md).
        if self.action in ("list", "retrieve", "risk_attempts"):
            return [HasKawaRole()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action in ("list", "retrieve"):
            return scope_plot_queryset(qs, self.request.user)
        return qs

    def perform_create(self, serializer):
        plot = serializer.save()
        enqueue_risk_check(plot.pk)  # returns immediately; the registry call happens in a worker

    @extend_schema(request=None, responses=PlotSerializer)
    @action(detail=True, methods=["post"])
    def recheck(self, request, pk=None):
        """Re-queue the risk check for a plot that is pending or whose check failed."""
        plot = self.get_object()
        if plot.risk_status not in (Plot.RiskStatus.PENDING, Plot.RiskStatus.CHECK_FAILED):
            return Response(
                {"error": {"code": "already_decided",
                           "message": f"Plot already has a final result: {plot.risk_status}."}},
                status=status.HTTP_409_CONFLICT,
            )
        plot.risk_status = Plot.RiskStatus.PENDING
        plot.save(update_fields=["risk_status"])
        enqueue_risk_check(plot.pk)
        return Response(PlotSerializer(plot).data, status=status.HTTP_202_ACCEPTED)

    @extend_schema(responses=RiskCheckAttemptSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="risk-attempts")
    def risk_attempts(self, request, pk=None):
        """Every registry call made for this plot: the evidence trail."""
        plot = self.get_object()
        return Response(RiskCheckAttemptSerializer(plot.risk_attempts.all(), many=True).data)


class DeliveryViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin,
                      mixins.ListModelMixin, viewsets.GenericViewSet):
    """POST records a delivery (unscoped - see DECISION_LOG.md). GET is matrix-governed:
    field_agent sees only their station, auditor sees metadata only, newest first, cursor-paginated."""

    queryset = Delivery.objects.select_related("plot__farmer", "washing_station")
    pagination_class = DeliveryFeedPagination
    filterset_fields = {
        "washing_station": ["exact"],
        "plot": ["exact"],
        "delivered_at": ["gte", "lte"],
    }

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [HasKawaRole()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action in ("list", "retrieve"):
            return scope_delivery_queryset(qs, self.request.user)
        return qs

    def get_serializer_class(self):
        return DeliveryFeedSerializer if self.action == "list" else DeliverySerializer

    def create(self, request, *args, **kwargs):
        # A retry over a flaky link must not double-record: same client_ref => same delivery.
        ref = request.data.get("client_ref")
        if ref:
            existing = Delivery.objects.filter(client_ref=ref).first()
            if existing:
                return Response(DeliverySerializer(existing).data, status=status.HTTP_200_OK)
        return super().create(request, *args, **kwargs)


class PriceScheduleView(APIView):
    @extend_schema(responses=PriceSerializer(many=True))
    def get(self, request):
        """Current season's price per kg for each cherry grade, in RWF."""
        rows = PriceSchedule.objects.filter(is_active=True)
        seasons = sorted({r.season for r in rows})
        return Response({
            "season": seasons[-1] if seasons else None,
            "currency": "RWF",
            "prices": PriceSerializer([r for r in rows if not seasons or r.season == seasons[-1]], many=True).data,
        })


class AccessLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """compliance_auditor's read access to the audit trail (Task 4 / matrix 'Audit log' column)."""

    queryset = AccessLogEntry.objects.select_related("user", "sector")
    serializer_class = AccessLogEntrySerializer
    pagination_class = StandardPagination
    filterset_fields = ["action", "role", "user", "object_type"]

    def get_permissions(self):
        return [HasKawaRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        if get_role(self.request.user) != Role.COMPLIANCE_AUDITOR:
            return qs.none()
        return qs


class LoginView(APIView):
    """Session login for the internal cooperative dashboard (Task 2).

    Token/JWT auth (for buyer and registry integrations) is handled separately
    by djangorestframework-simplejwt at /api/auth/token/ - see urls.py.
    """

    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={200: dict})
    def post(self, request):
        username = request.data.get("username", "")
        password = request.data.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {"error": {"code": "invalid_credentials", "message": "Invalid username or password."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        login(request, user)
        return Response({"username": user.username, "role": get_role(user)})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """Quick 'who am I, what role/station' check - handy for the dashboard and for debugging RBAC."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: dict})
    def get(self, request):
        profile = getattr(request.user, "profile", None)
        return Response({
            "username": request.user.username,
            "role": profile.role if profile else None,
            "washing_station": profile.washing_station_id if profile else None,
        })