from django.urls import path

from apps.healthcheck.interface.views import HealthCheckView

urlpatterns = [
    path("", HealthCheckView.as_view(), name="health-check"),
]
