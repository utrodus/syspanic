# SysPanic — UI/UX Specification (v0.1.0)

**Status:** Approved source of truth · 2026-11-16 (visual refinement revision: Modern Diagnostic Workstation; dual-theme revision: Dark + Soft Light with global switcher, approved by user)
**Framework:** PySide6 6.12, Qt Widgets (QtCore/QtGui/QtWidgets only)
**Target:** 1920×1080 desktop; default 1440×900; minimum 1280×720

## 1. Direction

**Modern Diagnostic Workstation** — a premium Linux developer tool in the spirit of Linear/Raycast/observability tools, without copying their interfaces. Two approved themes share one visual identity: the original deep-charcoal **Dark** theme (default) and a premium low-glare **Soft Light** theme — soft neutral off-white surfaces, subtle layering, charcoal text, and a muted teal/emerald accent; never a default Qt light look, never pure-white large surfaces. One restrained mint/teal accent per theme; clear typography hierarchy; generous but purposeful spacing; consistent local outline iconography (QPainter or local assets, never emoji, never remote); polished hover/focus/selected/pressed/disabled states. No excessive gradients, shadows, decorative charts, or unnecessary effects; no animation beyond a determinate progress bar. Severity is conveyed by labeled badges plus color. Evidence is monospace and never rendered as rich text. Native KDE window decoration and normal window management are kept; no custom frameless title bar — decorations may follow the desktop's own theme. Outline icons share a consistent 24×24 coordinate system with semantic glyphs (dashboard, history, file search, CPU, file text, shield check, sun, moon), rendered locally via QPainter with antialiasing, a safe stroke margin, and correct device-pixel-ratio handling so nothing clips at any size or scale.

The interface answers five questions in order: **What happened? (Overview) → When? (Timeline) → What is the proof? (Evidence) → What hardware/software context applies? (System Information) → What can I share? (Report).**

## 2. Design tokens

One semantic token set, two approved themes. **Dark is the default** when no valid preference exists. Soft Light uses off-white layered surfaces, charcoal text, and a muted emerald accent; pure white appears only as small text on the accent button. Values below are the single source for QPalette and QSS generation (`ui/theme.py`); widgets never hardcode colors.

| Token | Dark | Soft Light |
|---|---|---|
| `bg.canvas` | `#101115` | `#F3F4F2` |
| `bg.sidebar` | `#16181E` | `#E9ECE9` |
| `bg.surface` | `#191B22` | `#FAFBF9` |
| `bg.elevated` | `#23262F` | `#F0F3EF` |
| `bg.nav_selected` | `#294238` | `#D8EAE2` |
| `bg.code` | `#14161B` | `#F0F3EF` |
| `border.default` | `#30343D` | `#D9DFDA` |
| `border.hover` | `#3A3F4A` | `#B9C4BB` |
| `text.primary` | `#E7EBF1` | `#26332E` |
| `text.secondary` | `#98A1AF` | `#55645C` |
| `text.muted` | `#8A93A4` | `#5F6E65` |
| `accent` | `#62D8B2` | `#237A62` |
| `accent.text` | `#101115` | `#FFFFFF` |
| `accent.hover` | `#74E0BF` | `#1C6A54` |
| `accent.pressed` | `#52C9A2` | `#175A47` |
| `nav_selected_text` | `#62D8B2` | `#1B6B55` |
| `nav.hover` | `#23262F` | `#DEE4DD` |
| `control.hover` | `#2A2E38` | `#E4E9E3` |
| `control.pressed` | `#191B22` | `#DCE2DB` |
| `focus.ring` | `#62D8B2` | `#237A62` |
| `disabled.fg` | `#5C6470` | `#9AA69D` |
| `disabled.bg` | `#191B22` | `#F0F3EF` |
| `disabled.border` | `#262A33` | `#E2E7E1` |
| `input.bg` | `#23262F` | `#F0F3EF` |
| `input.selection` | `#294238` | `#D8EAE2` |
| `input.selection_text` | `#E7EBF1` | `#26332E` |
| `evidence.highlight` | `#E3D08A` | `#F4E6A2` |
| `evidence.highlight_text` | `#2B2410` | `#33290D` |
| `scrollbar.track` | transparent | transparent |
| `scrollbar.thumb` | `#30343D` | `#B4BFB5` |
| `scrollbar.thumb_hover` | `#3A3F4A` | `#97A69B` |
| `tooltip.bg` | `#23262F` | `#FAFBF9` |
| `tooltip.text` | `#E7EBF1` | `#26332E` |
| `tooltip.border` | `#30343D` | `#D9DFDA` |
| `severity.critical` | `#e5484d` | `#B3261E` |
| `severity.critical.bg` | `#261216` | `#F7E4E2` |
| `severity.warning` | `#f5a524` | `#8A5D00` |
| `severity.warning.bg` | `#3A2E14` | `#F6ECD4` |
| `severity.notice` | `#6e8efb` | `#3D5A99` |
| `severity.notice.bg` | `#232A44` | `#E3E9F7` |
| `severity.info` | `#8b949e` | `#566159` |
| `severity.info.bg` | `#262A33` | `#E9ECE9` |
| `state.success` | `#46a758` | `#1B7230` |
| `state.success.bg` | `#16281B` | `#E1F0E4` |
| `state.warning` | `#f5a524` | `#8A5D00` |
| `state.warning.bg` | `#3A2E14` | `#F6ECD4` |
| `state.error` | `#e5484d` | `#B3261E` |
| `state.error.bg` | `#261216` | `#F7E4E2` |

Accessibility adjustments (approved): Soft Light `text.secondary`, `text.muted`, `accent`, `nav_selected_text`, and the severity/state foregrounds were deepened from the initial proposal so normal text meets WCAG AA (≥4.5:1) on every surface it appears on; dark severity/state tint backgrounds were chosen for the same reason. Severity colors are theme-specific, never shared. Disabled controls are exempt from AA but must stay distinguishable.

- **Type:** UI font `Inter` → `Noto Sans` → system sans; evidence font `JetBrains Mono` → `Noto Sans Mono` → `monospace`. Page heading 26–28px/600; section heading 16px/600; body 14px/400; metadata 12px; badges 11px/600 uppercase; evidence 13px. Accessible contrast; distinct disabled states. Respect system font scaling and high-DPI. Identical in both themes.
- **Spacing:** 4 / 8 / 12 / 16 / 24 / 32. Content padding 24–32px. Card padding 20–24px. Navigation rows 40–44px. Controls ≥34px. Cards: subtle 1px border, 12px radius. Controls and navigation: 8px radius. Focus ring `focus.ring`. Identical in both themes — switching never changes layout dimensions.
- **Elevation:** layered surfaces plus 1px borders; no shadows, no gradients. Labels inherit their container background — no unintended widget rectangles in either theme.

### 2.1 Theme switching and persistence

- A compact segmented **Light / Dark** control (sun/moon outline icons) sits near the bottom of the sidebar, above the privacy indicator. Both choices are keyboard reachable with accessible names and tooltips; the active choice uses `bg.nav_selected` + `nav_selected_text`.
- Switching applies immediately in place via one centralized theme manager (`ui/theme.py`): application-wide QPalette + QSS regenerated from the active token set, themed QPainter icons re-rendered. No restart, no QApplication/window recreation; selected page, boot selection, and control states are preserved; repeated switching creates no duplicate widgets or connections.
- Persistence: `QSettings` with organization/application `SysPanic`/`SysPanic`, single key `appearance/theme` ∈ {`light`, `dark`}. Missing, invalid, or unreadable preferences fall back to Dark. A write failure never blocks switching in the current session. This appearance preference is the **only** persisted setting — never diagnostic data, journal content, artifacts, or identifiers; no database, settings framework, or separate settings page.
- Demo mode (`--demo`) starts Dark deterministically and switches session-only via an in-memory store; it never reads or writes real user preferences. Automated tests use isolated temporary or injected stores.
- No system-theme synchronization in v0.1.0. Native KDE title bar/decorations are kept and may follow the desktop's own theme.

## 3. Window structure

```
┌──────────────┬────────────────────────────────────────────────────────────┐
│ [pulse]      │  Page heading                                              │
│ SysPanic     │  Page subtitle                                             │
│ Don't panic. │                                                            │
│ Diagnose.    │  [banner: demo / partial coverage / permission / stale]    │
│              │                                                            │
│ WORKSPACE    │  page content (scrollable cards)                           │
│ [ic] Overview│                                                            │
│ [ic] Timeline│                                                            │
│ [ic] Evidence│                                                            │
│ [ic] System… │                                                            │
│ [ic] Report  │                                                            │
│              │                                                            │
│ [Light|Dark] │                                                            │
│ [shield]     │                                                            │
│ Offline ·    │                                                            │
│ Read-only    │                                                            │
├──────────────┴────────────────────────────────────────────────────────────┤
│ Local only · Idle · v0.1.0                                                │
└───────────────────────────────────────────────────────────────────────────┘
```

- Sidebar ≈224px fixed (`bg.sidebar`): product identity with a simple activity/pulse outline icon; tagline (hidden below 1360px window width); `WORKSPACE` section label; five navigation rows 40–44px tall with consistent 18–20px outline icons; rounded selected state (`bg.nav_selected`, `nav_selected_text`); hover, focus, selected, and pressed states; a compact Light/Dark appearance switcher (§2.1) near the bottom; a privacy indicator below it (shield-check icon + `Offline · Read-only`). The phrase `Local only` appears only in the footer, not duplicated in the sidebar. No emoji icons.
- No top header bar: session controls (boot selector, Analyze) live in the Overview **Analysis session** card (§4).
- Content: `QStackedWidget`; each page is a scroll area with 24–32px padding, a page heading + descriptive subtitle, and consistently aligned cards/sections. No tabs.
- Footer ≈32px status bar: privacy statement, state, version; readable, aligned, visually separated from content. Never displays hostname or username.
- Native KDE window decoration; no menu bar, no toolbar strip, no status dialogs except the export dialog and close confirmation.

## 4. Session controls (Overview Analysis session card)

A concise `Boot session` field label with a history icon precedes the selector. The Analyze button is width-balanced against the selector; both share the same control height, padding, corner radius, and disabled styling. In M0 both remain disabled placeholders with a clear note that diagnostics are not implemented yet.

**Boot selector** (`QComboBox`, min width 320px, shrinks to 280px at narrow widths):

- Current boot: `Current boot · 59570339 · 16 Nov 13:34`
- Previous: `Previous boot · 45f38eb0 · 16 Nov 08:30`
- Older: `Boot -2 · …` through the journal limit.
- Tooltip: full boot ID, first/last observed entry times, and truncation note.
- Refresh via F5 re-reads boots; the selected boot is preserved by boot ID when possible.
- Zero previous boots: combo contains current boot and a disabled item `No previous boots in the journal`.

**Analyze button:** primary, accent-filled. During collection it is replaced by an enabled `Cancel` control; the Analyze action is unavailable until the run ends. Shortcut Ctrl+R.

**Stale banner:** if the selected boot differs from the analyzed boot, show a notice bar:
`Results are for boot 59570339. Select Analyze to collect the new selection.`

## 5. Page specifications

### 5.1 Overview

1. **Incident summary card:** boot id8, observed time range, duration, and a status chip: `Shutdown-sequence marker observed` / `Journald stopped only` / `No shutdown-sequence marker observed` / `Shutdown assessment incomplete` / `Current boot` / `Insufficient evidence` / `Demo data`.
2. **Severity counts:** four labeled cards — Critical, Warning, Notice, Info. Zero counts are dimmed, not hidden.
3. **Findings list:** ordered by severity then rule ID. Each row: severity badge, title, rule ID, one-line interpretation, and a `Show evidence` button. Expanding a row reveals the observed excerpts, suspected causes (each labeled as unconfirmed), unknowns, next steps, and linked evidence IDs. Show the first 5; `Show all N findings` expands in place.
4. **Coverage strip:** `11 of 13 sources available` with state chips for missing sources and a `tail unreliable` chip when a journal tail is incomplete; `View coverage` switches to Evidence.
5. **Crash artifacts card:** vmcore count/size, `vmcore-dmesg.txt` present, pstore records, crash kernel loaded, and each artifact's association label (`Matched to this boot` / `Possibly related` / `Unknown association`). Always includes `Binary vmcore contents were not analyzed.`
6. **Next steps card:** up to three distinct suggestions aggregated from findings, each prefixed by rule ID.

Empty (no findings): `No supported crash signatures were found in the available evidence. This does not establish that the hardware is healthy.` + coverage strip.

Idle (no analysis) — the Overview must feel complete even without data:
1. Page heading + descriptive subtitle.
2. **Analysis session card:** a `Boot session` field label (history icon) plus the boot selector and a width-balanced Analyze control. In M0 both are disabled placeholders with a clear note that diagnostics arrive with the collection milestones. Never present fake findings, hardware readings, counts, or analysis results.
3. **Empty-state card:** diagnostic outline icon, headline `Every crash leaves a clue.`, copy `Understand Linux crashes with clear, evidence-based insights from your system logs.` (word-wrapped, fully visible at all supported sizes), and a subtle shield-check icon with `Offline · Read-only · Privacy-first`.
4. Two small capability cards (crash investigation; sanitized diagnostic reports) with concise, readable descriptions when they fit naturally. Do not fill the lower empty canvas unnecessarily.

### 5.2 Timeline

- `QTableView` + `QAbstractTableModel`, columns: **Time · Event · Severity · Evidence**.
- Rows: boot start, first occurrence per finding, shutdown markers, boot end. Evidence column shows `JRN-00123` or `BTM-00001`; double-click opens Evidence at that ID.
- Severity filter chips: All (default), Critical, Warning, Notice, Info (multi-select). Filtering never reorders.
- Maximum 200 rows; footer inside the page: `Showing first 200 of N key events.`
- Empty: `No timeline events for this boot.` Insufficient source: `Timeline unavailable — the journal for this boot could not be read.` Idle: heading + subtitle and a purposeful empty state (`No timeline yet.` with a concise explanation), never a bare corner heading.
- Timestamps use local time with offset in the tooltip; rows are not grouped by minute.

### 5.3 Evidence

Two-pane splitter (left 280px):

- **Source list:** evidence-bearing sources only — `journal.system`, `journal.kernel`, `dmesg`, `vmcore-dmesg`, `pstore`, `vmcore metadata`, `artifact metadata`, `boot metadata`, `boots`. Each row: name, entry count, state badge (`Available`, `Empty`, `Truncated (head)`, `Truncated (tail)`, `Denied`, `Not found`, `Unsupported`, `Timeout`, `Error`), and `Tail unreliable` when applicable. For historical boots, `dmesg` shows `Unsupported` with the explanation that dmesg provides only current-boot evidence. The five `system.*` profile sources are reported in the Overview coverage strip, System Information, and the report's coverage table; all 13 attempted sources appear there.
- **Detail pane:** header with source name, state detail, and a filter field `Filter lines`. Body is read-only `QPlainTextEdit`, monospace, no wrapping, horizontal scroll. Line format:
  `[JRN-00123] 08:33:37.412 kernel: amdgpu 0000:0a:00.0: ring gfx_0.0.0 timeout`
- Artifact sources list paths, sizes, and boot association. Text artifacts render as evidence lines. `vmcore metadata` and `artifact metadata` show only metadata, never content.
- Denied state panel: `System journal is not readable by this user. SysPanic will not request elevated privileges.` plus the collector's neutral hint.
- Search with no matches: `No lines match "…".`
- Copy uses normal text selection (Ctrl+C); no raw JSON view.
- Jump-to-evidence (Overview finding link or Timeline double-click) highlights the **whole target line** with a soft-yellow background (`evidence.highlight` / `evidence.highlight_text` tokens, both themes) using a persistent extra selection, centers it in the viewer, and refreshes on theme switch. The highlight is independent of widget focus, so it stays visible after navigation (user-approved polish 2026-11-17).
- Idle: heading + subtitle and a purposeful empty state (`No evidence yet.` with a concise explanation of sources and coverage states).

### 5.4 System Information

Persistent banner: `Collected now — this is not a crash-time snapshot.`

Sections as cards:

| Section | Fields |
|---|---|
| OS & kernel | Distribution, version, kernel release, architecture |
| CPU | Model, logical cores, microcode version |
| Memory | Total RAM |
| GPUs | Table: PCI address, model, driver in use |
| Firmware & board | BIOS vendor/version/date, board vendor/name |
| Crash artifacts | vmcore files (name, size, mtime, boot association), `vmcore-dmesg.txt`, pstore records, crash kernel loaded |

Missing values render `Not available` with a muted reason; never an invented value. No serial numbers, UUIDs, or machine IDs appear here or in the report. Idle: heading + subtitle and a purposeful empty state (`No system profile yet.` noting the "collected now" semantics).

### 5.5 Report

- Readiness line: `Report covers boot 59570339 · bounded evidence excerpts · full logs are not included.`
- Redaction summary: `Redacted: HOST ×2, USER ×3, IP ×1, SERIAL ×1, UUID ×1, CRED ×2` (only non-zero tokens).
- Redaction notice: `Redaction is best-effort. Review the preview before sharing; unrecognized secrets may remain.`
- Preview: read-only `QPlainTextEdit`, monospace, raw Markdown text (no rendered HTML). Preview is mandatory before any copy or save action.
- Actions: `Copy Markdown` (secondary), `Save Markdown…` (primary, Ctrl+E). Both disabled until analysis completes and preview has been shown.
- Save dialog: default filename `syspanic-report-<bootid8>-<YYYYMMDD-HHMMSSZ>.md`, filter `Markdown (*.md)`, UTF-8. Success updates the footer: `Report saved.` Failure shows an inline error card with the OS error, not a modal.
- Demo mode prepends `> DEMO DATA — not collected from this machine.` to the preview.
- The page never exports automatically and never includes full logs.
- Idle: heading + subtitle and a purposeful empty state (`No report yet.` noting bounded excerpts and mandatory preview).

## 6. State matrix

| State | Trigger | Presentation |
|---|---|---|
| **Idle** | App start, no results | Overview empty state; other pages disabled placeholders; footer state `Idle` (not `Ready`); Analyze enabled |
| **Collecting** | Analyze pressed | Progress bar + `Collecting journal.kernel (3/13)` + enabled Cancel; Analyze unavailable; pages keep previous results if any |
| **Ready** | Analysis complete, findings > 0 | All pages populated; coverage footer; export enabled |
| **No findings** | Analysis complete, findings = 0 | Overview "no supported signatures" copy; Evidence/Timeline still populated; export enabled |
| **Partial** | Some sources unavailable | Yellow notice bar: `3 of 13 sources were unavailable. Findings may be incomplete.`; affected pages show state panels |
| **Tail uncertain** | Journal tail incomplete (byte cap, timeout, denial, cancellation, error) | Notice bar: `The journal tail was not reliably collected. Shutdown-sequence absence is not assessed.`; no SHD-002 |
| **Permission denied** | Journal/pstore/dmesg denied | Muted explanation + neutral hint; no sudo prompt; findings limited to available evidence |
| **Error** | Collection failed entirely | Error card: `Collection failed: <source>. Partial results are shown where available.`; Analyze re-enabled |
| **Cancelled** | User cancels | Footer `Collection cancelled.`; previous results retained; Analyze re-enabled |
| **Stale** | Boot selection changed after results | Info bar naming the analyzed boot; export remains enabled for the displayed report |
| **Demo** | `--demo` | Persistent top banner `DEMO DATA — synthetic logs; not from this machine.`; cannot be dismissed |

## 7. Microcopy rules

- Separate **observation** ("The kernel reported…"), **interpretation** ("This is consistent with…"), and **unknown** ("The logs cannot determine…").
- Never use defect or certainty language: `defective`, `broken`, `faulty hardware`, `PSU failure`, `confirmed cause`, percentages, `guaranteed`, `must replace`.
- Missing evidence: "not available" or "not readable", never "no errors" or "healthy".
- Shutdown: "A shutdown-sequence marker was observed" describes only the retained journal ending. `Journal stopped` alone means journald stopped; it does not prove a clean system shutdown. Missing markers never prove power loss.
- Artifacts: "Matched to this boot", "Possibly related", or "Unknown association". Never imply that an unverified dump corroborates the selected incident; mtime alone is not confirmation.
- Redaction: "best-effort", never "guaranteed" or "safe to share" without review.
- Power: "the logs cannot distinguish power loss from a hard reset, hang, watchdog, or firmware reset."
- Current hardware: always "collected now", never "at the time of the incident".
- Severity is impact, not confidence; never show a confidence score.
- Numbers: use localized time, IEC sizes (MiB), and exact counts.

## 8. Interaction and keyboard

| Shortcut | Action |
|---|---|
| Ctrl+R | Analyze / retry |
| Ctrl+E | Export report |
| Ctrl+1…5 | Switch page |
| F5 | Refresh boot list |
| Esc | Cancel collection (not export) |
| Tab / Shift+Tab | Standard focus order: boot selector → Analyze → nav → page content → export |

- Changing the boot selector never starts analysis automatically.
- Analyze is single-flight; repeated activation is ignored.
- Cancellation terminates the running subprocess; UI state updates only after the worker acknowledges.
- Window close during collection: request cancel and wait up to 5 s. If the worker has not acknowledged, ignore the close event, keep the window open, and show `Finishing collection before closing…`; close automatically only after the worker finishes. Never terminate or destroy a running QThread.
- No desktop or browser automation is used for QA; the manual script is in [05-implementation-plan.md](05-implementation-plan.md).

## 9. Accessibility and resizing

- Text contrast in **both themes**: normal text ≥ 4.5:1 (WCAG AA); primary on canvas ≥ 11:1; muted on surface ≥ 4.5:1; badge text on tinted background ≥ 4.5:1; accent and focus ring against adjacent surfaces ≥ 3:1. Automated contrast tests enforce the token pairs.
- Severity always includes a text label; color is supplementary.
- Focus visible on every interactive control; no focus traps; nav items are keyboard reachable.
- Minimum navigation row height 40px and control height 34px; evidence text never below 11px.
- Layout at 1280×720: sidebar tagline hides, combo shrinks to 280px, sidebar stays ≈224px, content scrolls vertically; no horizontal page scroll except evidence text; no clipped controls.
- Respect the system font scale; avoid fixed-height text containers. No custom cursor, no animations, no splash screen.

## 10. Explicit UI exclusions

No QML, WebEngine, chart library, external icon pack (local QPainter/asset outline icons only), onboarding wizard, settings dialog or separate settings page, system-theme synchronization, notification tray integration, or auto-refresh polling. No rendered Markdown/HTML preview; the raw sanitized text is the source of truth. The only appearance control is the sidebar Light/Dark switcher (§2.1).
