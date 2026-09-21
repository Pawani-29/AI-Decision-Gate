from io import BytesIO
import json

from app import create_app
from app.services.foundry_agent import (
    PAYMENT_REVIEW_QUESTION,
    FoundryConfigurationError,
    FoundryRequestError,
)
from app.services.foundry_documents import FoundryDocumentIngestionError

SAMPLE_AGENT_STRUCTURED_JSON = json.dumps({
    "invoice_total_stated": 12500.00,
    "invoice_items": [
        {
            "description": "Cabinet installation",
            "quantity": 10,
            "unit": "units",
            "unit_rate": 1250.00,
            "stated_total": 12500.00,
            "boq_quantity": 10,
            "boq_unit_rate": 1250.00,
        }
    ],
    "matches": [
        {"title": "Cabinet Scope", "description": "10 units match quotation.", "source_reference": "BOQ #1"}
    ],
    "approved_changes": [
        {"title": "Handle upgrade", "description": "Approved in CO-1.", "source_reference": "CO-1"}
    ],
    "possible_mismatches": [
        {"title": "Plywood spec", "description": "Commercial plywood substituted.", "source_reference": "CO-1"}
    ],
    "missing_evidence": [
        {"title": "Delivery receipt", "description": "Receipt not provided.", "source_reference": "Site log"}
    ],
    "human_verification_required": [
        {"title": "Check cabinet thickness", "description": "Verify 18mm thickness before payment.", "source_reference": "Inspection"}
    ],
})


class FakeDocumentService:
    def ingest_review_documents(self, documents):
        return type(
            "IngestionResult",
            (),
            {
                "review_id": "review-test",
                "vector_store_id": "vs-test",
                "uploaded_documents": (),
            },
        )()


class FakeFoundryAgentService:
    def ask(self, question, vector_store_id=None, json_output=False):
        if json_output:
            return SAMPLE_AGENT_STRUCTURED_JSON
        return f"Mock analysis for {vector_store_id}: {question}"


def create_test_app(extra_config=None):
    config = {
        "TESTING": True,
        "FOUNDRY_DOCUMENT_SERVICE_FACTORY": FakeDocumentService,
        "FOUNDRY_SERVICE_FACTORY": FakeFoundryAgentService,
    }
    if extra_config:
        config.update(extra_config)
    return create_app(config)


def test_home_page_loads():
    app = create_test_app()
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b"final payment decision is always yours" in response.data


def test_successful_upload(tmp_path):
    app = create_test_app()
    app.config.update(TESTING=True, UPLOAD_FOLDER=tmp_path)

    response = app.test_client().post(
        "/payment-request",
        data=_valid_request_data(),
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"Documents received for human review" in response.data
    saved_files = list(tmp_path.iterdir())
    assert len(saved_files) == 3
    assert all(file.name != "boq.pdf" for file in saved_files)


def test_missing_required_document_returns_validation_error(tmp_path):
    app = create_test_app()
    app.config.update(TESTING=True, UPLOAD_FOLDER=tmp_path)
    data = _valid_request_data()
    del data["contractor_invoice"]

    response = app.test_client().post(
        "/payment-request", data=data, content_type="multipart/form-data"
    )

    assert response.status_code == 400
    assert b"Contractor invoice is required." in response.data
    assert not tmp_path.exists() or not list(tmp_path.iterdir())


def test_unsupported_file_type_returns_validation_error(tmp_path):
    app = create_test_app()
    app.config.update(TESTING=True, UPLOAD_FOLDER=tmp_path)
    data = _valid_request_data()
    data["original_boq"] = (BytesIO(b"not a document"), "boq.txt")

    response = app.test_client().post(
        "/payment-request", data=data, content_type="multipart/form-data"
    )

    assert response.status_code == 400
    assert b"Original BOQ / quotation must be a PDF or DOCX file." in response.data


def test_invalid_payment_amount_returns_validation_error(tmp_path):
    app = create_test_app()
    app.config.update(TESTING=True, UPLOAD_FOLDER=tmp_path)
    data = _valid_request_data()
    data["payment_amount"] = "0"

    response = app.test_client().post(
        "/payment-request", data=data, content_type="multipart/form-data"
    )

    assert response.status_code == 400
    assert b"Requested payment amount must be a positive number." in response.data


def test_successful_form_submission_shows_uploaded_document_names(tmp_path):
    app = create_test_app()
    app.config.update(TESTING=True, UPLOAD_FOLDER=tmp_path)

    response = app.test_client().post(
        "/payment-request",
        data=_valid_request_data(),
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"boq.pdf" in response.data
    assert b"change-order.docx" in response.data
    assert b"invoice.pdf" in response.data
    assert b"Nothing has been approved or rejected." in response.data
    assert b"review-test" in response.data
    assert b"vs-test" in response.data
    assert b"Decision Gate Report" in response.data
    assert b"Matches" in response.data
    assert b"10 units match quotation" in response.data
    assert b"Approved Changes" in response.data
    assert b"Handle upgrade" in response.data
    assert b"Possible Mismatches" in response.data
    assert b"Commercial plywood substituted" in response.data
    assert b"Missing Evidence" in response.data
    assert b"Delivery receipt" in response.data
    assert b"Human Verification Required" in response.data
    assert b"Check cabinet thickness" in response.data
    assert b"Deterministic arithmetic status" in response.data
    assert b"Arithmetic verified" in response.data
    assert b"The final payment decision is always yours." in response.data
    assert b"Original AI Evidence Analysis (Traceability)" in response.data


def test_successful_form_submission_invokes_agent_with_review_vector_store(tmp_path):
    captured = {}

    class SpyingAgentService:
        def ask(self, question, vector_store_id=None, json_output=False):
            captured["question"] = question
            captured["vector_store_id"] = vector_store_id
            captured["json_output"] = json_output
            return SAMPLE_AGENT_STRUCTURED_JSON

    app = create_test_app({"FOUNDRY_SERVICE_FACTORY": SpyingAgentService})
    app.config.update(TESTING=True, UPLOAD_FOLDER=tmp_path)

    response = app.test_client().post(
        "/payment-request",
        data=_valid_request_data(),
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert captured["vector_store_id"] == "vs-test"
    assert captured["question"] == PAYMENT_REVIEW_QUESTION
    assert captured["json_output"] is True
    assert b"Decision Gate Report" in response.data


def test_form_submission_handles_malformed_ai_output_gracefully(tmp_path):
    class MalformedAgentService:
        def ask(self, question, vector_store_id=None, json_output=False):
            return "This is unformatted model prose with no JSON structure."

    app = create_test_app({"FOUNDRY_SERVICE_FACTORY": MalformedAgentService})
    app.config.update(TESTING=True, UPLOAD_FOLDER=tmp_path)

    response = app.test_client().post(
        "/payment-request",
        data=_valid_request_data(),
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"Decision Gate Report" in response.data
    assert b"Unstructured Analysis Output" in response.data
    assert b"This is unformatted model prose with no JSON structure." in response.data
    assert b"Unable to verify arithmetic automatically" in response.data


def test_agent_failure_returns_bad_gateway(tmp_path):
    class FailingAgentService:
        def ask(self, question, vector_store_id=None):
            raise FoundryRequestError("Agent unreachable")

    app = create_test_app({"FOUNDRY_SERVICE_FACTORY": FailingAgentService})
    app.config.update(TESTING=True, UPLOAD_FOLDER=tmp_path)

    response = app.test_client().post(
        "/payment-request",
        data=_valid_request_data(),
        content_type="multipart/form-data",
    )

    assert response.status_code == 502
    assert (
        b"Documents were indexed, but the payment verification agent could not analyze the evidence."
        in response.data
    )


def test_ingestion_failure_returns_bad_gateway(tmp_path):
    class FailingDocumentService:
        def ingest_review_documents(self, documents):
            raise FoundryDocumentIngestionError("Ingestion failed")

    app = create_test_app({"FOUNDRY_DOCUMENT_SERVICE_FACTORY": FailingDocumentService})
    app.config.update(TESTING=True, UPLOAD_FOLDER=tmp_path)

    response = app.test_client().post(
        "/payment-request",
        data=_valid_request_data(),
        content_type="multipart/form-data",
    )

    assert response.status_code == 502
    assert (
        b"Documents were saved locally, but could not be prepared for Foundry review."
        in response.data
    )


def _valid_request_data():
    return {
        "original_boq": (BytesIO(b"sample boq"), "boq.pdf"),
        "change_order": (BytesIO(b"sample change order"), "change-order.docx"),
        "contractor_invoice": (BytesIO(b"sample invoice"), "invoice.pdf"),
        "payment_amount": "12500.00",
    }
