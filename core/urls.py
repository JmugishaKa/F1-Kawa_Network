from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

router = DefaultRouter()
router.register("sectors", views.SectorViewSet)
router.register("stations", views.WashingStationViewSet)
router.register("farmers", views.FarmerViewSet)
router.register("plots", views.PlotViewSet)
router.register("deliveries", views.DeliveryViewSet)
router.register("access-log", views.AccessLogViewSet, basename="access-log")

urlpatterns = [
    path("status/", views.StatusView.as_view(), name="status"),
    path("price-schedule/", views.PriceScheduleView.as_view(), name="price-schedule"),
    # Session auth: internal cooperative dashboard (Task 2).
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/staff-login/", views.LoginView.as_view(), name="staff-login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    # Token auth: buyer / registry integrations (Task 2).
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/api-token/", TokenObtainPairView.as_view(), name="api-token"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("", include(router.urls)),
]