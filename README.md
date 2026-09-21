# AI Decision Gate — Contractor Payment Verification

## Problem statement

Homeowners often receive contractor payment requests without a simple way to compare the invoice with the original BOQ/quotation and approved changes. Differences can be legitimate, undocumented, or mistaken, and a homeowner needs a clear review process before paying.

## Solution

AI Decision Gate is a human-in-the-loop review tool. It will organize the available evidence and surface matches, changes, possible mismatches, missing evidence, and questions that require verification. It will never approve or reject a payment automatically.

## MVP scope

The MVP provides a small Flask foundation, a review-oriented landing page, and a payment-request form. Users can submit an original BOQ/quotation, approved change order, contractor invoice, and positive requested amount. Development uploads are stored locally outside the `app/` package and are not publicly served.

Out of scope for this stage:

- Microsoft Foundry and Azure integrations
- Document intelligence or image analysis
- Authentication
- WhatsApp or other messaging integrations
- Payment processing
- Databases and additional services

## Architecture

```text
Browser
  -> Flask routes
       -> services (comparison logic, added incrementally)
       -> templates and static assets
```

The web layer receives requests and renders pages. The service layer will hold comparison rules so that future AI/document adapters can be added without coupling them to routes or UI. The homeowner remains the final decision maker.

## Run locally

1. Create and activate a Python virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Start the app: `flask --app app run --debug`
4. Open `http://127.0.0.1:5000`.

## Development roadmap

1. Build deterministic item matching and a transparent discrepancy summary.
2. Add tests for comparison scenarios and missing-evidence cases.
3. Add local document parsing with content and size validation.
4. Add Foundry File Search/RAG through a dedicated service adapter.
5. Evaluate optional Azure Document Intelligence and image analysis.
