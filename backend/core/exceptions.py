from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    """DRF's handler, plus: a database rule violation (CHECK constraint, immutability trigger, unique key)
    becomes a 400 with a readable message instead of a 500."""
    response = drf_exception_handler(exc, context)
    if response is None and isinstance(exc, IntegrityError):
        message = str(exc).split("\n")[0].strip() or "The change breaks a data integrity rule."
        return Response({"detail": f"Rejected by the database: {message}"}, status=status.HTTP_400_BAD_REQUEST)
    return response
