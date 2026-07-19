"""Base contract every use case in every module implements.

A use case is the only thing an interface layer (a DRF view, a future
Telegram handler) or an infrastructure layer (a Celery task) is allowed to
call to trigger a business action — see HRMS_Architecture.md section 1.2.
Interfaces never contain business decisions themselves; they parse input
into a request DTO, call `execute()`, and serialize the response DTO.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

RequestT = TypeVar("RequestT")
ResponseT = TypeVar("ResponseT")


class UseCase(ABC, Generic[RequestT, ResponseT]):
    """Every concrete use case takes one input DTO and returns one output DTO."""

    @abstractmethod
    def execute(self, request: RequestT) -> ResponseT:
        raise NotImplementedError
