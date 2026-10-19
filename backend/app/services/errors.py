"""Errors raised by the service layer."""


class ServiceError(Exception):
    """Base class for expected, client-facing errors."""

    status_code = 400


class NotFoundError(ServiceError):
    status_code = 404


class ForbiddenError(ServiceError):
    status_code = 403


class ConflictError(ServiceError):
    status_code = 409


class UpstreamError(ServiceError):
    status_code = 503
