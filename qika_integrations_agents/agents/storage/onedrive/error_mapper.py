"""
Map OneDrive/Microsoft Graph HTTP errors to standardized error codes for the agent surface.
"""

from typing import Dict, Any


def map_error(status: int, body: Dict[str, Any]) -> Dict[str, Any]:
    error_obj = body.get("error", {}) if body else {}
    message = error_obj.get("message") or body.get("message") if body else None
    code = error_obj.get("code")

    if status == 401:
        error_code = "TOKEN_EXPIRED"
    elif status == 403:
        if code in ("accessDenied", "forbidden"):
            error_code = "PERMISSION_DENIED"
        elif code in ("throttled", "tooManyRequests"):
            error_code = "RATE_LIMIT"
        else:
            error_code = "PERMISSION_DENIED"
    elif status == 404:
        error_code = "FILE_NOT_FOUND"
    elif status in (429, 500, 502, 503, 504):
        error_code = "RATE_LIMIT"
    else:
        error_code = "UNKNOWN_ERROR"

    return {
        "error_code": error_code,
        "message": message or "Request failed",
        "debug": {"status": status, "code": code},
    }
