"""
Custom exceptions for Lanework.
"""

from typing import Any, Dict, Optional


class LaneworkException(Exception):
    """Base exception for all Lanework errors."""
    
    def __init__(
        self,
        message: str,
        code: str = "LANEWORK_ERROR",
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details
            }
        }


class NotFoundException(LaneworkException):
    """Resource not found."""
    
    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        message: Optional[str] = None
    ):
        msg = message or f"{resource_type} with ID '{resource_id}' not found"
        super().__init__(
            message=msg,
            code="NOT_FOUND",
            details={"resource_type": resource_type, "resource_id": resource_id},
            status_code=404
        )


class ValidationException(LaneworkException):
    """Validation error."""
    
    def __init__(
        self,
        message: str,
        errors: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details={"errors": errors or {}},
            status_code=400
        )


class PermissionException(LaneworkException):
    """Permission denied."""
    
    def __init__(
        self,
        message: str = "Permission denied",
        required_permission: Optional[str] = None
    ):
        super().__init__(
            message=message,
            code="PERMISSION_DENIED",
            details={"required_permission": required_permission} if required_permission else {},
            status_code=403
        )


class ConflictException(LaneworkException):
    """Resource conflict."""
    
    def __init__(
        self,
        message: str,
        resource_type: str,
        resource_id: str
    ):
        super().__init__(
            message=message,
            code="CONFLICT",
            details={"resource_type": resource_type, "resource_id": resource_id},
            status_code=409
        )


class AuthenticationException(LaneworkException):
    """Authentication failed."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            code="AUTHENTICATION_FAILED",
            status_code=401
        )


class RateLimitException(LaneworkException):
    """Rate limit exceeded."""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": retry_after},
            status_code=429
        )


class TenantNotFoundException(LaneworkException):
    """Tenant not found."""
    
    def __init__(self, tenant_id: str):
        super().__init__(
            message=f"Tenant with ID '{tenant_id}' not found",
            code="TENANT_NOT_FOUND",
            details={"tenant_id": tenant_id},
            status_code=404
        )


class TrustLevelException(LaneworkException):
    """Trust level violation."""
    
    def __init__(
        self,
        message: str,
        required_trust_level: str,
        current_trust_level: str
    ):
        super().__init__(
            message=message,
            code="TRUST_LEVEL_VIOLATION",
            details={
                "required_trust_level": required_trust_level,
                "current_trust_level": current_trust_level
            },
            status_code=403
        )
