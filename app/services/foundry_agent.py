"""Small adapter for invoking the existing Microsoft Foundry agent."""

from dataclasses import dataclass
import os
from typing import Callable, Mapping

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FileSearchTool, PromptAgentDefinition, StructuredInputDefinition
from azure.identity import DefaultAzureCredential

CABINET_MATERIAL_QUESTION = (
    "Compare the kitchen cabinet material across the BOQ, change order, "
    "and contractor invoice."
)


class FoundryConfigurationError(ValueError):
    """Raised when required Foundry environment configuration is missing."""


class FoundryRequestError(RuntimeError):
    """Raised when the existing Foundry agent cannot be reached."""


class FoundryAgentVersionError(RuntimeError):
    """Raised when a safe dynamic File Search version cannot be created."""


@dataclass(frozen=True)
class FoundrySettings:
    """Non-secret configuration used to reach the pre-existing Foundry agent."""

    project_endpoint: str
    agent_name: str
    dynamic_agent_version: str | None = None

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "FoundrySettings":
        environment = os.environ if environment is None else environment
        project_endpoint = environment.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
        agent_name = environment.get("FOUNDRY_AGENT_NAME", "").strip()
        dynamic_agent_version = environment.get("FOUNDRY_DYNAMIC_AGENT_VERSION", "").strip() or None

        if not project_endpoint or not agent_name:
            raise FoundryConfigurationError(
                "FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_AGENT_NAME must be configured."
            )

        return cls(
            project_endpoint=project_endpoint,
            agent_name=agent_name,
            dynamic_agent_version=dynamic_agent_version,
        )


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

    def ask(self, question: str, vector_store_id: str | None = None) -> str:
        """Send a question to the fixed or explicitly selected dynamic agent version."""
        if vector_store_id and not self._settings.dynamic_agent_version:
            raise FoundryConfigurationError(
                "FOUNDRY_DYNAMIC_AGENT_VERSION must be configured for dynamic File Search."
            )

        try:
            project_client = self._project_client_factory(
                endpoint=self._settings.project_endpoint,
                credential=self._credential_factory(),
            )
            if vector_store_id:
                return self._ask_with_dynamic_vector_store(
                    project_client, question, vector_store_id
                )

            openai_client = project_client.get_openai_client(agent_name=self._settings.agent_name)
            conversation = openai_client.conversations.create()
            response = openai_client.responses.create(
                conversation=conversation.id,
                input=question,
            )
        except FoundryConfigurationError:
            raise
        except Exception as error:
            raise FoundryRequestError("The Foundry agent could not be reached.") from error

        return response.output_text

    def create_dynamic_file_search_version(self) -> str:
        """Create a draft version with only a runtime-bound File Search store.

        The current working version is never updated or deleted. The created draft can
        be selected explicitly for dynamic requests after its version is configured.
        """
        try:
            project_client = self._project_client_factory(
                endpoint=self._settings.project_endpoint,
                credential=self._credential_factory(),
            )
            existing_agent = project_client.agents.get(self._settings.agent_name)
            current_definition = existing_agent.versions.latest.definition
            model = getattr(current_definition, "model", None)
            instructions = getattr(current_definition, "instructions", None)
            if model != "gpt-5-mini" or not instructions:
                raise FoundryAgentVersionError(
                    "The existing agent must provide instructions and use gpt-5-mini."
                )

            dynamic_definition = PromptAgentDefinition(
                model=model,
                instructions=instructions,
                tools=[FileSearchTool(vector_store_ids=["{{vector_store_id}}"])],
                structured_inputs={
                    "vector_store_id": StructuredInputDefinition(
                        description="Vector store ID for the current payment review.",
                        required=True,
                        schema={"type": "string"},
                    ),
                },
            )
            created_version = project_client.agents.create_version(
                agent_name=self._settings.agent_name,
                definition=dynamic_definition,
                description="Dynamic File Search candidate for payment-review evidence.",
                draft=True,
            )
        except FoundryAgentVersionError:
            raise
        except Exception as error:
            raise FoundryAgentVersionError(
                "The dynamic File Search agent version could not be created."
            ) from error

        return created_version.version

    def _ask_with_dynamic_vector_store(
        self, project_client: AIProjectClient, question: str, vector_store_id: str
    ) -> str:
        openai_client = project_client.get_openai_client()
        conversation = openai_client.conversations.create()
        response = openai_client.responses.create(
            conversation=conversation.id,
            input=question,
            extra_body={
                "agent_reference": {
                    "name": self._settings.agent_name,
                    "version": self._settings.dynamic_agent_version,
                    "type": "agent_reference",
                },
                "structured_inputs": {"vector_store_id": vector_store_id},
            },
        )
        return response.output_text
