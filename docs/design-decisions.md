# OpenSOAR Design Decisions

This document captures UX and architectural design choices made during development so they persist across sessions and serve as a reference for future work.

---

## Alert Detail Page — Single-Page Layout (No Tabs)

**Decision**: Use a single scrollable page instead of tabs for the alert detail view.

**Why**: When an analyst is triaging 100+ alerts, they need to scan everything about an alert quickly without clicking between tabs. Tabs hide information and add clicks. A vertical scroll lets them see header → details → IOCs → playbook runs → timeline → evidence in one motion. The right sidebar handles secondary actions (run playbook, metadata) without interrupting the flow.

**Layout**: 8-col left (main content) + 4-col right (sidebar actions/info). Everything on one page.

---

## Unified Timeline (Audit Log + Comments)

**Decision**: Comments and system events (status changes, assignments, playbook triggers, enrichments) live in one unified timeline.

**Why**: Splitting comments from the audit log means an analyst has to mentally reconstruct what happened. In incident response, the sequence matters — "who changed what, when, and what did they say about it" should be one stream. Comments are visually differentiated (accent-colored node, bubble-styled detail) but appear in chronological order with system events.

**Future**: AI-generated summary of the timeline can be added at the top of the timeline card, synthesizing comments + system events into a brief "what happened so far" paragraph.

---

## No Acknowledge Button

**Decision**: Removed the standalone "Acknowledge" action from the alert detail page.

**Why**: Acknowledge (moving status from `new` → `in_progress`) is redundant with Claim. When an analyst claims an alert, it automatically moves to `in_progress`. Having a separate Acknowledge button is confusing — "what's the difference between acknowledging and claiming?" There is no real-world scenario where an analyst wants to mark an alert as in-progress without also taking ownership. If they just want to look at it, they don't need to change the status. The transition happens naturally through Claim.

---

## Determination Field

**Decision**: Alerts have a `determination` field with values: `unknown` (default), `malicious`, `suspicious`, `benign`. Must be set to a non-unknown value before an alert can be resolved.

**Why**: The core workflow of IR is: receive alert → investigate → determine if real → act on it. Determination is separate from status because an alert can be determined as malicious but still be open (under active response). Requiring determination before resolving forces analysts to classify every alert — this feeds metrics and helps tune detection rules. Values:
- **Unknown** — default, not yet classified
- **Malicious** — confirmed security incident, requires response
- **Suspicious** — needs more investigation, can't determine yet
- **Benign** — real activity but not malicious (e.g., authorized pentest, false positive)

Determination is shown in the resolve dialog (required) and is also editable inline on the detail page during investigation. Can be set by analysts or by automation/playbooks.

---

## Reassign to Any Analyst

**Decision**: Alert reassignment shows a dialog with all active analysts rather than just "reassign to me".

**Why**: In a SOC team, alerts often need to be routed — L1 escalates to L2, specialist hands off to another specialist on a different shift. "Reassign to me" only covers one case. The dialog lists all active analysts with name/username/role so the assigner can pick the right person. This also enables future features like workload-based suggestions.

---

## Sidebar Navigation — Settings at Bottom

**Decision**: Settings link lives at the bottom of the sidebar, grouped with the user avatar and sign-out.

**Why**: Settings is an infrequent action. Putting it alongside primary nav (Dashboard, Alerts, Runs, Playbooks) gives it undeserved visual weight. Every SOAR/SIEM product (Splunk, Sentinel, XSOAR) puts settings in the bottom or behind a user menu. The primary nav should only contain the pages analysts visit frequently during their shift.

---

## Checkbox Column — Hidden Until Needed

**Decision**: The bulk-select checkbox column in the alerts list is hidden by default, revealed on table hover or when any selection is active.

**Why**: Most of the time analysts are scanning the list, not bulk-selecting. The checkbox column takes 40px of space and adds visual noise. CSS transitions (width/padding/opacity) make it appear smoothly on hover. Once a selection is active, the column stays visible until cleared. The bulk action bar is a fixed bottom overlay (not inline) to avoid layout shift.

---

## Row Click Navigation

**Decision**: Clicking anywhere on an alert/run row navigates to its detail page. Interactive sub-elements (checkboxes, links) use `stopPropagation`.

**Why**: Fitts's law — the whole row is a larger target than a small title link. Analysts triaging fast shouldn't have to aim at the title text. Sub-elements like checkboxes and the source-IP link prevent bubbling so they still work independently.

---

## Dashboard — IR Analyst Perspective

**Decision**: Dashboard shows priority queue (severity-weighted), MTTR, my assignments, unassigned count — not generic charts.

**Why**: An IR analyst starting their shift needs to know: "What's most urgent? What's assigned to me? How are we doing on response times? What's unassigned?" Generic bar charts of severity distribution don't answer these questions. The priority queue is sorted by severity (critical > high > medium > low) so the analyst can start from the top.

---

## 12-Column Grid System

**Decision**: Use a consistent 12-column CSS grid across dashboard and detail pages for alignment.

**Why**: When stat cards at the top use one column width and content below uses a different grid, the result is misaligned edges. A 12-column grid with `col-span-*` ensures everything lines up. Stats: 4×3col. Main content: 8col. Sidebar: 4col.

---

## framer-motion for All Animations

**Decision**: All animations (dialogs, drawers, toasts, dropdowns, page transitions, timeline entries, checkboxes) use framer-motion, not CSS animations.

**Why**: Spring physics feel better than CSS easing for interactive elements. AnimatePresence handles enter/exit animations properly (CSS can't animate unmounting). Layout animations prevent janky reflows. Consistent animation library means consistent feel. The tradeoff is bundle size, but framer-motion is already a dependency for the sidebar.

---

## Component Library — Custom shadcn-Inspired

**Decision**: Build custom components (Card, Dialog, Drawer, Toast, Input, Table, etc.) inspired by shadcn/ui patterns rather than using a component library.

**Why**: Full control over dark theme, animation behavior, and API surface. No dependency risk. Components are tailored to SOAR-specific needs (severity badges, execution plans, IOC values with enrichment dropdowns). The pattern is: unstyled logic + Tailwind classes + framer-motion, with `cn()` utility for conditional classes.

---

## Dark Theme Only (For Now)

**Decision**: Single dark theme with CSS custom properties.

**Why**: SOC analysts work in dark environments (NOCs, SOCs). Dark theme reduces eye strain during long shifts. If light theme is needed later, the CSS custom property system (`--color-bg`, `--color-surface`, etc.) makes it a simple theme swap without touching component code.

---

## "Resolved" Not "Closed"

**Decision**: Alert terminal status is `resolved`, not `closed`. Lifecycle: `new` → `in_progress` → `resolved`.

**Why**: "Closed" implies swept under the rug. "Resolved" implies the analyst investigated, made a determination, and took appropriate action. The terminology matters in compliance reports and SLA tracking — stakeholders and auditors understand "resolved" better than "closed". The resolve action requires a determination (malicious/suspicious/benign) which enforces classification before an alert leaves the pipeline.

---

## Partner Field — MSSP Multi-Tenancy

**Decision**: Every alert has an optional `partner` field (string, up to 100 chars) for MSSP billing and tenant-scoped analytics.

**Why**: MSSPs manage security for multiple external clients. Each alert needs to be attributable to a partner/tenant for:
- **Billing**: Count alerts per partner per period
- **SLA tracking**: MTTR per partner to measure service quality
- **Dashboarding**: Per-partner open alert counts, severity breakdown
- **Filtering**: Analysts working a specific partner's queue

Partner is extracted from webhook payloads (looks for `partner`, `tenant`, `customer`, `organization` fields) and can also be set manually or via API. Dashboard shows partner breakdown with open counts and per-partner MTTR. Alerts list has a partner filter and column.

**Future**: Partner will evolve into a first-class tenant model with per-partner playbook configs, notification channels, and SLA thresholds.

---

## Determination Required to Resolve

**Decision**: An alert cannot be resolved while its determination is `unknown`. The resolve dialog only shows non-unknown options (malicious, suspicious, benign).

**Why**: Every alert that exits the pipeline should have a classification. This feeds:
- Detection tuning (benign → rule needs adjustment)
- Threat intelligence (malicious → confirmed IOCs)
- Analyst performance metrics (determination accuracy)
- Compliance reports (auditable trail of analyst judgment)

Without this enforcement, analysts would bulk-resolve without classifying, making the data useless for improving detection.
