# AI Decision Gate — Contractor Payment Verification

## Problem statement

Homeowners often receive contractor payment requests without a simple way to compare the invoice with the original BOQ/quotation and approved changes. Differences can be legitimate, undocumented, or mistaken, and a homeowner needs a clear review process before paying.

## Solution

AI Decision Gate is a human-in-the-loop review tool. It will organize the available evidence and surface matches, changes, possible mismatches, missing evidence, and questions that require verification. It will never approve or reject a payment automatically.

## MVP scope

The MVP provides a small Flask foundation, a review-oriented landing page, and a payment-request form. Users can submit an original BOQ/quotation, approved change order, contractor invoice, and positive requested amount. Development uploads are stored locally outside the `app/` package and are not publicly served.

Out of scope for this stage:

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

## Microsoft Foundry development setup

The development connection test uses an existing Foundry agent; it does not create or modify an agent, vector store, File Search configuration, or uploaded files.

1. Copy `.env.example` to `.env`.
2. Set `FOUNDRY_PROJECT_ENDPOINT` and `FOUNDRY_AGENT_NAME` in `.env`. Do not commit this file.
3. Sign in locally with `az login` so `DefaultAzureCredential` can obtain your Azure identity.
4. Start the Flask app and open `http://127.0.0.1:5000/development/foundry-test`.

The route asks the existing agent: “Compare the kitchen cabinet material across the BOQ, change order, and contractor invoice.” It is a connection check only; it does not make a payment decision.

## Dynamic File Search architecture

The existing agent's fixed File Search version remains unchanged. Run `python scripts/create_dynamic_foundry_agent_version.py` after local Azure authentication to create a new **draft** version of the same agent. The script reads the current agent's instructions and verifies its `gpt-5-mini` model before creating a definition with only `FileSearchTool(vector_store_ids=["{{vector_store_id}}"] )` and a required `vector_store_id` structured input.

Set the printed version in `FOUNDRY_DYNAMIC_AGENT_VERSION`. Calls that supply `vector_store_id` explicitly reference this draft version and pass the value as `extra_body["structured_inputs"]["vector_store_id"]`. Calls without it continue to use the fixed-index development path. No user files are uploaded to Foundry in this milestone.

## Demo dataset

`sample_data/` contains three fictional PDF documents for one renovation scenario: the original BOQ, an approved change order, and a contractor invoice requesting INR 1,50,000. The change order approves INR 8,000 of kitchen cabinet handle/design work and explicitly does not approve a material substitution. The invoice intentionally lists 16mm commercial plywood where the BOQ specifies 18mm BWP plywood. These files are demo evidence only and are not processed by the application yet.

## Development roadmap

1. Build deterministic item matching and a transparent discrepancy summary.
2. Add tests for comparison scenarios and missing-evidence cases.
3. Add local document parsing with content and size validation.
4. Add Foundry File Search/RAG through a dedicated service adapter.
5. Evaluate optional Azure Document Intelligence and image analysis.
