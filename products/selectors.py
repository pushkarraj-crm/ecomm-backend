from django.db.models import Avg, Exists, F, Min, OuterRef, Q
from .models import Category, Product, ProductVariant, Review


PRODUCT_SORT_OPTIONS = {
    'price_asc',
    'price_desc',
    'newest',
    'oldest',
    'name_asc',
    'name_desc',
}


def get_all_products(search=None, sort=None):
    products = Product.objects.select_related('category').prefetch_related(
        'variants__images'
    ).filter(is_active=True, status='approved')

    if search:
        # Each word may match any customer-visible product text or variant detail.
        # Correlated EXISTS avoids multiplying product rows across variants and
        # the expensive DISTINCT that a multi-valued join would require.
        for index, term in enumerate(search.split()):
            matching_variant = ProductVariant.objects.filter(
                product_id=OuterRef('pk'),
            ).filter(
                Q(size__icontains=term) | Q(color__icontains=term)
            )
            variant_match_alias = f'catalog_variant_match_{index}'
            products = products.alias(
                **{variant_match_alias: Exists(matching_variant)}
            ).filter(
                Q(name__icontains=term)
                | Q(description__icontains=term)
                | Q(category__name__icontains=term)
                | Q(**{variant_match_alias: True})
            )

    if sort in ('price_asc', 'price_desc'):
        products = products.annotate(
            catalog_min_price=Min(
                'variants__price',
                filter=Q(variants__stock__gt=0),
            )
        )
        price_order = (
            F('catalog_min_price').asc(nulls_last=True)
            if sort == 'price_asc'
            else F('catalog_min_price').desc(nulls_last=True)
        )
        return products.order_by(price_order, 'id')

    ordering = {
        'newest': ('-created_at', '-id'),
        'oldest': ('created_at', 'id'),
        'name_asc': ('name', 'id'),
        'name_desc': ('-name', '-id'),
    }.get(sort, ('-created_at', '-id'))
    return products.order_by(*ordering)


def get_seller_products(seller):
    return Product.objects.filter(seller=seller)


def get_seller_rating(seller):
    return Review.objects.filter(
        product__seller=seller
    ).aggregate(avg=Avg('rating'))['avg'] or 0


def get_product_detail(product_id):
    return Product.objects.select_related('category').prefetch_related(
        'variants__images'
    ).filter(id=product_id).first()


def get_category_tree(search=None):
    """Build the category picker tree from one bounded category query."""
    categories = list(Category.objects.only('id', 'name', 'parent_id').order_by('name', 'id'))
    by_id = {category.id: category for category in categories}
    included = set(by_id)
    if search:
        matched = {
            category.id for category in categories
            if search.casefold() in category.name.casefold()
        }
        included = set(matched)
        for category_id in tuple(matched):
            current = by_id[category_id]
            visited = {category_id}
            while current.parent_id in by_id and current.parent_id not in visited:
                current = by_id[current.parent_id]
                included.add(current.id)
                visited.add(current.id)

    children = {}
    for category in categories:
        if category.id not in included:
            continue
        parent_id = category.parent_id if category.parent_id in included else None
        children.setdefault(parent_id, []).append(category)

    def serialize(category, path):
        if category.id in path:
            return None
        next_path = path | {category.id}
        child_nodes = [
            node for child in children.get(category.id, [])
            if (node := serialize(child, next_path)) is not None
        ]
        return {
            'id': category.id,
            'name': category.name,
            'parent_id': category.parent_id,
            'children': child_nodes,
        }

    return [
        node for category in children.get(None, [])
        if (node := serialize(category, set())) is not None
    ]
