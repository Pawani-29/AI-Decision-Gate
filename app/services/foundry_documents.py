"""Review-specific Microsoft Foundry File Search document ingestion."""

from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep
from typing import Callable, Mapping
from uuid import uuid4

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from app.services.foundry_agent import FoundrySettings

READY_STATUS = "completed"
FAILED_STATUSES = {"cancelled", "expired", "failed"}


class FoundryDocumentIngestionError(RuntimeError):
    """Raised when a review-specific vector store cannot be prepared."""


@dataclass(frozen=True)
class UploadedDocument:
    """Non-sensitive metadata for one file indexed in a review vector store."""

    document_type: str
    file_id: str
    status: str


@dataclass(frozen=True)
class ReviewDocumentIngestionResult:
    """A ready vector store and the evidence indexed for one payment review."""

    review_id: str
    vector_store_id: str
    uploaded_documents: tuple[UploadedDocument, ...]


class FoundryDocumentService:
    """Create a new, isolated File Search vector store for each payment review."""

    def __init__(
        self,
        settings: FoundrySettings | None = None,
        credential_factory: Callable[[], DefaultAzureCredential] = DefaultAzureCredential,
        project_client_factory: Callable[..., AIProjectClient] = AIProjectClient,
        sleep_function: Callable[[float], None] = sleep,
        monotonic_function: Callable[[], float] = monotonic,
    ) -> None:
        self._settings = settings or FoundrySettings.from_environment()
        self._credential_factory = credential_factory
        self._project_client_factory = project_client_factory
        self._sleep = sleep_function
        self._monotonic = monotonic_function

    def ingest_review_documents(
        self, documents: Mapping[str, Path], readiness_timeout_seconds: float = 120
    ) -> ReviewDocumentIngestionResult:
        """Create, populate, and wait for an isolated vector store to become ready."""
        review_id = uuid4().hex
        vector_store_id: str | None = None

        try:
            project_client = self._project_client_factory(
                endpoint=self._settings.project_endpoint,
                credential=self._credential_factory(),
            )
            openai_client = project_client.get_openai_client()
            vector_store = openai_client.vector_stores.create(
                name=f"payment-review-{review_id}"
            )
            vector_store_id = vector_store.id
            uploaded_documents = self._upload_documents(
                openai_client, vector_store_id, documents
            )
            self._wait_until_ready(
                openai_client, vector_store_id, readiness_timeout_seconds
            )
        except Exception as error:
            if vector_store_id is not None:
                self._cleanup_vector_store(openai_client, vector_store_id)
            if isinstance(error, FoundryDocumentIngestionError):
                raise
            raise FoundryDocumentIngestionError(
                "Review documents could not be indexed in Foundry."
            ) from error

        return ReviewDocumentIngestionResult(
            review_id=review_id,
            vector_store_id=vector_store_id,
            uploaded_documents=tuple(uploaded_documents),
        )

    def _upload_documents(self, openai_client, vector_store_id: str, documents: Mapping[str, Path]):
        uploaded_documents = []
        for document_type, document_path in documents.items():
            with document_path.open("rb") as file_handle:
                indexed_file = openai_client.vector_stores.files.upload_and_poll(
                    vector_store_id=vector_store_id,
                    file=file_handle,
                )
            status = getattr(indexed_file, "status", READY_STATUS)
            if status != READY_STATUS:
                raise FoundryDocumentIngestionError(
                    "A review document did not finish indexing."
                )
            uploaded_documents.append(
                UploadedDocument(
                    document_type=document_type,
                    file_id=indexed_file.id,
                    status=status,
                )
            )
        return uploaded_documents

    def _wait_until_ready(self, openai_client, vector_store_id: str, timeout_seconds: float) -> None:
        deadline = self._monotonic() + timeout_seconds
        while True:
            vector_store = openai_client.vector_stores.retrieve(vector_store_id)
            status = getattr(vector_store, "status", None)
            if status == READY_STATUS:
                return
            if status in FAILED_STATUSES:
                raise FoundryDocumentIngestionError(
                    "The review vector store did not become ready."
                )
            if self._monotonic() >= deadline:
                raise FoundryDocumentIngestionError(
                    "Timed out waiting for the review vector store to become ready."
                )
            self._sleep(1)

    @staticmethod
    def _cleanup_vector_store(openai_client, vector_store_id: str) -> None:
        try:
            openai_client.vector_stores.delete(vector_store_id)
        except Exception:
            # Preserve the original indexing error without disclosing service details.
            pass
