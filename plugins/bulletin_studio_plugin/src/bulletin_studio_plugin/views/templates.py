from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST

from ..models import BulletinPublishConfig, BulletinTemplate
from ..services.layout import validate_layout
from ._helpers import fail, json_body, ok


def _template_summary(template):
    last_issue = template.issues.first()
    config = getattr(template, "publish_config", None)
    return {
        "id": template.pk,
        "name": template.name,
        "slug": template.slug,
        "language": template.language,
        "is_active": template.is_active,
        "updated_at": template.updated_at.isoformat(),
        "issue_count": template.issues.count(),
        "last_issue": {
            "id": last_issue.pk,
            "issue_number": last_issue.issue_number,
            "period_start": last_issue.period_start.isoformat(),
            "status": last_issue.status,
        } if last_issue else None,
        "publish_config": {
            "service_category_id": config.service_category_id,
            "product_id": config.product_id,
            "product_item_type_id": config.product_item_type_id,
            "product_page_id": config.product_page_id,
            "valid_for_days": config.valid_for_days,
            "issue_title_pattern": config.issue_title_pattern,
        } if config else None,
    }


@require_http_methods(["GET", "POST"])
@json_body
def template_list(request):
    if request.method == "GET":
        return ok(templates=[_template_summary(t) for t in BulletinTemplate.objects.all()])

    name = request.json.get("name")
    if not name:
        return fail("A template name is required")
    template = BulletinTemplate.objects.create(
        name=name,
        description=request.json.get("description", ""),
        language=request.json.get("language", "en"),
        created_by=request.user,
    )
    return ok(template=_template_summary(template), layout=template.layout)


@require_http_methods(["GET", "POST"])
@json_body
def template_detail(request, pk):
    template = get_object_or_404(BulletinTemplate, pk=pk)

    if request.method == "POST":
        data = request.json
        for field in ("name", "description", "language", "is_active"):
            if field in data:
                setattr(template, field, data[field])
        template.save()

        wiring = data.get("publish_config")
        if wiring:
            BulletinPublishConfig.objects.update_or_create(
                template=template,
                defaults={
                    "service_category_id": wiring["service_category_id"],
                    "product_id": wiring["product_id"],
                    "product_item_type_id": wiring["product_item_type_id"],
                    "product_page_id": wiring["product_page_id"],
                    "valid_for_days": wiring.get("valid_for_days", 10),
                    "issue_title_pattern": wiring.get("issue_title_pattern", "{product_name} - {period}"),
                },
            )

    return ok(template=_template_summary(template), layout=template.layout)


@require_POST
@json_body
def template_layout_save(request, pk):
    template = get_object_or_404(BulletinTemplate, pk=pk)
    layout = request.json.get("layout")
    errors = validate_layout(layout)
    if errors:
        return fail("Invalid layout", errors=errors)
    template.layout = layout
    template.save(update_fields=["layout", "updated_at"])
    return ok()


@require_POST
def template_delete(request, pk):
    template = get_object_or_404(BulletinTemplate, pk=pk)
    if template.issues.exists():
        return fail("This template has issues; archive it instead (is_active=false)")
    template.delete()
    return ok()


@require_POST
def template_duplicate(request, pk):
    template = get_object_or_404(BulletinTemplate, pk=pk)
    copy = BulletinTemplate.objects.create(
        name=f"{template.name} (copy)",
        slug=f"{template.slug}-copy-{BulletinTemplate.objects.count()}",
        description=template.description,
        language=template.language,
        page_size=template.page_size,
        orientation=template.orientation,
        layout=template.layout,
        created_by=request.user,
    )
    return ok(template=_template_summary(copy))
