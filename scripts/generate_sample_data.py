"""Generate fictional PDF evidence documents for the local demo dataset."""

from pathlib import Path

PAGE_WIDTH = 612
PAGE_HEIGHT = 792


def escape_pdf_text(text: str) -> str:
    """Escape text for a PDF literal string using a standard PDF font."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_content(lines: list[str]) -> bytes:
    """Create a simple, readable single-page PDF text stream."""
    commands = ["BT", "/F1 10 Tf", "48 744 Td", "14 TL"]
    for line in lines:
        commands.append(f"({escape_pdf_text(line)}) Tj")
        commands.append("T*")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1")


def create_pdf(destination: Path, lines: list[str]) -> None:
    """Write a minimal valid PDF using the built-in Helvetica font."""
    stream = pdf_content(lines)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ).encode("ascii"),
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
    ]

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, pdf_object in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(pdf_object)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(output)


def main() -> None:
    """Create the three documents used in the contractor-payment demo."""
    sample_directory = Path(__file__).parent.parent / "sample_data"
    common = [
        "GREENFIELD RENOVATIONS LLP",
        "Project: 24 Oakwood Lane - Kitchen and Bathroom Renovation",
        "Customer: Ananya Mehta (fictional demo customer)",
        "",
    ]

    create_pdf(
        sample_directory / "original_boq.pdf",
        common
        + [
            "ORIGINAL BOQ / QUOTATION  |  Quote Q-2026-041  |  15 May 2026",
            "Item                                      Qty       Rate          Amount",
            "Demolition and debris removal              1 LS      INR 20,000    INR 20,000",
            "Kitchen cabinets - 18mm BWP plywood       10 sheets INR 6,000     INR 60,000",
            "Countertop - 20mm quartz, Snow White       32 sq ft  INR 2,500     INR 80,000",
            "Bathroom wall tiles - ceramic, Ivory        180 sq ft INR 200       INR 36,000",
            "Plumbing fixtures and installation          1 LS      INR 40,000    INR 40,000",
            "",
            "Original quotation total:                                      INR 2,36,000",
            "Payment terms: progress claims against completed work and supplied materials.",
        ],
    )

    create_pdf(
        sample_directory / "change_order.pdf",
        common
        + [
            "APPROVED CHANGE ORDER  |  CO-01  |  22 May 2026",
            "Kitchen cabinet design changed. Approved scope: handle and design detail.",
            "",
            "Approved addition                          Qty       Rate          Amount",
            "Kitchen cabinet handle and design work     1 LS      INR 8,000     INR 8,000",
            "",
            "Approved change order total:                                   INR 8,000",
            "Material approval: NO material substitution was approved.",
            "Revised project total (Q-2026-041 plus CO-01):                INR 2,44,000",
            "Approval: Ananya Mehta (fictional)  |  Status: Approved",
        ],
    )

    create_pdf(
        sample_directory / "contractor_invoice.pdf",
        common
        + [
            "CONTRACTOR INVOICE / PAYMENT REQUEST  |  INV-2026-078  |  10 June 2026",
            "Progress claim: completed work and supplied materials to date.",
            "Item                                      Qty       Rate          Amount",
            "Demolition and debris removal              1 LS      INR 20,000    INR 20,000",
            "Kitchen cabinets - 16mm commercial plywood 10 sheets INR 5,800     INR 58,000",
            "Additional handle and design work           1 LS      INR 8,000     INR 8,000",
            "Countertop - 20mm quartz, Snow White       20 sq ft  INR 2,500     INR 50,000",
            "Bathroom wall tiles - installed to date    70 sq ft  INR 200       INR 14,000",
            "",
            "Payment requested this invoice:                                INR 1,50,000",
            "Please review all evidence before making a payment decision.",
        ],
    )


if __name__ == "__main__":
    main()
