"""
Idempotent creation of the climweb publication chain:
ServiceCategory → Product (+ ProductCategory + ProductItemType)
→ ProductIndexPage → ProductPage.

Every step reuses existing objects when possible; re-running is a no-op.
"""
from dataclasses import dataclass, field

from django.db import transaction
from django.utils.text import slugify
from django.utils.translation import gettext as _


@dataclass
class SetupResult:
    service_category: object = None
    product: object = None
    product_category: object = None
    product_item_type: object = None
    product_index_page: object = None
    product_page: object = None
    created: dict = field(default_factory=dict)

    def as_dict(self):
        return {
            "service_category": {"id": self.service_category.pk, "name": self.service_category.name},
            "product": {"id": self.product.pk, "name": self.product.name},
            "product_category": {"id": self.product_category.pk, "name": self.product_category.name},
            "product_item_type": {"id": self.product_item_type.pk, "name": self.product_item_type.name},
            "product_index_page": {"id": self.product_index_page.pk, "title": self.product_index_page.title},
            "product_page": {"id": self.product_page.pk, "title": self.product_page.title},
            "created": self.created,
        }


@transaction.atomic
def ensure_publication_chain(
        *,
        service_category_id=None,
        service_category_name=None,
        service_icon="environment",
        product_id=None,
        product_name=None,
        temporal_resolution="dekadal",
        category_name=None,
        item_type_name=None,
        valid_for_days=10,
        product_page_title=None,
        user=None,
):
    from climweb.base.models import Product, ProductCategory, ProductItemType, ServiceCategory
    from climweb.pages.home.models import HomePage
    from climweb.pages.products.models import ProductIndexPage, ProductPage

    result = SetupResult()

    # 1. service category ---------------------------------------------------
    if service_category_id:
        result.service_category = ServiceCategory.objects.get(pk=service_category_id)
        result.created["service_category"] = False
    else:
        result.service_category, created = ServiceCategory.objects.get_or_create(
            name=service_category_name,
            defaults={"icon": service_icon},
        )
        result.created["service_category"] = created

    # 2. product snippet (+ pdf category + item type) -----------------------
    if product_id:
        result.product = Product.objects.get(pk=product_id)
        result.created["product"] = False
    else:
        result.product, created = Product.objects.get_or_create(
            variable_name=slugify(product_name).replace("-", "_"),
            defaults={"name": product_name, "temporal_resolution": temporal_resolution},
        )
        result.created["product"] = created

    category, created = ProductCategory.objects.get_or_create(
        product=result.product,
        category_format="pdf",
        defaults={"name": category_name or _("Bulletins"), "icon": "doc-full"},
    )
    result.product_category = category
    result.created["product_category"] = created

    item_type, created = ProductItemType.objects.get_or_create(
        category=category,
        name=item_type_name or _("Bulletin PDF"),
        defaults={"valid_for_days": valid_for_days},
    )
    result.product_item_type = item_type
    result.created["product_item_type"] = created

    # 3. products index page (max_count=1) ----------------------------------
    index_page = ProductIndexPage.objects.first()
    if index_page is None:
        home = HomePage.objects.first()
        if home is None:
            raise RuntimeError("No HomePage found; cannot create the products index page")
        index_page = ProductIndexPage(title=_("Products"))
        home.add_child(instance=index_page)
        index_page.save_revision(user=user).publish()
        result.created["product_index_page"] = True
    else:
        result.created["product_index_page"] = False
    result.product_index_page = index_page

    # 4. product page (one per product snippet) ------------------------------
    product_page = ProductPage.objects.filter(product=result.product).first()
    if product_page is None:
        title = product_page_title or result.product.name
        product_page = ProductPage(
            title=title,
            service=result.service_category,
            product=result.product,
            introduction_title=title,
            introduction_text=f"<p>{title}</p>",
        )
        index_page.add_child(instance=product_page)
        product_page.save_revision(user=user).publish()
        result.created["product_page"] = True
    else:
        result.created["product_page"] = False
    result.product_page = product_page

    return result
