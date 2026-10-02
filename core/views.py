from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Delivery, Farmer, Plot, PriceSchedule, Sector, WashingStation
from .pagination import DeliveryFeedPagination, StandardPagination
from .serializers import (
    DeliveryFeedSerializer, DeliverySerializer, FarmerSerializer, PlotSerializer,
    PriceSerializer, RiskCheckAttemptSerializer, SectorSerializer, WashingStationSerializer,
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


class PlotViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin,
                  mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Plot.objects.select_related("farmer", "sector", "washing_station")
    serializer_class = PlotSerializer
    pagination_class = StandardPagination
    filterset_fields = ["farmer", "sector", "washing_station", "risk_status"]

    def perform_create(self, serializer):
        plot = serializer.save()
        enqueue_risk_check(plot.pk)

    @extend_schema(request=None, responses=PlotSerializer)
    @action(detail=True, methods=["post"])
    def recheck(self, request, pk=None):
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
        plot = self.get_object()
        return Response(RiskCheckAttemptSerializer(plot.risk_attempts.all(), many=True).data)


class DeliveryViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin,
                      mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Delivery.objects.select_related("plot__farmer", "washing_station")
    pagination_class = DeliveryFeedPagination
    filterset_fields = {
        "washing_station": ["exact"],
        "plot": ["exact"],
        "delivered_at": ["gte", "lte"],
    }

    def get_serializer_class(self):
        return DeliveryFeedSerializer if self.action == "list" else DeliverySerializer

    def create(self, request, *args, **kwargs):
        ref = request.data.get("client_ref")
        if ref:
            existing = Delivery.objects.filter(client_ref=ref).first()
            if existing:
                return Response(DeliverySerializer(existing).data, status=status.HTTP_200_OK)
        return super().create(request, *args, **kwargs)


class PriceScheduleView(APIView):
    @extend_schema(responses=PriceSerializer(many=True))
    def get(self, request):
        rows = PriceSchedule.objects.filter(is_active=True)
        seasons = sorted({r.season for r in rows})
        return Response({
            "season": seasons[-1] if seasons else None,
            "currency": "RWF",
            "prices": PriceSerializer([r for r in rows if not seasons or r.season == seasons[-1]], many=True).data,
        })