import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from products.models import Category
from products.cache import invalidate_catalog

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "marketplace_categories.json"


class Command(BaseCommand):
    help = "Add the reviewed marketplace category hierarchy, preserving existing categories and product assignments."

    @transaction.atomic
    def handle(self, *args, **options):
        dataset = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        existing = {}
        for category in Category.objects.order_by("pk"):
            existing.setdefault(
                (category.parent_id, category.name.casefold()), category
            )
        created = reused = 0
        level = [(node, None) for node in dataset["categories"]]
        while level:
            pending = {}
            resolved = []
            for node, parent_id in level:
                name = node["name"].strip()
                if not name or len(name) > 100:
                    raise ValueError("Category names must contain 1 to 100 characters.")
                key = (parent_id, name.casefold())
                category = existing.get(key) or pending.get(key)
                if category is None:
                    category = Category(parent_id=parent_id, name=name)
                    pending[key] = category
                    created += 1
                else:
                    reused += 1
                resolved.append((node, category))
            # The source is a tree with parents from the previous level. Bulk insert
            # avoids hundreds of round trips; invalidate catalog once after commit.
            Category.objects.bulk_create(list(pending.values()))
            existing.update(pending)
            level = [
                (child, category.pk)
                for node, category in resolved
                for child in node.get("children", [])
            ]
        transaction.on_commit(invalidate_catalog)
        self.stdout.write(
            self.style.SUCCESS(
                f"Categories added: {created}; existing paths reused: {reused}."
            )
        )
