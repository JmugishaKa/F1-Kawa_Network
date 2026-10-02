from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler


class PlotFlagged(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "plot_flagged"
    default_detail = "This plot is flagged for recently cleared land; deliveries are blocked."


def structured_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, ValidationError):
        error = {"code": "validation_error", "message": "Request validation failed.", "fields": response.data}
    else:
        detail = response.data.get("detail") if isinstance(response.data, dict) else response.data
        error = {"code": getattr(detail, "code", "error"), "message": str(detail)}
    response.data = {"error": error}
    return response