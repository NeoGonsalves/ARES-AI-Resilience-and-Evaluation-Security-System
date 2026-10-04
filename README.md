# ARES — Week 1 Prototype

ARES is an Adaptive Red-Teaming, Prompt Hardening, and Runtime Enforcement workspace for LLM applications. This repository contains the Week 1 Blazor prototype: a mock security dashboard and an interactive Arena test workflow.

## Run locally

1. Install the [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0) (the runtime alone is not sufficient).
2. From this directory run `dotnet restore Ares.sln`.
3. Run `dotnet run --project src/Ares.Web` and open the reported local URL.
4. Run `dotnet test Ares.sln` for the logic tests.

The prototype makes no AI-provider or production API calls. `MockAresApiClient` is the replaceable boundary for the planned FastAPI service. See the [implementation guide](docs/implementation-guide.md), [Arena challenge system](docs/arena-challenge-system.md), and [integration flow](docs/integration-flow.md).

## Security note

Do not add provider API keys to this repository or frontend configuration. Provider keys and authentication belong to the server-side gateway. See [architecture decisions](docs/architecture-decisions.md).
