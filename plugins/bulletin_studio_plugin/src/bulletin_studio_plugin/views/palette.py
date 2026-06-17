"""Read-only JSON endpoints feeding the editor sidebars and the setup wizard."""
from django.views.decorators.http import require_GET

from ._helpers import ok, fail


@require_GET
def geomanager_tree(request):
    """Category → Dataset → raster layers tree, one call for the cascading selects."""
    from geomanager.models import Category, Dataset

    categories = []
    for category in Category.objects.all().order_by("order", "title"):
        datasets = []
        dataset_qs = Dataset.objects.filter(category=category, layer_type="raster_file")
        for dataset in dataset_qs:
            layers = []
            for layer in dataset.raster_file_layers.all():
                latest = layer.raster_files.order_by("-time").first()
                layers.append({
                    "id": str(layer.pk),
                    "title": layer.title,
                    "has_style": layer.style_id is not None,
                    "file_count": layer.raster_files.count(),
                    "latest_time": latest.time.isoformat() if latest else None,
                })
            if layers:
                datasets.append({"id": str(dataset.pk), "title": dataset.title, "layers": layers})
        if datasets:
            categories.append({"id": category.pk, "title": category.title, "datasets": datasets})

    return ok(categories=categories)


@require_GET
def layer_timestamps(request, layer_id):
    from geomanager.models import RasterFileLayer

    layer = RasterFileLayer.objects.filter(pk=layer_id).first()
    if layer is None:
        return fail("Layer not found", status=404)
    timestamps = list(layer.raster_files.order_by("-time").values_list("time", flat=True))
    return ok(timestamps=[t.isoformat() for t in timestamps])


@require_GET
def publication_palette(request):
    """Existing publication-chain objects for the setup wizard pickers."""
    from climweb.base.models import Product, ServiceCategory
    from climweb.pages.products.models import ProductIndexPage, ProductPage

    services = [{"id": s.pk, "name": s.name, "icon": s.icon}
                for s in ServiceCategory.objects.all()]

    products = []
    for product in Product.objects.all():
        categories = []
        for category in product.categories.all():
            categories.append({
                "id": category.pk,
                "name": category.name,
                "format": category.category_format,
                "item_types": [{"id": it.pk, "name": it.name}
                               for it in category.product_item_types.all()],
            })
        products.append({"id": product.pk, "name": product.name, "categories": categories})

    index_page = ProductIndexPage.objects.first()
    product_pages = [{"id": p.pk, "title": p.title, "product_id": p.product_id}
                     for p in ProductPage.objects.all()]

    return ok(
        services=services,
        products=products,
        product_index_page={"id": index_page.pk, "title": index_page.title} if index_page else None,
        product_pages=product_pages,
    )
