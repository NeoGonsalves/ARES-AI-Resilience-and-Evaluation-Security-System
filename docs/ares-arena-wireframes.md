# ARES Arena wireframes

ARES Arena is an individual AI-security learning platform inspired by focused coding and cyber-security practice platforms. Progress is private to the signed-in profile; this prototype has no leaderboard, team ranking, or public profile.

## Route map

| Route | Purpose |
|---|---|
| `/arena` | Arena hub: tracks, personal snapshot, optional learning paths, free-play entry. |
| `/arena/challenges` | Filterable individual challenge catalogue. |
| `/arena/challenge/{challengeId}` | Challenge brief, controlled attempt, analysis, and private scoring. |
| `/arena/rooms` | Optional themed room catalogue. |
| `/arena/rooms/{roomId}` | Optional room sequence and challenge progress. |
| `/arena/workspace` | Unscored free-play red-team workspace. |
| `/arena/profile` | Private XP, badges, and challenge progress. |

## Arena hub

```text
┌ ARES Arena ────────────────────────────────────────────────────────────────┐
│ Train as an attacker or defender                         [isolated mock]    │
├──────────────── Choose your role ──────────────────────────────────────────┤
│ ┌ Attacker ─────────────────────┐  ┌ Defender ───────────────────────────┐ │
│ │ attack techniques and goals   │  │ prompt-hardening techniques/goals   │ │
│ │ [Start attacking]             │  │ [Start defending]                  │ │
│ └───────────────────────────────┘  └─────────────────────────────────────┘ │
├──────────────── Your progress ─────────────────────────────────────────────┤
│ solved | attacker | defender | badges | Level / XP progress                 │
├──────────────── Optional learning paths ───────────────────────────────────┤
│ themed path cards → [Explore optional rooms]                                │
├──────────────── Free-play workspace ───────────────────────────────────────┤
│ Unscored custom test configuration → [Open free-play workspace]             │
└────────────────────────────────────────────────────────────────────────────┘
```

| Aspect | Definition |
|---|---|
| Primary action | Pick Attacker or Defender and open a relevant challenge list. |
| Hierarchy | Tracks first; personal progress second; optional structure and free-play last. |
| States | Loading profile, available track actions, private-progress explanation. |
| Responsive behavior | Track and path cards stack on smaller screens; metrics retain two columns on mobile. |
| Accessibility | Semantic headings, labelled navigation, text plus colour for track distinction, keyboard-accessible controls. |

## Challenge browser and detail

```text
┌ Challenges ─ track toggle ─ difficulty/category/search filters ────────────┐
│ challenge | track | difficulty | category | par | best | status | [Start] │
└────────────────────────────────────────────────────────────────────────────┘

┌ Challenge detail ──────────────────────────────────────────────────────────┐
│ title, track, difficulty                                              [Back]│
├ Challenge brief ───────────────┬ metadata: category / par / maximum score ┤
│ objective, scenario, optional  │                                              │
│ revealable guidance            │                                              │
├ Controlled workspace ──────────┼ Execute                                      │
│ target/hardened system prompt  │ running stage / progress / cancel / log    │
│ controlled input               │                                              │
│ [Run controlled attempt]       │                                              │
├ Result: risk analysis, response comparison, [Submit for score]              │
├ Score: components, XP, badge result, next challenge, profile shortcut       │
└────────────────────────────────────────────────────────────────────────────┘
```

The challenge workspace is deliberately separated from free-play. Challenge configuration sets the challenge category and controlled variation count; the resulting mock test is submitted for an individual score only after analysis has completed. Raw prompt/model text is rendered as escaped text and never sent to a real provider in this prototype.

## Optional rooms

```text
┌ Optional rooms ────────────────────────────────────────────────────────────┐
│ A room is a themed learning sequence, not a gate to the full catalogue.     │
│ ┌ Prompt Injection 101 ───────────┐  ┌ Data and Policy Attacks ───────────┐ │
│ │ 2 / 4 completed   [Explore room]│  │ 1 / 4 completed   [Explore room]   │ │
│ └─────────────────────────────────┘  └────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

Within a room, prerequisites are shown as recommended preparation and advanced challenges may be locked. A user can always return to the complete challenge catalogue rather than join a room.

## Profile and states

```text
┌ My Arena Progress ─────────────────────────────────────────────────────────┐
│ individual-only notice                         [Back to Arena hub]          │
├ level / XP ── solved ── attacker ── defender                                │
├ earned badges ──────────────────────┬ continue learning                     │
├ private challenge history: best / last attempt / status                      │
└────────────────────────────────────────────────────────────────────────────┘
```

| State | Treatment |
|---|---|
| Locked challenge | Explain prerequisite; provide an available-challenges action. |
| Loading | Announced loading state for profile, rooms, challenge, and attempt data. |
| Failed/cancelled attempt | Safe message only; no output retained; no score awarded. |
| Completed attempt | Risk analysis appears before the explicit Submit for score action. |
| Empty profile | Explain how completing a challenge earns the first badge. |
