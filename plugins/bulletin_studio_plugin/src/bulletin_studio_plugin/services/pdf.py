"""
PDF generation: resolve the issue's layout snapshot into a render context,
render the weasyprint HTML template, write the PDF to the issue.
"""
import logging
from pathlib import Path

from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone, translation

from . import layout as layout_service
from .map_render import MapRenderError, get_legend_for_element, render_map_element

logger = logging.getLogger(__name__)


class PdfGenerationError(Exception):
    pass


def _file_uri(django_file):
    return Path(django_file.path).as_uri()


def _image_uri(image_id):
    from wagtail.images import get_image_model
    image = get_image_model().objects.filter(pk=image_id).first()
    if image is None:
        return None
    return _file_uri(image.file)


def _resolve_element(element, issue, values, state):
    """Return a render dict for one element, or None if skipped/unresolvable."""
    overrides = (issue.content or {}).get(element.get("id"), {})
    if overrides.get("skip"):
        return None

    el_type = element.get("type")
    resolved = {"type": el_type, "id": element.get("id"), "style": element.get("style") or {}}

    if el_type == "text":
        html = overrides.get("html", element.get("html", ""))
        resolved["html"] = layout_service.substitute(
            layout_service.sanitize_html(html), issue, values)
    elif el_type == "title":
        resolved["level"] = int(element.get("level", 2))
        resolved["text"] = layout_service.substitute(element.get("text", ""), issue, values)
    elif el_type == "field":
        value = values.get(element.get("field"), "")
        resolved["text"] = f"{element.get('prefix', '')}{value}{element.get('suffix', '')}"
    elif el_type == "image":
        uri = _image_uri(element.get("image_id"))
        if uri is None:
            return None
        resolved["src"] = uri
        resolved["width_pct"] = element.get("width_pct", 100)
        resolved["alt"] = element.get("alt", "")
    elif el_type == "map":
        try:
            asset = render_map_element(element, issue)
        except MapRenderError as e:
            state["errors"].append({"element_id": element.get("id"), "message": str(e)})
            return None
        state["figure_counter"] += 1
        caption = overrides.get("caption", element.get("caption", ""))
        resolved.update({
            "src": _file_uri(asset.file),
            "figure_number": state["figure_counter"],
            "caption": layout_service.substitute(caption, issue, values),
            "legend": get_legend_for_element(element),
            "legend_position": element.get("legend_position", "below"),
        })
    elif el_type == "spacer":
        resolved["height_mm"] = element.get("height_mm", 5)
    # divider needs nothing more

    return resolved


def _resolve_rows(rows, issue, values, state):
    resolved_rows = []
    for row in rows or []:
        columns = []
        for column in row.get("columns", []):
            elements = [
                resolved for element in column.get("elements", [])
                if (resolved := _resolve_element(element, issue, values, state)) is not None
            ]
            columns.append({
                "width_pct": round(column.get("width", 12) / 12 * 100, 2),
                "elements": elements,
            })
        resolved_rows.append({"columns": columns})
    return resolved_rows


def build_render_context(issue, strict=True):
    """Walk the layout snapshot and produce the context for the PDF template.

    With strict=True, unresolvable map elements raise PdfGenerationError;
    otherwise they are silently dropped (used for previews).
    """
    layout = issue.layout_snapshot
    values = layout_service.issue_context(issue)
    state = {"figure_counter": 0, "errors": []}

    sections = []
    for section in layout.get("body", []):
        sections.append({
            "page_break_before": section.get("page_break_before", False),
            "columns_mode": section.get("columns_mode", "grid"),
            "rows": _resolve_rows(section.get("rows"), issue, values, state),
        })

    context = {
        "issue": issue,
        "template": issue.template,
        "values": values,
        "page": layout.get("page", {}),
        "margins_mm": layout.get("page", {}).get("margins_mm", [30, 12, 22, 12]),
        "header_rows": _resolve_rows((layout.get("header") or {}).get("rows"), issue, values, state),
        "footer_rows": _resolve_rows((layout.get("footer") or {}).get("rows"), issue, values, state),
        "sections": sections,
        "errors": state["errors"],
    }

    if strict and state["errors"]:
        messages = "; ".join(e["message"] for e in state["errors"])
        raise PdfGenerationError(messages)

    return context


def render_html(issue, strict=True):
    context = build_render_context(issue, strict=strict)
    with translation.override(issue.template.language or "en"):
        return render_to_string("bulletin_studio_plugin/pdf/bulletin.html", context)


def generate_pdf(issue, user=None):
    """Generate the PDF for an issue. Updates status and pdf_file in place."""
    from weasyprint import HTML

    issue.status = issue.STATUS_GENERATING
    issue.error_message = ""
    issue.save(update_fields=["status", "error_message", "updated_at"])

    try:
        html = render_html(issue, strict=True)
        pdf_bytes = HTML(string=html).write_pdf()
    except Exception as e:
        logger.exception("PDF generation failed for issue %s", issue.pk)
        issue.status = issue.STATUS_FAILED
        issue.error_message = str(e)
        issue.save(update_fields=["status", "error_message", "updated_at"])
        raise PdfGenerationError(str(e)) from e

    filename = f"{issue.template.slug}_{issue.period_start:%Y-%m-%d}"
    if issue.issue_number:
        filename += f"_no{issue.issue_number}"
    if issue.pdf_file:
        issue.pdf_file.delete(save=False)
    issue.pdf_file.save(f"{filename}.pdf", ContentFile(pdf_bytes), save=False)
    issue.status = issue.STATUS_GENERATED
    issue.generated_at = timezone.now()
    issue.save()
    return issue
