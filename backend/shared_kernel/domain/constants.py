"""Small set of cross-module constants.

Deliberately not a large "kitchen sink" constants file — only values that
are genuinely shared infrastructure concerns (pagination defaults) live
here. Module-specific constants (e.g. a leave request's maximum look-ahead
window) belong in that module's own domain layer, not here.
"""
from __future__ import annotations

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100

# The version segment of the versioned API prefix (`/api/{API_VERSION}/`),
# named once so it's a single source of truth rather than a string repeated
# in config/urls.py and any documentation that needs to reference it. A
# second, concurrently-supported version is not something this project needs
# yet — DRF's versioning classes (URLPathVersioning etc.) are available to
# formalize this further the day a v2 actually needs to coexist with v1;
# building that machinery now, for one version, would be exactly the kind of
# unnecessary complexity PROJECT_SPEC.md asks to avoid.
API_VERSION = "v1"
