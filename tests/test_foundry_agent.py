import pytest

from app import create_app
from app.services.foundry_agent import (
    CABINET_MATERIAL_QUESTION,
    FoundryAgentService,
    FoundryConfigurationError,
    FoundrySettings,
)


def test_settings_reads_required_environment_values():
    settings = FoundrySettings.from_environment(
        {
            "FOUNDRY_PROJECT_ENDPOINT": "https://example.services.ai.azure.com/api/projects/demo",
            "FOUNDRY_AGENT_NAME": "payment-verification-agent",
        }
    )

    assert settings.project_endpoint.endswith("/demo")
    assert settings.agent_name == "payment-verification-agent"


def test_settings_requires_endpoint_and_agent_name():
    with pytest.raises(FoundryConfigurationError):
        FoundrySettings.from_environment({})


def test_service_sends_question_to_existing_agent_with_mocks():
    captured = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured["response_request"] = kwargs
            return type("Response", (), {"output_text": "Cabinet material requires review."})()

    class FakeConversations:
        def create(self):
            return type("Conversation", (), {"id": "conversation-123"})()

    class FakeOpenAIClient:
        conversations = FakeConversations()
        responses = FakeResponses()

    class FakeProjectClient:
        def get_openai_client(self, agent_name):
            captured["agent_name"] = agent_name
            return FakeOpenAIClient()

    def project_client_factory(**kwargs):
        captured["project_client_args"] = kwargs
        return FakeProjectClient()

    service = FoundryAgentService(
        settings=FoundrySettings("https://example.test/project", "existing-agent"),
        credential_factory=lambda: "credential",
        project_client_factory=project_client_factory,
    )

    assert service.ask(CABINET_MATERIAL_QUESTION) == "Cabinet material requires review."
    assert captured["project_client_args"]["endpoint"] == "https://example.test/project"
    assert captured["agent_name"] == "existing-agent"
    assert captured["response_request"] == {
        "conversation": "conversation-123",
        "input": CABINET_MATERIAL_QUESTION,
    }


def test_development_route_displays_mocked_agent_response():
    class FakeService:
        def ask(self, question):
            assert question == CABINET_MATERIAL_QUESTION
            return "The invoice material differs from the BOQ."

    app = create_app({"TESTING": True, "FOUNDRY_SERVICE_FACTORY": FakeService})
    response = app.test_client().get("/development/foundry-test")

    assert response.status_code == 200
    assert b"The invoice material differs from the BOQ." in response.data
