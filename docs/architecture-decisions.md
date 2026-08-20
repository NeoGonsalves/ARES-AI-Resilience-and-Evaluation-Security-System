# ARES architecture decisions — Week 1

| Decision | Rationale | Consequence |
|---|---|---|
| Blazor Web App on .NET 8 | Provides a strongly typed UI and server-rendered shell with interactive components. | The prototype needs only the .NET SDK; no JavaScript framework or UI package is introduced. |
| `IAresApiClient` boundary | Pages should describe security workflows, not transport. | `MockAresApiClient` can be replaced with FastAPI HTTP integration without rewriting UI. |
| Deterministic mock data | Makes reviews and demos repeatable, including failure and critical states. | Mock values are not operational security metrics. |
| JSON snake_case attributes | FastAPI/Pydantic normally uses snake_case contracts. | Avoids an implicit casing translation during API integration. |
| Untrusted strings rendered as text | Model responses and evidence can contain adversarial content. | Razor HTML-encodes output; no `MarkupString` is used for those fields. |
| Redacted default logging | Prompts may contain sensitive business context. | Store hashes, classifications, excerpts, and references by default; require privileged, audited access for raw diagnostic data. |
| Stable enums only | Categories, providers, statuses, and severity are shared domain vocabulary. | New server values need a coordinated UI release or a tolerant DTO fallback. |
| No authentication in Week 1 | The brief excludes production auth. | Future deployment must put OIDC authentication, RBAC, tenant boundaries, audit trails, and CSRF/session protections in front of routes and APIs. |

## Security boundaries

- Provider credentials exist only in FastAPI secret storage or an external secret manager. `.env.example` has names only.
- The frontend submits a typed test configuration to the ARES API, never directly to OpenAI, Groq, Gemini, or NVIDIA NIM.
- Correlation IDs tie a UI action to redacted server logs and incident records.
- Prompt redaction happens before durable logging and before evidence export. The raw-prompt exception path needs role checks, a reason, expiry, and audit events.
- Dashboard aggregates should be authorization-scoped by organization and protected application.

## Future authentication and authorization

Use OIDC at the web/API boundary. Define at least `SecurityAnalyst`, `PromptEngineer`, `IncidentResponder`, and `Administrator` roles. Enforce application-level scopes on runs, corpus writes, exports, and incident views. API authorization is authoritative; hiding a UI control is not an authorization control.
