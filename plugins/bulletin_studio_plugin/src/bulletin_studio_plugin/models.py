from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from wagtail.documents import get_document_model_string

from .services.layout import default_layout


class BulletinTemplate(models.Model):
    ORIENTATIONS = [
        ("portrait", _("Portrait")),
        ("landscape", _("Landscape")),
    ]

    name = models.CharField(max_length=255, verbose_name=_("Name"))
    slug = models.SlugField(max_length=255, unique=True, verbose_name=_("Slug"))
    description = models.TextField(blank=True, default="", verbose_name=_("Description"))
    language = models.CharField(max_length=10, default="en", verbose_name=_("Language"),
                                help_text=_("Used to format dates in the generated PDF"))
    page_size = models.CharField(max_length=10, default="A4", verbose_name=_("Page size"))
    orientation = models.CharField(max_length=10, choices=ORIENTATIONS, default="portrait",
                                   verbose_name=_("Orientation"))
    layout = models.JSONField(default=default_layout, verbose_name=_("Layout"))
    schema_version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("Bulletin Template")
        verbose_name_plural = _("Bulletin Templates")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class BulletinPublishConfig(models.Model):
    """Wires a template to the climweb publication chain (snippets + pages)."""

    template = models.OneToOneField(BulletinTemplate, on_delete=models.CASCADE,
                                    related_name="publish_config")
    service_category = models.ForeignKey("base.ServiceCategory", on_delete=models.PROTECT,
                                         related_name="+", verbose_name=_("Service Category"))
    product = models.ForeignKey("base.Product", on_delete=models.PROTECT,
                                related_name="+", verbose_name=_("Product"))
    product_item_type = models.ForeignKey("base.ProductItemType", on_delete=models.PROTECT,
                                          related_name="+", verbose_name=_("Product Item Type"))
    product_page = models.ForeignKey("wagtailcore.Page", on_delete=models.PROTECT,
                                     related_name="+", verbose_name=_("Product Page"))
    valid_for_days = models.PositiveIntegerField(default=10, verbose_name=_("Valid for (days)"),
                                                 help_text=_("Fallback validity when the issue has no period end"))
    issue_title_pattern = models.CharField(max_length=255, default="{product_name} - {period}",
                                           verbose_name=_("Issue title pattern"))

    class Meta:
        verbose_name = _("Bulletin Publish Config")

    def __str__(self):
        return f"{self.template.name} → {self.product}"


class BulletinIssue(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_GENERATING = "generating"
    STATUS_GENERATED = "generated"
    STATUS_PUBLISHED = "published"
    STATUS_FAILED = "failed"
    STATUSES = [
        (STATUS_DRAFT, _("Draft")),
        (STATUS_GENERATING, _("Generating")),
        (STATUS_GENERATED, _("Generated")),
        (STATUS_PUBLISHED, _("Published")),
        (STATUS_FAILED, _("Failed")),
    ]

    template = models.ForeignKey(BulletinTemplate, on_delete=models.PROTECT, related_name="issues")
    issue_number = models.CharField(max_length=50, blank=True, default="", verbose_name=_("Issue number"))
    issue_date = models.DateField(default=timezone.now, verbose_name=_("Issue date"))
    period_start = models.DateField(verbose_name=_("Period start"))
    period_end = models.DateField(null=True, blank=True, verbose_name=_("Period end"))
    # frozen copy of template.layout at creation time: editing the template
    # never alters or breaks previously created issues
    layout_snapshot = models.JSONField(verbose_name=_("Layout snapshot"))
    # per-element overrides only: {"<element_id>": {"html": ..., "time": ..., "caption": ..., "skip": bool}}
    content = models.JSONField(default=dict, blank=True, verbose_name=_("Content overrides"))
    status = models.CharField(max_length=20, choices=STATUSES, default=STATUS_DRAFT)
    pdf_file = models.FileField(upload_to="bulletin_studio/pdfs/", blank=True, null=True)
    document = models.ForeignKey(get_document_model_string(), null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="+")
    product_item_page = models.ForeignKey("wagtailcore.Page", null=True, blank=True,
                                          on_delete=models.SET_NULL, related_name="+")
    error_message = models.TextField(blank=True, default="")
    generated_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_start", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["template", "period_start"], name="unique_issue_per_period"),
        ]
        verbose_name = _("Bulletin Issue")
        verbose_name_plural = _("Bulletin Issues")

    def __str__(self):
        return f"{self.template.name} — {self.issue_number or self.period_start}"

    @property
    def period_anchor(self):
        """The date used to resolve 'latest available' map files."""
        return self.period_end or self.issue_date


class IssueAsset(models.Model):
    """Rendered map PNG for one map element of one issue (cache)."""

    issue = models.ForeignKey(BulletinIssue, on_delete=models.CASCADE, related_name="assets")
    element_id = models.CharField(max_length=64)
    file = models.FileField(upload_to="bulletin_studio/assets/")
    params_hash = models.CharField(max_length=64)
    raster_file_id = models.IntegerField(null=True, blank=True)
    raster_time = models.DateTimeField(null=True, blank=True)
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)
    rendered_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["issue", "element_id"], name="unique_asset_per_element"),
        ]

    def __str__(self):
        return f"{self.issue_id} / {self.element_id}"


@receiver(post_delete, sender=IssueAsset)
def _delete_asset_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)


@receiver(post_delete, sender=BulletinIssue)
def _delete_issue_pdf(sender, instance, **kwargs):
    if instance.pdf_file:
        instance.pdf_file.delete(save=False)
