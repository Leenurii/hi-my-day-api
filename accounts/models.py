from django.db import models

class AppUser(models.Model):
    toss_user_key = models.BigIntegerField(unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

class TossOAuthToken(models.Model):
    toss_user_key = models.BigIntegerField(db_index=True)
    refresh_token = models.TextField()
    refresh_token_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
