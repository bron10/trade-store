import re
from datetime import date

_USERINFO = re.compile(r"://[^/\s:]+:[^@\s]+@")


def redact(text: str) -> str:
    """Remove userinfo from URLs so logs do not keep database passwords."""
    return _USERINFO.sub("://***:***@", text)


class AppError(Exception):
    status_code = 400
    code = "error"

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class VersionConflictError(AppError):
    status_code = 409
    code = "version_conflict"

    def __init__(self, trade_id: str, incoming_version: int, stored_version: int) -> None:
        super().__init__(
            "Incoming version is lower than the stored version.",
            details={
                "trade_id": trade_id,
                "incoming_version": incoming_version,
                "stored_version": stored_version,
            },
        )


class MaturityDateError(AppError):
    status_code = 422
    code = "maturity_in_past"

    def __init__(
        self,
        *,
        trade_id: str,
        maturity_date: date,
        business_date: date,
        business_timezone: str,
    ) -> None:
        super().__init__(
            "Maturity date is earlier than the current business date.",
            details={
                "trade_id": trade_id,
                "maturity_date": maturity_date.isoformat(),
                "business_date": business_date.isoformat(),
                "business_timezone": business_timezone,
            },
        )


class TradeNotFoundError(AppError):
    status_code = 404
    code = "trade_not_found"

    def __init__(self, trade_id: str) -> None:
        super().__init__(
            "Trade not found.",
            details={"trade_id": trade_id},
        )


class InvalidBatchError(AppError):
    status_code = 422
    code = "invalid_batch"

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message, details=details)


class InternalError(AppError):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str = "An unexpected error occurred.") -> None:
        super().__init__(message)


def error_payload(code: str, message: str, details: dict[str, object] | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }


def validation_details(errors: list[dict]) -> dict[str, object]:
    return {
        "errors": [
            {
                "loc": [part for part in error.get("loc", ())],
                "msg": str(error.get("msg", "Invalid value.")),
                "type": str(error.get("type", "value_error")),
            }
            for error in errors
        ]
    }
