# DC1 Supply Chain Health Board

A local, lightweight command board for turning DC1 allocation files, Command Center snapshots, and carrier status updates into executive-ready supply chain health checks.

## What this MVP does

- Uploads a daily allocation workbook.
- Reads `Carrier Summary` and `Site Summary`.
- Captures manual Command Center metrics.
- Uploads Command Center snapshot history files and stores each snapshot with source, timestamp, and upload time.
- Tracks carrier tender/confirmation status.
- Uploads weekly OTP bridge workbooks.
- Summarizes carrier reliability, late pallets, missing check calls, and bridge reasons.
- Uploads the DC1 OA performance workbook.
- Summarizes recent Ops productivity, UPH, bridge notes, and weekly pack UPH trend.
- Normalizes tender pipeline workbooks into a validated Uber Freight upload table.
- Builds Uber Freight BulkUpload workbooks from daily allocation files without using the Ship Allocations Template.
- Flags missing TMS fields, duplicates, and conflicting TO updates.
- Shows a Data Inputs Health panel so users can see which uploaded sources are powering the current dashboard.
- Shows a BulkUpload validation summary before download, including rows ready, review rows, duplicates, conflicts, and issue reasons.
- Saves generated BulkUploads into a daily run history with optional notes.
- Replaces shared reference workbook uploads by filename so the latest exported version is active.
- Exports clean normalized intake and Uber Freight upload files as CSV or XLSX.
- Captures read-only carrier Slack signals for decision support.
- Saves uploaded presentation and PDF files to SQLite for later download.
- Provides Presentation Locker and PDF Locker destination views for saved files.
- Adds LEAN/5S project spaces with project profiles, wins, next steps, ownership matrices, flowcharts, and per-project file lockers.
- Stages shared reference workbook exports with detected tabs, columns, tags, and notes.
- Generates copy-ready snapshot reports for Transportation, Operations, Executive, and future Finance workflows.
- Produces a screenshot-ready health view.
- Generates a copy-ready leadership brief.

## Quick start

```bash
cd dc1-health-board
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The app creates a local SQLite database at:

```text
data/dc1_health_board.sqlite
```

This database stores saved tender batches and carrier signals so they survive browser refreshes and can be shared by users connected to the same running Streamlit instance.
It also stores uploaded presentation and PDF files for later retrieval from the app.
Shared reference workbook exports are stored with metadata so useful files can later be promoted into app functionality.


## Streamlit hosting and Google Sites embed

This app is now deployable to Streamlit Community Cloud as the live engine behind the Google Sites page.

Deployment files added for hosted use:

- `STREAMLIT_DEPLOYMENT.md`
- `.streamlit/secrets.example.toml`

Hosted Streamlit should use a Google Cloud service account, not the local desktop OAuth flow. Add the service account JSON values to Streamlit app secrets under `[gcp_service_account]`, then share each connected Google Sheet with the service account `client_email` as a viewer.

The app can also seed its connected Google Sheet catalog from Streamlit secrets. Add one `[[google_sheets]]` block per live source:

```toml
[[google_sheets]]
tag = "SDT Schedule"
notes = "Standard Departure Times"
source_url = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit"
```

On first hosted run, those secret-defined sheet URLs are synced into the app cache. The app checks every 5 minutes while awake, runs full connected-sheet refreshes at the scheduled full-refresh slots, and refreshes live operating sheets hourly from 5 AM through 11 PM.

For the Google Sites embedded operating views, add `PHL Ships` as a connected Google Sheet. The app reads tabs named like `7/16 shipDate`, detects the `Alloc`, `Totals`, and `SDT` tables by their headers, then compares `PHL Ships` ship dates against the OB Tracker planned ship date by `TO Number`.

For Google Sites, embed the deployed Streamlit URL. Use direct query URLs for specific page modules, for example:

```text
https://YOUR-APP.streamlit.app/?site_embed=home_live_metrics&embed=true
https://YOUR-APP.streamlit.app/?site_embed=daily_health&embed=true
https://YOUR-APP.streamlit.app/?site_embed=transportation_control&embed=true
https://YOUR-APP.streamlit.app/?site_embed=executive_brief&embed=true
https://YOUR-APP.streamlit.app/?site_embed=market_profiles&embed=true
```

See `STREAMLIT_DEPLOYMENT.md` for the full deployment checklist.

## Local operator workflow

1. Start the app with `streamlit run app.py`.
2. Upload the daily allocation files from the sidebar.
3. Open `Transportation > Ship Allocation Builder`.
4. Confirm carrier mapping, origin IDs, SCACs, equipment, mode, and order type.
5. Review the BulkUpload validation summary.
6. Download the Uber Freight BulkUpload XLSX only after the ready/review counts make sense.
7. Add optional run notes and save the generated BulkUpload to SQLite.
8. Use `Home > Executive Overview` for the Data Inputs Health panel and copy-ready executive snapshot.
9. Use `Home > Reports` to download a SQLite backup before moving machines or sharing the prototype.

## Command Center Snapshots

The sidebar accepts an optional Command Center snapshot history file as `CSV`, `XLSX`, or `XLSM`.
Useful columns include:

- Created or Created Orders
- Cancelled or Cancelled Orders
- Created vs Forecast
- DT > 50m
- DT > 60m
- Time, Date, Timestamp, Updated, or Last Updated

Each detected row is saved to SQLite with the source file and sheet. The Executive Overview uses the latest saved snapshot while preserving previous readings for trend review. Manual entries can also be saved from the sidebar expander.

## Brand layer

The app includes a lightweight gopuff-inspired visual layer:

- `styles.css`
- `assets/gopuff-logo.png`
- `assets/gopuff-wordmark-white.jpeg`
- `assets/gopuff-wordmark-blue.jpeg`

The CSS controls the header, sidebar, tabs, metrics, buttons, and table framing.

## Expected allocation workbook tabs

- `Carrier Summary`
- `Site Summary`

The app expects the allocation structure seen in the DC1 files:

- Carrier
- TO Number
- goPuff Site Location
- Site ID
- UNITS
- LINES
- Pick Date
- Ship Date
- Delivery Date
- Pallets Final
- Water Weight
- Non-Water Weight

## Expected OTP bridge workbook columns

The app can read weekly bridge tabs that include:

- MEID
- TO #
- Business
- Status
- SCAC
- Origin
- Destination
- Deliver By
- Actual Delivery Arrival
- Pallets
- On-Time Status
- Detailed Bridge

The bridge data is used to create a carrier reliability view and add historical OTP context to the executive health drivers.

## Expected Ops productivity workbook

The app can read the DC1 OA performance workbook pattern:

- Daily date-named tabs such as `4.27`, `4.28`, `4.29`, `4.30`
- Recent productivity blocks with name, UPH, units, hours, bridge, and accepted status
- `Pack UPH WoW` for weekly pack UPH trend

The Ops data is used to show whether DC throughput and productivity are supporting the transportation plan.

## Tender Pipeline

The Tender Pipeline tab is retained as an advanced QA/review workspace for normalized tender batches. The primary daily allocation workflow now lives in the Ship Allocation Builder tab.

Current validation checks include:

- missing TO / primary reference
- missing destination or site ID
- missing ship or delivery dates
- missing pallets or total weight
- missing origin external ID
- missing vendor external ID
- duplicate TO rows with identical key fields
- conflicting TO rows with changed key fields

Rows marked `Ready` can be exported as an Uber Freight upload CSV. Rows marked `Needs Review`, `Duplicate`, or `Conflict` should be resolved before upload.

Tender batches can be saved to SQLite and loaded later from the Tender Pipeline tab.

The tab also provides two download paths:

- clean normalized intake, including validation status and source file/sheet traceability
- Uber Freight upload export for rows marked `Ready`

Both downloads can be generated as `CSV` or `XLSX`.

## Ship Allocation Builder

The Ship Allocation Builder tab recreates the useful part of the Ship Allocations Template inside the app. Upload daily allocation files from the sidebar, choose the source groups to include, review or edit carrier mapping, then generate a 29-column Uber Freight BulkUpload workbook.

Phase 1 supports daily allocation files such as:

- DC1 allocation workbooks with a `Site Summary` tab
- DC2 order workbooks with an `Allocation Summary` tab

Generated BulkUpload files can be downloaded immediately and saved to SQLite for later download from the same tab.
Saved files appear in the Daily Run History table with source files, source groups, row counts, ready counts, issue counts, and run notes.

## Carrier Signals

The Carrier Signals tab is a manual intake area for carrier Slack messages. It classifies messages into operational signals such as receiving constraints, water pallet issues, reschedule requests, pickup/delivery delays, compliance/audit items, and shipment exceptions.

This module is read-only decision support. It does not send messages to carriers or automate carrier communication. The end user remains responsible for deciding and executing any follow-up.

Carrier signals can be saved to SQLite. Status changes in the signal grid should be saved with the `Save Signal Updates to SQLite` button.

## File Library

The sidebar includes uploaders for presentation and PDF files. Saved files appear in the `Presentation Locker` and `PDF Locker` views, where users can select and download the original file.

Supported presentation formats:

- `ppt`
- `pptx`
- `pptm`
- `pps`
- `ppsx`
- `key`
- `odp`

## LEAN/5S

The `Operations > LEAN/5S` view creates lightweight project spaces for process improvement work.
Each project stores:

- project purpose
- owner / lead
- area
- status
- current state
- target state
- project wins
- next steps
- ownership / deadline matrix rows with risk coloring
- warehouse and LEAN/5S flowchart nodes and connections
- project-specific uploaded files

Project files are stored as-is in SQLite and can be downloaded from the project file locker.
The Matrix Builder tracks areas of ownership, owners, deadlines, status, and notes. Deadline risk is color-coded from overdue through on-track.
The Flowchart Builder stores structured nodes and connections with warehouse-oriented step types such as dock, forklift, pallet, staging, carrier handoff, quality check, and 5S steps. It also exports Mermaid diagram text for later documentation or presentation use.

## Reference Sheets

The Reference Sheets view is a staging area for shared Google Sheet exports and other workbook references. Upload reference workbooks from the sidebar, then tag them as:

- Carrier Mapping
- PHL Ships
- Rates
- Schedules
- Allocation History
- Contacts
- Ops Reference
- Other

The app saves the original file and detects each workbook's sheet names, preview row counts, column counts, and column names. This lets the team keep shared sheets in sync with the dashboard before deciding which sources should become full app modules.

When a reference workbook is uploaded again with the same filename, the app treats it as the latest active version. It replaces the stored file/blob and metadata while keeping the existing tag and notes unless new values are provided. The table shows replacement count and replacement timestamp.

Reference Sheets can also connect directly to Google Sheets after local OAuth setup:

- create a Google Cloud OAuth desktop client
- download the client file as `google_credentials.json`
- place `google_credentials.json` in the project folder
- run `pip install -r requirements.txt`
- use `Operations > Reference Sheets > Connect Google Sheet`

Connected Google Sheets are synced into SQLite with sheet metadata, values, Drive permissions, modified time, and recent Drive Activity when the Google APIs return it. True live co-editor presence is not exposed like the native Google Sheets UI, so the app shows shared users and recent activity instead.

## Reports

The Reports tab generates copy-ready snapshots for:

- Executive Combined
- Transportation
- Operations
- Finance Placeholder

The Finance Placeholder is intentionally prepared before finance data is connected. It reserves space for linehaul rate, fuel surcharge per mile, accessorials, spot vs contract cost, benchmark lane rate, and invoice variance.

Email sending and scheduled reports are not active in this local MVP. A future controlled version can add draft-only email generation first, then scheduled sends after access, review, and approval controls are defined.

## MVP positioning

This is not intended to replace TMS, Command Center, or Encompass systems. It is a local visibility layer that helps a Transportation Specialist answer:

- Are we healthy today?
- Where is the risk?
- What changed?
- What action is being taken?
