"""Result shapes for the health check use case.

A full domain/ layer (entities, value objects) is intentionally not created
for this app. A health check has no business concept to isolate — only
infrastructure connectivity to verify — so an empty domain/ folder would
just be following the module template with nothing to put in it. These
dataclasses are as close to a domain concept as this app has, and they live
in application/ rather than a domain/ layer for that reason.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ComponentStatus:
    name: str
    healthy: bool
    detail: str = ""


@dataclass(frozen=True)
class HealthCheckResult:
    healthy: bool
    components: list[ComponentStatus] = field(default_factory=list)
