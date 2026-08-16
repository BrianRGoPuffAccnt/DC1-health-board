# DC1 Health Board — User Guide

The DC1 Health Board (DC1 HCDB) is a live operations dashboard for Gopuff's DC1 distribution center in Cherry Hill, NJ. It connects data from Google Sheets used daily by the DC operations, transportation, and supply chain teams and surfaces it in one place so anyone — from the floor to leadership — can see the current state of shipping without hunting across spreadsheets.

---

## Who This Is For

| Role | Primary Use |
|---|---|
| DC Floor Lead / OA | Daily Health Check — pallet staging progress, cross-dock readiness, labor focus by MFC |
| Transportation Coordinator | Transportation Control — carrier SDT windows, open TOs, route timing risk |
| Supply Chain BP (SCBP) | MFC LookUp — site profiles, lane assignments, contact directory |
| Site Leadership / DC Manager | Executive Briefs — shipping readiness summary, outstanding sites by SDT window |
| Regional Manager | Home → Live Update — current health status, top 3 risks, window mix |

---

## Pages at a Glance

### Home
The entry point. Shows a live pulse of DC1 operations including:
- **Live Health** status (Green / Yellow / Red) driven by SDT windows × OB Tracker × Fill Rate
- **TO Progress** — how many transfer orders are loaded vs still open
- **Top 3 Live Risks** — the carrier routes most at risk of missing their departure window
- **Window Mix** — a visual breakdown of routes by SDT timing status
- **Executive Briefs** and **Leadership Brief** subviews provide leadership-ready summaries for sharing

### Daily Health Check
The primary view for DC floor leads. Two embedded panels:

**Ops & Labor Pulse** (Fill Rate / Pallet Ops driven)
- Pallet completion percentage — how many pallets are staged vs total for today's ship date
- Open pallets remaining for prep and staging
- Active GUSTOs and MFC destinations
- Units Left (units not yet picked) with fill rate progress
- Cross-Dock Readiness bar chart by lane
- Labor Focus by MFC — the specific GUSTOs that need the most attention right now

**OA Performance** (OA productivity metrics)

### Transportation Control
For the transportation team managing daily carrier loads.
- Route-by-route progress: Loaded vs Open TOs per carrier
- SDT timing windows — Load Ready Time, Departure Time, Dock Door
- Timing Risk flags: Normal, Work Remaining, Past Departure Risk, Missing SDT Window
- GUSTO lane breakdown — open GUSTOs grouped by delivery location per carrier
- Allocation vs OB Tracker — how many GUSTOs were allocated vs how many are in the tracker, and any gap

### MFC LookUp
A searchable directory of every MFC served by DC1. Search by site name, number, city, lane, carrier owner, or SCBP name.

Each MFC profile shows:
- **Lane** — the shipping region this site is part of (e.g. MCO, PHL, JFK)
- **Active GUSTO** — the current transfer order for this site if one is in flight
- **People** — Site Leader, Regional Manager, SCBP, and Slack channel
- **Location** — full address, city/state, delivery day and window, business hours
- **S&OP Signal** — hypercare status and priority flag if the site is flagged
- **Lane SDT Windows** — what time the truck for this lane departs and which dock door it uses
- **Other MFCs in the same lane** — useful for understanding total lane scope

### Executive Briefs
A leadership-facing summary designed for the Google Sites Executive Briefs page. Shows:
- Overall shipping health with Red / Yellow / Green executive status
- Loaded percentage, open TOs, pallet exceptions
- Outstanding sites table broken down by SDT carrier window
- Per-carrier detail expandable by route
- On-Time Shipping Readiness and Pallet & Fill Rate Readiness summaries
- Copy-ready executive brief text for Slack or email

### Continuous Improvement
Tracks LEAN and 5S projects underway at DC1 — project status, owners, current/target state, action matrix, and flowchart builder.

### Signal Notifications *(coming soon)*
Will scan carrier and ops Slack channels for operational signals — late GUSTOs, carrier delays, escalations — and surface them here with enriched context and action links.

### Decision Support Chat
A Claude-powered assistant (Home section) that answers questions against live DC1 data: carrier route progress and open TOs, MFC profiles, carrier/SCBP assignments, GUSTO status, and delivery windows. Strictly read-only — it cannot send messages, write to any spreadsheet, or take action, only describe what the current data shows.

---

## Key Terms

| Term | What It Means |
|---|---|
| **GUSTO** | A transfer order number (e.g. GUSTO-3495434) — one shipment to one MFC destination |
| **MFC** | Micro-Fulfillment Center — a Gopuff delivery site (e.g. PHL_Philadelphia_367) |
| **Lane** | A shipping region grouping MFCs by geography (e.g. PHL, JFK, MCO, ATL) |
| **SDT** | Standard Departure Time — the scheduled load-ready and departure window per carrier |
| **Cross-Dock** | The lane code used to organize pallets on the dock floor (same as lane) |
| **OB Tracker** | The Outbound TO Tracker Google Sheet — updated by the DC team daily with TO status |
| **Fill Rate** | The Operations Fill Rate sheet — tracks pallet staging, units left, and dock activity |
| **Units Left** | Units allocated to a GUSTO but not yet staged or scanned (formerly "NYP" / units not yet picked) |
| **Open TO** | A transfer order that is not yet in Loaded / Closed status |
| **Allocation History** | The DC1 Allocations Tracker — the original source of what GUSTOs were planned for each ship date |

---

## Reading the OB Tracker

The OB TO Tracker is DC1's most detailed live source — Live Update, Executive Briefs, and Decision Support Chat are all built on top of it. A few of its conventions aren't self-explanatory:

**Status progression** — every GUSTO row moves through four states in order:

`Allocated` → `Picking` → `Staged` → `Loaded`

- **Allocated** — assigned to the tracker, picking hasn't started
- **Picking** — actively being picked right now
- **Staged** — picking finished, palletized and ready to load, but not yet on a truck
- **Loaded** — physically loaded and gone. This is the only state that counts as fully done — Staged is close, but not confirmed complete.

**Planned Ship Date classification** (Executive Briefs' Previous/Current Operational Day tables) groups every GUSTO by its Planned Ship Date and classifies the whole date:

- **CLOSED** — every GUSTO for that date is Loaded
- **ACTIVE** — at least one GUSTO is Picking, or the date is a mix that's neither 100% Loaded nor 100% Allocated (e.g. some Staged, some still Allocated) — anything short of fully Loaded still counts as outstanding
- **UPCOMING** — every GUSTO for that date is still Allocated

More than one date showing ACTIVE at once is a real signal, not a bug — it usually means an earlier date never fully closed out while a newer one is already being worked.

**Picker columns** (`PICKER(S) DAYS`, `PICKER(S) NIGHTS`) use shorthand: a picker's name is followed by the placard number(s) they've completed toward that GUSTO, where **one placard = one pallet**. A `/` divider means two pickers split the same GUSTO. Examples:

- `DOM 1-3` — DOM completed placards 1 through 3
- `DOM 1-3 / JAY 4` — DOM did placards 1–3, JAY did placard 4, same GUSTO
- `KAREEM 1, 3 / NIA 2-5` — a non-contiguous split between two pickers

**Shift schedule**: Day 7:00 AM–3:00 PM, NS (second shift) 3:00 PM–11:30 PM Eastern. NS is expected to be phased out eventually under a day-shift-only model — not yet scheduled, so the app tracks both shifts as parallel scenarios rather than assuming one is "current."

---

## How Data Flows

```
DC1 Allocations Tracker  →  what was assigned (GUSTOs, lanes, pallets)
OB TO Tracker            →  what's being worked (status per GUSTO — staged / loaded / closed)
Operations Fill Rate     →  what's been prepped (pallets scanned, units remaining, dock activity)
DC1 SDTs                 →  when each carrier departs (load ready time, departure time, dock door)
Training Cheat Sheet     →  MFC directory (lane, delivery day/window, addresses, linehaul)
GoPuff Site Information  →  contact directory (SCBP, RM, Site Leader per location)
S&OP HyperCare Dashboard →  performance flags (hypercare status, OOS %, site tier)
```

The dashboard refreshes connected sheets automatically at 4 AM and 4 PM. You can trigger a manual refresh from the Data Inputs Menu (sidebar) at any time.

---

## Navigation Tips

- Click any **MFC site card** in the MFC LookUp gallery to open its full profile
- From a profile, click the lane name to see all other MFCs on the same route
- The **Fullscreen** button in each Google Sites embed opens the view directly in Streamlit for more detail
- All views support a **Copy-ready** text area at the bottom for pasting summaries into Slack or email

---

## Data Questions or Issues

If something looks wrong or outdated, the most likely cause is one of:
1. The source Google Sheet was updated but the app hasn't refreshed yet — use the Refresh button in the sidebar
2. The sheet was not shared with the service account — check with the dashboard owner
3. A column name changed in the source sheet — the app uses flexible column matching but renamed columns can break joins

For feature requests or bugs, contact the dashboard owner (DC1 Supply Chain lead).
