"""
End-to-end smoke test (no UI): publication chain → template → issue
→ PDF generation → publication as a ProductItemPage.

Run inside the climweb container:
    climweb bulletin_studio_smoke
Re-runnable: every step reuses existing objects.
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from bulletin_studio_plugin.models import BulletinIssue, BulletinPublishConfig, BulletinTemplate
from bulletin_studio_plugin.services.layout import new_element_id
from bulletin_studio_plugin.services.pdf import generate_pdf
from bulletin_studio_plugin.services.publish import publish_issue
from bulletin_studio_plugin.services.setup_chain import ensure_publication_chain

TEMPLATE_SLUG = "smoke-bulletin"


def seed_layout(map_layer_id=None):
    body_elements = [
        {"id": f"el-{new_element_id()}", "type": "title", "level": 2,
         "text": "Situation overview"},
        {"id": f"el-{new_element_id()}", "type": "text", "editable": True,
         "html": "<p>Prose placeholder — filled per issue.</p>"},
        {"id": f"el-{new_element_id()}", "type": "divider"},
    ]
    columns = [{"width": 12 if not map_layer_id else 6, "elements": body_elements}]
    if map_layer_id:
        columns.append({"width": 6, "elements": [{
            "id": f"el-{new_element_id()}", "type": "map",
            "layer_id": str(map_layer_id),
            "time_strategy": {"mode": "latest_at_period_end"},
            "show_boundaries": True, "show_legend": True,
            "caption": "Situation map for {period}",
        }]})

    return {
        "version": 1,
        "page": {"margins_mm": [30, 12, 22, 12]},
        "header": {"rows": [{"id": f"row-{new_element_id()}", "columns": [
            {"width": 8, "elements": [{"id": f"el-{new_element_id()}", "type": "title",
                                       "level": 1, "text": "{product_name}"}]},
            {"width": 4, "elements": [{"id": f"el-{new_element_id()}", "type": "field",
                                       "field": "period", "prefix": "Period: "}]},
        ]}]},
        "footer": {"rows": [{"id": f"row-{new_element_id()}", "columns": [
            {"width": 12, "elements": [{"id": f"el-{new_element_id()}", "type": "field",
                                        "field": "issue_number", "prefix": "Issue No "}]},
        ]}]},
        "body": [{"id": f"sec-{new_element_id()}", "page_break_before": False,
                  "columns_mode": "grid",
                  "rows": [{"id": f"row-{new_element_id()}", "columns": columns}]}],
    }


class Command(BaseCommand):
    help = "Bulletin Studio end-to-end smoke test (setup → template → issue → PDF → publish)"

    def add_arguments(self, parser):
        parser.add_argument("--with-map", action="store_true",
                            help="Include a map element (requires a raster layer with files)")
        parser.add_argument("--skip-publish", action="store_true")

    def handle(self, *args, **options):
        user = get_user_model().objects.filter(is_superuser=True).first()

        self.stdout.write("1. Publication chain...")
        result = ensure_publication_chain(
            service_category_name="Agriculture",
            product_name="Smoke Test Bulletin",
            temporal_resolution="dekadal",
            user=user,
        )
        self.stdout.write(self.style.SUCCESS(f"   {result.as_dict()['created']}"))

        map_layer_id = None
        if options["with_map"]:
            from geomanager.models import RasterFileLayer
            layer = RasterFileLayer.objects.filter(raster_files__isnull=False).first()
            if layer:
                map_layer_id = layer.pk
                self.stdout.write(f"   using raster layer: {layer.title}")
            else:
                self.stdout.write(self.style.WARNING("   no raster layer with files — map skipped"))

        self.stdout.write("2. Template...")
        template, created = BulletinTemplate.objects.get_or_create(
            slug=TEMPLATE_SLUG,
            defaults={"name": "Smoke Test Bulletin", "language": "en", "created_by": user},
        )
        template.layout = seed_layout(map_layer_id)
        template.save()
        BulletinPublishConfig.objects.update_or_create(
            template=template,
            defaults={
                "service_category": result.service_category,
                "product": result.product,
                "product_item_type": result.product_item_type,
                "product_page": result.product_page,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"   template #{template.pk} ({'created' if created else 'updated'})"))

        self.stdout.write("3. Issue...")
        today = datetime.date.today()
        issue, created = BulletinIssue.objects.get_or_create(
            template=template,
            period_start=today.replace(day=1),
            defaults={
                "issue_number": "1",
                "issue_date": today,
                "period_end": today,
                "layout_snapshot": template.layout,
                "created_by": user,
            },
        )
        if not created:
            issue.layout_snapshot = template.layout
            issue.save(update_fields=["layout_snapshot", "updated_at"])
        # simulate the per-issue prose edit
        text_el = next(e for e in issue.layout_snapshot["body"][0]["rows"][0]["columns"][0]["elements"]
                       if e["type"] == "text")
        issue.content = {text_el["id"]: {"html": "<p>Filled-in analysis text for the smoke test, "
                                                 "<b>with bold</b> and sanitized <script>html</script>.</p>"}}
        issue.save(update_fields=["content", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"   issue #{issue.pk} ({'created' if created else 'reused'})"))

        self.stdout.write("4. PDF generation (weasyprint)...")
        generate_pdf(issue, user=user)
        self.stdout.write(self.style.SUCCESS(f"   {issue.pdf_file.path} ({issue.pdf_file.size} bytes)"))

        if options["skip_publish"]:
            self.stdout.write(self.style.SUCCESS("Done (publish skipped)."))
            return

        self.stdout.write("5. Publish (document + ProductItemPage)...")
        publish_issue(issue, user=user, live=True)
        page = issue.product_item_page
        self.stdout.write(self.style.SUCCESS(
            f"   page #{page.pk} '{page.title}' live={page.live} url={page.get_url()}"
        ))
        self.stdout.write(self.style.SUCCESS("Smoke test OK."))
