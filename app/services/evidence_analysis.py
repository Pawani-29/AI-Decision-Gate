"""Structured findings model and deterministic arithmetic checks for payment verification."""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, Iterable, Mapping, Sequence


def to_optional_decimal(value: Any) -> Decimal | None:
    """Convert a string or numeric value to Decimal, returning None on failure or empty input."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if not cleaned:
            return None
        # Remove currency symbols if present like INR, $, Rs.
        cleaned = re.sub(r"^[^\d\-+.]+", "", cleaned).strip()
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None
    return None


@dataclass(frozen=True)
class InvoiceItem:
    """A line item extracted from the contractor invoice."""

    description: str
    quantity: Decimal | None = None
    unit: str | None = None
    unit_rate: Decimal | None = None
    stated_total: Decimal | None = None
    boq_quantity: Decimal | None = None
    boq_unit_rate: Decimal | None = None
    boq_total: Decimal | None = None


@dataclass(frozen=True)
class LineItemCheck:
    """Deterministic arithmetic and difference analysis for one line item."""

    description: str
    quantity: Decimal | None
    unit: str | None
    unit_rate: Decimal | None
    stated_total: Decimal | None
    calculated_total: Decimal | None
    is_item_total_correct: bool | None
    quantity_difference: Decimal | None  # invoice_quantity - boq_quantity
    rate_difference: Decimal | None      # invoice_rate - boq_rate
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DeterministicChecksResult:
    """Results of deterministic Python arithmetic and variance checks."""

    requested_amount: Decimal
    invoice_stated_total: Decimal | None
    invoice_calculated_total: Decimal
    is_line_items_sum_correct: bool | None
    is_payment_matching_invoice: bool | None
    payment_difference: Decimal | None  # requested_amount - invoice_stated_total
    line_item_checks: tuple[LineItemCheck, ...]
    status: str  # e.g. "Arithmetic verified", "Arithmetic discrepancy detected", "Incomplete arithmetic data"
    summary_notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EvidenceFindingItem:
    """A specific observation or cross-document finding produced by AI interpretation."""

    title: str
    description: str
    source_reference: str | None = None


@dataclass(frozen=True)
class StructuredFindings:
    """The structured Decision Gate report combining deterministic math and AI observations."""

    matches: tuple[EvidenceFindingItem, ...]
    approved_changes: tuple[EvidenceFindingItem, ...]
    possible_mismatches: tuple[EvidenceFindingItem, ...]
    missing_evidence: tuple[EvidenceFindingItem, ...]
    human_verification_required: tuple[EvidenceFindingItem, ...]
    raw_evidence_text: str
    invoice_items: tuple[InvoiceItem, ...] = field(default_factory=tuple)
    invoice_stated_total: Decimal | None = None
    deterministic_checks: DeterministicChecksResult | None = None
    is_structured: bool = True


def calculate_line_item_total(
    quantity: Decimal | None, unit_rate: Decimal | None
) -> Decimal | None:
    """Deterministically compute quantity * unit_rate if both are available."""
    if quantity is None or unit_rate is None:
        return None
    return quantity * unit_rate


def calculate_invoice_total(items: Iterable[InvoiceItem]) -> Decimal:
    """Sum the line items deterministically, preferring stated totals or calculated values."""
    total = Decimal("0")
    for item in items:
        if item.stated_total is not None:
            total += item.stated_total
        elif item.quantity is not None and item.unit_rate is not None:
            total += item.quantity * item.unit_rate
    return total


def compare_payment_vs_invoice(
    requested_amount: Decimal, invoice_total: Decimal | None
) -> tuple[bool | None, Decimal | None, str]:
    """Compare the user-requested payment amount against the invoice total."""
    if invoice_total is None:
        return None, None, "Invoice total is not available for comparison."

    diff = requested_amount - invoice_total
    if diff == 0:
        return True, Decimal("0"), f"Requested payment amount matches invoice total ({requested_amount})."
    elif diff > 0:
        return False, diff, f"Requested payment amount ({requested_amount}) exceeds invoice total ({invoice_total}) by {diff}."
    else:
        return False, diff, f"Requested payment amount ({requested_amount}) is less than invoice total ({invoice_total}) by {abs(diff)} (partial claim)."


def calculate_quantity_difference(
    invoice_qty: Decimal | None, boq_qty: Decimal | None
) -> Decimal | None:
    """Compute invoice quantity minus BOQ quantity."""
    if invoice_qty is None or boq_qty is None:
        return None
    return invoice_qty - boq_qty


def calculate_rate_difference(
    invoice_rate: Decimal | None, boq_rate: Decimal | None
) -> Decimal | None:
    """Compute invoice unit rate minus BOQ unit rate."""
    if invoice_rate is None or boq_rate is None:
        return None
    return invoice_rate - boq_rate


def perform_deterministic_checks(
    requested_amount_raw: Any,
    invoice_stated_total: Decimal | None,
    items: Sequence[InvoiceItem],
) -> DeterministicChecksResult:
    """Execute deterministic arithmetic and variance checks using Python Decimals."""
    requested_amount = to_optional_decimal(requested_amount_raw) or Decimal("0")
    line_checks: list[LineItemCheck] = []
    summary_notes: list[str] = []
    has_discrepancy = False

    calculated_sum = Decimal("0")

    for item in items:
        notes: list[str] = []
        calc_total = calculate_line_item_total(item.quantity, item.unit_rate)
        is_total_correct: bool | None = None

        if calc_total is not None and item.stated_total is not None:
            if calc_total == item.stated_total:
                is_total_correct = True
            else:
                is_total_correct = False
                has_discrepancy = True
                notes.append(
                    f"Line total arithmetic discrepancy: {item.quantity} * {item.unit_rate} = {calc_total}, but stated as {item.stated_total}."
                )

        item_effective_total = item.stated_total if item.stated_total is not None else calc_total
        if item_effective_total is not None:
            calculated_sum += item_effective_total

        qty_diff = calculate_quantity_difference(item.quantity, item.boq_quantity)
        if qty_diff is not None:
            if qty_diff > 0:
                notes.append(f"Invoiced quantity exceeds BOQ quantity by +{qty_diff} {item.unit or ''}.".strip())
            elif qty_diff < 0:
                notes.append(f"Invoiced quantity is {abs(qty_diff)} {item.unit or ''} less than BOQ (partial progress claim).".strip())

        rate_diff = calculate_rate_difference(item.unit_rate, item.boq_unit_rate)
        if rate_diff is not None:
            if rate_diff > 0:
                has_discrepancy = True
                notes.append(f"Invoiced unit rate exceeds BOQ rate by +{rate_diff}.")
            elif rate_diff < 0:
                notes.append(f"Invoiced unit rate is less than BOQ rate by -{abs(rate_diff)}.")

        line_checks.append(
            LineItemCheck(
                description=item.description,
                quantity=item.quantity,
                unit=item.unit,
                unit_rate=item.unit_rate,
                stated_total=item.stated_total,
                calculated_total=calc_total,
                is_item_total_correct=is_total_correct,
                quantity_difference=qty_diff,
                rate_difference=rate_diff,
                notes=tuple(notes),
            )
        )

    # Line item sum vs stated invoice total
    is_sum_correct: bool | None = None
    if invoice_stated_total is not None:
        if calculated_sum == invoice_stated_total:
            is_sum_correct = True
            summary_notes.append(f"Sum of invoice line items matches stated invoice total ({calculated_sum}).")
        else:
            is_sum_correct = False
            has_discrepancy = True
            summary_notes.append(
                f"Sum of line items ({calculated_sum}) does not match stated invoice total ({invoice_stated_total})."
            )
    elif items:
        summary_notes.append(f"Calculated invoice total from line items is {calculated_sum}.")

    # Requested amount vs invoice total
    target_invoice_total = invoice_stated_total if invoice_stated_total is not None else calculated_sum
    is_payment_matching, payment_diff, payment_note = compare_payment_vs_invoice(
        requested_amount, target_invoice_total if (invoice_stated_total is not None or items) else None
    )
    if payment_note:
        summary_notes.append(payment_note)
    if is_payment_matching is False and payment_diff is not None and payment_diff > 0:
        has_discrepancy = True

    if not items and invoice_stated_total is None:
        status = "Incomplete arithmetic data"
    elif has_discrepancy:
        status = "Arithmetic discrepancy detected"
    else:
        status = "Arithmetic verified"

    return DeterministicChecksResult(
        requested_amount=requested_amount,
        invoice_stated_total=invoice_stated_total,
        invoice_calculated_total=calculated_sum,
        is_line_items_sum_correct=is_sum_correct,
        is_payment_matching_invoice=is_payment_matching,
        payment_difference=payment_diff,
        line_item_checks=tuple(line_checks),
        status=status,
        summary_notes=tuple(summary_notes),
    )


def parse_evidence_analysis(raw_text: str, requested_amount: Any) -> StructuredFindings:
    """Parse AI output into structured findings, running deterministic checks with resilient fallback."""
    raw_text_clean = raw_text.strip() if raw_text else ""

    # Attempt to extract JSON from markdown code blocks or curly braces
    json_candidate = raw_text_clean
    code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text_clean, re.DOTALL)
    if code_block_match:
        json_candidate = code_block_match.group(1).strip()
    else:
        brace_match = re.search(r"(\{.*\})", raw_text_clean, re.DOTALL)
        if brace_match:
            json_candidate = brace_match.group(1).strip()

    parsed_data: dict[str, Any] | None = None
    try:
        parsed_data = json.loads(json_candidate)
        if not isinstance(parsed_data, dict):
            parsed_data = None
    except Exception:
        parsed_data = None

    if parsed_data is None:
        # Graceful fallback for malformed or unstructured AI text
        requested_dec = to_optional_decimal(requested_amount) or Decimal("0")
        basic_checks = DeterministicChecksResult(
            requested_amount=requested_dec,
            invoice_stated_total=None,
            invoice_calculated_total=Decimal("0"),
            is_line_items_sum_correct=None,
            is_payment_matching_invoice=None,
            payment_difference=None,
            line_item_checks=(),
            status="Unable to verify arithmetic automatically",
            summary_notes=("The AI response did not provide structured invoice figures for automated arithmetic.",),
        )
        return StructuredFindings(
            matches=(),
            approved_changes=(),
            possible_mismatches=(),
            missing_evidence=(),
            human_verification_required=(
                EvidenceFindingItem(
                    title="Unstructured Analysis Output",
                    description="The AI model provided free-text findings rather than a structured schema. Review the raw evidence analysis below.",
                    source_reference="System fallback",
                ),
            ),
            raw_evidence_text=raw_text_clean,
            invoice_items=(),
            invoice_stated_total=None,
            deterministic_checks=basic_checks,
            is_structured=False,
        )

    # Extract finding lists
    def extract_finding_items(key: str) -> tuple[EvidenceFindingItem, ...]:
        items: list[EvidenceFindingItem] = []
        raw_list = parsed_data.get(key)
        if isinstance(raw_list, list):
            for entry in raw_list:
                if isinstance(entry, dict):
                    title = str(entry.get("title", entry.get("item", ""))).strip()
                    desc = str(entry.get("description", entry.get("explanation", entry.get("notes", "")))).strip()
                    src = entry.get("source_reference", entry.get("reference", None))
                    if title or desc:
                        items.append(
                            EvidenceFindingItem(
                                title=title or "Finding",
                                description=desc,
                                source_reference=str(src).strip() if src else None,
                            )
                        )
                elif isinstance(entry, str) and entry.strip():
                    items.append(EvidenceFindingItem(title="Observation", description=entry.strip()))
        return tuple(items)

    matches = extract_finding_items("matches")
    approved_changes = extract_finding_items("approved_changes")
    possible_mismatches = extract_finding_items("possible_mismatches")
    missing_evidence = extract_finding_items("missing_evidence")
    human_verification = extract_finding_items("human_verification_required")

    # Extract invoice items
    invoice_items: list[InvoiceItem] = []
    raw_items = parsed_data.get("invoice_items", [])
    if isinstance(raw_items, list):
        for entry in raw_items:
            if isinstance(entry, dict):
                invoice_items.append(
                    InvoiceItem(
                        description=str(entry.get("description", entry.get("item", "Item"))).strip(),
                        quantity=to_optional_decimal(entry.get("quantity")),
                        unit=str(entry.get("unit")).strip() if entry.get("unit") else None,
                        unit_rate=to_optional_decimal(entry.get("unit_rate", entry.get("rate"))),
                        stated_total=to_optional_decimal(entry.get("stated_total", entry.get("amount", entry.get("total")))),
                        boq_quantity=to_optional_decimal(entry.get("boq_quantity")),
                        boq_unit_rate=to_optional_decimal(entry.get("boq_unit_rate", entry.get("boq_rate"))),
                        boq_total=to_optional_decimal(entry.get("boq_total", entry.get("boq_amount"))),
                    )
                )

    invoice_stated_total = to_optional_decimal(
        parsed_data.get("invoice_total_stated", parsed_data.get("invoice_total"))
    )

    deterministic_checks = perform_deterministic_checks(
        requested_amount_raw=requested_amount,
        invoice_stated_total=invoice_stated_total,
        items=invoice_items,
    )

    return StructuredFindings(
        matches=matches,
        approved_changes=approved_changes,
        possible_mismatches=possible_mismatches,
        missing_evidence=missing_evidence,
        human_verification_required=human_verification,
        raw_evidence_text=raw_text_clean,
        invoice_items=tuple(invoice_items),
        invoice_stated_total=invoice_stated_total,
        deterministic_checks=deterministic_checks,
        is_structured=True,
    )
