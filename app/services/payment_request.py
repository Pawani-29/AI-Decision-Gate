"""Validation and local development storage for payment request evidence."""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping
from uuid import uuid4

from werkzeug.datastructures import FileStorage

REQUIRED_DOCUMENTS = {
    "original_boq": "Original BOQ / quotation",
    "change_order": "Approved change order",
    "contractor_invoice": "Contractor invoice",
}
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


@dataclass
class PaymentRequestResult:
    """The result of validating and storing a payment request."""

    errors: dict[str, str] = field(default_factory=dict)
    payment_amount: str = ""
    uploaded_documents: dict[str, str] = field(default_factory=dict)
    stored_documents: dict[str, Path] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def process_payment_request(
    files: Mapping[str, FileStorage], payment_amount: str, upload_folder: Path
) -> PaymentRequestResult:
    """Validate a complete request, then store its documents with generated names."""
    result = PaymentRequestResult(payment_amount=payment_amount.strip())
    _validate_documents(files, result.errors)
    _validate_payment_amount(result.payment_amount, result.errors)

    if result.errors:
        return result

    upload_folder.mkdir(parents=True, exist_ok=True)
    for field_name, display_name in REQUIRED_DOCUMENTS.items():
        uploaded_file = files[field_name]
        extension = Path(uploaded_file.filename).suffix.lower()
        stored_filename = f"{uuid4().hex}{extension}"
        stored_path = upload_folder / stored_filename
        uploaded_file.save(stored_path)
        result.uploaded_documents[display_name] = uploaded_file.filename
        result.stored_documents[display_name] = stored_path

    return result


def _validate_documents(files: Mapping[str, FileStorage], errors: dict[str, str]) -> None:
    for field_name, display_name in REQUIRED_DOCUMENTS.items():
        uploaded_file = files.get(field_name)
        if uploaded_file is None or not uploaded_file.filename:
            errors[field_name] = f"{display_name} is required."
            continue

        extension = Path(uploaded_file.filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            errors[field_name] = f"{display_name} must be a PDF or DOCX file."


def _validate_payment_amount(payment_amount: str, errors: dict[str, str]) -> None:
    try:
        amount = Decimal(payment_amount)
    except InvalidOperation:
        errors["payment_amount"] = "Requested payment amount must be a positive number."
        return

    if not amount.is_finite() or amount <= 0:
        errors["payment_amount"] = "Requested payment amount must be a positive number."
