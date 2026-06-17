"""
Layout JSON schema utilities: default layout, validation, element iteration,
placeholder substitution and HTML sanitization.

Layout shape (schema_version 1):

{
  "version": 1,
  "page": {"margins_mm": [30, 12, 22, 12]},
  "header": {"rows": [...]},          # repeated on every page
  "footer": {"rows": [...]},          # repeated on every page
  "body": [                           # ordered sections
    {"id": "sec-1", "page_break_before": false, "columns_mode": "grid",
     "rows": [
       {"id": "row-1", "columns": [
         {"width": 6, "elements": [{...element...}]}
       ]}
     ]}
  ]
}

Element types: text, title, field, image, map, spacer, divider.
"""
import re
import uuid
from html.parser import HTMLParser
from io import StringIO

from django.utils import translation
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _

ELEMENT_TYPES = {"text", "title", "field", "image", "map", "spacer", "divider"}

FIELD_NAMES = {"issue_number", "issue_date", "period", "period_start", "period_end", "product_name"}

TIME_STRATEGY_MODES = {"latest_at_period_end", "latest_at_issue_date", "offset_days", "exact"}

ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "s", "br", "p", "ul", "ol", "li",
                "h1", "h2", "h3", "h4", "sub", "sup", "blockquote"}

PLACEHOLDER_RE = re.compile(r"\{(issue_number|issue_date|period|period_start|period_end|product_name)\}")


def new_element_id():
    return uuid.uuid4().hex[:12]


def default_layout():
    return {
        "version": 1,
        "page": {"margins_mm": [30, 12, 22, 12]},
        "header": {"rows": []},
        "footer": {"rows": []},
        "body": [
            {
                "id": f"sec-{new_element_id()}",
                "page_break_before": False,
                "columns_mode": "grid",
                "rows": [
                    {
                        "id": f"row-{new_element_id()}",
                        "columns": [
                            {
                                "width": 12,
                                "elements": [
                                    {
                                        "id": f"el-{new_element_id()}",
                                        "type": "title",
                                        "level": 1,
                                        "text": "{product_name}",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# iteration

def iter_rows(layout):
    for band in ("header", "footer"):
        for row in (layout.get(band) or {}).get("rows", []):
            yield row
    for section in layout.get("body", []):
        for row in section.get("rows", []):
            yield row


def iter_elements(layout):
    for row in iter_rows(layout):
        for column in row.get("columns", []):
            for element in column.get("elements", []):
                yield element


def get_element(layout, element_id):
    for element in iter_elements(layout):
        if element.get("id") == element_id:
            return element
    return None


# ---------------------------------------------------------------------------
# validation

def validate_layout(layout):
    """Structural validation. Returns a list of error strings (empty = valid)."""
    errors = []

    if not isinstance(layout, dict):
        return [str(_("Layout must be an object"))]
    if layout.get("version") != 1:
        errors.append(str(_("Unsupported layout version")))
    if not isinstance(layout.get("body"), list):
        errors.append(str(_("Layout body must be a list of sections")))
        return errors

    seen_ids = set()
    for element in iter_elements(layout):
        el_id = element.get("id")
        el_type = element.get("type")
        if not el_id:
            errors.append(str(_("Element without id")))
            continue
        if el_id in seen_ids:
            errors.append(str(_("Duplicate element id: %s")) % el_id)
        seen_ids.add(el_id)
        if el_type not in ELEMENT_TYPES:
            errors.append(str(_("Unknown element type '%(type)s' (element %(id)s)"))
                          % {"type": el_type, "id": el_id})
            continue
        if el_type == "field" and element.get("field") not in FIELD_NAMES:
            errors.append(str(_("Unknown field '%(field)s' (element %(id)s)"))
                          % {"field": element.get("field"), "id": el_id})
        if el_type == "map":
            if not element.get("layer_id"):
                errors.append(str(_("Map element %s has no layer")) % el_id)
            strategy = (element.get("time_strategy") or {}).get("mode", "latest_at_period_end")
            if strategy not in TIME_STRATEGY_MODES:
                errors.append(str(_("Unknown time strategy '%(mode)s' (element %(id)s)"))
                              % {"mode": strategy, "id": el_id})
        if el_type == "text" and element.get("html"):
            element["html"] = sanitize_html(element["html"])

    for row in iter_rows(layout):
        widths = [c.get("width", 12) for c in row.get("columns", [])]
        if widths and sum(widths) > 12:
            errors.append(str(_("Row %(id)s column widths exceed 12 units"))
                          % {"id": row.get("id", "?")})

    return errors


# ---------------------------------------------------------------------------
# placeholder substitution

def issue_context(issue):
    """Resolved placeholder values for an issue, formatted in the template language."""
    template = issue.template
    with translation.override(template.language or "en"):
        period_start = date_format(issue.period_start, "DATE_FORMAT") if issue.period_start else ""
        period_end = date_format(issue.period_end, "DATE_FORMAT") if issue.period_end else ""
        issue_date = date_format(issue.issue_date, "DATE_FORMAT") if issue.issue_date else ""
        if period_start and period_end:
            period = f"{period_start} – {period_end}"
        else:
            period = period_start or issue_date
    return {
        "issue_number": issue.issue_number or "",
        "issue_date": issue_date,
        "period": period,
        "period_start": period_start,
        "period_end": period_end,
        "product_name": template.name,
    }


def substitute(text, issue, context=None):
    if not text:
        return text
    values = context or issue_context(issue)
    return PLACEHOLDER_RE.sub(lambda m: str(values.get(m.group(1), "")), text)


# ---------------------------------------------------------------------------
# HTML sanitization (allowlist, no attributes kept)

class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = StringIO()

    def handle_starttag(self, tag, attrs):
        if tag in ALLOWED_TAGS:
            self.out.write(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in ALLOWED_TAGS and tag != "br":
            self.out.write(f"</{tag}>")

    def handle_startendtag(self, tag, attrs):
        if tag in ALLOWED_TAGS:
            self.out.write(f"<{tag}/>")

    def handle_data(self, data):
        self.out.write(
            data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )


def sanitize_html(html):
    parser = _Sanitizer()
    parser.feed(html or "")
    parser.close()
    return parser.out.getvalue()
