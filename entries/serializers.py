# entries/serializers.py
from rest_framework import serializers
from .models import Entry

class EntryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Entry
        fields = ["id", "title", "original_lang", "original_text", "meta", "date"]  

    def validate(self, attrs):
        text = attrs.get("original_text", "") or ""
        words = text.strip().split()

        if len(text.strip()) < 30 or len(words) < 3:
            raise serializers.ValidationError({
                "사유": "최소 30자 이상, 3단어 이상 입력해주세요."
        })
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        return Entry.objects.create(**validated_data)

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
