"""Root URL configuration.

Health/ops endpoints are wired directly here, outside the `/api/v1/`
namespace. Business module endpoints are wired generically from
`config.module_registry.API_MODULE_URL_PREFIXES` — each entry becomes
`/api/v1/<prefix>/`, routed to that module's own `interface/urls.py`.
Adding a module means adding one dict entry there, not editing this file.
"""
from __future__ import annotations

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from config.module_registry import API_MODULE_URL_PREFIXES
from shared_kernel.domain.constants import API_VERSION

api_v1_patterns = [
    path(f"{prefix}/", include(f"{app_label}.interface.urls"))
    for prefix, app_label in API_MODULE_URL_PREFIXES.items()
]

urlpatterns = [
    path("health/", include("apps.healthcheck.interface.urls")),
    path(f"api/{API_VERSION}/", include(api_v1_patterns)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]
