# Dashboard wireframes

## Desktop overview

```text
┌─────────────── sidebar ──────────────┐ ┌──────────────── top bar ────────────────┐
│ ARES                                  │ │ Security operations / Overview   [profile]│
│ 01 Overview                           │ └──────────────────────────────────────────┘
│ 02 ARES Arena                         │ ┌─ heading ─────────────────────────────────┐
│ …                                     │ │ Control surface                 refreshed │
│ service state                         │ └──────────────────────────────────────────┘
└──────────────────────────────────────┘ ┌ metric ┬ metric ┬ metric ┬ metric ┐
                                         ├ metric ┼ metric ┼ metric ┼ metric ┤
                                         └──────────────────────────────────┘
                                         ┌──────── security trend ───────┬ category analysis ───┐
                                         │ chart + labelled legend        │ success-rate bars     │
                                         └───────────────────────────────┴──────────────────────┘
                                         ┌──── recent critical incidents ─┬ hardening comparison ┐
                                         └───────────────────────────────┴──────────────────────┘
                                         ┌──────────── provider health rows ──────────────────────┐
                                         └────────────────────────────────────────────────────────┘
```

| Aspect | Definition |
|---|---|
| Purpose | Answer whether apps are safe, controls are improving, and what needs attention. |
| Primary action | Open Arena or an incident route after reviewing an indicator. |
| Hierarchy | Metrics first; trend/category drivers second; active incidents and service readiness third. |
| Components | Metric summary, SVG trend chart, labelled category bars, incident table, provider health rows, empty/error/loading states. |
| Empty/error/loading | Loading uses an announced spinner; no incidents uses a positive empty state; partial response has an inline notice; unavailable dashboard shows retry. |
| Accessibility | Semantic headings; real table headers/captions; chart has text legend and label; state has words plus a dot; focus indicators are visible. |

## Mobile overview (about 360px)

```text
┌ ARES ──────────────────────────┐
│ Overview  Arena  Corpus  ... →  │  horizontally scrollable primary navigation
├ Security operations / Overview ┤
│ Control surface                │
│ security posture summary       │
├───────────┬────────────────────┤
│ metric    │ metric             │
├───────────┼────────────────────┤
│ metric    │ metric             │
├ security trend ────────────────┤
├ attack category analysis ──────┤
├ incidents (horizontally scrollable table)
├ hardening comparison ──────────┤
└ provider health rows ──────────┘
```

At tablet width the sidebar remains compact and paired dashboard panels stack as needed. At mobile width the sidebar becomes a compact horizontal navigation strip, metric cards stay two columns, analysis panels stack, and tables retain proper columns inside a labelled horizontal scroll container. Nothing relies on hover.
