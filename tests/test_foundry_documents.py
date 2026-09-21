from pathlib import Path

import pytest

from app.services.foundry_documents import (
    FoundryDocumentIngestionError,
    FoundryDocumentService,
)
from app.services.foundry_agent import FoundrySettings


def test_ingestion_creates_vector_store_uploads_three_files_and_waits_for_ready(tmp_path):
    documents = _create_documents(tmp_path)
    captured = {"uploaded": [], "statuses": iter(["in_progress", "completed"])}

    class FakeVectorStoreFiles:
        def upload_and_poll(self, *, vector_store_id, file):
            captured["uploaded"].append((vector_store_id, Path(file.name).name))
            return type("VectorStoreFile", (), {"id": f"file-{len(captured['uploaded'])}", "status": "completed"})()

    class FakeVectorStores:
        files = FakeVectorStoreFiles()

        def create(self, *, name):
            captured["store_name"] = name
            return type("VectorStore", (), {"id": "vs-review-123"})()

        def retrieve(self, vector_store_id):
            captured.setdefault("retrieved", []).append(vector_store_id)
            return type("VectorStore", (), {"status": next(captured["statuses"])})()

        def delete(self, vector_store_id):
            captured["deleted"] = vector_store_id

    class FakeOpenAIClient:
        vector_stores = FakeVectorStores()

    class FakeProjectClient:
        def get_openai_client(self):
            return FakeOpenAIClient()

    service = FoundryDocumentService(
        settings=FoundrySettings("https://example.test/project", "existing-agent"),
        credential_factory=lambda: "credential",
        project_client_factory=lambda **kwargs: FakeProjectClient(),
        sleep_function=lambda seconds: captured.setdefault("sleeps", []).append(seconds),
    )

    result = service.ingest_review_documents(documents)

    assert result.vector_store_id == "vs-review-123"
    assert len(result.review_id) == 32
    assert captured["store_name"] == f"payment-review-{result.review_id}"
    assert captured["uploaded"] == [
        ("vs-review-123", "boq.pdf"),
        ("vs-review-123", "change-order.pdf"),
        ("vs-review-123", "invoice.pdf"),
    ]
    assert [document.file_id for document in result.uploaded_documents] == ["file-1", "file-2", "file-3"]
    assert captured["retrieved"] == ["vs-review-123", "vs-review-123"]
    assert captured["sleeps"] == [1]
    assert "deleted" not in captured


def test_ingestion_cleans_up_new_vector_store_when_upload_fails(tmp_path):
    documents = _create_documents(tmp_path)
    captured = {"upload_calls": 0}

    class FakeVectorStoreFiles:
        def upload_and_poll(self, *, vector_store_id, file):
            captured["upload_calls"] += 1
            if captured["upload_calls"] == 2:
                raise RuntimeError("indexing failed")
            return type("VectorStoreFile", (), {"id": "file-1", "status": "completed"})()

    class FakeVectorStores:
        files = FakeVectorStoreFiles()

        def create(self, *, name):
            return type("VectorStore", (), {"id": "vs-created-for-cleanup"})()

        def delete(self, vector_store_id):
            captured["deleted"] = vector_store_id

    class FakeOpenAIClient:
        vector_stores = FakeVectorStores()

    class FakeProjectClient:
        def get_openai_client(self):
            return FakeOpenAIClient()

    service = FoundryDocumentService(
        settings=FoundrySettings("https://example.test/project", "existing-agent"),
        credential_factory=lambda: "credential",
        project_client_factory=lambda **kwargs: FakeProjectClient(),
    )

    with pytest.raises(FoundryDocumentIngestionError, match="could not be indexed"):
        service.ingest_review_documents(documents)

    assert captured["upload_calls"] == 2
    assert captured["deleted"] == "vs-created-for-cleanup"


def test_ingestion_cleans_up_new_vector_store_when_readiness_fails(tmp_path):
    documents = _create_documents(tmp_path)
    captured = {}

    class FakeVectorStoreFiles:
        def upload_and_poll(self, *, vector_store_id, file):
            return type("VectorStoreFile", (), {"id": "file", "status": "completed"})()

    class FakeVectorStores:
        files = FakeVectorStoreFiles()

        def create(self, *, name):
            return type("VectorStore", (), {"id": "vs-not-ready"})()

        def retrieve(self, vector_store_id):
            return type("VectorStore", (), {"status": "failed"})()

        def delete(self, vector_store_id):
            captured["deleted"] = vector_store_id

    class FakeOpenAIClient:
        vector_stores = FakeVectorStores()

    class FakeProjectClient:
        def get_openai_client(self):
            return FakeOpenAIClient()

    service = FoundryDocumentService(
        settings=FoundrySettings("https://example.test/project", "existing-agent"),
        credential_factory=lambda: "credential",
        project_client_factory=lambda **kwargs: FakeProjectClient(),
    )

    with pytest.raises(FoundryDocumentIngestionError, match="did not become ready"):
        service.ingest_review_documents(documents)

    assert captured["deleted"] == "vs-not-ready"


def _create_documents(directory: Path) -> dict[str, Path]:
    documents = {
        "Original BOQ / quotation": directory / "boq.pdf",
        "Approved change order": directory / "change-order.pdf",
        "Contractor invoice": directory / "invoice.pdf",
    }
    for document in documents.values():
        document.write_bytes(b"fictional evidence")
    return documents
