# ARES Arena wireframes

## Configuration / idle

```text
┌ Arena heading ─ isolated mock mode ───────────────────────────────────┐
├ 01 Configure ───────── 02 Execute ───────── 03 Analyse ──────────────┤
├ Configure (validated form) ──────────────┬ Execute                    ┤
│ test name / target app                   │ IDLE / READY               │
│ system prompt                             │ explanatory safe state    │
│ user prompt                               │ short redacted audit log  │
│ provider / model / attack source          │                            │
│ attack-category checkboxes                │                            │
│ temperature / tokens / variations         │                            │
│ hardened comparison toggle / Run test     │                            │
├──────────────────────────────────────────┴────────────────────────────┤
│ Analyse: awaiting test result                                           │
└ Recent test history table ─────────────────────────────────────────────┘
```

| Aspect | Definition |
|---|---|
| Purpose | Configure a safe, deterministic red-team test. |
| Primary action | Validate and run a controlled test. |
| Information hierarchy | Target prompt and test prompt first, provider/attack controls next, tuning details last. |
| States | Inline validation; idle explanation; disabled Run during execution. |
| Responsive behavior | Configuration and execution stack below 900px; form columns collapse to a single column below 680px. |
| Accessibility | Every input has a visible label/help text; categories use a fieldset/legend; validation is announced; keyboard users can operate every control. |

## Running

```text
┌ Configure (disabled during execution) ───┬ Execute / RUNNING ● ───────┐
│ preserved submitted configuration         │ stage name       55%       │
│                                            │ ━━━━━━━━━━━━━━━━          │
│                                            │ provider / model           │
│                                            │ duration / token estimate  │
│                                            │ [Cancel test]              │
│                                            │ recent stage log           │
└───────────────────────────────────────────┴────────────────────────────┘
```

The stage, percentage, duration estimate, and log update through a cancellation-aware mock operation. The running indication uses text and a gold dot, not animation alone. With reduced motion enabled the dot does not pulse.

## Completed / analysis

```text
┌ Analyse ─ [Save to corpus] [Export report] ───────────────────────────┐
│ Summary | Responses | Evidence | Execution log                         │
│ risk score / severity / attack result / runtime classification          │
│ triggered detection rules                                                │
│ recommended prompt change                                                │
│ (Responses) baseline model output   | hardened model output             │
│ (Evidence) retrieval items with match score and source                  │
└────────────────────────────────────────────────────────────────────────┘
```

Model output cards are labelled separately from security analysis. `Save to corpus` and export surface a mock confirmation including a correlation ID rather than implying a production write.

## Failure and cancelled states

```text
┌ Execute / FAILED ● ────────────────────────────────────────────────────┐
│ safe provider-timeout message; no output retained                       │
├ Analyse ─ provider request failed safely ─ [Retry via new test] ───────┤
└────────────────────────────────────────────────────────────────────────┘

┌ Execute / CANCELLED ● ─────────────────────────────────────────────────┐
│ analyst cancellation retained in redacted history                       │
├ Analyse ─ no analysis was produced ────────────────────────────────────┤
└────────────────────────────────────────────────────────────────────────┘
```

Failure never displays provider internals or raw prompts. The analyst can adjust configuration and run again. Existing history supplies blocked, failed, cancelled, critical, and safe examples for review.
