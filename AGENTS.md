# AI Decision Gate — Contractor Payment Verification

## Project purpose

Help a homeowner review a contractor payment request against the original bill of quantities (BOQ) or quotation, approved change orders, and contractor invoice. The system highlights matching items, changed items, possible mismatches, missing evidence, and details requiring human review.

The product supports a decision; it does not make one.

## Architecture

Keep the application a small Flask web app with clear boundaries:

- `app/`: web application package.
- `app/routes/`: HTTP routes and request/response handling.
- `app/services/`: business logic, such as future evidence comparison.
- `app/templates/`: server-rendered HTML pages.
- `app/static/`: CSS and browser JavaScript.
- `tests/`: automated tests that mirror the application package.
- `docs/`: short design notes as the project grows.

For the MVP, use in-memory or request-scoped data only. Add Foundry File Search/RAG behind a service interface when that feature is explicitly scheduled. Keep document extraction and image analysis as separate future adapters.

## Business rules

- Never automatically approve or reject a payment.
- The final payment decision always belongs to a human.
- Clearly distinguish source evidence, system observations, and user-entered decisions.
- Flag uncertainty, missing documents, and conflicts for human verification.
- Do not present an AI output as a verified fact without traceable source evidence.
- Preserve original uploaded evidence when document handling is added.

## Coding conventions

- Use Python 3, Flask, and standard library features before adding dependencies.
- Prefer small, focused modules and explicit function names.
- Keep route handlers thin; put business logic in `services`.
- Use type hints for new non-trivial Python functions.
- Use `snake_case` for Python names and `kebab-case` for static asset filenames.
- Keep HTML semantic and accessible; keep CSS and JavaScript in static files.
- Add or update focused tests when behavior changes.

## Security rules

- Never commit secrets, API keys, customer documents, or personally identifiable information.
- Read configuration from environment variables when integrations are introduced; document variable names in `.env.example`, never real values.
- Validate file type, size, and content before accepting uploads in a future milestone.
- Treat document text and AI responses as untrusted input; escape rendered content and avoid executing it.
- Use least privilege for all future cloud identities and storage access.
- Log operational events without logging sensitive document contents.

## Development principles

- Build one vertical slice at a time and keep each change reviewable.
- Avoid adding Azure, Microsoft Foundry, authentication, databases, messaging, or payment processing until a scoped milestone requires it.
- Prefer interfaces and adapters at integration boundaries, not speculative infrastructure.
- Maintain backward-compatible behavior unless a change is explicitly approved.
- Keep dependencies minimal and explain why each new dependency is needed.

## Instructions for future Codex tasks

1. Inspect the repository and this file before editing.
2. State a concise plan before making changes.
3. Work only within the requested milestone; do not scaffold unrelated services.
4. Preserve the human-decision rule in UI copy, APIs, and future AI prompts.
5. Keep routes, services, templates, and static assets separated.
6. Run the smallest relevant verification after changes and report its result.
7. Update `README.md` and this file when architecture, setup, or business rules materially change.
