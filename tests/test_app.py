from io import BytesIO

from app import create_app


def test_home_page_loads():
    app = create_app()
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b"final payment decision is always yours" in response.data


def test_successful_upload(tmp_path):
    app = create_app()
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
    app = create_app()
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
    app = create_app()
    app.config.update(TESTING=True, UPLOAD_FOLDER=tmp_path)
    data = _valid_request_data()
    data["original_boq"] = (BytesIO(b"not a document"), "boq.txt")

    response = app.test_client().post(
        "/payment-request", data=data, content_type="multipart/form-data"
    )

    assert response.status_code == 400
    assert b"Original BOQ / quotation must be a PDF or DOCX file." in response.data


def test_invalid_payment_amount_returns_validation_error(tmp_path):
    app = create_app()
    app.config.update(TESTING=True, UPLOAD_FOLDER=tmp_path)
    data = _valid_request_data()
    data["payment_amount"] = "0"

    response = app.test_client().post(
        "/payment-request", data=data, content_type="multipart/form-data"
    )

    assert response.status_code == 400
    assert b"Requested payment amount must be a positive number." in response.data


def test_successful_form_submission_shows_uploaded_document_names(tmp_path):
    app = create_app()
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


def _valid_request_data():
    return {
        "original_boq": (BytesIO(b"sample boq"), "boq.pdf"),
        "change_order": (BytesIO(b"sample change order"), "change-order.docx"),
        "contractor_invoice": (BytesIO(b"sample invoice"), "invoice.pdf"),
        "payment_amount": "12500.00",
    }
