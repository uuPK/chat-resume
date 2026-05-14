"""用于定义独立于 HTTP 框架的服务层错误。"""

from __future__ import annotations


class ServiceError(Exception):
    """Base class for recoverable service-layer failures."""


class ServiceNotFoundError(ServiceError):
    """Raised when a requested domain object cannot be found."""


class ServicePermissionError(ServiceError):
    """Raised when the caller cannot access a domain object."""


class ServiceValidationError(ServiceError):
    """Raised when service input is invalid for the requested operation."""


class ServicePayloadTooLargeError(ServiceValidationError):
    """Raised when a payload exceeds the configured service limit."""
