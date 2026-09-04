# ARES implementation guide

## Purpose

This repository implements a Week 1 prototype for ARES — Adaptive Red-Teaming, Prompt Hardening, and Runtime Enforcement for LLM applications. It provides a security overview, an individual-progress Arena skills platform, and a separate free-play controlled-test workspace. All security data and AI behavior are deterministic mocks.

## Technology stack

| Layer | Technology | How it is used |
|---|---|---|
| Application | C# / .NET 8 | Strongly typed application, records, validation, async/cancellation, and test runtime. |
| UI | Blazor Web App with interactive server components | Razor pages/components provide the app shell, routing, forms, tables, live execution progress, and accessible UI. |
| Styling | CSS design tokens in `wwwroot/app.css` | Deep-charcoal visual system, gold accents, responsive grids, focus states, status treatments, and reduced-motion support. |
| Domain models | C# records and enums | Arena test runs, evidence, risks, challenge tracks, rooms, scores, badges, private profiles, and API errors. |
| API boundary | `IAresApiClient` | Keeps page components independent from transport. The mock implementation can be replaced by an HTTP FastAPI client. |
| Mock backend | `MockAresApiClient` and `MockData` | Deterministic tests, trends, incidents, challenges, rooms, scoring, XP, badges, and provider states; no network/provider call. |
| Testing | xUnit | Tests mock state transitions, classifications, cancellation, and score/progression behavior. |
| Planned production backend | Python / FastAPI, Qdrant, PostgreSQL, MongoDB/object storage | Documented target architecture only; not started or contacted by this prototype. |

## Key implementation areas

```text
src/Ares.Web/
  Pages/                 Overview, Arena hub, challenge catalogue/detail, rooms, profile, free-play
  Components/            Reusable layout, dashboard, Arena, score, progress, and state components
  Models/                Typed API/domain models with Python-compatible JSON names
  Services/              IAresApiClient plus deterministic MockAresApiClient
  wwwroot/app.css        Design tokens and responsive styles
tests/Ares.Web.Tests/    xUnit logic and lifecycle tests
docs/                    Architecture, contracts, flows, wireframes, and implementation guides
```

## How the application works

1. `Program.cs` registers Razor components and the singleton `MockAresApiClient` behind `IAresApiClient`.
2. The Overview requests mock dashboard metrics through the interface.
3. The Arena hub exposes Attacker/Defender tracks, private profile progress, optional rooms, and free-play.
4. A challenge creates a typed `ArenaTestConfiguration`, starts a cancellation-aware simulated run, receives analysis, then explicitly submits it for a private score.
5. The mock client updates progress, XP, and badges in memory. Restarting the app resets mock state.
6. The free-play workspace uses the same test lifecycle but never awards challenge XP or a badge.

## Run locally

Prerequisite: .NET 8 SDK. Check with `dotnet --version`.

```powershell
dotnet restore Ares.sln
dotnet run --project src/Ares.Web
```

Open the URL printed by ASP.NET Core. The configured development URLs are:

- `https://localhost:7149`
- `http://localhost:5149`

If a system-wide SDK is unavailable but the repository contains the ignored local SDK created for validation, use:

```powershell
$env:DOTNET_CLI_HOME = "$PWD\.dotnet-cli-home"
.\.dotnet\dotnet.exe restore Ares.sln
.\.dotnet\dotnet.exe run --project src/Ares.Web
```

Run validation with:

```powershell
dotnet build Ares.sln --no-restore
dotnet test Ares.sln --no-build
dotnet format Ares.sln whitespace --verify-no-changes --no-restore
```

## Replacing the mock API

Implement `FastApiAresClient : IAresApiClient` with `IHttpClientFactory` and `System.Net.Http.Json`. Keep Razor pages unchanged. Register the real client in `Program.cs` only after FastAPI implements the request/response contracts in `api-contracts.md`. Send cancellation tokens and correlation IDs on each call; map non-success responses to `ApiError`.

## Security posture

- No API key, authentication secret, or provider SDK is in frontend code.
- Model output/evidence is displayed as encoded Razor text.
- Prompt redaction and authenticated raw-log access are future server-side responsibilities.
- Current individual-progress data is in-memory mock data and is not durable or shared.
