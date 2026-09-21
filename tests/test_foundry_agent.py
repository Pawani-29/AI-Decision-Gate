import pytest

from app import create_app
from app.services.foundry_agent import (
    CABINET_MATERIAL_QUESTION,
    FoundryAgentService,
    FoundryAgentVersionError,
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
    assert settings.dynamic_agent_version is None


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


def test_service_passes_dynamic_vector_store_through_structured_inputs():
    captured = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured["response_request"] = kwargs
            return type("Response", (), {"output_text": "Dynamic evidence reviewed."})()

    class FakeOpenAIClient:
        conversations = type(
            "Conversations",
            (),
            {"create": lambda self: type("Conversation", (), {"id": "dynamic-123"})()},
        )()
        responses = FakeResponses()

    class FakeProjectClient:
        def get_openai_client(self, **kwargs):
            captured["openai_client_args"] = kwargs
            return FakeOpenAIClient()

    service = FoundryAgentService(
        settings=FoundrySettings(
            "https://example.test/project", "existing-agent", dynamic_agent_version="7"
        ),
        credential_factory=lambda: "credential",
        project_client_factory=lambda **kwargs: FakeProjectClient(),
    )

    assert service.ask("Review this evidence.", vector_store_id="vs_user_review") == "Dynamic evidence reviewed."
    assert captured["openai_client_args"] == {}
    assert captured["response_request"]["extra_body"] == {
        "agent_reference": {"name": "existing-agent", "version": "7", "type": "agent_reference"},
        "structured_inputs": {"vector_store_id": "vs_user_review"},
    }


def test_dynamic_vector_store_requires_dynamic_agent_version():
    service = FoundryAgentService(
        settings=FoundrySettings("https://example.test/project", "existing-agent"),
        credential_factory=lambda: "credential",
        project_client_factory=lambda **kwargs: object(),
    )

    with pytest.raises(FoundryConfigurationError, match="FOUNDRY_DYNAMIC_AGENT_VERSION"):
        service.ask("Review this evidence.", vector_store_id="vs_user_review")


def test_service_creates_draft_dynamic_file_search_version_from_existing_agent():
    captured = {}

    class FakeAgents:
        def get(self, agent_name):
            captured["get_agent_name"] = agent_name
            definition = type(
                "Definition", (), {"model": "gpt-5-mini", "instructions": "Keep a human in control."}
            )()
            latest = type("Latest", (), {"definition": definition})()
            return type("Agent", (), {"versions": type("Versions", (), {"latest": latest})()})()

        def create_version(self, **kwargs):
            captured["create_version"] = kwargs
            return type("CreatedVersion", (), {"version": "12"})()

    class FakeProjectClient:
        agents = FakeAgents()

    service = FoundryAgentService(
        settings=FoundrySettings("https://example.test/project", "payment-verification-agent"),
        credential_factory=lambda: "credential",
        project_client_factory=lambda **kwargs: FakeProjectClient(),
    )

    assert service.create_dynamic_file_search_version() == "12"
    definition = captured["create_version"]["definition"]
    assert captured["get_agent_name"] == "payment-verification-agent"
    assert captured["create_version"]["draft"] is True
    assert definition.model == "gpt-5-mini"
    assert definition.instructions == "Keep a human in control."
    assert definition.tools[0].vector_store_ids == ["{{vector_store_id}}"]
    assert definition.structured_inputs["vector_store_id"].required is True


def test_dynamic_version_creation_rejects_an_unexpected_existing_model():
    class FakeAgents:
        def get(self, agent_name):
            definition = type(
                "Definition",
                (),
                {"model": "unexpected-model", "instructions": "Existing instructions"},
            )()
            latest = type("Latest", (), {"definition": definition})()
            return type("Agent", (), {"versions": type("Versions", (), {"latest": latest})()})()

    class FakeProjectClient:
        agents = FakeAgents()

    service = FoundryAgentService(
        settings=FoundrySettings("https://example.test/project", "existing-agent"),
        credential_factory=lambda: "credential",
        project_client_factory=lambda **kwargs: FakeProjectClient(),
    )

    with pytest.raises(FoundryAgentVersionError, match="gpt-5-mini"):
        service.create_dynamic_file_search_version()


def test_development_route_displays_mocked_agent_response():
    class FakeService:
        def ask(self, question):
            assert question == CABINET_MATERIAL_QUESTION
            return "The invoice material differs from the BOQ."

    app = create_app({"TESTING": True, "FOUNDRY_SERVICE_FACTORY": FakeService})
    response = app.test_client().get("/development/foundry-test")

    assert response.status_code == 200
    assert b"The invoice material differs from the BOQ." in response.data
