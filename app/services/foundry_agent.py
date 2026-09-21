"""Small adapter for invoking the existing Microsoft Foundry agent."""

from dataclasses import dataclass
import os
from typing import Callable, Mapping

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

CABINET_MATERIAL_QUESTION = (
    "Compare the kitchen cabinet material across the BOQ, change order, "
    "and contractor invoice."
)


class FoundryConfigurationError(ValueError):
    """Raised when required Foundry environment configuration is missing."""


class FoundryRequestError(RuntimeError):
    """Raised when the existing Foundry agent cannot be reached."""


@dataclass(frozen=True)
class FoundrySettings:
    """Non-secret configuration used to reach the pre-existing Foundry agent."""

    project_endpoint: str
    agent_name: str

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "FoundrySettings":
        environment = environment or os.environ
        project_endpoint = environment.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
        agent_name = environment.get("FOUNDRY_AGENT_NAME", "").strip()

        if not project_endpoint or not agent_name:
            raise FoundryConfigurationError(
                "FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_AGENT_NAME must be configured."
            )

        return cls(project_endpoint=project_endpoint, agent_name=agent_name)


class FoundryAgentService:
    """Invoke an existing Foundry agent without changing its stored configuration."""

    def __init__(
        self,
        settings: FoundrySettings | None = None,
        credential_factory: Callable[[], DefaultAzureCredential] = DefaultAzureCredential,
        project_client_factory: Callable[..., AIProjectClient] = AIProjectClient,
    ) -> None:
        self._settings = settings or FoundrySettings.from_environment()
        self._credential_factory = credential_factory
        self._project_client_factory = project_client_factory

    def ask(self, question: str) -> str:
        """Send one question to the configured existing agent in a new conversation."""
        try:
            project_client = self._project_client_factory(
                endpoint=self._settings.project_endpoint,
                credential=self._credential_factory(),
            )
            openai_client = project_client.get_openai_client(agent_name=self._settings.agent_name)
            conversation = openai_client.conversations.create()
            response = openai_client.responses.create(
                conversation=conversation.id,
                input=question,
            )
        except Exception as error:
            raise FoundryRequestError("The Foundry agent could not be reached.") from error

        return response.output_text
