from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("sectors", views.SectorViewSet)
router.register("stations", views.WashingStationViewSet)
router.register("farmers", views.FarmerViewSet)
router.register("plots", views.PlotViewSet)
router.register("deliveries", views.DeliveryViewSet)

urlpatterns = [
    path("price-schedule/", views.PriceScheduleView.as_view(), name="price-schedule"),
    path("", include(router.urls)),
]