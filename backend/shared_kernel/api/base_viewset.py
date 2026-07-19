"""Base ViewSet every future module's interface layer extends.

Was left as a bare `pass` until a real module existed to prove out what's
actually shared — Employee is that module. What turned out to be genuinely
uniform across any future module's list/retrieve endpoints: parse query
params, call the service, format the response (including pagination). What
did NOT turn out to be uniform: create/update, whose request DTO shape is
inherently module-specific — those stay explicit per-module methods, the
same judgment already applied when `DjangoBaseRepository` was designed (see
shared_kernel/infrastructure/base_repository.py's docstring for the same
reasoning stated from the repository side).

No branching business logic lives here, and none should be added — that
belongs in the application layer's services/use cases
(CODING_STANDARD.md: "no business logic in views" applies to this base too,
not just to concrete view methods).
"""
from __future__ import annotations

import uuid

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from shared_kernel.api.query_params import parse_list_query_params
from shared_kernel.api.response import paginated_response, success_response
from shared_kernel.application.base_service import BaseService


class BaseViewSet(GenericViewSet):
    #: Serializer used to shape each item in `list()`/`retrieve()` responses.
    #: Distinct from DRF's own `serializer_class` (still used for schema
    #: generation / `get_serializer` on write actions) so a module can keep
    #: separate request vs. response serializers, as Identity already does.
    response_serializer_class = None

    #: Query-string parsing configuration for `list()` — see
    #: shared_kernel/api/query_params.py.
    filter_fields: tuple[str, ...] = ()
    search_fields: tuple[str, ...] = ()
    default_ordering: tuple[str, ...] = ()

    def get_service(self) -> BaseService:
        """Subclasses return the (already composed, via that module's
        interface/dependencies.py) service instance this ViewSet delegates
        to. Not a class attribute, because building a service means wiring
        concrete repositories/UnitOfWork — exactly the composition-root
        responsibility interface/dependencies.py owns (see
        apps/identity/interface/dependencies.py for the established
        pattern); a ViewSet only ever calls into it, never constructs
        infrastructure itself.
        """
        raise NotImplementedError

    def get_response_serializer_class(self):
        assert self.response_serializer_class is not None, (
            f"{self.__class__.__name__} must set response_serializer_class"
        )
        return self.response_serializer_class

    def list(self, request: Request, *args, **kwargs) -> Response:
        query = parse_list_query_params(
            request,
            filter_fields=self.filter_fields,
            search_fields=self.search_fields,
            default_ordering=self.default_ordering,
        )
        page_result = self.get_service().list(query)
        serializer_class = self.get_response_serializer_class()
        serialized = serializer_class(page_result.items, many=True).data
        return paginated_response(page_result, serialized)

    def retrieve(self, request: Request, pk: uuid.UUID | str | None = None, *args, **kwargs) -> Response:
        entity = self.get_service().get_by_id(pk)
        serializer_class = self.get_response_serializer_class()
        return success_response(serializer_class(entity).data)
