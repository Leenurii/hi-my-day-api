# entries/models.py
from django.conf import settings
from django.db import models
from datetime import date as date_func

class Entry(models.Model):
    LANG_CHOICES = (("en", "English"), ("ko", "Korean"))

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="entries")
    date = models.DateField(default=date_func.today)  # KST 기준(SETTINGS: USE_TZ=False 가정)
    title = models.CharField(max_length=200)
    original_lang = models.CharField(max_length=2, choices=LANG_CHOICES)
    original_text = models.TextField()
    meta = models.JSONField(default=dict, blank=True)  # {"weather": "...", "mood": "..."}
    analysis = models.JSONField(null=True, blank=True) # 저장 후 analyze에서 채움

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"[{self.date}] {self.title} (user={self.user_id})"
