"""Health check endpoint.

Deliberately public (AllowAny, no authentication classes) — monitoring
systems, load balancers, and container orchestrators cannot authenticate,
and a health check that requires auth defeats its own purpose.
"""
from __future__ import annotations

from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.healthcheck.application.use_cases.check_system_health import CheckSystemHealthUseCase


class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request: Request) -> Response:
        result = CheckSystemHealthUseCase().execute()
        status_code = 200 if result.healthy else 503
        return Response(
            {
                "status": "healthy" if result.healthy else "unhealthy",
                "version": getattr(settings, "APP_VERSION", "0.1.0"),
                "components": {
                    component.name: {"healthy": component.healthy, "detail": component.detail}
                    for component in result.components
                },
            },
            status=status_code,
        )
