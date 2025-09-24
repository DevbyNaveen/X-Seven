"""Custom exceptions for better error handling."""
from fastapi import HTTPException, status


class BusinessNotFoundError(HTTPException):
    """Raised when business doesn't exist."""
    def __init__(self, business_id: int):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Business with id {business_id} not found"
        )


class UnauthorizedError(HTTPException):
    """Raised when user lacks permissions."""
    def __init__(self, detail: str = "Not authorized to perform this action"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class DuplicateError(HTTPException):
    """Raised when trying to create duplicate resource."""
    def __init__(self, resource: str, field: str, value: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{resource} with {field} '{value}' already exists"
        )


class ValidationError(HTTPException):
    """Raised when validation fails."""
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail
        )


class PaymentError(HTTPException):
    """Raised when payment processing fails."""
    def __init__(self, detail: str = "Payment processing failed"):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=detail
        )