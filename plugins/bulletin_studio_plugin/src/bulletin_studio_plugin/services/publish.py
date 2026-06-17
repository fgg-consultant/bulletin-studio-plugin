"""
Publication of a generated issue through the standard climweb chain:
wagtail Document (with PDF thumbnail) + ProductItemPage with a
`document_product` block, created/updated under the wired ProductPage.
"""
import logging
from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext as _

from .layout import issue_context, substitute
from .pdf import generate_pdf

logger = logging.getLogger(__name__)


class PublishError(Exception):
    pass


def _ensure_document(issue, title, user):
    """Create or update the wagtail Document holding the issue PDF.

    Re-publishing reuses the same Document pk so download URLs stay stable.
    """
    from wagtail.documents import get_document_model
    Document = get_document_model()

    issue.pdf_file.open("rb")
    try:
        pdf_content = issue.pdf_file.read()
    finally:
        issue.pdf_file.close()

    filename = issue.pdf_file.name.rsplit("/", 1)[-1]

    document = issue.document
    if document is not None:
        document.file.delete(save=False)
        from django.core.files.base import ContentFile
        document.file.save(filename, ContentFile(pdf_content), save=False)
        document.title = title
        document.thumbnail = None  # force regeneration from the new first page
        document.save()
    else:
        from django.core.files.base import ContentFile
        document = Document(title=title, uploaded_by_user=user)
        document.file.save(filename, ContentFile(pdf_content), save=True)

    thumbnail = None
    if hasattr(document, "get_thumbnail"):
        thumbnail = document.get_thumbnail()
    return document, thumbnail


def publish_issue(issue, user=None, live=True):
    """Publish an issue: document + ProductItemPage under the wired ProductPage."""
    from climweb.pages.products.models import ProductItemPage

    config = getattr(issue.template, "publish_config", None)
    if config is None:
        raise PublishError(_("This template is not wired to a publication chain yet. "
                             "Run the setup assistant first."))

    if issue.status not in (issue.STATUS_GENERATED, issue.STATUS_PUBLISHED) or not issue.pdf_file:
        generate_pdf(issue, user=user)

    values = issue_context(issue)
    title = substitute(config.issue_title_pattern, issue, values)
    valid_until = issue.period_end or issue.period_start + timedelta(days=config.valid_for_days)

    document, thumbnail = _ensure_document(issue, title, user)

    stream_data = [{
        "type": "document_product",
        "value": {
            "product_type": str(config.product_item_type_id),
            "date": issue.period_start.isoformat(),
            "valid_until": valid_until.isoformat(),
            "document": document.pk,
            "auto_generate_thumbnail": True,
            "thumbnail": thumbnail.pk if thumbnail else None,
            "description": "",
        },
    }]

    parent = config.product_page.specific
    page = issue.product_item_page.specific if issue.product_item_page else None

    if page is None:
        page = ProductItemPage(
            title=title,
            date=issue.period_start,
            valid_until=valid_until,
        )
        page.products = page.products.stream_block.to_python(stream_data)
        parent.add_child(instance=page)
    else:
        page.title = title
        page.draft_title = title
        page.date = issue.period_start
        page.valid_until = valid_until
        page.products = page.products.stream_block.to_python(stream_data)

    revision = page.save_revision(user=user)
    if live:
        revision.publish()

    issue.document = document
    issue.product_item_page = page
    issue.status = issue.STATUS_PUBLISHED
    issue.published_at = timezone.now()
    issue.save()
    return issue
