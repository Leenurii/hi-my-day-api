# entries/admin.py
from django.contrib import admin
from .models import Entry

@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "date", "title")
    list_filter = ("date",)
    search_fields = ("title", "original_text")
