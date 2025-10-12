# entries/serializers.py
from rest_framework import serializers
from .models import Entry

class EntryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Entry
        fields = ["id", "title", "original_lang", "original_text", "meta", "date"]  

    def validate(self, attrs):
        text = attrs.get("original_text", "") or ""
        if len(text.strip().split()) < 3:
            raise serializers.ValidationError({"original_text": "내용이 너무 짧아요."})
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        return Entry.objects.create(user=user, **validated_data)

class EntryDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Entry
        fields = [
            "id", "date", "title", "original_lang", "original_text",
            "meta", "analysis", "created_at", "updated_at"
        ]

class EntryListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Entry
        fields = ["id", "date", "title", "meta"]
