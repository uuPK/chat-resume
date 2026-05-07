from app.infra.config import settings
from app.services.digital_human.volcengine_service import VolcengineVoiceService


def test_volcengine_voice_service_requires_app_id_and_access_key(monkeypatch):
    monkeypatch.setattr(settings, "VOLCENGINE_DIALOGUE_APP_ID", "")
    monkeypatch.setattr(settings, "VOLCENGINE_DIALOGUE_ACCESS_KEY", "access-key")

    service = VolcengineVoiceService()

    assert service.is_configured() is False


def test_volcengine_voice_service_builds_correct_headers(monkeypatch):
    monkeypatch.setattr(settings, "VOLCENGINE_DIALOGUE_APP_ID", "123456789")
    monkeypatch.setattr(settings, "VOLCENGINE_DIALOGUE_ACCESS_KEY", "access-key")
    monkeypatch.setattr(settings, "VOLCENGINE_DIALOGUE_RESOURCE_ID", "resource-id")

    service = VolcengineVoiceService()

    assert service.is_configured() is True
    assert service.build_headers("connect-id") == {
        "X-Api-App-Key": "PlgvMymc7f3tQnJ6",
        "X-Api-App-ID": "123456789",
        "X-Api-Access-Key": "access-key",
        "X-Api-Resource-Id": "resource-id",
        "X-Api-Connect-Id": "connect-id",
    }
