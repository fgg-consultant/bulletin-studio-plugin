from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from ..models import BulletinIssue, BulletinTemplate
from ..services import layout as layout_service
from ..services.map_render import MapRenderError, get_layer, render_map_element, resolve_raster_file
from ..services.pdf import PdfGenerationError, generate_pdf
from ..services.publish import PublishError, publish_issue
from ._helpers import fail, json_body, ok


def _issue_summary(issue):
    return {
        "id": issue.pk,
        "template_id": issue.template_id,
        "template_name": issue.template.name,
        "issue_number": issue.issue_number,
        "issue_date": issue.issue_date.isoformat(),
        "period_start": issue.period_start.isoformat(),
        "period_end": issue.period_end.isoformat() if issue.period_end else None,
        "status": issue.status,
        "error_message": issue.error_message,
        "pdf_url": issue.pdf_file.url if issue.pdf_file else None,
        "page_id": issue.product_item_page_id,
        "updated_at": issue.updated_at.isoformat(),
    }


def _map_resolution(issue):
    """Per-map-element resolution status for the issue editor's right rail."""
    resolutions = []
    for element in layout_service.iter_elements(issue.layout_snapshot):
        if element.get("type") != "map":
            continue
        entry = {"element_id": element.get("id"), "caption": element.get("caption", "")}
        try:
            layer = get_layer(element.get("layer_id"))
            raster_file = resolve_raster_file(layer, element, issue)
            entry.update({
                "resolved": True,
                "layer_title": layer.title,
                "time": raster_file.time.isoformat(),
            })
        except MapRenderError as e:
            entry.update({"resolved": False, "message": str(e)})
        resolutions.append(entry)
    return resolutions


@require_http_methods(["GET", "POST"])
@json_body
def issue_list_create(request, pk):
    template = get_object_or_404(BulletinTemplate, pk=pk)

    if request.method == "GET":
        return ok(issues=[_issue_summary(i) for i in template.issues.all()])

    data = request.json
    if not data.get("period_start"):
        return fail("period_start is required")
    issue = BulletinIssue.objects.create(
        template=template,
        issue_number=data.get("issue_number", ""),
        issue_date=data.get("issue_date") or None,
        period_start=data["period_start"],
        period_end=data.get("period_end") or None,
        layout_snapshot=template.layout,
        created_by=request.user,
    )
    return ok(issue=_issue_summary(issue))


@require_http_methods(["GET", "POST"])
@json_body
def issue_detail(request, pk):
    issue = get_object_or_404(BulletinIssue, pk=pk)

    if request.method == "POST":
        data = request.json
        for field in ("issue_number", "issue_date", "period_start", "period_end"):
            if field in data:
                setattr(issue, field, data[field] or None)
        if "content" in data:
            content = data["content"] or {}
            for overrides in content.values():
                if "html" in overrides:
                    overrides["html"] = layout_service.sanitize_html(overrides["html"])
            issue.content = content
        issue.save()

    return ok(
        issue=_issue_summary(issue),
        layout=issue.layout_snapshot,
        content=issue.content,
        values=layout_service.issue_context(issue),
        maps=_map_resolution(issue),
    )


@require_POST
def issue_element_render(request, pk, element_id):
    issue = get_object_or_404(BulletinIssue, pk=pk)
    element = layout_service.get_element(issue.layout_snapshot, element_id)
    if element is None or element.get("type") != "map":
        return fail("Map element not found", status=404)
    try:
        asset = render_map_element(element, issue, force=True)
    except MapRenderError as e:
        return fail(e, status=409)
    return ok(asset={"url": asset.file.url, "time": asset.raster_time.isoformat()})


@require_POST
def issue_generate(request, pk):
    issue = get_object_or_404(BulletinIssue, pk=pk)
    try:
        generate_pdf(issue, user=request.user)
    except PdfGenerationError as e:
        return fail(e, status=409)
    return ok(issue=_issue_summary(issue))


@require_GET
def issue_pdf(request, pk):
    issue = get_object_or_404(BulletinIssue, pk=pk)
    if not issue.pdf_file:
        return fail("No PDF generated yet", status=404)
    return FileResponse(issue.pdf_file.open("rb"), content_type="application/pdf")


@require_POST
@json_body
def issue_publish(request, pk):
    issue = get_object_or_404(BulletinIssue, pk=pk)
    live = request.json.get("live", True)
    try:
        publish_issue(issue, user=request.user, live=live)
    except (PublishError, PdfGenerationError) as e:
        return fail(e, status=409)
    page = issue.product_item_page
    return ok(
        issue=_issue_summary(issue),
        page={"id": page.pk, "title": page.title, "url": page.get_full_url()} if page else None,
    )


@require_POST
def issue_delete(request, pk):
    issue = get_object_or_404(BulletinIssue, pk=pk)
    if issue.status == issue.STATUS_PUBLISHED:
        return fail("Published issues cannot be deleted (unpublish the page first)")
    issue.delete()
    return ok()
