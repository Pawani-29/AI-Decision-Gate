"""Tests for structured evidence findings and deterministic arithmetic checks."""

from decimal import Decimal
import json

from app.services.evidence_analysis import (
    InvoiceItem,
    calculate_invoice_total,
    calculate_line_item_total,
    calculate_quantity_difference,
    calculate_rate_difference,
    compare_payment_vs_invoice,
    parse_evidence_analysis,
    perform_deterministic_checks,
)


def test_calculate_line_item_total():
    assert calculate_line_item_total(Decimal("10"), Decimal("5800")) == Decimal("58000")
    assert calculate_line_item_total(Decimal("1.5"), Decimal("20000")) == Decimal("30000.0")
    assert calculate_line_item_total(None, Decimal("5000")) is None
    assert calculate_line_item_total(Decimal("10"), None) is None


def test_calculate_invoice_total():
    items = [
        InvoiceItem(description="Demolition", stated_total=Decimal("20000")),
        InvoiceItem(description="Cabinets", quantity=Decimal("10"), unit_rate=Decimal("5800"), stated_total=Decimal("58000")),
        InvoiceItem(description="Handles", stated_total=Decimal("8000")),
        InvoiceItem(description="Countertop", quantity=Decimal("20"), unit_rate=Decimal("2500"), stated_total=Decimal("50000")),
        InvoiceItem(description="Tiles", quantity=Decimal("70"), unit_rate=Decimal("200"), stated_total=Decimal("14000")),
    ]
    assert calculate_invoice_total(items) == Decimal("150000")


def test_compare_payment_vs_invoice():
    # Matching
    is_match, diff, note = compare_payment_vs_invoice(Decimal("150000"), Decimal("150000"))
    assert is_match is True
    assert diff == Decimal("0")
    assert "matches" in note

    # Overbilling / requested amount exceeds invoice
    is_match, diff, note = compare_payment_vs_invoice(Decimal("160000"), Decimal("150000"))
    assert is_match is False
    assert diff == Decimal("10000")
    assert "exceeds" in note

    # Partial payment / requested amount less than invoice
    is_match, diff, note = compare_payment_vs_invoice(Decimal("100000"), Decimal("150000"))
    assert is_match is False
    assert diff == Decimal("-50000")
    assert "less than" in note

    # None invoice total
    is_match, diff, note = compare_payment_vs_invoice(Decimal("150000"), None)
    assert is_match is None
    assert diff is None


def test_quantity_difference_detection():
    # Matching
    assert calculate_quantity_difference(Decimal("10"), Decimal("10")) == Decimal("0")
    # Partial claim (invoice < boq)
    assert calculate_quantity_difference(Decimal("20"), Decimal("32")) == Decimal("-12")
    assert calculate_quantity_difference(Decimal("70"), Decimal("180")) == Decimal("-110")
    # Excess (invoice > boq)
    assert calculate_quantity_difference(Decimal("15"), Decimal("10")) == Decimal("5")
    # Missing data
    assert calculate_quantity_difference(None, Decimal("10")) is None
    assert calculate_quantity_difference(Decimal("10"), None) is None


def test_rate_difference_detection():
    # Matching
    assert calculate_rate_difference(Decimal("2500"), Decimal("2500")) == Decimal("0")
    # Invoice rate less than BOQ rate
    assert calculate_rate_difference(Decimal("5800"), Decimal("6000")) == Decimal("-200")
    # Invoice rate exceeds BOQ rate
    assert calculate_rate_difference(Decimal("6500"), Decimal("6000")) == Decimal("500")
    # Missing data
    assert calculate_rate_difference(None, Decimal("6000")) is None
    assert calculate_rate_difference(Decimal("5800"), None) is None


def test_perform_deterministic_checks_detects_arithmetic_discrepancy():
    items = [
        # 10 * 5800 = 58000, but stated as 60000
        InvoiceItem(
            description="Cabinets with wrong total",
            quantity=Decimal("10"),
            unit="sheets",
            unit_rate=Decimal("5800"),
            stated_total=Decimal("60000"),
            boq_quantity=Decimal("10"),
            boq_unit_rate=Decimal("6000"),
        )
    ]
    result = perform_deterministic_checks(
        requested_amount_raw="60000",
        invoice_stated_total=Decimal("60000"),
        items=items,
    )
    assert result.status == "Arithmetic discrepancy detected"
    assert result.line_item_checks[0].is_item_total_correct is False
    assert any("arithmetic discrepancy" in note for note in result.line_item_checks[0].notes)


def test_structured_ai_findings_parsing():
    sample_json = {
        "invoice_total_stated": 150000,
        "invoice_items": [
            {
                "description": "Demolition and debris removal",
                "quantity": 1,
                "unit": "LS",
                "unit_rate": 20000,
                "stated_total": 20000,
                "boq_quantity": 1,
                "boq_unit_rate": 20000,
            },
            {
                "description": "Kitchen cabinets - 16mm commercial plywood",
                "quantity": 10,
                "unit": "sheets",
                "unit_rate": 5800,
                "stated_total": 58000,
                "boq_quantity": 10,
                "boq_unit_rate": 6000,
            },
            {
                "description": "Additional handle and design work",
                "quantity": 1,
                "unit": "LS",
                "unit_rate": 8000,
                "stated_total": 8000,
            },
            {
                "description": "Countertop - 20mm quartz, Snow White",
                "quantity": 20,
                "unit": "sq ft",
                "unit_rate": 2500,
                "stated_total": 50000,
                "boq_quantity": 32,
                "boq_unit_rate": 2500,
            },
            {
                "description": "Bathroom wall tiles",
                "quantity": 70,
                "unit": "sq ft",
                "unit_rate": 200,
                "stated_total": 14000,
                "boq_quantity": 180,
                "boq_unit_rate": 200,
            },
        ],
        "matches": [
            {
                "title": "Demolition Scope",
                "description": "Demolition work matches BOQ line 1.",
                "source_reference": "BOQ Item 1 vs Invoice Item 1",
            }
        ],
        "approved_changes": [
            {
                "title": "Handle and Design Work",
                "description": "Approved in Change Order CO-01 for INR 8,000.",
                "source_reference": "CO-01",
            }
        ],
        "possible_mismatches": [
            {
                "title": "Kitchen Cabinet Material Substitution",
                "description": "Invoice lists 16mm commercial plywood instead of 18mm BWP plywood.",
                "source_reference": "BOQ Item 2 vs Invoice Item 2 vs CO-01",
            }
        ],
        "missing_evidence": [
            {
                "title": "Material Substitution Approval",
                "description": "No written approval found for downgrade to commercial plywood.",
                "source_reference": "CO-01",
            }
        ],
        "human_verification_required": [
            {
                "title": "Verify Cabinet Material on Site",
                "description": "Confirm whether 16mm commercial plywood was authorized and installed.",
                "source_reference": "Homeowner decision required",
            }
        ],
    }

    raw_text = f"```json\n{json.dumps(sample_json)}\n```"
    findings = parse_evidence_analysis(raw_text, requested_amount="150000.00")

    assert findings.is_structured is True
    assert findings.invoice_stated_total == Decimal("150000")
    assert len(findings.invoice_items) == 5
    assert len(findings.matches) == 1
    assert findings.matches[0].title == "Demolition Scope"
    assert len(findings.approved_changes) == 1
    assert len(findings.possible_mismatches) == 1
    assert "16mm commercial plywood" in findings.possible_mismatches[0].description
    assert len(findings.missing_evidence) == 1
    assert len(findings.human_verification_required) == 1

    # Check deterministic checks on parsed data
    checks = findings.deterministic_checks
    assert checks is not None
    assert checks.invoice_calculated_total == Decimal("150000")
    assert checks.is_line_items_sum_correct is True
    assert checks.is_payment_matching_invoice is True
    assert checks.status == "Arithmetic verified"

    # Check specific line item diffs
    cabinet_check = checks.line_item_checks[1]
    assert cabinet_check.description == "Kitchen cabinets - 16mm commercial plywood"
    assert cabinet_check.is_item_total_correct is True
    assert cabinet_check.quantity_difference == Decimal("0")
    assert cabinet_check.rate_difference == Decimal("-200")


def test_malformed_ai_output_handling():
    malformed_text = "The contractor requested payment for kitchen cabinets. Everything looks mostly fine except plywood."
    findings = parse_evidence_analysis(malformed_text, requested_amount="150000")

    assert findings.is_structured is False
    assert findings.raw_evidence_text == malformed_text
    assert len(findings.human_verification_required) == 1
    assert "Unstructured Analysis Output" in findings.human_verification_required[0].title
    assert findings.deterministic_checks is not None
    assert findings.deterministic_checks.status == "Unable to verify arithmetic automatically"
    assert findings.deterministic_checks.requested_amount == Decimal("150000")
