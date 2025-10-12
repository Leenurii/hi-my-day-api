# entries/management/commands/seed_entries.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from datetime import date, timedelta
from entries.models import Entry

User = get_user_model()

class Command(BaseCommand):
    help = "Create dummy entries for calendar demo"

    def handle(self, *args, **options):
        user, _ = User.objects.get_or_create(username="devuser")
        base = date(2025, 10, 1)
        days = [0, 2, 6, 10]  # 1,3,7,11일
        for i, d in enumerate(days):
            Entry.objects.get_or_create(
                user=user,
                date=base + timedelta(days=d),
                title=f"Dummy #{i+1}",
                original_lang="en",
                original_text="This is a demo text.",
                meta={"weather": "sunny", "mood": "good"},
            )
        self.stdout.write(self.style.SUCCESS("Seeded entries."))
