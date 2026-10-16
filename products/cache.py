from uuid import uuid4
from django.core.cache import cache


def catalog_revision():
    return cache.get('catalog:revision', 'initial')


def invalidate_catalog():
    cache.set('catalog:revision', uuid4().hex, timeout=None)
