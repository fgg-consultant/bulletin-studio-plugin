import json
from functools import wraps

from django.http import JsonResponse


def ok(**payload):
    return JsonResponse({"status": "success", **payload})


def fail(message, status=400, **payload):
    return JsonResponse({"status": "error", "message": str(message), **payload}, status=status)


def json_body(view):
    """Parse the request JSON body into request.json (empty dict when absent)."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        request.json = {}
        if request.body:
            try:
                request.json = json.loads(request.body)
            except ValueError:
                return fail("Invalid JSON body")
        return view(request, *args, **kwargs)

    return wrapper
