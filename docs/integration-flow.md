# ARES integration flow

This prototype calls `IAresApiClient`. `MockAresApiClient` is registered in `Program.cs`; replace that registration with an authenticated `FastApiAresClient` once the API exists. Page components must not call `HttpClient` or provider SDKs directly.

## System context

```mermaid
flowchart LR
  Analyst[Security analyst] --> Web[Blazor ARES web app]
  Web --> API[FastAPI security API]
  API --> Providers[AI provider adapters]
  API --> Runtime[Runtime enforcement gateway]
  API --> Engine[Red-team engine]
  Engine --> Qdrant[(Qdrant evidence index)]
  API --> Postgres[(PostgreSQL)]
  API --> Logs[(MongoDB / object logs)]
  API --> Corpus[Attack corpus]
```

## Component architecture

```mermaid
flowchart TB
  UI[Overview and Arena components] --> Client[IAresApiClient]
  Client --> Http[FastApiAresClient]
  Client -. Week 1 .-> Mock[MockAresApiClient]
  Http --> Tests[Test run API]
  Http --> Dashboard[Dashboard API]
  Tests --> Orchestrator[Test orchestrator]
  Orchestrator --> RedTeam[Red-team engine]
  Orchestrator --> Harden[Prompt-hardening service]
  Orchestrator --> Classifier[Runtime classifier]
  Dashboard --> Analytics[Analytics projector]
```

## Arena test sequence

```mermaid
sequenceDiagram
  actor A as Analyst
  participant B as Blazor Arena
  participant F as FastAPI
  participant R as Red-team engine
  participant Q as Qdrant
  participant P as Provider adapter
  participant C as Runtime classifier
  participant H as Hardening service
  A->>B: Configure and run test
  B->>B: Validate typed form
  B->>F: POST /tests (correlation ID)
  F->>R: Create test run and select attack
  R->>Q: Retrieve similar evidence
  R->>P: Evaluate baseline request
  P-->>R: Sanitized model output
  R->>C: Classify output
  R->>H: Produce hardened prompt
  R->>P: Evaluate hardened request
  R->>C: Classify comparison
  R->>F: Store redacted results and logs
  F-->>B: Test result / status updates
  B-->>A: Risk, evidence, comparison
```

## Runtime incident sequence

```mermaid
sequenceDiagram
  participant App as Protected application
  participant G as Enforcement gateway
  participant C as Runtime classifier
  participant L as Incident log
  participant A as Analytics
  participant D as Dashboard
  App->>G: Prompt and model response
  G->>C: Evaluate policy and detections
  alt violation is blocked
    C-->>G: Block / redact / quarantine action
    G->>L: Persist redacted incident + correlation ID
    L->>A: Project aggregate metrics
    A-->>D: Updated incident and trend data
  else safe response
    C-->>G: Allow response
  end
```

## Data flow and retention

```mermaid
flowchart LR
  Form[Typed Arena configuration] --> Validate[Frontend validation]
  Validate --> Run[Test run record]
  Run --> Evidence[Retrieved evidence]
  Run --> Output[Untrusted model output]
  Evidence --> Analysis[Classification and hardening result]
  Output --> Analysis
  Analysis --> PG[(PostgreSQL metadata)]
  Output --> Redact[Redaction boundary]
  Redact --> Object[(Object/Mongo logs)]
  Analysis --> Aggregate[Dashboard aggregates]
  Analysis --> Corpus[Successful attacks to corpus]
```

Raw prompts and model output should be redacted or tokenized before durable logging. PostgreSQL holds workflow metadata and queryable summaries; object/Mongo storage holds access-controlled redacted diagnostic material; Qdrant stores vetted evidence embeddings, not frontend credentials.

## Failure handling

```mermaid
flowchart TD
  Start[API call / provider action] --> Outcome{Succeeded?}
  Outcome -->|Yes| Continue[Persist result and refresh metrics]
  Outcome -->|No| Known{Retryable?}
  Known -->|Yes| Retry[Bounded retry with backoff]
  Retry --> Outcome
  Known -->|No| Fail[Mark run failed with safe error]
  Fail --> Log[Store redacted error + correlation ID]
  Log --> UI[Show retry guidance in UI]
  Start --> Cancel{Analyst cancelled?}
  Cancel -->|Yes| Stop[Cancel work and mark run cancelled]
```

The UI never renders error bodies as HTML. It uses the user-safe message and correlation ID from the standard API error. A provider timeout becomes a failed test with no retained model output; a partial dashboard response retains available panels and shows a partial-data notice.

## Replacing mock services

1. Implement `FastApiAresClient : IAresApiClient` using `IHttpClientFactory`, `System.Net.Http.Json`, and the same JSON names in `Models/AresModels.cs`.
2. Register a named HTTP client with the API base URL from server-side configuration; do not expose provider keys to WebAssembly/browser code.
3. Send an `X-Correlation-ID` for every request and pass cancellation tokens to `SendAsync`.
4. Map non-success responses into `ApiError`; only retry endpoints marked retryable.
5. Keep the page and reusable components unchanged; remove the mock registration only after endpoint contract tests pass.

## Arena private progression flow

```mermaid
sequenceDiagram
  actor Learner
  participant Arena as Blazor Arena
  participant API as FastAPI
  participant Engine as Test orchestrator
  participant Store as Progress store
  Learner->>Arena: Open private challenge
  Arena->>API: Get challenge + own progress
  Learner->>Arena: Run controlled attempt
  Arena->>API: Create test run
  API->>Engine: Evaluate selected mock/production test
  Engine-->>API: Redacted analysis
  API-->>Arena: Completed run
  Learner->>Arena: Submit for score
  Arena->>API: Challenge ID + test run ID
  API->>Store: Verify owner, score, update XP/badges
  Store-->>API: Private score and next challenge
  API-->>Arena: Submission result
```

The profile scope is always the authenticated user. Optional rooms are metadata that organize challenges; they do not grant access to another user's records or impose participation in a learning path.
