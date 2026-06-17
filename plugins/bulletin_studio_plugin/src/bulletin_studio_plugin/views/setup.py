from django.views.decorators.http import require_POST

from ..services.setup_chain import ensure_publication_chain
from ._helpers import fail, json_body, ok


@require_POST
@json_body
def setup_run(request):
    """Create/reuse the publication chain. Body mirrors ensure_publication_chain kwargs.

    Pass {"dry_run": true} to preview without writing (the transaction is rolled back).
    """
    from django.db import transaction

    data = request.json
    kwargs = {
        "service_category_id": data.get("service_category_id"),
        "service_category_name": data.get("service_category_name"),
        "service_icon": data.get("service_icon", "environment"),
        "product_id": data.get("product_id"),
        "product_name": data.get("product_name"),
        "temporal_resolution": data.get("temporal_resolution", "dekadal"),
        "category_name": data.get("category_name"),
        "item_type_name": data.get("item_type_name"),
        "valid_for_days": data.get("valid_for_days", 10),
        "product_page_title": data.get("product_page_title"),
        "user": request.user,
    }

    if not kwargs["service_category_id"] and not kwargs["service_category_name"]:
        return fail("A service category (id or name) is required")
    if not kwargs["product_id"] and not kwargs["product_name"]:
        return fail("A product (id or name) is required")

    try:
        if data.get("dry_run"):
            with transaction.atomic():
                result = ensure_publication_chain(**kwargs)
                payload = result.as_dict()
                transaction.set_rollback(True)
            return ok(dry_run=True, **payload)
        result = ensure_publication_chain(**kwargs)
        return ok(**result.as_dict())
    except Exception as e:
        return fail(e, status=500)
