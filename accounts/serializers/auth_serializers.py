from rest_framework import serializers

class TossLoginSerializer(serializers.Serializer):
    authorizationCode = serializers.CharField()
    referrer = serializers.CharField(required=False, allow_blank=True)

class RefreshSerializer(serializers.Serializer):
    tossUserKey = serializers.IntegerField()
