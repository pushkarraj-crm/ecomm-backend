from django.db import transaction
from django.db.models.signals import post_save, post_delete
from .cache import invalidate_catalog
from .models import Category, Product, ProductVariant, ProductImage, Review
from sellers.models import SellerProfile
from accounts.models import User


def catalog_changed(sender, **kwargs):
    transaction.on_commit(invalidate_catalog)


for model in (
    Category,
    Product,
    ProductVariant,
    ProductImage,
    Review,
    SellerProfile,
    User,
):
    post_save.connect(
        catalog_changed, sender=model, dispatch_uid=f"catalog-save-{model.__name__}"
    )
    post_delete.connect(
        catalog_changed, sender=model, dispatch_uid=f"catalog-delete-{model.__name__}"
    )
