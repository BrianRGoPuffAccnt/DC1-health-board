from __future__ import annotations

import base64
import html
import json
import re
import sqlite3
from difflib import SequenceMatcher
from urllib.parse import quote
from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components


APP_TITLE = "DC1 Supply Chain Health Board"
DB_PATH = Path("data/dc1_health_board.sqlite")
STYLE_PATH = Path("styles.css")
LOGO_PATH = Path("assets/gopuff-logo.png")
GOOGLE_CREDENTIALS_PATH = Path("google_credentials.json")
GOOGLE_TOKEN_PATH = Path("data/google_token.json")
LIVE_GOOGLE_ONLY = True
GOOGLE_REFRESH_SCHEDULE_HOURS = [4, 16]
AUTO_REFRESH_CHECK_MINUTES = 15
STATUS_OPTIONS = ["Not Tendered", "Tendered", "Confirmed", "At Risk", "Escalated"]
LEAN_MATRIX_COLUMNS = ["area", "owner", "deadline", "status", "notes"]
LEAN_MATRIX_STATUS_OPTIONS = ["Not Started", "In Progress", "Blocked", "Complete", "Sustained"]
LEAN_FLOW_NODE_TYPES = [
    "Start/End",
    "Process",
    "Decision",
    "Dock",
    "Forklift",
    "Pallet",
    "Staging",
    "Inventory",
    "Carrier Handoff",
    "Quality Check",
    "5S Sort",
    "5S Set in Order",
    "5S Shine",
    "5S Standardize",
    "5S Sustain",
]
LEAN_FLOW_NODE_COLUMNS = ["node_id", "label", "node_type", "lane", "notes"]
LEAN_FLOW_EDGE_COLUMNS = ["from_node", "to_node", "label"]
OTP_COLUMNS = [
    "MEID",
    "TO #",
    "Business",
    "Status",
    "SCAC",
    "Origin",
    "Destination",
    "Deliver By",
    "Actual Delivery Arrival",
    "Pallets",
    "On-Time Status",
    "Detailed Bridge",
]
OPS_LOOKBACK_DAYS = 10
TENDER_EXPORT_COLUMNS = [
    "ACTION",
    "PRIMARY_REFERENCE",
    "PO NUMBER",
    "MATERIAL TRANSFER ORDER NUMBER",
    "BUSINESS_UNIT_TYPE",
    "PICKUP_EARLIEST_DATETIME",
    "PICKUP_LATEST_DATETIME",
    "DELIVERY_EARLIEST_DATETIME",
    "DELIVERY_LATEST_DATETIME",
    "VENDOR_EXTERNAL_ID",
    "ORIGIN_EXTERNAL_ID",
    "DESTINATION_EXTERNAL_ID",
    "CUSTOMER_LINE_ITEM_ID",
    "QUANTITY",
    "LINES",
    "PALLETS",
    "WATER_WEIGHT",
    "NON_WATER_WEIGHT",
    "TOTAL_WEIGHT",
]
SHIP_BULK_UPLOAD_COLUMNS = [
    "ACTION",
    "PRIMARY REFERENCE",
    "PO NUMBER",
    "MATERIAL TRANSFER ORDER NUMBER",
    "BUSINESS_UNIT_TYPE",
    "PICKUP_EARLIEST_DATETIME",
    "PICKUP_LATEST_DATETIME",
    "DELIVERY_EARLIEST_DATETIME",
    "DELIVERY_LATEST_DATETIME",
    "VENDOR_EXTERNAL_ID",
    "ORIGIN_EXTERNAL_ID",
    "DESTINATION_EXTERNAL_ID",
    "CUSTOMER_LINE_ITEM_ID",
    "QUANTITY",
    "QUANTITY_UOM",
    "LINES",
    "WEIGHT",
    "WEIGHT_UOM",
    "WATER_WEIGHT",
    "EQUIPMENT_TYPE",
    "SCAC",
    "MODE_TYPE",
    "ORDER_TYPE",
    "HANDLING_UNIT",
    "HANDLING_UNIT_UOM",
    "WATER_PALLETS",
    "LTL_CLASS",
    "TOP_OPERATIONAL_COMMENTS",
    "TOP_CARRIER_COMMENTS",
]
TENDER_VALIDATION_COLUMNS = [
    "source_file",
    "source_sheet",
    "to_number",
    "carrier",
    "site_id",
    "location_name",
    "ship_date",
    "delivery_date",
    "pallets",
    "total_weight",
    "vendor_external_id",
    "origin_external_id",
    "destination_external_id",
    "validation_status",
    "validation_issues",
    "row_fingerprint",
]
CARRIER_CHANNELS = {
    "WARP": "warp-mike",
    "Misfits": "ext-misfits-gopuff",
}
SIGNAL_STATUSES = ["Open", "Monitoring", "Resolved", "Escalated"]
PRESENTATION_FILE_TYPES = ["ppt", "pptx", "pptm", "pps", "ppsx", "key", "odp"]
PDF_FILE_TYPES = ["pdf"]
SHIP_ALLOCATION_SOURCE_OPTIONS = ["DC1", "DC2", "ALC", "Inbound", "CoreMark", "Southern G", "Unknown"]
REFERENCE_SHEET_TAGS = [
    "OTP",
    "SDT Schedule",
    "OB TO Tracker",
    "Fill Rate",
    "Core-Mark",
    "RFP Cost",
    "Tender Template",
    "Transportation Schedule",
    "Carrier Mapping",
    "Rates",
    "Schedules",
    "Allocation History",
    "Contacts",
    "Ops Reference",
    "Other",
]
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive.activity.readonly",
]
NAVIGATION = {
    "Home": ["Executive Overview", "Live Update", "Executive Briefs", "Leadership Brief", "Reports"],
    "Transportation": [
        "Ship Allocation Builder",
        "Schedule Sync",
        "Outbound TO Control",
        "MFC Site Map",
        "Allocation Detail",
        "Tender Pipeline",
        "Carrier OTP Bridge",
        "Carrier Signals",
        "Cost & Lane Intelligence",
    ],
    "Operations": [
        "Operations Productivity",
        "Fill Rate / Pallet Ops",
        "Core-Mark",
        "Market Profiles",
        "Placard Builder",
        "Reference Sheets",
        "LEAN/5S",
        "Presentation Locker",
        "PDF Locker",
    ],
}
EMBED_TARGETS = {
    "home_live_metrics": "Home Live Metrics",
    "live_metrics": "Home Live Metrics",
    "daily_health": "Daily Health Check",
    "daily_ops_labor": "Daily Health Ops & Labor",
    "daily_health_ops": "Daily Health Ops & Labor",
    "operations_labor": "Daily Health Ops & Labor",
    "transportation_control": "Transportation Control",
    "transportation_allocations": "Transportation Control",
    "executive_brief": "Executive Brief",
    "executive_briefs": "Executive Brief",
    "executive_summary": "Executive Brief Summary",
    "executive_watchlist": "Executive Route Watchlist",
    "executive_pallets": "Executive Pallet Readiness",
    "executive_note": "Executive Copy-Ready Note",
    "market_profiles": "Market Profiles",
    "mfc_lookup": "MFC Lookup",
    "mfc_profiles": "MFC Profiles",
    "mfc_network_map": "MFC Network Map",
    "resource_library": "Resource Library Profiles",
}
COMMAND_CENTER_DEFAULTS = {
    "created": 0,
    "cancelled": 0,
    "created_vs_forecast": 0,
    "dt_over_50": 0,
    "dt_over_60": 0,
}
COMMAND_CENTER_ALIASES = {
    "snapshot_time": ["snapshot_time", "last_updated", "updated", "updated_at", "time", "date", "timestamp"],
    "created": ["created", "created_orders", "orders_created", "order_count", "orders"],
    "cancelled": ["cancelled", "canceled", "cancelled_orders", "canceled_orders"],
    "created_vs_forecast": ["created_vs_forecast", "vs_forecast", "forecast_delta", "created_forecast_delta"],
    "dt_over_50": ["dt_over_50", "dt_50", "dt_greater_than_50", "dt_50m", "dt_over_50m"],
    "dt_over_60": ["dt_over_60", "dt_60", "dt_greater_than_60", "dt_60m", "dt_over_60m"],
}
MFC_MARKET_COORDS = {
    "ATL": (33.7490, -84.3880, "Atlanta, GA"),
    "AUS": (30.2672, -97.7431, "Austin, TX"),
    "BFL": (35.3733, -119.0187, "Bakersfield, CA"),
    "BNA": (36.1627, -86.7816, "Nashville, TN"),
    "BOS": (42.3601, -71.0589, "Boston, MA"),
    "BTR": (30.4515, -91.1871, "Baton Rouge, LA"),
    "BUR": (34.1808, -118.3090, "Burbank, CA"),
    "BWG": (36.9685, -86.4808, "Bowling Green, KY"),
    "BWI": (39.2904, -76.6122, "Baltimore, MD"),
    "CAE": (34.0007, -81.0348, "Columbia, SC"),
    "CHO": (38.0293, -78.4767, "Charlottesville, VA"),
    "CID": (41.9779, -91.6656, "Cedar Rapids, IA"),
    "CLE": (41.4993, -81.6944, "Cleveland, OH"),
    "CLL": (30.6279, -96.3344, "College Station, TX"),
    "CLT": (35.2271, -80.8431, "Charlotte, NC"),
    "CMH": (39.9612, -82.9988, "Columbus, OH"),
    "CMI": (40.1164, -88.2434, "Champaign / Urbana, IL"),
    "CVG": (39.1031, -84.5120, "Cincinnati, OH"),
    "DAL": (32.7767, -96.7970, "Dallas, TX"),
    "DCA": (38.9072, -77.0369, "Washington, DC"),
    "DEN": (39.7392, -104.9903, "Denver, CO"),
    "DFW": (32.7767, -96.7970, "Dallas / Fort Worth, TX"),
    "DSM": (41.5868, -93.6250, "Des Moines, IA"),
    "DTW": (42.3314, -83.0458, "Detroit, MI"),
    "ELP": (31.7619, -106.4850, "El Paso, TX"),
    "EUG": (44.0521, -123.0868, "Eugene, OR"),
    "FAT": (36.7378, -119.7871, "Fresno, CA"),
    "FLG": (35.1983, -111.6513, "Flagstaff, AZ"),
    "FLL": (26.1224, -80.1373, "Fort Lauderdale, FL"),
    "GNV": (29.6516, -82.3248, "Gainesville, FL"),
    "GSO": (36.0726, -79.7920, "Greensboro, NC"),
    "HVN": (41.3083, -72.9279, "New Haven, CT"),
    "IAH": (29.7604, -95.3698, "Houston, TX"),
    "IND": (39.7684, -86.1581, "Indianapolis, IN"),
    "JAX": (30.3322, -81.6557, "Jacksonville, FL"),
    "JFK": (40.6782, -73.9442, "Brooklyn / Queens, NY"),
    "LAN": (42.7325, -84.5555, "Lansing, MI"),
    "LAS": (36.1699, -115.1398, "Las Vegas, NV"),
    "LAX": (34.0522, -118.2437, "Los Angeles, CA"),
    "LBB": (33.5779, -101.8552, "Lubbock, TX"),
    "LEX": (38.0406, -84.5037, "Lexington, KY"),
    "LGB": (33.7701, -118.1937, "Long Beach, CA"),
    "LNK": (40.8136, -96.7026, "Lincoln, NE"),
    "LOU": (38.2527, -85.7585, "Louisville, KY"),
    "MCI": (39.0997, -94.5786, "Kansas City, MO"),
    "MCO": (28.5383, -81.3792, "Orlando, FL"),
    "MDT": (40.2732, -76.8867, "Harrisburg, PA"),
    "MEM": (35.1495, -90.0490, "Memphis, TN"),
    "MFR": (42.3265, -122.8756, "Medford, OR"),
    "MIA": (25.7617, -80.1918, "Miami, FL"),
    "MKE": (43.0389, -87.9065, "Milwaukee, WI"),
    "MOR": (39.6295, -79.9559, "Morgantown, WV"),
    "MSN": (43.0731, -89.4012, "Madison, WI"),
    "MSP": (44.9778, -93.2650, "Minneapolis, MN"),
    "MSY": (29.9511, -90.0715, "New Orleans, LA"),
    "OAK": (37.8044, -122.2712, "Oakland, CA"),
    "OKC": (35.4676, -97.5164, "Oklahoma City, OK"),
    "ONT": (34.0633, -117.6509, "Ontario, CA"),
    "ORD": (41.8781, -87.6298, "Chicago, IL"),
    "ORF": (36.8508, -76.2859, "Norfolk, VA"),
    "PDX": (45.5152, -122.6784, "Portland, OR"),
    "PHL": (39.9526, -75.1652, "Philadelphia, PA"),
    "PHX": (33.4484, -112.0740, "Phoenix, AZ"),
    "PIE": (27.7731, -82.6403, "St. Petersburg, FL"),
    "PIT": (40.4406, -79.9959, "Pittsburgh, PA"),
    "PNS": (30.4213, -87.2169, "Pensacola, FL"),
    "PSP": (33.8303, -116.5453, "Palm Springs, CA"),
    "PVD": (41.8240, -71.4128, "Providence, RI"),
    "RDU": (35.7796, -78.6382, "Raleigh / Durham, NC"),
    "RDD": (40.5865, -122.3917, "Redding, CA"),
    "RIC": (37.5407, -77.4360, "Richmond, VA"),
    "RNO": (39.5296, -119.8138, "Reno, NV"),
    "ROC": (43.1566, -77.6088, "Rochester, NY"),
    "SAN": (32.7157, -117.1611, "San Diego, CA"),
    "SAT": (29.4241, -98.4936, "San Antonio, TX"),
    "SBA": (34.4208, -119.6982, "Santa Barbara, CA"),
    "SBD": (34.1083, -117.2898, "San Bernardino, CA"),
    "SBN": (41.6764, -86.2520, "South Bend, IN"),
    "SBP": (35.2828, -120.6596, "San Luis Obispo, CA"),
    "SEA": (47.6062, -122.3321, "Seattle, WA"),
    "SFO": (37.7749, -122.4194, "San Francisco, CA"),
    "SGF": (37.2089, -93.2923, "Springfield, MO"),
    "SJC": (37.3382, -121.8863, "San Jose, CA"),
    "SLE": (44.9429, -123.0351, "Salem, OR"),
    "SMF": (38.5816, -121.4944, "Sacramento, CA"),
    "SNA": (33.7455, -117.8677, "Orange County, CA"),
    "STL": (38.6270, -90.1994, "St. Louis, MO"),
    "TPA": (27.9506, -82.4572, "Tampa, FL"),
    "TUL": (36.1540, -95.9928, "Tulsa, OK"),
    "TUS": (32.2226, -110.9747, "Tucson, AZ"),
    "TYS": (35.9606, -83.9207, "Knoxville, TN"),
}


@dataclass
class HealthResult:
    label: str
    score: int
    drivers: list[str]


@dataclass
class DailyHealthContext:
    progress: pd.DataFrame
    sdt: pd.DataFrame
    ob_tracker: pd.DataFrame
    fill_rate: pd.DataFrame
    sdt_source: str
    ob_source: str
    fill_source: str
    ob_sheet: str
    ob_reason: str
    ob_target_day: pd.Timestamp
    matched_columns: dict[str, str]


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS carrier_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tender_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                ready_count INTEGER NOT NULL,
                issue_count INTEGER NOT NULL,
                duplicate_count INTEGER NOT NULL,
                conflict_count INTEGER NOT NULL,
                records_json TEXT NOT NULL,
                export_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                file_blob BLOB NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_uploaded_files_unique
            ON uploaded_files (category, filename, file_size)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ship_allocation_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                source_files TEXT NOT NULL,
                source_groups TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                ready_count INTEGER NOT NULL,
                issue_count INTEGER NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                records_json TEXT NOT NULL,
                export_json TEXT NOT NULL,
                file_blob BLOB NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reference_sheets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                replaced_at TEXT NOT NULL DEFAULT '',
                replacement_count INTEGER NOT NULL DEFAULT 0,
                tag TEXT NOT NULL,
                notes TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                file_blob BLOB NOT NULL
            )
            """
        )
        ensure_column(conn, "ship_allocation_batches", "notes", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "reference_sheets", "replaced_at", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "reference_sheets", "replacement_count", "INTEGER NOT NULL DEFAULT 0")
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_reference_sheets_unique
            ON reference_sheets (filename, file_size)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS google_sheet_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spreadsheet_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                tag TEXT NOT NULL,
                notes TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_synced_at TEXT NOT NULL,
                last_modified_time TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                values_json TEXT NOT NULL,
                permissions_json TEXT NOT NULL,
                activity_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS google_sheet_refresh_runs (
                slot_key TEXT PRIMARY KEY,
                scheduled_at TEXT NOT NULL,
                ran_at TEXT NOT NULL,
                status TEXT NOT NULL,
                message_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS command_center_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uploaded_at TEXT NOT NULL,
                snapshot_time TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_sheet TEXT NOT NULL,
                created INTEGER NOT NULL,
                cancelled INTEGER NOT NULL,
                created_vs_forecast INTEGER NOT NULL,
                dt_over_50 INTEGER NOT NULL,
                dt_over_60 INTEGER NOT NULL,
                notes TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lean_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                status TEXT NOT NULL,
                owner TEXT NOT NULL,
                area TEXT NOT NULL,
                purpose TEXT NOT NULL,
                current_state TEXT NOT NULL,
                target_state TEXT NOT NULL,
                wins TEXT NOT NULL,
                next_steps TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lean_project_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                uploaded_at TEXT NOT NULL,
                file_blob BLOB NOT NULL,
                FOREIGN KEY(project_id) REFERENCES lean_projects(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lean_project_matrix (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                area TEXT NOT NULL,
                owner TEXT NOT NULL,
                deadline TEXT NOT NULL,
                status TEXT NOT NULL,
                notes TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES lean_projects(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lean_project_flowcharts (
                project_id INTEGER PRIMARY KEY,
                nodes_json TEXT NOT NULL,
                edges_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES lean_projects(id)
            )
            """
        )


def ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
    existing_columns = {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in existing_columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def inject_brand_styles() -> None:
    if STYLE_PATH.exists():
        st.markdown(f"<style>{STYLE_PATH.read_text()}</style>", unsafe_allow_html=True)


def image_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    suffix = path.suffix.lower().lstrip(".")
    mime = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    return f"data:image/{mime};base64,{encoded}"


def render_brand_header() -> None:
    logo_uri = image_data_uri(LOGO_PATH)
    logo_html = f'<img class="gp-header__logo" src="{logo_uri}" alt="gopuff" />' if logo_uri else ""
    st.markdown(
        f"""
        <div class="gp-header">
          <div class="gp-header__brand">
            {logo_html}
            <div>
              <div class="gp-header__eyebrow">Supply Chain Visibility</div>
              <div class="gp-header__title">DC1 Health Board</div>
              <div class="gp-header__subtitle">Tender pipeline, carrier signals, Ops productivity, and executive reports.</div>
            </div>
          </div>
          <div class="gp-header__pill">Local MVP • Decision support only</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_query_param(name: str) -> str:
    value = st.query_params.get(name, "")
    if isinstance(value, list):
        return value[0] if value else ""
    return str(value)


def get_site_embed_mode() -> str:
    # Streamlit reserves `embed` for its own chrome-hiding mode; use `site_embed` for module routing.
    for name in ("site_embed", "embed_target", "module", "embed"):
        value = get_query_param(name).strip().casefold()
        if value and value not in {"true", "false", "1", "0"}:
            return value
    return ""


def app_href(section: str, view: str, **params: object) -> str:
    query = {"section": section, "view": view, **params}
    return "?" + "&".join(
        f"{quote(str(key))}={quote(str(value))}"
        for key, value in query.items()
        if value is not None and str(value).strip()
    )


def render_navigation_menu(active_section: str, active_view: str) -> tuple[str, str]:
    section_links = []
    for section in NAVIGATION:
        view = NAVIGATION[section][0] if section != active_section else active_view
        active_class = " gp-nav-link--active" if section == active_section else ""
        href = app_href(section, view)
        section_links.append(f'<a class="gp-nav-link{active_class}" href="{href}" target="_self">{html.escape(section)}</a>')
    section_views = NAVIGATION[active_section]
    view_links = []
    for section_view in section_views:
        active_class = " gp-nav-link--active" if section_view == active_view else ""
        href = app_href(active_section, section_view)
        view_links.append(f'<a class="gp-nav-link gp-nav-link--view{active_class}" href="{href}" target="_self">{html.escape(section_view)}</a>')
    st.markdown(
        f"""
        <div class="gp-click-nav">
          <div class="gp-nav-row gp-nav-row--sections">{''.join(section_links)}</div>
          <div class="gp-click-nav__label">Current {html.escape(active_section)} view</div>
          <div class="gp-nav-row gp-nav-row--views">{''.join(view_links)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["main_section"] = active_section
    st.session_state["main_view"] = active_view
    return active_section, active_view


def render_sidebar_brand() -> None:
    logo_uri = image_data_uri(LOGO_PATH)
    if not logo_uri:
        return
    st.sidebar.markdown(
        f"""
        <div class="gp-sidebar-topbar">
          <div class="gp-sidebar-brand">
            <img src="{logo_uri}" alt="gopuff" />
          </div>
          <div class="gp-sidebar-title">Data Inputs Menu</div>
          <div class="gp-sidebar-collapse-spacer"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def local_today() -> datetime.date:
    return datetime.now().date()


def df_to_json(df: pd.DataFrame) -> str:
    if df.empty:
        return "[]"
    serializable = df.copy()
    for col in serializable.columns:
        if pd.api.types.is_datetime64_any_dtype(serializable[col]):
            serializable[col] = serializable[col].dt.strftime("%Y-%m-%d %H:%M:%S")
    return serializable.to_json(orient="records", date_format="iso")


def df_from_json(payload: str) -> pd.DataFrame:
    data = json.loads(payload or "[]")
    return pd.DataFrame(data)


def load_saved_signals() -> list[dict[str, str]]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT payload_json FROM carrier_signals ORDER BY id").fetchall()
    return [json.loads(row[0]) for row in rows]


def insert_signal(signal: dict[str, str | int]) -> None:
    init_db()
    timestamp = now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO carrier_signals (created_at, updated_at, payload_json)
            VALUES (?, ?, ?)
            """,
            (timestamp, timestamp, json.dumps(signal)),
        )


def replace_signals(signals: list[dict[str, str]]) -> None:
    init_db()
    timestamp = now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM carrier_signals")
        conn.executemany(
            """
            INSERT INTO carrier_signals (created_at, updated_at, payload_json)
            VALUES (?, ?, ?)
            """,
            [(timestamp, timestamp, json.dumps(signal)) for signal in signals],
        )


def save_tender_batch(batch_name: str, tender_pipeline: dict[str, pd.DataFrame]) -> None:
    init_db()
    records = tender_pipeline["records"]
    ready = tender_pipeline["ready"]
    issues = tender_pipeline["issues"]
    duplicates = tender_pipeline["duplicates"]
    conflicts = tender_pipeline["conflicts"]
    export = tender_pipeline["export"]
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO tender_batches (
                batch_name,
                created_at,
                row_count,
                ready_count,
                issue_count,
                duplicate_count,
                conflict_count,
                records_json,
                export_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch_name,
                now_iso(),
                len(records),
                len(ready),
                len(issues),
                len(duplicates),
                len(conflicts),
                df_to_json(records),
                df_to_json(export),
            ),
        )


def list_tender_batches() -> pd.DataFrame:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            """
            SELECT
                id,
                batch_name,
                created_at,
                row_count,
                ready_count,
                issue_count,
                duplicate_count,
                conflict_count
            FROM tender_batches
            ORDER BY id DESC
            """,
            conn,
        )


def load_tender_batch(batch_id: int) -> dict[str, pd.DataFrame]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT records_json, export_json FROM tender_batches WHERE id = ?",
            (batch_id,),
        ).fetchone()
    if row is None:
        return rebuild_tender_pipeline(pd.DataFrame())

    records = df_from_json(row[0])
    for col in ["pick_date", "ship_date", "delivery_date"]:
        if col in records.columns:
            records[col] = pd.to_datetime(records[col], errors="coerce")
    return rebuild_tender_pipeline(records)


def save_uploaded_file(category: str, uploaded_file) -> bool:
    init_db()
    payload = uploaded_file.getvalue()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO uploaded_files (
                    category,
                    filename,
                    content_type,
                    file_size,
                    created_at,
                    file_blob
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    category,
                    uploaded_file.name,
                    uploaded_file.type or "application/octet-stream",
                    len(payload),
                    now_iso(),
                    payload,
                ),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def first_existing_column(df: pd.DataFrame, aliases: list[str]) -> pd.Series:
    for alias in aliases:
        if alias in df.columns:
            return df[alias]
    return pd.Series([pd.NA] * len(df), index=df.index)


def parse_command_center_snapshots(uploaded_file) -> pd.DataFrame:
    uploaded_file.seek(0)
    source_name = getattr(uploaded_file, "name", "Command Center Upload")
    if source_name.lower().endswith(".csv"):
        workbook = {"CSV Upload": pd.read_csv(uploaded_file)}
    else:
        workbook = pd.read_excel(uploaded_file, sheet_name=None)

    frames: list[pd.DataFrame] = []
    for sheet_name, raw in workbook.items():
        if raw.empty:
            continue
        df = clean_columns(raw).dropna(how="all")
        if df.empty:
            continue
        df = df.rename(columns={col: normalize_header(col) for col in df.columns})
        parsed = pd.DataFrame(index=df.index)
        parsed["snapshot_time"] = first_existing_column(df, COMMAND_CENTER_ALIASES["snapshot_time"])
        for field in ["created", "cancelled", "created_vs_forecast", "dt_over_50", "dt_over_60"]:
            parsed[field] = pd.to_numeric(
                first_existing_column(df, COMMAND_CENTER_ALIASES[field]),
                errors="coerce",
            )
        parsed = parsed.dropna(subset=["created", "cancelled", "created_vs_forecast", "dt_over_50", "dt_over_60"], how="all")
        if parsed.empty:
            continue
        parsed["snapshot_time"] = parsed["snapshot_time"].fillna("").astype(str).str.strip()
        parsed.loc[parsed["snapshot_time"].eq("") | parsed["snapshot_time"].str.lower().eq("nan"), "snapshot_time"] = now_iso()
        parsed["source_name"] = source_name
        parsed["source_sheet"] = sheet_name
        frames.append(parsed)

    if not frames:
        return pd.DataFrame(
            columns=[
                "snapshot_time",
                "source_name",
                "source_sheet",
                "created",
                "cancelled",
                "created_vs_forecast",
                "dt_over_50",
                "dt_over_60",
            ]
        )

    snapshots = pd.concat(frames, ignore_index=True)
    for field in COMMAND_CENTER_DEFAULTS:
        snapshots[field] = snapshots[field].fillna(0).round(0).astype(int)
    return snapshots


def save_command_center_snapshots(snapshots: pd.DataFrame, notes: str = "") -> int:
    init_db()
    if snapshots.empty:
        return 0
    upload_time = now_iso()
    rows = [
        (
            upload_time,
            str(row.get("snapshot_time", upload_time)),
            str(row.get("source_name", "Manual")),
            str(row.get("source_sheet", "")),
            int(row.get("created", 0) or 0),
            int(row.get("cancelled", 0) or 0),
            int(row.get("created_vs_forecast", 0) or 0),
            int(row.get("dt_over_50", 0) or 0),
            int(row.get("dt_over_60", 0) or 0),
            notes,
        )
        for _, row in snapshots.iterrows()
    ]
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            """
            INSERT INTO command_center_snapshots (
                uploaded_at,
                snapshot_time,
                source_name,
                source_sheet,
                created,
                cancelled,
                created_vs_forecast,
                dt_over_50,
                dt_over_60,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows)


def list_command_center_snapshots(limit: int | None = None) -> pd.DataFrame:
    init_db()
    query = """
        SELECT
            id,
            uploaded_at,
            snapshot_time,
            source_name,
            source_sheet,
            created,
            cancelled,
            created_vs_forecast,
            dt_over_50,
            dt_over_60,
            notes
        FROM command_center_snapshots
        ORDER BY datetime(uploaded_at) DESC, id DESC
    """
    if limit:
        query += f" LIMIT {int(limit)}"
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(query, conn)


def latest_command_center_snapshot() -> dict[str, int | str]:
    history = list_command_center_snapshots(limit=1)
    if history.empty:
        return {
            **COMMAND_CENTER_DEFAULTS,
            "last_updated": "No saved Command Center snapshot",
        }
    row = history.iloc[0]
    return {
        "created": int(row["created"]),
        "cancelled": int(row["cancelled"]),
        "created_vs_forecast": int(row["created_vs_forecast"]),
        "dt_over_50": int(row["dt_over_50"]),
        "dt_over_60": int(row["dt_over_60"]),
        "last_updated": str(row["snapshot_time"]),
    }


def delete_manual_command_center_snapshots() -> int:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "DELETE FROM command_center_snapshots WHERE source_name = ?",
            ("Manual Entry",),
        )
        return int(cursor.rowcount or 0)


def parse_optional_int(value: str) -> int | None:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return int(round(float(text)))
    except ValueError:
        return None


def list_uploaded_files(category: str) -> pd.DataFrame:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT id, filename, content_type, file_size, created_at
            FROM uploaded_files
            WHERE category = ?
            ORDER BY datetime(created_at) DESC, id DESC
            """,
            (category,),
        ).fetchall()
    return pd.DataFrame(
        rows,
        columns=["id", "filename", "content_type", "file_size", "created_at"],
    )


def load_uploaded_file(file_id: int) -> tuple[str, str, bytes] | None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            """
            SELECT filename, content_type, file_blob
            FROM uploaded_files
            WHERE id = ?
            """,
            (file_id,),
        ).fetchone()
    if row is None:
        return None
    return row[0], row[1], row[2]


def create_lean_project(project: dict[str, str]) -> int:
    init_db()
    timestamp = now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO lean_projects (
                project_name,
                status,
                owner,
                area,
                purpose,
                current_state,
                target_state,
                wins,
                next_steps,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project.get("project_name", "Untitled LEAN/5S Project").strip() or "Untitled LEAN/5S Project",
                project.get("status", "Planning"),
                project.get("owner", ""),
                project.get("area", ""),
                project.get("purpose", ""),
                project.get("current_state", ""),
                project.get("target_state", ""),
                project.get("wins", ""),
                project.get("next_steps", ""),
                timestamp,
                timestamp,
            ),
        )
        return int(cursor.lastrowid)


def list_lean_projects() -> pd.DataFrame:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            """
            SELECT
                id,
                project_name,
                status,
                owner,
                area,
                purpose,
                current_state,
                target_state,
                wins,
                next_steps,
                created_at,
                updated_at
            FROM lean_projects
            ORDER BY datetime(updated_at) DESC, id DESC
            """,
            conn,
        )


def load_lean_project(project_id: int) -> pd.Series | None:
    projects = list_lean_projects()
    if projects.empty or project_id not in projects["id"].tolist():
        return None
    return projects[projects["id"].eq(project_id)].iloc[0]


def update_lean_project(project_id: int, project: dict[str, str]) -> None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE lean_projects
            SET
                project_name = ?,
                status = ?,
                owner = ?,
                area = ?,
                purpose = ?,
                current_state = ?,
                target_state = ?,
                wins = ?,
                next_steps = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                project.get("project_name", ""),
                project.get("status", "Planning"),
                project.get("owner", ""),
                project.get("area", ""),
                project.get("purpose", ""),
                project.get("current_state", ""),
                project.get("target_state", ""),
                project.get("wins", ""),
                project.get("next_steps", ""),
                now_iso(),
                project_id,
            ),
        )


def save_lean_project_file(project_id: int, uploaded_file) -> bool:
    init_db()
    payload = uploaded_file.getvalue()
    with sqlite3.connect(DB_PATH) as conn:
        existing = conn.execute(
            """
            SELECT id FROM lean_project_files
            WHERE project_id = ? AND filename = ? AND file_size = ?
            """,
            (project_id, uploaded_file.name, len(payload)),
        ).fetchone()
        if existing:
            return False
        conn.execute(
            """
            INSERT INTO lean_project_files (
                project_id,
                filename,
                content_type,
                file_size,
                uploaded_at,
                file_blob
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                uploaded_file.name,
                uploaded_file.type or "application/octet-stream",
                len(payload),
                now_iso(),
                payload,
            ),
        )
    return True


def list_lean_project_files(project_id: int) -> pd.DataFrame:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            """
            SELECT id, filename, content_type, file_size, uploaded_at
            FROM lean_project_files
            WHERE project_id = ?
            ORDER BY datetime(uploaded_at) DESC, id DESC
            """,
            conn,
            params=(project_id,),
        )


def load_lean_project_file(file_id: int) -> tuple[str, str, bytes] | None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            """
            SELECT filename, content_type, file_blob
            FROM lean_project_files
            WHERE id = ?
            """,
            (file_id,),
        ).fetchone()
    if row is None:
        return None
    return row[0], row[1], row[2]


def default_lean_matrix_rows(project: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "area": str(project.get("area", "")) or "Project area",
                "owner": str(project.get("owner", "")),
                "deadline": "",
                "status": "Not Started",
                "notes": "Define first ownership lane.",
            }
        ],
        columns=LEAN_MATRIX_COLUMNS,
    )


def list_lean_matrix_items(project_id: int) -> pd.DataFrame:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = pd.read_sql_query(
            """
            SELECT area, owner, deadline, status, notes
            FROM lean_project_matrix
            WHERE project_id = ?
            ORDER BY id ASC
            """,
            conn,
            params=(project_id,),
        )
    if rows.empty:
        return pd.DataFrame(columns=LEAN_MATRIX_COLUMNS)
    return rows


def replace_lean_matrix_items(project_id: int, matrix_rows: pd.DataFrame) -> None:
    init_db()
    cleaned = matrix_rows.copy()
    for column in LEAN_MATRIX_COLUMNS:
        if column not in cleaned.columns:
            cleaned[column] = ""
    cleaned = cleaned[LEAN_MATRIX_COLUMNS].fillna("")
    cleaned = cleaned[
        cleaned["area"].astype(str).str.strip().ne("")
        | cleaned["owner"].astype(str).str.strip().ne("")
        | cleaned["deadline"].astype(str).str.strip().ne("")
    ]
    timestamp = now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM lean_project_matrix WHERE project_id = ?", (project_id,))
        conn.executemany(
            """
            INSERT INTO lean_project_matrix (project_id, area, owner, deadline, status, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    project_id,
                    str(row["area"]).strip(),
                    str(row["owner"]).strip(),
                    str(row["deadline"]).strip(),
                    str(row["status"]).strip() or "Not Started",
                    str(row["notes"]).strip(),
                    timestamp,
                )
                for _, row in cleaned.iterrows()
            ],
        )


def classify_deadline(deadline_value: object) -> tuple[str, int | None]:
    deadline = pd.to_datetime(deadline_value, errors="coerce")
    if pd.isna(deadline):
        return "No Date", None
    days_left = int((deadline.date() - datetime.now().date()).days)
    if days_left < 0:
        return "Overdue", days_left
    if days_left <= 3:
        return "Due Now", days_left
    if days_left <= 7:
        return "This Week", days_left
    if days_left <= 14:
        return "Watch", days_left
    return "On Track", days_left


def style_lean_matrix(row: pd.Series) -> list[str]:
    risk = row.get("deadline_risk", "")
    colors = {
        "Overdue": "#ffd8d8",
        "Due Now": "#ffe8cc",
        "This Week": "#fff4bf",
        "Watch": "#dbeafe",
        "On Track": "#d9f99d",
        "No Date": "#f1f5f9",
    }
    return [f"background-color: {colors.get(risk, '#ffffff')}; color: #111827;" for _ in row]


def default_flow_nodes(project: pd.Series) -> pd.DataFrame:
    area = str(project.get("area", "")) or "Project"
    return pd.DataFrame(
        [
            {"node_id": "start", "label": f"{area} current state", "node_type": "Start/End", "lane": "Current", "notes": ""},
            {"node_id": "sort", "label": "Sort waste / blockers", "node_type": "5S Sort", "lane": "Improve", "notes": ""},
            {"node_id": "standardize", "label": "Standardize new process", "node_type": "5S Standardize", "lane": "Sustain", "notes": ""},
        ],
        columns=LEAN_FLOW_NODE_COLUMNS,
    )


def default_flow_edges() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"from_node": "start", "to_node": "sort", "label": "review"},
            {"from_node": "sort", "to_node": "standardize", "label": "improve"},
        ],
        columns=LEAN_FLOW_EDGE_COLUMNS,
    )


def load_lean_flowchart(project_id: int, project: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            """
            SELECT nodes_json, edges_json
            FROM lean_project_flowcharts
            WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()
    if row is None:
        return default_flow_nodes(project), default_flow_edges()
    try:
        nodes = pd.DataFrame(json.loads(row[0]))
        edges = pd.DataFrame(json.loads(row[1]))
    except (TypeError, json.JSONDecodeError):
        return default_flow_nodes(project), default_flow_edges()
    for column in LEAN_FLOW_NODE_COLUMNS:
        if column not in nodes.columns:
            nodes[column] = ""
    for column in LEAN_FLOW_EDGE_COLUMNS:
        if column not in edges.columns:
            edges[column] = ""
    return nodes[LEAN_FLOW_NODE_COLUMNS], edges[LEAN_FLOW_EDGE_COLUMNS]


def save_lean_flowchart(project_id: int, nodes: pd.DataFrame, edges: pd.DataFrame) -> None:
    init_db()
    clean_nodes = nodes.copy()
    clean_edges = edges.copy()
    for column in LEAN_FLOW_NODE_COLUMNS:
        if column not in clean_nodes.columns:
            clean_nodes[column] = ""
    for column in LEAN_FLOW_EDGE_COLUMNS:
        if column not in clean_edges.columns:
            clean_edges[column] = ""
    clean_nodes = clean_nodes[LEAN_FLOW_NODE_COLUMNS].fillna("")
    clean_edges = clean_edges[LEAN_FLOW_EDGE_COLUMNS].fillna("")
    clean_nodes = clean_nodes[
        clean_nodes["node_id"].astype(str).str.strip().ne("")
        & clean_nodes["label"].astype(str).str.strip().ne("")
    ]
    clean_edges = clean_edges[
        clean_edges["from_node"].astype(str).str.strip().ne("")
        & clean_edges["to_node"].astype(str).str.strip().ne("")
    ]
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO lean_project_flowcharts (project_id, nodes_json, edges_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                nodes_json = excluded.nodes_json,
                edges_json = excluded.edges_json,
                updated_at = excluded.updated_at
            """,
            (
                project_id,
                clean_nodes.to_json(orient="records"),
                clean_edges.to_json(orient="records"),
                now_iso(),
            ),
        )


def mermaid_safe_id(value: object) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]", "_", str(value).strip())
    return safe or "node"


def mermaid_safe_label(value: object) -> str:
    return str(value).replace('"', "'").strip() or "Step"


def build_mermaid_flowchart(nodes: pd.DataFrame, edges: pd.DataFrame) -> str:
    node_shape = {
        "Decision": ("{", "}"),
        "Start/End": ("([", "])"),
    }
    icon_prefix = {
        "Dock": "[Dock] ",
        "Forklift": "[Forklift] ",
        "Pallet": "[Pallet] ",
        "Staging": "[Staging] ",
        "Inventory": "[Inventory] ",
        "Carrier Handoff": "[Carrier] ",
        "Quality Check": "[QC] ",
        "5S Sort": "[5S Sort] ",
        "5S Set in Order": "[5S Set] ",
        "5S Shine": "[5S Shine] ",
        "5S Standardize": "[5S Std] ",
        "5S Sustain": "[5S Sustain] ",
    }
    lines = ["flowchart LR"]
    clean_nodes = nodes.fillna("")
    valid_ids = set()
    for _, row in clean_nodes.iterrows():
        raw_id = str(row.get("node_id", "")).strip()
        label = mermaid_safe_label(row.get("label", ""))
        if not raw_id or not label:
            continue
        node_id = mermaid_safe_id(raw_id)
        valid_ids.add(raw_id)
        node_type = str(row.get("node_type", "Process"))
        prefix = icon_prefix.get(node_type, "")
        left, right = node_shape.get(node_type, ("[", "]"))
        lines.append(f'    {node_id}{left}"{prefix}{label}"{right}')
    for _, row in edges.fillna("").iterrows():
        from_node = str(row.get("from_node", "")).strip()
        to_node = str(row.get("to_node", "")).strip()
        if from_node not in valid_ids or to_node not in valid_ids:
            continue
        label = str(row.get("label", "")).strip()
        label_text = f"|{mermaid_safe_label(label)}|" if label else ""
        lines.append(f"    {mermaid_safe_id(from_node)} -->{label_text} {mermaid_safe_id(to_node)}")
    return "\n".join(lines)


def inspect_reference_workbook(uploaded_file) -> dict[str, object]:
    uploaded_file.seek(0)
    filename = getattr(uploaded_file, "name", "Reference Workbook")
    if filename.lower().endswith(".csv"):
        df = pd.read_csv(uploaded_file, nrows=200)
        return {
            "sheets": [
                {
                    "sheet_name": "CSV Upload",
                    "row_count": int(len(df)),
                    "column_count": int(len(df.columns)),
                    "columns": [str(col) for col in df.columns],
                }
            ]
        }

    excel = pd.ExcelFile(uploaded_file)
    sheets = []
    for sheet_name in excel.sheet_names:
        preview = pd.read_excel(excel, sheet_name=sheet_name, nrows=200)
        preview = preview.dropna(how="all")
        sheets.append(
            {
                "sheet_name": sheet_name,
                "row_count": int(len(preview)),
                "column_count": int(len(preview.columns)),
                "columns": [str(col) for col in preview.columns if str(col) != "nan"],
            }
        )
    return {"sheets": sheets}


def save_reference_sheet(uploaded_file, tag: str = "Other", notes: str = "") -> str:
    init_db()
    payload = uploaded_file.getvalue()
    metadata = inspect_reference_workbook(uploaded_file)
    detected_type = detect_reference_workbook_type(uploaded_file.name, metadata)
    if tag == "Other" and detected_type != "Other":
        tag = detected_type
    metadata["detected_type"] = detected_type
    with sqlite3.connect(DB_PATH) as conn:
        existing = conn.execute(
            "SELECT id, tag, notes, replacement_count FROM reference_sheets WHERE filename = ? ORDER BY id DESC LIMIT 1",
            (uploaded_file.name,),
        ).fetchone()
        if existing:
            saved_tag = tag if tag != "Other" else existing[1]
            saved_notes = notes if notes else existing[2]
            conn.execute(
                """
                UPDATE reference_sheets
                SET
                    content_type = ?,
                    file_size = ?,
                    created_at = ?,
                    replaced_at = ?,
                    replacement_count = ?,
                    tag = ?,
                    notes = ?,
                    metadata_json = ?,
                    file_blob = ?
                WHERE id = ?
                """,
                (
                    uploaded_file.type or "application/octet-stream",
                    len(payload),
                    now_iso(),
                    now_iso(),
                    int(existing[3] or 0) + 1,
                    saved_tag,
                    saved_notes,
                    json.dumps(metadata),
                    payload,
                    int(existing[0]),
                ),
            )
            return "replaced"

        conn.execute(
            """
            INSERT INTO reference_sheets (
                filename,
                content_type,
                file_size,
                created_at,
                tag,
                notes,
                metadata_json,
                file_blob
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uploaded_file.name,
                uploaded_file.type or "application/octet-stream",
                len(payload),
                now_iso(),
                tag,
                notes,
                json.dumps(metadata),
                payload,
            ),
        )
    return "saved"


def list_reference_sheets() -> pd.DataFrame:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                filename,
                content_type,
                file_size,
                created_at,
                replaced_at,
                replacement_count,
                tag,
                notes,
                metadata_json
            FROM reference_sheets
            ORDER BY datetime(created_at) DESC, id DESC
            """
        ).fetchall()
    return pd.DataFrame(
        rows,
        columns=[
            "id",
            "filename",
            "content_type",
            "file_size",
            "created_at",
            "replaced_at",
            "replacement_count",
            "tag",
            "notes",
            "metadata_json",
        ],
    )


def update_reference_sheets(rows: list[dict[str, object]]) -> None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        for row in rows:
            conn.execute(
                "UPDATE reference_sheets SET tag = ?, notes = ? WHERE id = ?",
                (str(row.get("tag", "Other")), str(row.get("notes", "")), int(row["id"])),
            )


def load_reference_sheet(file_id: int) -> tuple[str, str, bytes] | None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT filename, content_type, file_blob FROM reference_sheets WHERE id = ?",
            (file_id,),
        ).fetchone()
    if row is None:
        return None
    return row[0], row[1], row[2]


def detect_reference_workbook_type(filename: str, metadata: dict[str, object]) -> str:
    haystack_parts = [filename]
    for sheet in metadata.get("sheets", []):
        if not isinstance(sheet, dict):
            continue
        haystack_parts.append(str(sheet.get("sheet_name", "")))
        haystack_parts.extend(str(col) for col in sheet.get("columns", [])[:30])
    haystack = " ".join(haystack_parts).lower()

    if "operation fill rate" in haystack or "raw airtable pif" in haystack or "manifest send" in haystack:
        return "Fill Rate"
    if "core-mark" in haystack or "core mark" in haystack or ("cm opco" in haystack and "temp category" in haystack):
        return "Core-Mark"
    if "ob to tracker" in haystack or ("lines remaining" in haystack and "loaded by" in haystack):
        return "OB TO Tracker"
    if "sdt" in haystack or ("load ready time" in haystack and "departure time" in haystack):
        return "SDT Schedule"
    if "rfp cost" in haystack or "current pricing" in haystack or "bid (ppc)" in haystack:
        return "RFP Cost"
    if "otp bridge" in haystack or "otp tracking" in haystack or ("on-time status" in haystack and "detailed bridge" in haystack):
        return "OTP"
    if "transportation specilist" in haystack or "transportation specialist" in haystack or "task / action item" in haystack:
        return "Transportation Schedule"
    if "linehaul tender template" in haystack or ("upload output" in haystack and "business_unit_type" in haystack):
        return "Tender Template"
    if "alloc tracking" in haystack or ("allocation date" in haystack and "planned pick date" in haystack and "planned ship date" in haystack):
        return "Allocation History"
    return "Other"


def reference_catalog() -> pd.DataFrame:
    refs = list_reference_sheets()
    if refs.empty:
        return refs
    catalog = refs.copy()
    workbook_types = []
    sheet_counts = []
    preview_rows = []
    preview_columns = []
    for _, row in catalog.iterrows():
        metadata = json.loads(row.get("metadata_json") or "{}")
        workbook_type = metadata.get("detected_type") or detect_reference_workbook_type(str(row.get("filename", "")), metadata)
        sheets = [sheet for sheet in metadata.get("sheets", []) if isinstance(sheet, dict)]
        workbook_types.append(workbook_type)
        sheet_counts.append(len(sheets))
        preview_rows.append(sum(int(sheet.get("row_count", 0) or 0) for sheet in sheets))
        column_names = []
        for sheet in sheets[:3]:
            column_names.extend(str(col) for col in sheet.get("columns", [])[:6])
        preview_columns.append(", ".join(dict.fromkeys(column_names))[:180])
    catalog["workbook_type"] = workbook_types
    catalog["sheet_count"] = sheet_counts
    catalog["preview_rows"] = preview_rows
    catalog["preview_columns"] = preview_columns
    return catalog


def latest_reference_by_type(workbook_type: str) -> pd.Series | None:
    catalog = reference_catalog()
    if catalog.empty or "workbook_type" not in catalog.columns:
        return None
    matches = catalog[catalog["workbook_type"].eq(workbook_type)].copy()
    if matches.empty:
        return None
    matches["created_sort"] = pd.to_datetime(matches["created_at"], errors="coerce")
    return matches.sort_values(["created_sort", "id"], ascending=False).iloc[0]


def read_reference_workbook_table(file_id: int, preferred_sheets: list[str] | None = None) -> pd.DataFrame:
    loaded = load_reference_sheet(file_id)
    if loaded is None:
        return pd.DataFrame()
    filename, _, payload = loaded
    buffer = BytesIO(payload)
    if filename.lower().endswith(".csv"):
        return pd.read_csv(buffer)

    excel = pd.ExcelFile(buffer)
    sheet_names = excel.sheet_names
    selected_sheet = sheet_names[0] if sheet_names else None
    if preferred_sheets:
        lowered = {sheet.lower(): sheet for sheet in sheet_names}
        for preferred in preferred_sheets:
            exact = lowered.get(preferred.lower())
            if exact:
                selected_sheet = exact
                break
            fuzzy = next((sheet for sheet in sheet_names if preferred.lower() in sheet.lower()), None)
            if fuzzy:
                selected_sheet = fuzzy
                break
    if selected_sheet is None:
        return pd.DataFrame()

    raw = pd.read_excel(excel, sheet_name=selected_sheet, header=None)
    return infer_header_table(raw)


def infer_header_table(raw: pd.DataFrame) -> pd.DataFrame:
    clean = raw.dropna(how="all").dropna(axis=1, how="all")
    if clean.empty:
        return pd.DataFrame()
    best_index = clean.index[0]
    best_score = -1
    keywords = {
        "carrier",
        "to",
        "po",
        "status",
        "date",
        "ship",
        "pickup",
        "delivery",
        "location",
        "route",
        "lines",
        "units",
        "pallet",
        "lane",
        "rate",
        "dock",
    }
    for idx, row in clean.head(30).iterrows():
        values = [str(value).strip().lower() for value in row.tolist() if str(value).strip() and str(value).lower() != "nan"]
        score = sum(any(keyword in value for keyword in keywords) for value in values) + min(len(values), 12) / 20
        if score > best_score:
            best_score = score
            best_index = idx

    header_values = clean.loc[best_index].fillna("").astype(str).str.strip().tolist()
    columns = []
    seen: dict[str, int] = {}
    for i, value in enumerate(header_values):
        base = value if value and value.lower() != "nan" else f"Column {i + 1}"
        count = seen.get(base, 0)
        seen[base] = count + 1
        columns.append(base if count == 0 else f"{base}_{count + 1}")
    table = clean.loc[clean.index > best_index].copy()
    table.columns = columns[: len(table.columns)]
    table = table.dropna(how="all")
    return table.reset_index(drop=True)


def column_by_keywords(df: pd.DataFrame, keywords: list[str]) -> str | None:
    lowered = {str(col).lower().strip(): col for col in df.columns}
    for col_lower, original in lowered.items():
        if all(keyword.lower() in col_lower for keyword in keywords):
            return original
    return None


def first_matching_column(df: pd.DataFrame, candidates: list[list[str]]) -> str | None:
    for keywords in candidates:
        col = column_by_keywords(df, keywords)
        if col:
            return col
    return None


def read_reference_type_table(workbook_type: str, preferred_sheets: list[str] | None = None) -> tuple[pd.Series | None, pd.DataFrame]:
    ref = latest_reference_by_type(workbook_type)
    if ref is None:
        return None, pd.DataFrame()
    return ref, read_reference_workbook_table(int(ref["id"]), preferred_sheets)


def list_reference_sheet_names(ref: pd.Series | None) -> list[str]:
    if ref is None:
        return []
    metadata = json.loads(ref.get("metadata_json") or "{}")
    return [
        str(sheet.get("sheet_name", ""))
        for sheet in metadata.get("sheets", [])
        if isinstance(sheet, dict) and str(sheet.get("sheet_name", "")).strip()
    ]


def read_reference_workbook_named_sheet(file_id: int, sheet_name: str) -> pd.DataFrame:
    loaded = load_reference_sheet(file_id)
    if loaded is None:
        return pd.DataFrame()
    filename, _, payload = loaded
    if filename.lower().endswith(".csv"):
        return pd.DataFrame()
    excel = pd.ExcelFile(BytesIO(payload))
    if sheet_name not in excel.sheet_names:
        return pd.DataFrame()
    raw = pd.read_excel(excel, sheet_name=sheet_name, header=None)
    return infer_header_table(raw)


def read_reference_workbook_named_values(file_id: int, sheet_name: str) -> list[list[object]]:
    loaded = load_reference_sheet(file_id)
    if loaded is None:
        return []
    filename, _, payload = loaded
    if filename.lower().endswith(".csv"):
        return []
    excel = pd.ExcelFile(BytesIO(payload))
    if sheet_name not in excel.sheet_names:
        return []
    raw = pd.read_excel(excel, sheet_name=sheet_name, header=None)
    return raw.fillna("").values.tolist()


def latest_google_sheet_by_type(workbook_type: str) -> pd.Series | None:
    connections = list_google_sheet_connections()
    if connections.empty:
        return None
    matches = connections[
        connections["tag"].astype(str).str.casefold().eq(workbook_type.casefold())
        | connections["name"].astype(str).str.casefold().str.contains(workbook_type.casefold(), regex=False, na=False)
    ].copy()
    if matches.empty:
        return None
    matches["synced_sort"] = pd.to_datetime(matches["last_synced_at"], errors="coerce")
    return matches.sort_values(["synced_sort", "id"], ascending=False).iloc[0]


def list_google_sheet_names(connection: pd.Series | None) -> list[str]:
    if connection is None:
        return []
    metadata = json.loads(connection.get("metadata_json") or "{}")
    return [
        str(sheet.get("sheet_name", ""))
        for sheet in metadata.get("sheets", [])
        if isinstance(sheet, dict) and str(sheet.get("sheet_name", "")).strip()
    ]


def read_google_sheet_named_table(connection: pd.Series | None, sheet_name: str) -> pd.DataFrame:
    if connection is None:
        return pd.DataFrame()
    values_by_sheet = json.loads(connection.get("values_json") or "{}")
    values = values_by_sheet.get(sheet_name, [])
    if not values:
        return pd.DataFrame()
    raw = pd.DataFrame(values)
    return infer_header_table(raw)


def read_google_sheet_named_values(connection: pd.Series | None, sheet_name: str) -> list[list[object]]:
    if connection is None:
        return []
    values_by_sheet = json.loads(connection.get("values_json") or "{}")
    return values_by_sheet.get(sheet_name, [])


def read_google_sheet_type_table(workbook_type: str, preferred_sheets: list[str] | None = None) -> tuple[pd.Series | None, pd.DataFrame]:
    connection = latest_google_sheet_by_type(workbook_type)
    if connection is None:
        return None, pd.DataFrame()
    sheet_names = list_google_sheet_names(connection)
    selected_sheet = ""
    if preferred_sheets:
        lowered = {sheet.casefold(): sheet for sheet in sheet_names}
        for preferred in preferred_sheets:
            exact = lowered.get(preferred.casefold())
            if exact:
                selected_sheet = exact
                break
            fuzzy = next((sheet for sheet in sheet_names if preferred.casefold() in sheet.casefold()), "")
            if fuzzy:
                selected_sheet = fuzzy
                break
    if not selected_sheet and sheet_names:
        selected_sheet = sheet_names[0]
    if not selected_sheet:
        return connection, pd.DataFrame()
    return connection, read_google_sheet_named_table(connection, selected_sheet)


def previous_working_day(day: datetime | pd.Timestamp | None = None) -> pd.Timestamp:
    current = pd.Timestamp(day or datetime.now()).normalize()
    previous = current - pd.Timedelta(days=1)
    while previous.weekday() >= 5:
        previous -= pd.Timedelta(days=1)
    return previous


def date_sheet_name(day: pd.Timestamp) -> str:
    return f"{int(day.month)}.{int(day.day)}"


def select_ob_tracker_sheet(sheet_names: list[str], day: datetime | pd.Timestamp | None = None) -> tuple[str, pd.Timestamp, str]:
    target_day = previous_working_day(day)
    clean_names = [sheet for sheet in sheet_names if str(sheet).strip()]
    if len(clean_names) >= 3:
        selected = clean_names[-3]
        parsed = parse_date_sheet_name(str(selected))
        if parsed is not None:
            month, day_num = parsed
            target_day = pd.Timestamp(year=target_day.year, month=month, day=day_num)
        return selected, target_day, "third tab from right"

    target_name = date_sheet_name(target_day)
    lookup = {str(sheet).strip().casefold(): sheet for sheet in clean_names}
    exact = lookup.get(target_name.casefold())
    if exact:
        return exact, target_day, "previous working day exact match"

    dated = []
    for sheet in clean_names:
        parsed = parse_date_sheet_name(str(sheet))
        if parsed is None:
            continue
        month, day_num = parsed
        candidate = pd.Timestamp(year=target_day.year, month=month, day=day_num)
        if candidate <= pd.Timestamp(datetime.now()).normalize():
            dated.append((candidate, sheet))
    if dated:
        dated.sort(key=lambda item: item[0], reverse=True)
        return dated[0][1], dated[0][0], "latest available dated tab"

    fallback_names = [sheet for sheet in clean_names if "mix label" not in str(sheet).casefold()]
    if fallback_names:
        return fallback_names[-1], target_day, "last non-Mix Label fallback"
    return "", target_day, "no usable tab found"


def normalize_route_key(value: object) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_time_today(value: object) -> pd.Timestamp | pd.NaT:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none"}:
        return pd.NaT
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return pd.NaT
    today = pd.Timestamp.now().normalize()
    return today + pd.Timedelta(hours=parsed.hour, minutes=parsed.minute, seconds=parsed.second)


def add_window_status(progress: pd.DataFrame) -> pd.DataFrame:
    if progress.empty:
        return progress
    visual = progress.copy()
    now = pd.Timestamp.now()
    visual["_ready_dt"] = visual["Load Ready Time"].map(parse_time_today) if "Load Ready Time" in visual.columns else pd.NaT
    visual["_depart_dt"] = visual["Departure Time"].map(parse_time_today) if "Departure Time" in visual.columns else pd.NaT
    visual["Window Status"] = "No SDT Window"
    has_window = visual["_ready_dt"].notna() | visual["_depart_dt"].notna()
    visual.loc[has_window, "Window Status"] = "Upcoming"
    visual.loc[
        visual["_ready_dt"].notna()
        & visual["_depart_dt"].notna()
        & visual["_ready_dt"].le(now)
        & visual["_depart_dt"].ge(now),
        "Window Status",
    ] = "In Window"
    visual.loc[visual["_depart_dt"].notna() & visual["_depart_dt"].lt(now), "Window Status"] = "Past Departure"
    visual.loc[visual["Open TOs"].fillna(0).le(0), "Window Status"] = "Complete"
    visual.loc[
        visual["Window Status"].eq("Past Departure") & visual["Open TOs"].fillna(0).gt(0),
        "Timing Risk",
    ] = "Past Departure Risk"
    return visual.drop(columns=["_ready_dt", "_depart_dt"], errors="ignore")


def build_fill_rate_readiness(fill_rate: pd.DataFrame) -> pd.DataFrame:
    if fill_rate.empty:
        return pd.DataFrame()

    to_col = first_matching_column(fill_rate, [["po", "number"], ["to", "number"], ["to"]])
    carrier_col = first_matching_column(fill_rate, [["carrier"]])
    route_col = first_matching_column(fill_rate, [["route"]])
    location_col = first_matching_column(fill_rate, [["location", "name"], ["location"]])
    units_nyp_col = first_matching_column(fill_rate, [["units", "nyp"]])
    fill_rate_col = first_matching_column(fill_rate, [["fill", "rate"]])
    lbi_col = first_matching_column(fill_rate, [["lbi", "pick"], ["pick", "quantity"]])
    total_pallets_col = first_matching_column(fill_rate, [["total", "pallets"], ["pallets"]])
    po_water_pallets_col = first_matching_column(fill_rate, [["po", "w", "o", "pallets"], ["water", "pallets"]])
    weight_col = first_matching_column(fill_rate, [["total", "pallet", "weight"], ["weight"]])

    if not to_col and not carrier_col and not route_col:
        return pd.DataFrame()

    work = fill_rate.copy()
    group_col = carrier_col or route_col
    if group_col is None:
        return pd.DataFrame()

    work["Units NYP"] = pd.to_numeric(work[units_nyp_col], errors="coerce").fillna(0) if units_nyp_col else 0
    work["LBI Pick Quantity"] = pd.to_numeric(work[lbi_col], errors="coerce").fillna(0) if lbi_col else 0
    work["Total Pallets"] = pd.to_numeric(work[total_pallets_col], errors="coerce").fillna(0) if total_pallets_col else 0
    work["PO W/O Pallets"] = pd.to_numeric(work[po_water_pallets_col], errors="coerce").fillna(0) if po_water_pallets_col else 0
    work["Total Pallet Weight"] = pd.to_numeric(work[weight_col], errors="coerce").fillna(0) if weight_col else 0
    if fill_rate_col:
        fill_text = work[fill_rate_col].astype(str).str.replace("%", "", regex=False)
        fill_numeric = pd.to_numeric(fill_text, errors="coerce")
        work["Fill Rate %"] = fill_numeric.where(fill_numeric.le(1), fill_numeric / 100).fillna(0)
    else:
        work["Fill Rate %"] = 0

    summary = (
        work.groupby(group_col, dropna=False)
        .agg(
            Fill_POs=(to_col if to_col else group_col, "nunique"),
            Fill_Locations=(location_col if location_col else group_col, "nunique"),
            Units_NYP=("Units NYP", "sum"),
            LBI_Pick_Quantity=("LBI Pick Quantity", "sum"),
            Fill_Total_Pallets=("Total Pallets", "sum"),
            PO_WO_Pallets=("PO W/O Pallets", "sum"),
            Total_Pallet_Weight=("Total Pallet Weight", "sum"),
            Avg_Fill_Rate=("Fill Rate %", "mean"),
        )
        .reset_index()
        .rename(columns={group_col: "Fill Carrier"})
    )
    summary["_route_key"] = summary["Fill Carrier"].map(normalize_route_key)
    summary["Pallet Readiness Risk"] = "Normal"
    summary.loc[summary["Units_NYP"].gt(0), "Pallet Readiness Risk"] = "Units NYP"
    summary.loc[summary["PO_WO_Pallets"].gt(0), "Pallet Readiness Risk"] = "PO W/O Pallets"
    return summary


def merge_fill_rate_readiness(progress: pd.DataFrame, fill_rate: pd.DataFrame) -> pd.DataFrame:
    readiness = build_fill_rate_readiness(fill_rate)
    if progress.empty or readiness.empty:
        return progress
    merged = progress.copy()
    merged["_route_key"] = merged["Carrier"].map(normalize_route_key)
    merged = merged.merge(readiness.drop(columns=["Fill Carrier"], errors="ignore"), on="_route_key", how="left")
    merged = merged.drop(columns=["_route_key"], errors="ignore")
    for col in ["Fill_POs", "Fill_Locations", "Units_NYP", "LBI_Pick_Quantity", "Fill_Total_Pallets", "PO_WO_Pallets", "Total_Pallet_Weight"]:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)
    if "Avg_Fill_Rate" in merged.columns:
        merged["Avg_Fill_Rate"] = pd.to_numeric(merged["Avg_Fill_Rate"], errors="coerce").fillna(0)
    if "Pallet Readiness Risk" in merged.columns:
        merged["Pallet Readiness Risk"] = merged["Pallet Readiness Risk"].fillna("No Fill Rate Match")
    return merged


def cell_text(value: object) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in {"nan", "none"} else text


def numeric_value(value: object) -> float:
    text = cell_text(value).replace(",", "").replace("%", "")
    if not text:
        return 0
    parsed = pd.to_numeric(text, errors="coerce")
    return 0 if pd.isna(parsed) else float(parsed)


def parse_mfc_number(location_name: object) -> str:
    text = cell_text(location_name)
    match = re.search(r"_(\d+)$", text)
    return match.group(1) if match else ""


def parse_crossdock(location_name: object, route: object) -> str:
    location = cell_text(location_name)
    if "_" in location:
        prefix = location.split("_", 1)[0].strip().upper()
        if prefix:
            return prefix
    route_text = cell_text(route).upper()
    tokens = re.findall(r"\b[A-Z]{3}\b", route_text)
    return tokens[-1] if tokens else "Unassigned"


def format_mfc_site_label(location_name: object) -> str:
    text = cell_text(location_name)
    match = re.match(r"([A-Za-z]{3})_.*?_(\d+)$", text)
    if match:
        return f"{match.group(1).upper()} {match.group(2)}"
    return text


def pallet_status_complete(status: object) -> bool:
    text = cell_text(status).casefold()
    if not text:
        return False
    incomplete_tokens = ["pallet-prep-drop", "prep drop", "prep-drop", "prep"]
    return not any(token in text for token in incomplete_tokens)


def load_daily_pallet_count_values() -> tuple[list[list[object]], str]:
    google_connection = latest_google_sheet_by_type("Fill Rate")
    google_values = read_google_sheet_named_values(google_connection, "Daily Pallet Counts")
    if google_values:
        source = str(google_connection["name"]) if google_connection is not None else "Google Sheet"
        return google_values, source
    return [], ""


def load_all_daily_pallet_counts() -> pd.DataFrame:
    google_connection = latest_google_sheet_by_type("Fill Rate")
    if google_connection is None:
        return pd.DataFrame()
    frames = []
    for sheet_name in list_google_sheet_names(google_connection):
        if "daily pallet counts" not in sheet_name.casefold():
            continue
        values = read_google_sheet_named_values(google_connection, sheet_name)
        parsed, selected_date = parse_daily_pallet_counts(values)
        if parsed.empty:
            continue
        parsed["Pallet Count Sheet"] = sheet_name
        parsed["Pallet Count Date"] = selected_date
        frames.append(parsed)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def parse_daily_pallet_counts(values: list[list[object]]) -> tuple[pd.DataFrame, pd.Timestamp | None]:
    if not values:
        return pd.DataFrame(), None

    selected_date = None
    for row in values[:12]:
        for idx, value in enumerate(row):
            if cell_text(value).casefold().startswith("date"):
                if idx + 1 < len(row):
                    parsed = pd.to_datetime(cell_text(row[idx + 1]), errors="coerce")
                    if not pd.isna(parsed):
                        selected_date = parsed.normalize()
                        break
        if selected_date is not None:
            break

    header_index = None
    for idx, row in enumerate(values):
        lowered = [cell_text(value).casefold() for value in row]
        if "location name" in lowered and "po number" in lowered and "pallet count" in lowered:
            header_index = idx
            break
    if header_index is None:
        return pd.DataFrame(), selected_date

    headers = [cell_text(value) for value in values[header_index]]

    def header_col(label: str) -> int | None:
        label_key = label.casefold()
        for col_idx, header in enumerate(headers):
            if header.casefold() == label_key:
                return col_idx
        return None

    assign_col = header_col("Assign")
    location_col = header_col("Location Name")
    route_col = header_col("Route")
    po_col = header_col("PO Number")
    pallet_count_col = header_col("Pallet Count")
    total_weight_col = header_col("Weight")
    if location_col is None or route_col is None or po_col is None or pallet_count_col is None:
        return pd.DataFrame(), selected_date

    records: list[dict[str, object]] = []
    for row in values[header_index + 1:]:
        padded = list(row) + [""] * max(0, len(headers) - len(row))
        location = cell_text(padded[location_col]) if location_col < len(padded) else ""
        route = cell_text(padded[route_col]) if route_col < len(padded) else ""
        po_number = cell_text(padded[po_col]) if po_col < len(padded) else ""
        if not location and not route and not po_number:
            continue
        if not po_number.upper().startswith("GUSTO"):
            continue

        pallet_count = int(numeric_value(padded[pallet_count_col])) if pallet_count_col < len(padded) else 0
        total_weight = numeric_value(padded[total_weight_col]) if total_weight_col is not None and total_weight_col < len(padded) else 0
        assign = cell_text(padded[assign_col]) if assign_col is not None and assign_col < len(padded) else ""
        crossdock = parse_crossdock(location, route)
        mfc_number = parse_mfc_number(location)

        first_pallet_col = (total_weight_col or pallet_count_col) + 1
        for pallet_index in range(1, max(pallet_count, 0) + 1):
            weight_col = first_pallet_col + ((pallet_index - 1) * 2)
            status_col = weight_col + 1
            pallet_weight = numeric_value(padded[weight_col]) if weight_col < len(padded) else 0
            pallet_status = cell_text(padded[status_col]) if status_col < len(padded) else ""
            if pallet_weight <= 0 and not pallet_status:
                continue
            records.append(
                {
                    "Ship Date": selected_date,
                    "Cross-Dock": crossdock,
                    "MFC": mfc_number,
                    "Location Name": location,
                    "Route": route,
                    "Gusto": po_number,
                    "Assign": assign,
                    "Pallet": pallet_index,
                    "Pallet Count": pallet_count,
                    "Pallet Label": f"{pallet_index} of {pallet_count}",
                    "Pallet Weight": pallet_weight,
                    "Total PO Weight": total_weight,
                    "Pallet Status": pallet_status or "Not Assigned",
                    "Completion Status": "Complete" if pallet_status_complete(pallet_status) else "Open",
                    "Complete": pallet_status_complete(pallet_status),
                }
            )

    return pd.DataFrame(records), selected_date


def summarize_crossdock_pallet_completion(pallets: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if pallets.empty:
        return pd.DataFrame(), pd.DataFrame()

    crossdock_summary = (
        pallets.groupby("Cross-Dock", dropna=False)
        .agg(
            Gustos=("Gusto", "nunique"),
            MFCs=("MFC", "nunique"),
            Pallets=("Pallet", "count"),
            Completed=("Complete", "sum"),
            Weight=("Pallet Weight", "sum"),
        )
        .reset_index()
    )
    crossdock_summary["Open Pallets"] = crossdock_summary["Pallets"] - crossdock_summary["Completed"]
    crossdock_summary["Completion %"] = crossdock_summary["Completed"] / crossdock_summary["Pallets"].replace(0, pd.NA)
    crossdock_summary = crossdock_summary.sort_values(["Completion %", "Pallets"], ascending=[True, False])

    mfc_summary = (
        pallets.groupby(["Cross-Dock", "MFC", "Location Name", "Gusto", "Route"], dropna=False)
        .agg(
            Pallets=("Pallet", "count"),
            Completed=("Complete", "sum"),
            Weight=("Pallet Weight", "sum"),
        )
        .reset_index()
    )
    mfc_summary["Open Pallets"] = mfc_summary["Pallets"] - mfc_summary["Completed"]
    mfc_summary["Completion %"] = mfc_summary["Completed"] / mfc_summary["Pallets"].replace(0, pd.NA)
    mfc_summary["Pallet Progress"] = mfc_summary["Completed"].astype(int).astype(str) + " of " + mfc_summary["Pallets"].astype(int).astype(str)
    mfc_summary = mfc_summary.sort_values(["Cross-Dock", "Completion %", "Open Pallets"], ascending=[True, True, False])
    return crossdock_summary, mfc_summary


def summarize_fill_rate_dock_activity(fill_rate: pd.DataFrame) -> pd.DataFrame:
    if fill_rate.empty:
        return pd.DataFrame()

    dock_col = first_matching_column(fill_rate, [["dock", "door"], ["door"]])
    route_col = first_matching_column(fill_rate, [["route"], ["carrier"]])
    to_col = first_matching_column(fill_rate, [["po", "number"], ["to", "number"], ["to"]])
    location_col = first_matching_column(fill_rate, [["location", "name"], ["location"]])
    units_nyp_col = first_matching_column(fill_rate, [["units", "nyp"]])
    lbi_col = first_matching_column(fill_rate, [["lbi", "pick"], ["pick", "quantity"]])
    pallets_col = first_matching_column(fill_rate, [["total", "pallets"], ["pallets"]])
    weight_col = first_matching_column(fill_rate, [["total", "pallet", "weight"], ["weight"]])

    if not dock_col:
        return pd.DataFrame()

    work = fill_rate.copy()
    work["Dock Door"] = work[dock_col].fillna("Unassigned").astype(str).str.strip()
    work.loc[work["Dock Door"].isin(["", "nan", "None"]), "Dock Door"] = "Unassigned"
    work["Units NYP"] = pd.to_numeric(work[units_nyp_col], errors="coerce").fillna(0) if units_nyp_col else 0
    work["Picked Units"] = pd.to_numeric(work[lbi_col], errors="coerce").fillna(0) if lbi_col else 0
    work["Pallets"] = pd.to_numeric(work[pallets_col], errors="coerce").fillna(0) if pallets_col else 0
    work["Weight"] = pd.to_numeric(work[weight_col], errors="coerce").fillna(0) if weight_col else 0

    return (
        work.groupby("Dock Door", dropna=False)
        .agg(
            Routes=(route_col if route_col else dock_col, "nunique"),
            Gustos=(to_col if to_col else dock_col, "nunique"),
            MFCs=(location_col if location_col else dock_col, "nunique"),
            Picked_Units=("Picked Units", "sum"),
            Units_NYP=("Units NYP", "sum"),
            Pallets=("Pallets", "sum"),
            Weight=("Weight", "sum"),
        )
        .reset_index()
        .sort_values(["Units_NYP", "Pallets", "Gustos"], ascending=[False, False, False])
    )


def load_daily_health_context() -> DailyHealthContext:
    sdt_google = latest_google_sheet_by_type("SDT Schedule")
    sdt_sheets = list_google_sheet_names(sdt_google)
    selected_sdt_sheet = next((sheet for sheet in sdt_sheets if sheet.casefold() in {"sheet1", "sdt"}), sdt_sheets[0] if sdt_sheets else "")
    sdt = read_google_sheet_named_table(sdt_google, selected_sdt_sheet) if selected_sdt_sheet else pd.DataFrame()
    sdt_source = f"{sdt_google['name']} / {selected_sdt_sheet}" if sdt_google is not None and selected_sdt_sheet else ""

    fill_google, fill_rate = read_google_sheet_type_table(
        "Fill Rate",
        ["Raw Airtable PIF", "Last 7 Days Raw Airtable PIF", "Daily Dashboard"],
    )
    fill_source = str(fill_google["name"]) if fill_google is not None else ""

    ob_source = ""
    ob_sheet = ""
    ob_reason = ""
    ob_target_day = previous_working_day()
    ob_tracker = pd.DataFrame()
    ob_google = latest_google_sheet_by_type("OB TO Tracker")
    ob_sheet_names = list_google_sheet_names(ob_google)
    ob_sheet, ob_target_day, ob_reason = select_ob_tracker_sheet(ob_sheet_names)
    if ob_sheet:
        ob_tracker = read_google_sheet_named_table(ob_google, ob_sheet)
        ob_source = str(ob_google["name"]) if ob_google is not None else ""

    progress = pd.DataFrame()
    matched_columns: dict[str, str] = {}
    if not sdt.empty and not ob_tracker.empty:
        progress, matched_columns = build_schedule_progress(sdt, ob_tracker)
        if not progress.empty:
            progress = merge_fill_rate_readiness(progress, fill_rate)

    return DailyHealthContext(
        progress=progress,
        sdt=sdt,
        ob_tracker=ob_tracker,
        fill_rate=fill_rate,
        sdt_source=sdt_source,
        ob_source=ob_source,
        fill_source=fill_source,
        ob_sheet=ob_sheet,
        ob_reason=ob_reason,
        ob_target_day=ob_target_day,
        matched_columns=matched_columns,
    )


def build_schedule_progress(sdt: pd.DataFrame, tracker: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    if sdt.empty or tracker.empty:
        return pd.DataFrame(), {}

    sdt_route_col = first_matching_column(sdt, [["route"], ["carrier"]])
    sdt_day_col = first_matching_column(sdt, [["day"]])
    ready_col = first_matching_column(sdt, [["load", "ready"], ["ready", "time"], ["start", "time"]])
    depart_col = first_matching_column(sdt, [["departure"], ["depart"], ["end", "time"]])
    door_col = first_matching_column(sdt, [["dock", "door"], ["door"]])

    carrier_col = first_matching_column(tracker, [["carrier"]])
    status_col = first_matching_column(tracker, [["status"]])
    to_col = first_matching_column(tracker, [["to"], ["po", "number"]])
    lines_col = first_matching_column(tracker, [["lines", "remaining"], ["lines"]])
    units_col = first_matching_column(tracker, [["units"]])
    location_col = first_matching_column(tracker, [["locations"], ["location"]])
    pallets_col = first_matching_column(tracker, [["total", "pallets"], ["pallets"]])

    required = {
        "sdt_route_col": sdt_route_col or "",
        "ready_col": ready_col or "",
        "depart_col": depart_col or "",
        "carrier_col": carrier_col or "",
        "status_col": status_col or "",
        "to_col": to_col or "",
    }
    if not sdt_route_col or not carrier_col:
        return pd.DataFrame(), required

    schedule = sdt.copy()
    if sdt_day_col:
        weekday_token = datetime.now().strftime("%a").casefold()
        schedule_day = schedule[sdt_day_col].astype(str).str.casefold()
        matched_day = schedule[schedule_day.str.contains(weekday_token, regex=False, na=False)]
        if not matched_day.empty:
            schedule = matched_day
    schedule["_route_key"] = schedule[sdt_route_col].map(normalize_route_key)
    schedule_cols = ["_route_key", sdt_route_col]
    schedule_rename = {sdt_route_col: "SDT Route"}
    for source_col, target_col in [
        (ready_col, "Load Ready Time"),
        (depart_col, "Departure Time"),
        (door_col, "Shipping Dock Door"),
        (sdt_day_col, "SDT Day"),
    ]:
        if source_col and source_col not in schedule_cols:
            schedule_cols.append(source_col)
            schedule_rename[source_col] = target_col
    schedule = schedule[schedule_cols].drop_duplicates("_route_key").rename(columns=schedule_rename)

    work = tracker.copy()
    work["_route_key"] = work[carrier_col].map(normalize_route_key)
    work["Lines Remaining"] = pd.to_numeric(work[lines_col], errors="coerce").fillna(0) if lines_col else 0
    work["Units"] = pd.to_numeric(work[units_col], errors="coerce").fillna(0) if units_col else 0
    work["Pallets"] = pd.to_numeric(work[pallets_col], errors="coerce").fillna(0) if pallets_col else 0
    work["Status Clean"] = work[status_col].fillna("Unknown").astype(str).str.strip() if status_col else "Unknown"
    work["is_complete"] = work["Status Clean"].str.casefold().str.contains("loaded|complete|closed", regex=True, na=False)
    work["is_active"] = work["Status Clean"].str.casefold().str.contains("picking|staged|allocated", regex=True, na=False)

    grouped = (
        work.groupby(["_route_key", carrier_col], dropna=False)
        .agg(
            TOs=(to_col if to_col else work.columns[0], "nunique"),
            Locations=(location_col if location_col else carrier_col, "nunique"),
            Loaded=("is_complete", "sum"),
            Active=("is_active", "sum"),
            Lines_Remaining=("Lines Remaining", "sum"),
            Units=("Units", "sum"),
            Pallets=("Pallets", "sum"),
        )
        .reset_index()
        .rename(columns={carrier_col: "Carrier"})
    )
    grouped["Progress %"] = grouped["Loaded"] / grouped["TOs"].replace(0, pd.NA)
    grouped["Open TOs"] = grouped["TOs"] - grouped["Loaded"]
    result = grouped.merge(schedule, on="_route_key", how="left")
    result["Window Matched"] = result["Load Ready Time"].notna() | result["Departure Time"].notna()
    result["Timing Risk"] = "Normal"
    result.loc[result["Open TOs"].gt(0) & result["Window Matched"].eq(False), "Timing Risk"] = "Missing SDT Window"
    result.loc[result["Open TOs"].gt(0) & result["Lines_Remaining"].gt(0), "Timing Risk"] = "Work Remaining"
    display_cols = [
        "Carrier",
        "SDT Day",
        "Load Ready Time",
        "Departure Time",
        "Shipping Dock Door",
        "TOs",
        "Loaded",
        "Open TOs",
        "Active",
        "Lines_Remaining",
        "Units",
        "Pallets",
        "Progress %",
        "Timing Risk",
    ]
    display_cols = [col for col in display_cols if col in result.columns]
    result = add_window_status(result[display_cols])
    sort_cols = [col for col in ["Timing Risk", "Window Status", "Departure Time", "Carrier"] if col in result.columns]
    result = result.sort_values(sort_cols, ascending=[False] * len(sort_cols))
    return result, required


def render_schedule_progress_visual(progress: pd.DataFrame, ob_target_day: pd.Timestamp, ob_sheet: str, ob_source: str) -> None:
    if progress.empty:
        return

    total_routes = len(progress)
    total_tos = int(progress["TOs"].sum()) if "TOs" in progress.columns else 0
    loaded = int(progress["Loaded"].sum()) if "Loaded" in progress.columns else 0
    open_tos = int(progress["Open TOs"].sum()) if "Open TOs" in progress.columns else 0
    work_remaining = int(progress["Lines_Remaining"].sum()) if "Lines_Remaining" in progress.columns else 0
    risk_routes = int(progress["Timing Risk"].ne("Normal").sum()) if "Timing Risk" in progress.columns else 0
    units_nyp = int(progress["Units_NYP"].sum()) if "Units_NYP" in progress.columns else 0
    po_without_pallets = int(progress["PO_WO_Pallets"].sum()) if "PO_WO_Pallets" in progress.columns else 0
    progress_rate = loaded / total_tos if total_tos else 0

    status = "Green"
    if risk_routes or open_tos or units_nyp or po_without_pallets:
        status = "Yellow"
    if "Past Departure Risk" in set(progress.get("Timing Risk", pd.Series(dtype=str)).astype(str)):
        status = "Red"

    st.markdown("### Daily Health Visual")
    st.caption(
        f"Live engine view built from SDT Schedule + OB TO Tracker. OB tab: {ob_sheet or 'Not found'} | "
        f"Target day: {ob_target_day.strftime('%m/%d/%Y')}"
        + (f" | Source: {ob_source}" if ob_source else "")
    )

    metric_cols = st.columns(6)
    metric_cols[0].metric("Window Health", status)
    metric_cols[1].metric("Routes", format_number(total_routes))
    metric_cols[2].metric("TO Progress", f"{loaded:,} / {total_tos:,}", format_percent(progress_rate))
    metric_cols[3].metric("Open TOs", format_number(open_tos))
    metric_cols[4].metric("Lines Remaining", format_number(work_remaining))
    metric_cols[5].metric("Units NYP", format_number(units_nyp))

    chart_df = progress.copy()
    chart_df["Progress Display"] = chart_df["Progress %"].fillna(0) if "Progress %" in chart_df.columns else 0
    chart_df["Open Work Label"] = chart_df["Open TOs"].fillna(0).astype(int).astype(str) + " open"

    chart_cols = st.columns([3, 2])
    with chart_cols[0]:
        progress_chart = chart_df.sort_values("Progress Display", ascending=True)
        fig = px.bar(
            progress_chart,
            x="Progress Display",
            y="Carrier",
            orientation="h",
            color="Window Status" if "Window Status" in progress_chart.columns else "Timing Risk",
            text="Open Work Label",
            color_discrete_map={
                "Complete": "#2e7d32",
                "Upcoming": "#4f8fbf",
                "In Window": "#f9a825",
                "Past Departure": "#c62828",
                "No SDT Window": "#78909c",
                "Normal": "#2e7d32",
                "Work Remaining": "#f9a825",
                "Missing SDT Window": "#78909c",
                "Past Departure Risk": "#c62828",
            },
            labels={"Progress Display": "Loaded Progress", "Carrier": ""},
        )
        fig.update_xaxes(tickformat=".0%", range=[0, 1])
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(height=max(360, 34 * len(progress_chart)), margin=dict(l=10, r=80, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with chart_cols[1]:
        open_chart = chart_df.sort_values("Open TOs", ascending=True)
        fig_open = px.bar(
            open_chart,
            x="Open TOs",
            y="Carrier",
            orientation="h",
            color="Timing Risk",
            color_discrete_map={
                "Normal": "#2e7d32",
                "Work Remaining": "#f9a825",
                "Missing SDT Window": "#78909c",
                "Past Departure Risk": "#c62828",
            },
            labels={"Open TOs": "Open TOs", "Carrier": ""},
        )
        fig_open.update_layout(height=max(360, 34 * len(open_chart)), margin=dict(l=10, r=30, t=20, b=10))
        st.plotly_chart(fig_open, use_container_width=True)

    if "Units_NYP" in progress.columns:
        readiness = progress.copy()
        readiness["Pallet Readiness"] = readiness["Pallet Readiness Risk"].fillna("No Fill Rate Match")
        readiness_chart = readiness.sort_values("Units_NYP", ascending=True)
        fig_readiness = px.bar(
            readiness_chart,
            x="Units_NYP",
            y="Carrier",
            orientation="h",
            color="Pallet Readiness",
            color_discrete_map={
                "Normal": "#2e7d32",
                "Units NYP": "#f9a825",
                "PO W/O Pallets": "#c62828",
                "No Fill Rate Match": "#78909c",
            },
            labels={"Units_NYP": "Units NYP", "Carrier": ""},
        )
        fig_readiness.update_layout(height=max(320, 30 * len(readiness_chart)), margin=dict(l=10, r=30, t=20, b=10))
        st.subheader("Pallet Readiness")
        st.plotly_chart(fig_readiness, use_container_width=True)

    watchlist = progress[progress["Timing Risk"].ne("Normal")].copy() if "Timing Risk" in progress.columns else pd.DataFrame()
    if watchlist.empty:
        st.success("All matched routes are currently normal against the SDT window view.")
    else:
        st.subheader("Route Watchlist")
        watch_cols = [
            "Carrier",
            "Window Status",
            "Load Ready Time",
            "Departure Time",
            "Open TOs",
            "Lines_Remaining",
            "Units_NYP",
            "PO_WO_Pallets",
            "Timing Risk",
            "Pallet Readiness Risk",
        ]
        st.dataframe(watchlist[[col for col in watch_cols if col in watchlist.columns]], use_container_width=True, hide_index=True)

    brief = (
        f"DC1 SDT x OB Tracker health for {ob_target_day.strftime('%m/%d')}: {status}. "
        f"{loaded:,} of {total_tos:,} TOs loaded across {total_routes:,} route(s); "
        f"{open_tos:,} TOs remain open with {work_remaining:,} lines remaining and {units_nyp:,} units NYP. "
        f"{risk_routes:,} route(s) require follow-up."
    )
    st.text_area("Copy-ready Daily Health note", value=brief, height=90)


def render_daily_ops_labor_embed(context: DailyHealthContext) -> None:
    values, pallet_source = load_daily_pallet_count_values()
    pallets, pallet_date = parse_daily_pallet_counts(values)
    crossdock_summary, mfc_summary = summarize_crossdock_pallet_completion(pallets)
    dock_summary = summarize_fill_rate_dock_activity(context.fill_rate)
    readiness = build_fill_rate_readiness(context.fill_rate)

    if pallets.empty and context.fill_rate.empty:
        render_enterprise_module_header(
            "Daily Health Operations",
            "Ops & Labor Pulse",
            "Connect the Operations Fill-Rate Google Sheet to populate pallet readiness, dock pressure, and workload focus.",
            "Yellow",
            "No fill-rate data loaded",
        )
        st.info("The embedded operations panel is waiting for the Operations Fill-Rate source.")
        return

    total_pallets = int(pallets["Pallet"].count()) if not pallets.empty else int(readiness.get("Fill_Total_Pallets", pd.Series(dtype=float)).sum())
    completed_pallets = int(pallets["Complete"].sum()) if not pallets.empty else 0
    open_pallets = max(total_pallets - completed_pallets, 0)
    completion_rate = completed_pallets / total_pallets if total_pallets else 0
    active_gustos = int(pallets["Gusto"].nunique()) if not pallets.empty else int(readiness.get("Fill_POs", pd.Series(dtype=float)).sum())
    active_mfcs = int(pallets["Location Name"].nunique()) if not pallets.empty else int(readiness.get("Fill_Locations", pd.Series(dtype=float)).sum())
    crossdock_count = int(pallets["Cross-Dock"].nunique()) if not pallets.empty else int(readiness["Fill Carrier"].nunique()) if not readiness.empty else 0
    total_weight = float(pallets["Pallet Weight"].sum()) if not pallets.empty else float(readiness.get("Total_Pallet_Weight", pd.Series(dtype=float)).sum())
    units_nyp = int(readiness.get("Units_NYP", pd.Series(dtype=float)).sum()) if not readiness.empty else 0
    po_without_pallets = int(readiness.get("PO_WO_Pallets", pd.Series(dtype=float)).sum()) if not readiness.empty else 0
    picked_units = int(readiness.get("LBI_Pick_Quantity", pd.Series(dtype=float)).sum()) if not readiness.empty else 0
    total_work_units = picked_units + units_nyp
    work_completion = picked_units / total_work_units if total_work_units else completion_rate

    status = "Green"
    if open_pallets or units_nyp or po_without_pallets:
        status = "Yellow"
    if completion_rate < 0.5 and (open_pallets or units_nyp):
        status = "Red"

    source_bits = []
    if pallet_source:
        source_bits.append(pallet_source)
    if pallet_date is not None:
        source_bits.append(f"Ship date {pallet_date.strftime('%m/%d/%Y')}")
    elif context.fill_source:
        source_bits.append(context.fill_source)

    render_enterprise_module_header(
        "Daily Health Operations",
        "Ops & Labor Pulse",
        "Operations Fill-Rate view for pallet readiness, dock pressure, and labor workload focus.",
        status,
        " | ".join(source_bits) if source_bits else "Operations Fill-Rate source",
    )

    render_enterprise_kpi_grid(
        [
            {
                "label": "Pallet Completion",
                "value": format_percent(completion_rate),
                "delta": f"{format_number(completed_pallets)} of {format_number(total_pallets)} staged",
                "accent": "green" if completion_rate >= 0.9 else "yellow" if completion_rate >= 0.5 else "red",
            },
            {
                "label": "Open Pallets",
                "value": format_number(open_pallets),
                "delta": "remaining prep / staging work",
                "accent": "green" if open_pallets == 0 else "yellow",
            },
            {
                "label": "Active GUSTOs",
                "value": format_number(active_gustos),
                "delta": f"{format_number(active_mfcs)} MFC destination(s)",
                "accent": "neutral",
            },
            {
                "label": "Units NYP",
                "value": format_number(units_nyp),
                "delta": f"{format_percent(work_completion)} progress to completion",
                "accent": "green" if units_nyp == 0 else "yellow",
            },
            {
                "label": "Weight in Flow",
                "value": format_number(total_weight),
                "delta": f"{format_number(crossdock_count)} cross-dock lane(s)",
                "accent": "neutral",
            },
            {
                "label": "PO W/O Pallets",
                "value": format_number(po_without_pallets),
                "delta": "fill-rate exception queue",
                "accent": "green" if po_without_pallets == 0 else "red",
            },
        ],
        columns=6,
    )

    if not crossdock_summary.empty:
        chart_cols = st.columns([1.1, 0.9])
        with chart_cols[0]:
            st.markdown("#### Cross-Dock Readiness")
            chart = crossdock_summary.copy()
            chart["Completion Label"] = chart["Completed"].astype(int).astype(str) + " / " + chart["Pallets"].astype(int).astype(str)
            fig = px.bar(
                chart.sort_values("Completion %", ascending=True),
                x="Completion %",
                y="Cross-Dock",
                orientation="h",
                color="Open Pallets",
                text="Completion Label",
                color_continuous_scale=["#2f7d55", "#efb13f", "#bd372f"],
                labels={"Completion %": "Pallet Completion", "Cross-Dock": "", "Open Pallets": "Open"},
            )
            fig.update_xaxes(tickformat=".0%", range=[0, 1])
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_layout(height=max(330, 36 * len(chart)), margin=dict(l=10, r=80, t=10, b=10), coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

        with chart_cols[1]:
            st.markdown("#### Labor Focus by MFC")
            focus = mfc_summary[mfc_summary["Open Pallets"].gt(0)].copy()
            if focus.empty:
                focus = mfc_summary.copy()
            focus = focus.sort_values(["Open Pallets", "Weight"], ascending=[False, False]).head(10)
            display = focus[["Cross-Dock", "Location Name", "Gusto", "Pallet Progress", "Open Pallets", "Weight", "Completion %"]].copy()
            display["Weight"] = display["Weight"].map(format_number)
            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Completion %": st.column_config.ProgressColumn("Completion", format="%.0f%%", min_value=0, max_value=1)
                },
            )

    if not dock_summary.empty:
        st.markdown("#### Dock Door Workload")
        dock_cols = st.columns([0.95, 1.05])
        with dock_cols[0]:
            fig_dock = px.bar(
                dock_summary.head(12).sort_values("Units_NYP", ascending=True),
                x="Units_NYP",
                y="Dock Door",
                orientation="h",
                color="Gustos",
                color_continuous_scale=["#3a77a8", "#efb13f"],
                labels={"Units_NYP": "Units NYP", "Dock Door": "", "Gustos": "GUSTOs"},
            )
            fig_dock.update_layout(height=320, margin=dict(l=10, r=30, t=10, b=10), coloraxis_showscale=False)
            st.plotly_chart(fig_dock, use_container_width=True)
        with dock_cols[1]:
            dock_display = dock_summary.head(12).copy()
            dock_display["Picked_Units"] = dock_display["Picked_Units"].map(format_number)
            dock_display["Units_NYP"] = dock_display["Units_NYP"].map(format_number)
            dock_display["Pallets"] = dock_display["Pallets"].map(format_number)
            dock_display["Weight"] = dock_display["Weight"].map(format_number)
            st.dataframe(dock_display, use_container_width=True, hide_index=True)

    note_parts = [
        f"Ops/Labor pulse: {status}.",
        f"{format_number(completed_pallets)} of {format_number(total_pallets)} pallets complete ({format_percent(completion_rate)}).",
        f"{format_number(open_pallets)} pallets remain open across {format_number(active_gustos)} GUSTO(s).",
        f"Units NYP: {format_number(units_nyp)}; PO without pallets: {format_number(po_without_pallets)}.",
    ]
    if not mfc_summary.empty:
        top = mfc_summary.sort_values(["Open Pallets", "Weight"], ascending=[False, False]).head(3)
        watch = "; ".join(
            f"{row['Location Name']} / {row['Gusto']} ({int(row['Open Pallets'])} open)"
            for _, row in top.iterrows()
            if int(row["Open Pallets"]) > 0
        )
        if watch:
            note_parts.append(f"Watch: {watch}.")
    st.text_area("Copy-ready operations note", value=" ".join(note_parts), height=95)


def summarize_daily_health_progress(progress: pd.DataFrame) -> dict[str, int | float | str]:
    total_routes = len(progress)
    total_tos = int(progress["TOs"].sum()) if "TOs" in progress.columns else 0
    loaded = int(progress["Loaded"].sum()) if "Loaded" in progress.columns else 0
    open_tos = int(progress["Open TOs"].sum()) if "Open TOs" in progress.columns else 0
    active = int(progress["Active"].sum()) if "Active" in progress.columns else 0
    work_remaining = int(progress["Lines_Remaining"].sum()) if "Lines_Remaining" in progress.columns else 0
    units = int(progress["Units"].sum()) if "Units" in progress.columns else 0
    pallets = int(progress["Pallets"].sum()) if "Pallets" in progress.columns else 0
    units_nyp = int(progress["Units_NYP"].sum()) if "Units_NYP" in progress.columns else 0
    po_without_pallets = int(progress["PO_WO_Pallets"].sum()) if "PO_WO_Pallets" in progress.columns else 0
    in_window = int(progress["Window Status"].eq("In Window").sum()) if "Window Status" in progress.columns else 0
    upcoming = int(progress["Window Status"].eq("Upcoming").sum()) if "Window Status" in progress.columns else 0
    past = int(progress["Window Status"].eq("Past Departure").sum()) if "Window Status" in progress.columns else 0
    risk_routes = int(progress["Timing Risk"].ne("Normal").sum()) if "Timing Risk" in progress.columns else 0
    completion = loaded / total_tos if total_tos else 0

    status = "Green"
    if risk_routes or open_tos or units_nyp or po_without_pallets:
        status = "Yellow"
    if past or "Past Departure Risk" in set(progress.get("Timing Risk", pd.Series(dtype=str)).astype(str)):
        status = "Red"

    return {
        "status": status,
        "total_routes": total_routes,
        "total_tos": total_tos,
        "loaded": loaded,
        "open_tos": open_tos,
        "active": active,
        "work_remaining": work_remaining,
        "units": units,
        "pallets": pallets,
        "units_nyp": units_nyp,
        "po_without_pallets": po_without_pallets,
        "in_window": in_window,
        "upcoming": upcoming,
        "past": past,
        "risk_routes": risk_routes,
        "completion": completion,
    }


def top_daily_health_risks(progress: pd.DataFrame, limit: int = 3) -> pd.DataFrame:
    if progress.empty:
        return pd.DataFrame()
    risks = progress.copy()
    risks["risk_score"] = 0
    if "Timing Risk" in risks.columns:
        risks.loc[risks["Timing Risk"].ne("Normal"), "risk_score"] += 30
        risks.loc[risks["Timing Risk"].eq("Past Departure Risk"), "risk_score"] += 50
    if "Window Status" in risks.columns:
        risks.loc[risks["Window Status"].eq("In Window"), "risk_score"] += 15
        risks.loc[risks["Window Status"].eq("Past Departure"), "risk_score"] += 40
    for col, weight in [("Open TOs", 5), ("Lines_Remaining", 1), ("Units_NYP", 2), ("PO_WO_Pallets", 10)]:
        if col in risks.columns:
            risks["risk_score"] += pd.to_numeric(risks[col], errors="coerce").fillna(0) * weight
    risks = risks[risks["risk_score"].gt(0)].sort_values("risk_score", ascending=False)
    display_cols = [
        "Carrier",
        "Window Status",
        "Departure Time",
        "Open TOs",
        "Lines_Remaining",
        "Units_NYP",
        "PO_WO_Pallets",
        "Timing Risk",
        "Pallet Readiness Risk",
    ]
    return risks[[col for col in display_cols if col in risks.columns]].head(limit)


def summarize_gusto_pallet_progress(pallet_counts: pd.DataFrame) -> pd.DataFrame:
    if pallet_counts.empty or "Gusto" not in pallet_counts.columns:
        return pd.DataFrame()
    work = pallet_counts.copy()
    work["Pallet Count"] = pd.to_numeric(work.get("Pallet Count", 0), errors="coerce").fillna(0)
    work["Pallet Weight"] = pd.to_numeric(work.get("Pallet Weight", 0), errors="coerce").fillna(0)
    work["Complete Int"] = work.get("Complete", pd.Series(False, index=work.index)).astype(bool).astype(int)
    work = (
        work.groupby(["Gusto", "Pallet"], dropna=False)
        .agg(
            **{
                "Pallet Count": ("Pallet Count", "max"),
                "Pallet Weight": ("Pallet Weight", "max"),
                "Complete Int": ("Complete Int", "max"),
                "Pallet Count Sheet": ("Pallet Count Sheet", lambda values: ", ".join(sorted(set(cell_text(value) for value in values if cell_text(value)))[:3])),
                "Pallet Count Date": ("Pallet Count Date", "max"),
            }
        )
        .reset_index()
    )
    summary = (
        work.groupby("Gusto", dropna=False)
        .agg(
            Pallet_Total=("Pallet Count", "max"),
            Pallet_Rows=("Pallet", "count"),
            Pallets_Complete=("Complete Int", "sum"),
            Pallet_Weight=("Pallet Weight", "sum"),
            Pallet_Count_Sheet=("Pallet Count Sheet", lambda values: ", ".join(sorted(set(cell_text(value) for value in values if cell_text(value)))[:3])),
            Pallet_Count_Date=("Pallet Count Date", "max"),
        )
        .reset_index()
    )
    summary["Pallet_Total"] = summary[["Pallet_Total", "Pallet_Rows"]].max(axis=1)
    summary["Pallets_Complete"] = summary["Pallets_Complete"].clip(upper=summary["Pallet_Total"])
    summary["Pallet_Completion"] = summary["Pallets_Complete"] / summary["Pallet_Total"].replace(0, pd.NA)
    return summary


def pallet_progress_label(row: pd.Series) -> str:
    total = int(row.get("Pallet_Total") or 0)
    complete = int(row.get("Pallets_Complete") or 0)
    if total <= 0:
        return "No pallet count match"
    percent = complete / total
    status = str(row.get("Status", "")).casefold()
    if "loaded" in status or "shipped" in status or "complete" in status or "closed" in status:
        stage = "Shipped"
    elif "staged" in status and complete >= total:
        stage = "Staged"
    elif "staged" in status:
        stage = "OB Staged"
    elif complete >= total:
        stage = "Pallets Complete"
    elif complete > 0:
        stage = "In Progress"
    else:
        stage = "Not Started"
    return f"{complete}/{total} Pallets {percent:.0%} {stage}"


def build_open_to_detail(context: DailyHealthContext, carrier: str) -> pd.DataFrame:
    tracker = context.ob_tracker
    if tracker.empty or not carrier:
        return pd.DataFrame()

    carrier_col = first_matching_column(tracker, [["carrier"]])
    status_col = first_matching_column(tracker, [["status"]])
    to_col = first_matching_column(tracker, [["to"], ["po", "number"]])
    location_col = first_matching_column(tracker, [["locations"], ["location"]])
    lines_col = first_matching_column(tracker, [["lines", "remaining"], ["lines"]])
    units_col = first_matching_column(tracker, [["units"]])
    if not carrier_col:
        return pd.DataFrame()

    work = tracker.copy()
    work["_route_key"] = work[carrier_col].map(normalize_route_key)
    route_key = normalize_route_key(carrier)
    route_rows = work[work["_route_key"].eq(route_key)].copy()
    if route_rows.empty:
        return pd.DataFrame()

    status_values = route_rows[status_col].fillna("Unknown").astype(str).str.strip() if status_col else pd.Series("Unknown", index=route_rows.index)
    complete_mask = status_values.str.casefold().str.contains("loaded|complete|closed", regex=True, na=False)
    detail = route_rows[~complete_mask].copy()
    if detail.empty:
        return pd.DataFrame()

    detail["Status"] = status_values.loc[detail.index]
    detail["GUSTO / TO"] = detail[to_col].astype(str).str.strip() if to_col else ""
    detail["Location"] = detail[location_col].astype(str).str.strip() if location_col else ""
    detail["Lines Remaining"] = pd.to_numeric(detail[lines_col], errors="coerce").fillna(0) if lines_col else 0
    detail["Units"] = pd.to_numeric(detail[units_col], errors="coerce").fillna(0) if units_col else 0
    pallet_summary = summarize_gusto_pallet_progress(load_all_daily_pallet_counts())
    if not pallet_summary.empty:
        detail = detail.merge(
            pallet_summary,
            left_on="GUSTO / TO",
            right_on="Gusto",
            how="left",
        )
    for col in ["Pallet_Total", "Pallets_Complete", "Pallet_Weight"]:
        if col not in detail.columns:
            detail[col] = 0
        detail[col] = pd.to_numeric(detail[col], errors="coerce").fillna(0)
    if "Pallet_Count_Sheet" not in detail.columns:
        detail["Pallet_Count_Sheet"] = ""
    detail["Pallet Progress"] = detail.apply(pallet_progress_label, axis=1)
    detail["Pallet Weight"] = detail.apply(
        lambda row: f"{format_number(row.get('Pallet_Weight'))} lbs" if int(row.get("Pallet_Total") or 0) > 0 else "",
        axis=1,
    )
    detail["Pallet Source"] = (
        detail["Pallet_Count_Sheet"]
        .fillna("")
        .astype(str)
        .str.replace("Warp-1-Daily Pallet Counts", "Warp-1", regex=False)
        .str.replace("Warp-2-Daily Pallet Counts", "Warp-2", regex=False)
        .str.replace("Daily Pallet Counts", "Daily", regex=False)
    )
    display_cols = ["GUSTO / TO", "Status", "Location", "Lines Remaining", "Units", "Pallet Progress", "Pallet Weight", "Pallet Source"]
    return detail[display_cols].sort_values(["Status", "GUSTO / TO"]).reset_index(drop=True)


def render_open_tos_drilldown(context: DailyHealthContext) -> None:
    carrier = get_query_param("open_tos")
    if not carrier:
        return
    detail = build_open_to_detail(context, carrier)
    embed_mode = get_site_embed_mode()
    close_href = app_href("Home", "Live Update", site_embed=embed_mode) if embed_mode else app_href("Home", "Live Update")
    st.markdown(
        f"""
        <div class="gp-drilldown-panel">
          <div>
            <div class="gp-drilldown-panel__eyebrow">Open TO Drilldown</div>
            <div class="gp-drilldown-panel__title">{html.escape(carrier)}</div>
          </div>
          <a class="gp-drilldown-panel__close" href="{close_href}" target="_self">Close</a>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if detail.empty:
        st.info("No open TO detail rows were found for this route in the live OB Tracker tab.")
        return
    st.dataframe(
        detail,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Lines Remaining": st.column_config.NumberColumn("Lines Remaining", format="%,.0f"),
            "Units": st.column_config.NumberColumn("Units", format="%,.0f"),
        },
    )


def health_status_class(status: object) -> str:
    text = str(status or "").strip().casefold()
    if text == "red":
        return "red"
    if text == "yellow":
        return "yellow"
    if text == "green":
        return "green"
    return "neutral"


def render_enterprise_module_header(eyebrow: str, title: str, subtitle: str, status: str, meta: str) -> None:
    status_class = health_status_class(status)
    st.markdown(
        f'<div class="gp-enterprise-hero"><div><div class="gp-enterprise-hero__eyebrow">{html.escape(eyebrow)}</div>'
        f'<div class="gp-enterprise-hero__title">{html.escape(title)}</div>'
        f'<div class="gp-enterprise-hero__subtitle">{html.escape(subtitle)}</div></div>'
        f'<div class="gp-enterprise-hero__side"><div class="gp-status-pill gp-status-pill--{status_class}">{html.escape(status)}</div>'
        f'<div class="gp-enterprise-hero__meta">{html.escape(meta)}</div></div></div>',
        unsafe_allow_html=True,
    )


def render_enterprise_kpi_grid(cards: list[dict[str, str]], columns: int = 4) -> None:
    card_html = []
    for card in cards:
        accent = health_status_class(card.get("accent", "neutral"))
        delta = card.get("delta", "")
        delta_html = f'<div class="gp-kpi-card__delta">{html.escape(delta)}</div>' if delta else ""
        card_html.append(
            f'<div class="gp-kpi-card gp-kpi-card--{accent}">'
            f'<div class="gp-kpi-card__label">{html.escape(card.get("label", ""))}</div>'
            f'<div class="gp-kpi-card__value">{html.escape(card.get("value", ""))}</div>'
            f'{delta_html}</div>'
        )
    st.markdown(
        f'<div class="gp-kpi-grid gp-kpi-grid--{columns}">' + "".join(card_html) + "</div>",
        unsafe_allow_html=True,
    )


def render_enterprise_risk_cards(risks: pd.DataFrame) -> None:
    if risks.empty:
        st.markdown(
            '<div class="gp-empty-state"><div class="gp-empty-state__title">No live route risks surfaced</div>'
            '<div class="gp-empty-state__body">Current matched routes are reading normal against the SDT window and OB Tracker progress view.</div></div>',
            unsafe_allow_html=True,
        )
        return

    cards = []
    for _, row in risks.iterrows():
        timing = str(row.get("Timing Risk", "Review"))
        window = str(row.get("Window Status", "Window review"))
        status_class = "red" if "Past" in timing or "Past" in window else "yellow"
        carrier = str(row.get("Carrier", "Unknown Carrier"))
        embed_mode = get_site_embed_mode()
        open_tos_href = (
            app_href("Home", "Live Update", open_tos=carrier, site_embed=embed_mode)
            if embed_mode
            else app_href("Home", "Live Update", open_tos=carrier)
        )
        details = [
            (f'<a class="gp-risk-card__metric-link" href="{open_tos_href}" target="_self">Open TOs</a>', format_number(row.get("Open TOs", 0))),
            ("Lines", format_number(row.get("Lines_Remaining", 0))),
            ("Units NYP", format_number(row.get("Units_NYP", 0))),
        ]
        detail_html = "".join(
            f'<div><span>{label if label.startswith("<a ") else html.escape(label)}</span><strong>{html.escape(value)}</strong></div>'
            for label, value in details
        )
        cards.append(
            f'<div class="gp-risk-card gp-risk-card--{status_class}"><div class="gp-risk-card__topline">'
            f'<div class="gp-risk-card__carrier">{html.escape(carrier)}</div>'
            f'<div class="gp-status-pill gp-status-pill--{status_class}">{html.escape(timing)}</div></div>'
            f'<div class="gp-risk-card__window">{html.escape(window)} | Depart {html.escape(str(row.get("Departure Time", "TBD")))}</div>'
            f'<div class="gp-risk-card__metrics">{detail_html}</div></div>'
        )
    st.markdown('<div class="gp-risk-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)


def render_brief_panel(title: str, body: str) -> None:
    st.markdown(
        f'<div class="gp-brief-panel"><div class="gp-brief-panel__title">{html.escape(title)}</div></div>',
        unsafe_allow_html=True,
    )
    st.text_area(title, value=body, height=170, label_visibility="collapsed")


def make_live_update_note(context: DailyHealthContext) -> str:
    if context.progress.empty:
        return "Daily Health live update is waiting on SDT Schedule, OB TO Tracker, and Fill Rate sources."
    summary = summarize_daily_health_progress(context.progress)
    risk_carriers = top_daily_health_risks(context.progress, 3)
    risk_line = "No top carrier risks currently surfaced."
    if not risk_carriers.empty:
        risk_line = "; ".join(
            f"{row['Carrier']} ({row.get('Timing Risk', 'Review')}, {format_number(row.get('Open TOs', 0))} open TOs)"
            for _, row in risk_carriers.iterrows()
        )
    return (
        f"DC1 live update for {context.ob_target_day.strftime('%m/%d')}: {summary['status']}. "
        f"{format_number(summary['loaded'])} of {format_number(summary['total_tos'])} TOs are loaded "
        f"({format_percent(summary['completion'])}) across {format_number(summary['total_routes'])} route(s). "
        f"{format_number(summary['open_tos'])} TOs remain open, {format_number(summary['in_window'])} route(s) are inside window, "
        f"and {format_number(summary['past'])} are past departure. Top watch: {risk_line}."
    )


def make_executive_daily_brief(context: DailyHealthContext, health: HealthResult, ops_data: dict[str, pd.DataFrame]) -> str:
    ops_summary = summarize_ops_overall(ops_data)
    summary = summarize_daily_health_progress(context.progress) if not context.progress.empty else {}
    if context.progress.empty:
        shipping_line = "Shipping readiness is waiting on the live SDT Schedule and OB TO Tracker match."
        action_line = "Connect or refresh the three Daily Health sources before publishing the executive note."
    else:
        risks = top_daily_health_risks(context.progress, 3)
        risk_line = "no surfaced route-level risks"
        if not risks.empty:
            risk_line = "; ".join(str(carrier) for carrier in risks["Carrier"].head(3))
        shipping_line = (
            f"Shipping readiness is {summary['status']}: {format_percent(summary['completion'])} loaded, "
            f"{format_number(summary['open_tos'])} open TOs, {format_number(summary['risk_routes'])} route(s) requiring review. "
            f"Current watch list: {risk_line}."
        )
        action_line = "Confirm open TO ownership, pallet readiness, and departure-window recovery for the watch-list carriers."

    ops_line = "Ops productivity source is not loaded."
    if ops_summary.get("latest_date"):
        ops_line = (
            f"Ops productivity {ops_summary['latest_date']}: {format_number(ops_summary.get('latest_units'))} units, "
            f"{format_number(ops_summary.get('latest_hours'))} hours, {format_number(ops_summary.get('latest_uph'))} UPH, "
            f"{format_number(ops_summary.get('bridge_count'))} bridge note(s)."
        )

    return (
        f"DC1 Executive Brief | {datetime.now().strftime('%m/%d/%Y %I:%M %p')}\n\n"
        f"Overall status: {health.label}\n\n"
        f"{shipping_line}\n\n"
        f"Pallet readiness: {format_number(summary.get('units_nyp', 0))} units NYP and "
        f"{format_number(summary.get('po_without_pallets', 0))} PO/pallet readiness exception(s).\n\n"
        f"{ops_line}\n\n"
        f"Recommended action: {action_line}"
    )


def build_outstanding_site_readiness(context: DailyHealthContext) -> pd.DataFrame:
    if context.progress.empty or context.fill_rate.empty:
        return pd.DataFrame()

    carrier_col = first_matching_column(context.fill_rate, [["carrier"], ["route"]])
    location_col = first_matching_column(context.fill_rate, [["location", "name"], ["location"]])
    po_col = first_matching_column(context.fill_rate, [["po", "number"], ["to", "number"], ["po"]])
    units_col = first_matching_column(context.fill_rate, [["units"]])
    units_nyp_col = first_matching_column(context.fill_rate, [["units", "nyp"]])
    picked_col = first_matching_column(context.fill_rate, [["lbi", "pick"], ["pick", "quantity"], ["picked", "units"]])
    pallet_col = first_matching_column(context.fill_rate, [["total", "pallets"], ["pallets"]])
    weight_col = first_matching_column(context.fill_rate, [["total", "pallet", "weight"], ["weight"]])
    if not carrier_col or not location_col:
        return pd.DataFrame()

    work = context.fill_rate.copy()
    work["Carrier"] = work[carrier_col].astype(str).str.strip()
    work["_route_key"] = work["Carrier"].map(normalize_route_key)
    work["Site"] = work[location_col].map(format_mfc_site_label)
    work["Location Name"] = work[location_col].astype(str).str.strip()
    work["Gusto"] = work[po_col].astype(str).str.strip() if po_col else ""
    work["Units"] = pd.to_numeric(work[units_col], errors="coerce").fillna(0) if units_col else 0
    work["Units NYP"] = pd.to_numeric(work[units_nyp_col], errors="coerce").fillna(0) if units_nyp_col else 0
    work["Picked Units"] = pd.to_numeric(work[picked_col], errors="coerce").fillna(0) if picked_col else (work["Units"] - work["Units NYP"]).clip(lower=0)
    work["Pallets"] = pd.to_numeric(work[pallet_col], errors="coerce").fillna(0) if pallet_col else 0
    work["Weight"] = pd.to_numeric(work[weight_col], errors="coerce").fillna(0) if weight_col else 0

    site_summary = (
        work.groupby(["_route_key", "Carrier", "Site", "Location Name", "Gusto"], dropna=False)
        .agg(
            Units=("Units", "sum"),
            Units_NYP=("Units NYP", "sum"),
            Picked_Units=("Picked Units", "sum"),
            Pallets=("Pallets", "sum"),
            Weight=("Weight", "sum"),
        )
        .reset_index()
    )
    site_summary = site_summary[site_summary["Units_NYP"].gt(0) | site_summary["Pallets"].gt(0)].copy()
    if site_summary.empty:
        return pd.DataFrame()

    progress_cols = [
        "Carrier",
        "SDT Day",
        "Load Ready Time",
        "Departure Time",
        "Open TOs",
        "Progress %",
        "Timing Risk",
        "Window Status",
    ]
    route_progress = context.progress[[col for col in progress_cols if col in context.progress.columns]].copy()
    route_progress["_route_key"] = route_progress["Carrier"].map(normalize_route_key)
    route_progress = route_progress.rename(columns={"Carrier": "SDT Carrier"})
    site_summary = site_summary.merge(route_progress, on="_route_key", how="left")
    site_summary["Outstanding %"] = site_summary["Units_NYP"] / site_summary["Units"].replace(0, pd.NA)
    site_summary["Progress to Completion"] = site_summary["Picked_Units"] / site_summary["Units"].replace(0, pd.NA)
    site_summary["Route Outstanding %"] = 1 - site_summary.get("Progress %", pd.Series(0, index=site_summary.index)).fillna(0)
    site_summary["SDT Window"] = (
        site_summary.get("Load Ready Time", pd.Series("", index=site_summary.index)).fillna("").astype(str)
        + " - "
        + site_summary.get("Departure Time", pd.Series("", index=site_summary.index)).fillna("").astype(str)
    ).str.strip(" -")
    now = pd.Timestamp.now()
    depart_times = site_summary.get("Departure Time", pd.Series("", index=site_summary.index)).map(parse_time_today)
    site_summary["Hours to SDT End"] = (depart_times - now).dt.total_seconds() / 3600
    site_summary["Hours Past SDT"] = ((now - depart_times).dt.total_seconds() / 3600).where(depart_times.notna(), pd.NA)
    site_summary["SDT Timing"] = "No SDT Window"
    site_summary.loc[site_summary["Hours to SDT End"].gt(0), "SDT Timing"] = "Before Window End"
    site_summary.loc[site_summary["Window Status"].astype(str).eq("In Window"), "SDT Timing"] = "Inside Window"
    site_summary.loc[site_summary["Hours to SDT End"].lt(0), "SDT Timing"] = "Past Window"
    site_summary["Timing Clock"] = ""
    site_summary.loc[site_summary["Hours to SDT End"].gt(0), "Timing Clock"] = site_summary.loc[
        site_summary["Hours to SDT End"].gt(0), "Hours to SDT End"
    ].map(lambda value: f"{value:.1f}h until end")
    site_summary.loc[site_summary["Hours to SDT End"].lt(0), "Timing Clock"] = site_summary.loc[
        site_summary["Hours to SDT End"].lt(0), "Hours Past SDT"
    ].map(lambda value: f"{value:.1f}h past")
    return site_summary.sort_values(["Route Outstanding %", "Units_NYP", "Weight"], ascending=[False, False, False])


def timing_status_class(value: object) -> str:
    text = cell_text(value).casefold()
    if "past" in text:
        return "red"
    if "inside" in text:
        return "yellow"
    if "before" in text:
        return "green"
    return "neutral"


def render_outstanding_route_summary_table(route_summary: pd.DataFrame) -> None:
    if route_summary.empty:
        return
    rows_html = []
    for _, row in route_summary.iterrows():
        timing_class = timing_status_class(row.get("SDT Timing", ""))
        progress = row.get("Progress to Completion", 0)
        progress = 0 if pd.isna(progress) else max(0, min(float(progress), 1))
        progress_percent = format_percent(progress)
        rows_html.append(
            "<tr>"
            f"<td>{html.escape(cell_text(row.get('SDT Carrier')))}</td>"
            f"<td>{html.escape(cell_text(row.get('SDT Day')))}</td>"
            f"<td>{html.escape(cell_text(row.get('SDT Window')))}</td>"
            f"<td><span class=\"gp-timing-badge gp-timing-badge--{timing_class}\">{html.escape(cell_text(row.get('SDT Timing')))}</span></td>"
            f"<td><span class=\"gp-clock-pill gp-clock-pill--{timing_class}\">{html.escape(cell_text(row.get('Timing Clock')) or 'No clock')}</span></td>"
            f"<td><div class=\"gp-progress-cell\"><div class=\"gp-progress-track\"><div class=\"gp-progress-fill gp-progress-fill--{timing_class}\" style=\"width: {progress * 100:.1f}%\"></div></div><span>{progress_percent}</span></div></td>"
            f"<td>{int(row.get('Gustos', 0) or 0):,}</td>"
            f"<td>{int(row.get('Pallets', 0) or 0):,}</td>"
            f"<td>{html.escape(cell_text(row.get('Site List')))}</td>"
            f"<td>{html.escape(cell_text(row.get('Timing Risk')))}</td>"
            "</tr>"
        )
    st.markdown(
        """
        <div class="gp-timing-table-wrap">
          <table class="gp-timing-table">
            <thead>
              <tr>
                <th>SDT Carrier</th>
                <th>SDT Day</th>
                <th>SDT Window</th>
                <th>SDT Timing</th>
                <th>Timing Clock</th>
                <th>Progress to Completion</th>
                <th>GUSTOs</th>
                <th>Pallets</th>
                <th>Site List</th>
                <th>Timing Risk</th>
              </tr>
            </thead>
            <tbody>
        """
        + "".join(rows_html)
        + """
            </tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_outstanding_site_blocks(context: DailyHealthContext) -> None:
    site_readiness = build_outstanding_site_readiness(context)
    if site_readiness.empty:
        return

    st.markdown('<div class="gp-section-label">Outstanding Sites By SDT Window</div>', unsafe_allow_html=True)
    route_summary = (
        site_readiness.groupby(["SDT Carrier", "SDT Day", "SDT Window", "Window Status", "SDT Timing", "Timing Risk"], dropna=False)
        .agg(
            Gustos=("Gusto", "nunique"),
            Units_NYP=("Units_NYP", "sum"),
            Units=("Units", "sum"),
            Picked_Units=("Picked_Units", "sum"),
            Pallets=("Pallets", "sum"),
            Weight=("Weight", "sum"),
            Route_Outstanding=("Route Outstanding %", "max"),
            Hours_to_SDT_End=("Hours to SDT End", "min"),
            Hours_Past_SDT=("Hours Past SDT", "max"),
        )
        .reset_index()
        .sort_values(["Route_Outstanding", "Units_NYP"], ascending=[False, False])
    )
    route_summary["Progress to Completion"] = route_summary["Picked_Units"] / route_summary["Units"].replace(0, pd.NA)
    route_summary["Timing Clock"] = ""
    route_summary.loc[route_summary["Hours_to_SDT_End"].gt(0), "Timing Clock"] = route_summary.loc[
        route_summary["Hours_to_SDT_End"].gt(0), "Hours_to_SDT_End"
    ].map(lambda value: f"{value:.1f}h until end")
    route_summary.loc[route_summary["Hours_to_SDT_End"].lt(0), "Timing Clock"] = route_summary.loc[
        route_summary["Hours_to_SDT_End"].lt(0), "Hours_Past_SDT"
    ].map(lambda value: f"{value:.1f}h past")
    route_summary["Site List"] = route_summary["SDT Carrier"].map(
        lambda carrier: ", ".join(
            site_readiness[site_readiness["SDT Carrier"].astype(str).eq(str(carrier))]
            .sort_values("Units_NYP", ascending=False)["Site"]
            .drop_duplicates()
            .head(8)
            .tolist()
        )
    )
    render_outstanding_route_summary_table(route_summary)

    for _, route in route_summary.head(8).iterrows():
        route_sites = site_readiness[site_readiness["SDT Carrier"].astype(str).eq(str(route["SDT Carrier"]))].copy()
        if route_sites.empty:
            continue
        label = (
            f"{route['SDT Carrier']} | {format_percent(route['Progress to Completion'])} progress | "
            f"{int(route['Gustos'])} GUSTO(s) | {route.get('Timing Clock', '')}"
        )
        with st.expander(label, expanded=False):
            detail_cols = [
                "Site",
                "Location Name",
                "Gusto",
                "Progress to Completion",
                "Timing Clock",
                "SDT Timing",
                "Units_NYP",
                "Units",
                "Pallets",
                "Weight",
                "Window Status",
                "Timing Risk",
            ]
            st.dataframe(
                route_sites[[col for col in detail_cols if col in route_sites.columns]].head(80),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Progress to Completion": st.column_config.ProgressColumn("Progress to Completion", format="%.0f%%", min_value=0, max_value=1),
                    "Units_NYP": st.column_config.NumberColumn("Units NYP", format="%,.0f"),
                    "Units": st.column_config.NumberColumn("Units", format="%,.0f"),
                    "Pallets": st.column_config.NumberColumn("Pallets", format="%,.0f"),
                    "Weight": st.column_config.NumberColumn("Weight", format="%,.0f"),
                },
            )


def render_live_update(context: DailyHealthContext) -> None:
    status = "Waiting"
    if not context.progress.empty:
        status = str(summarize_daily_health_progress(context.progress)["status"])
    render_enterprise_module_header(
        "Home Page Live Operations",
        "DC1 Live Update",
        "Google Sites-ready pulse view for shipping-window progress, pallet readiness, and route-level risk.",
        status,
        f"OB tab {context.ob_sheet or 'not selected'} | {datetime.now().strftime('%m/%d/%Y %I:%M %p')}",
    )
    if context.progress.empty:
        st.info("Refresh or connect the SDT Schedule, OB TO Tracker, and Fill Rate sheets to populate the live update.")
        if context.matched_columns:
            st.json(context.matched_columns)
        return

    summary = summarize_daily_health_progress(context.progress)
    render_enterprise_kpi_grid(
        [
            {"label": "Live Health", "value": str(summary["status"]), "delta": "SDT x OB x Fill Rate", "accent": str(summary["status"])},
            {
                "label": "TO Progress",
                "value": f"{format_number(summary['loaded'])} / {format_number(summary['total_tos'])}",
                "delta": format_percent(summary["completion"]),
                "accent": "green" if float(summary["completion"]) >= 0.9 else "yellow",
            },
            {"label": "Open TOs", "value": format_number(summary["open_tos"]), "delta": "Remaining carrier work", "accent": "yellow" if int(summary["open_tos"]) else "green"},
            {"label": "In Window", "value": format_number(summary["in_window"]), "delta": f"{format_number(summary['past'])} past departure", "accent": "red" if int(summary["past"]) else "neutral"},
            {"label": "Units NYP", "value": format_number(summary["units_nyp"]), "delta": "Pallet readiness", "accent": "yellow" if int(summary["units_nyp"]) else "green"},
            {"label": "PO W/O Pallets", "value": format_number(summary["po_without_pallets"]), "delta": "Fill-rate exception", "accent": "red" if int(summary["po_without_pallets"]) else "green"},
        ],
        columns=6,
    )

    risk_cols = st.columns([1.2, 1])
    with risk_cols[0]:
        risks = top_daily_health_risks(context.progress, 3)
        st.markdown('<div class="gp-section-label">Top 3 Live Risks</div>', unsafe_allow_html=True)
        render_enterprise_risk_cards(risks)
        render_open_tos_drilldown(context)
    with risk_cols[1]:
        st.markdown('<div class="gp-section-label">Window Mix</div>', unsafe_allow_html=True)
        window_counts = context.progress.get("Window Status", pd.Series(dtype=str)).value_counts().reset_index()
        window_counts.columns = ["Window Status", "Routes"]
        if window_counts.empty:
            st.caption("No window status data available.")
        else:
            fig = px.pie(
                window_counts,
                names="Window Status",
                values="Routes",
                hole=0.58,
                color="Window Status",
                color_discrete_map={
                    "Complete": "#2f6f4e",
                    "Upcoming": "#3c78a8",
                    "In Window": "#b7791f",
                    "Past Departure": "#b42318",
                    "No SDT Window": "#64748b",
                },
            )
            fig.update_layout(
                height=330,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#1f2937"),
                legend=dict(orientation="h", y=-0.08),
            )
            st.plotly_chart(fig, use_container_width=True)

    render_brief_panel("Copy-ready live briefing feed", make_live_update_note(context))


def render_executive_briefs_view(context: DailyHealthContext, health: HealthResult, ops_data: dict[str, pd.DataFrame]) -> None:
    brief = make_executive_daily_brief(context, health, ops_data)
    status = health.label
    if not context.progress.empty:
        status = str(summarize_daily_health_progress(context.progress)["status"])
    render_enterprise_module_header(
        "Executive Briefing Center",
        "DC1 Shipping Readiness Brief",
        "Leadership summary designed for the Google Sites Executive Briefs space.",
        status,
        f"Prepared {datetime.now().strftime('%m/%d/%Y %I:%M %p')}",
    )

    if context.progress.empty:
        st.info("Daily Executive Summary will populate after SDT Schedule and OB TO Tracker are connected or refreshed.")
    else:
        summary = summarize_daily_health_progress(context.progress)
        render_enterprise_kpi_grid(
            [
                {"label": "Shipping Health", "value": str(summary["status"]), "delta": "Executive status", "accent": str(summary["status"])},
                {"label": "Loaded", "value": format_percent(summary["completion"]), "delta": f"{format_number(summary['loaded'])} loaded TOs", "accent": "green" if float(summary["completion"]) >= 0.9 else "yellow"},
                {"label": "Open TOs", "value": format_number(summary["open_tos"]), "delta": "Carrier load progress", "accent": "yellow" if int(summary["open_tos"]) else "green"},
                {"label": "Pallet Exceptions", "value": format_number(int(summary["units_nyp"]) + int(summary["po_without_pallets"])), "delta": "Fill-rate readiness", "accent": "red" if int(summary["po_without_pallets"]) else "yellow" if int(summary["units_nyp"]) else "green"},
            ],
            columns=4,
        )

        render_outstanding_site_blocks(context)

        chart_cols = st.columns([1, 1])
        with chart_cols[0]:
            readiness_cols = [col for col in ["Carrier", "Progress %", "Open TOs", "Timing Risk", "Pallet Readiness Risk"] if col in context.progress.columns]
            st.markdown('<div class="gp-section-label">On-Time Shipping Readiness</div>', unsafe_allow_html=True)
            readiness_display = context.progress[readiness_cols]
            if "Open TOs" in readiness_display.columns:
                readiness_display = readiness_display.sort_values("Open TOs", ascending=False)
            readiness_display = readiness_display.head(12)
            if "Progress %" in readiness_cols:
                st.dataframe(
                    readiness_display,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Progress %": st.column_config.ProgressColumn("Progress %", format="%.0f%%", min_value=0, max_value=1)
                    },
                )
            else:
                st.dataframe(readiness_display, use_container_width=True, hide_index=True)
        with chart_cols[1]:
            st.markdown('<div class="gp-section-label">Pallet & Fill Rate Readiness</div>', unsafe_allow_html=True)
            pallet_cols = [col for col in ["Carrier", "Units_NYP", "PO_WO_Pallets", "Avg_Fill_Rate", "Pallet Readiness Risk"] if col in context.progress.columns]
            if pallet_cols:
                sort_cols = [col for col in ["Units_NYP", "PO_WO_Pallets"] if col in pallet_cols]
                pallet_display = context.progress[pallet_cols]
                if sort_cols:
                    pallet_display = pallet_display.sort_values(sort_cols, ascending=False)
                st.dataframe(
                    pallet_display.head(12),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.caption("Fill Rate source is not matched yet.")

    render_brief_panel("Copy-ready executive brief", brief)


def render_executive_summary_embed(context: DailyHealthContext, health: HealthResult, ops_data: dict[str, pd.DataFrame]) -> None:
    status = health.label
    if not context.progress.empty:
        status = str(summarize_daily_health_progress(context.progress)["status"])
    render_enterprise_module_header(
        "Executive Briefing Center",
        "DC1 Shipping Readiness Summary",
        "Compact leadership-ready status block for the Executive Briefs page.",
        status,
        f"Prepared {datetime.now().strftime('%m/%d/%Y %I:%M %p')}",
    )
    if context.progress.empty:
        st.info("Executive summary is waiting on SDT Schedule and OB TO Tracker data.")
        return
    summary = summarize_daily_health_progress(context.progress)
    render_enterprise_kpi_grid(
        [
            {"label": "Shipping Health", "value": str(summary["status"]), "delta": "Executive status", "accent": str(summary["status"])},
            {"label": "Loaded", "value": format_percent(summary["completion"]), "delta": f"{format_number(summary['loaded'])} loaded TOs", "accent": "green" if float(summary["completion"]) >= 0.9 else "yellow"},
            {"label": "Open TOs", "value": format_number(summary["open_tos"]), "delta": "Carrier load progress", "accent": "yellow" if int(summary["open_tos"]) else "green"},
            {"label": "Past Departure", "value": format_number(summary["past"]), "delta": "Routes beyond SDT", "accent": "red" if int(summary["past"]) else "green"},
        ],
        columns=4,
    )


def render_executive_watchlist_embed(context: DailyHealthContext) -> None:
    render_enterprise_module_header(
        "Executive Briefing Center",
        "Route Watchlist",
        "Focused view of carriers and SDT windows needing leadership attention.",
        str(summarize_daily_health_progress(context.progress)["status"]) if not context.progress.empty else "Waiting",
        f"OB tab {context.ob_sheet or 'not selected'}",
    )
    if context.progress.empty:
        st.info("Route watchlist is waiting on SDT Schedule and OB TO Tracker data.")
        return
    render_outstanding_site_blocks(context)
    risks = top_daily_health_risks(context.progress, 8)
    if not risks.empty:
        st.markdown('<div class="gp-section-label">Top Route Risks</div>', unsafe_allow_html=True)
        st.dataframe(risks, use_container_width=True, hide_index=True)


def render_executive_pallet_embed(context: DailyHealthContext) -> None:
    status = str(summarize_daily_health_progress(context.progress)["status"]) if not context.progress.empty else "Waiting"
    render_enterprise_module_header(
        "Executive Briefing Center",
        "Pallet Readiness",
        "Fill-rate and pallet exception view for routes not ready to load.",
        status,
        f"Prepared {datetime.now().strftime('%m/%d/%Y %I:%M %p')}",
    )
    if context.progress.empty:
        st.info("Pallet readiness is waiting on Fill Rate and OB Tracker data.")
        return
    pallet_cols = [col for col in ["Carrier", "Units_NYP", "PO_WO_Pallets", "Avg_Fill_Rate", "Pallet Readiness Risk", "Open TOs", "Timing Risk"] if col in context.progress.columns]
    if not pallet_cols:
        st.info("No pallet readiness columns are available yet.")
        return
    pallet_display = context.progress[pallet_cols].copy()
    sort_cols = [col for col in ["Units_NYP", "PO_WO_Pallets", "Open TOs"] if col in pallet_display.columns]
    if sort_cols:
        pallet_display = pallet_display.sort_values(sort_cols, ascending=False)
    if "Units_NYP" in pallet_display.columns and pd.to_numeric(pallet_display["Units_NYP"], errors="coerce").fillna(0).gt(0).any():
        chart = pallet_display.head(12).copy()
        fig = px.bar(
            chart,
            y="Carrier",
            x="Units_NYP",
            color="Pallet Readiness Risk" if "Pallet Readiness Risk" in chart.columns else None,
            orientation="h",
            color_discrete_map={"Normal": "#2f6f4e", "Units NYP": "#b7791f", "PO Without Pallets": "#b42318", "No Fill Rate Match": "#64748b"},
        )
        fig.update_layout(
            height=360,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(autorange="reversed"),
            font=dict(color="#1f2937"),
        )
        st.plotly_chart(fig, use_container_width=True)
    st.dataframe(pallet_display.head(25), use_container_width=True, hide_index=True)


def render_executive_note_embed(context: DailyHealthContext, health: HealthResult, ops_data: dict[str, pd.DataFrame]) -> None:
    render_enterprise_module_header(
        "Executive Briefing Center",
        "Copy-Ready Briefing Note",
        "One-block leadership note for the Executive Briefs page.",
        str(summarize_daily_health_progress(context.progress)["status"]) if not context.progress.empty else health.label,
        f"Prepared {datetime.now().strftime('%m/%d/%Y %I:%M %p')}",
    )
    render_brief_panel("Copy-ready executive brief", make_executive_daily_brief(context, health, ops_data))


def parse_google_sheet_id(value: str) -> str:
    text = value.strip()
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", text)
    if match:
        return match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", text):
        return text
    return ""


def google_credentials_ready() -> tuple[bool, str]:
    oauth_info = google_oauth_secret()
    if oauth_info:
        account = oauth_info.get("account") or "authorized Google user"
        return True, f"Google OAuth secrets are ready ({account})."
    secret_info = google_service_account_secret()
    if secret_info:
        email = secret_info.get("client_email", "service account")
        return True, f"Google service account secrets are ready ({email})."
    if not GOOGLE_CREDENTIALS_PATH.exists():
        return False, f"Missing {GOOGLE_CREDENTIALS_PATH} or Streamlit service account secrets."
    try:
        import google.auth.transport.requests  # noqa: F401
        from google.oauth2.credentials import Credentials  # noqa: F401
        from google.oauth2.service_account import Credentials as ServiceAccountCredentials  # noqa: F401
        from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: F401
        from googleapiclient.discovery import build  # noqa: F401
    except ImportError as exc:
        return False, f"Missing Google Python libraries. Run pip install -r requirements.txt. Detail: {exc}"
    return True, "Google credentials are ready."


def google_service_account_secret() -> dict[str, object] | None:
    try:
        for key in ("gcp_service_account", "google_service_account"):
            if key in st.secrets:
                secret = dict(st.secrets[key])
                private_key = secret.get("private_key")
                if isinstance(private_key, str):
                    secret["private_key"] = private_key.replace("\\n", "\n")
                return secret
    except Exception:
        return None
    return None


def google_oauth_secret() -> dict[str, object] | None:
    try:
        for key in ("google_oauth", "google_authorized_user"):
            if key in st.secrets:
                secret = dict(st.secrets[key])
                required = ("client_id", "client_secret", "refresh_token", "token_uri")
                if not all(secret.get(field) for field in required):
                    continue
                scopes = secret.get("scopes")
                if isinstance(scopes, str):
                    secret["scopes"] = [scope.strip() for scope in scopes.split(",") if scope.strip()]
                elif not scopes:
                    secret["scopes"] = GOOGLE_SCOPES
                return secret
    except Exception:
        return None
    return None


def get_google_services():
    ready, message = google_credentials_ready()
    if not ready:
        raise RuntimeError(message)

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google.oauth2.service_account import Credentials as ServiceAccountCredentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    oauth_info = google_oauth_secret()
    if oauth_info:
        creds = Credentials.from_authorized_user_info(oauth_info, GOOGLE_SCOPES)
        if not creds.valid:
            creds.refresh(Request())
        return (
            build("sheets", "v4", credentials=creds),
            build("drive", "v3", credentials=creds),
            build("driveactivity", "v2", credentials=creds),
        )

    service_account_info = google_service_account_secret()
    if service_account_info:
        creds = ServiceAccountCredentials.from_service_account_info(
            service_account_info,
            scopes=GOOGLE_SCOPES,
        )
        return (
            build("sheets", "v4", credentials=creds),
            build("drive", "v3", credentials=creds),
            build("driveactivity", "v2", credentials=creds),
        )

    creds = None
    if GOOGLE_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(GOOGLE_TOKEN_PATH), GOOGLE_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(GOOGLE_CREDENTIALS_PATH), GOOGLE_SCOPES)
            creds = flow.run_local_server(port=0)
        GOOGLE_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        GOOGLE_TOKEN_PATH.write_text(creds.to_json())

    return (
        build("sheets", "v4", credentials=creds),
        build("drive", "v3", credentials=creds),
        build("driveactivity", "v2", credentials=creds),
    )


def quote_google_sheet_range(sheet_name: str, range_suffix: str = "A:Z") -> str:
    escaped = sheet_name.replace("'", "''")
    return f"'{escaped}'!{range_suffix}"


def sheets_to_fetch_for_tag(tag: str, sheet_names: list[str]) -> tuple[list[str], str]:
    clean_names = [sheet for sheet in sheet_names if str(sheet).strip()]
    tag_key = str(tag or "").casefold()
    if not clean_names:
        return [], "no sheets found"

    if tag_key == "sdt schedule":
        preferred = next(
            (
                sheet
                for sheet in clean_names
                if sheet.casefold() in {"sheet1", "sdt"} or "sdt" in sheet.casefold()
            ),
            clean_names[0],
        )
        return [preferred], "SDT schedule primary tab"

    if tag_key == "ob to tracker":
        selected, target_day, reason = select_ob_tracker_sheet(clean_names)
        if selected:
            return [selected], f"OB tracker active tab for {target_day.strftime('%m/%d/%Y')} ({reason})"
        return [], "OB tracker tab not found"

    if tag_key == "fill rate":
        preferred_tokens = [
            "raw airtable pif",
            "last 7 days raw airtable pif",
            "daily dashboard",
            "daily pallet counts",
        ]
        selected = [
            sheet
            for sheet in clean_names
            if any(token in sheet.casefold() for token in preferred_tokens)
        ]
        return selected[:4] or clean_names[:1], "Fill Rate working tabs"

    if tag_key == "core-mark":
        selected = [sheet for sheet in clean_names if "tracker" in sheet.casefold()]
        return selected[:2] or clean_names[:1], "Core-Mark tracker tabs"

    if tag_key == "carrier mapping":
        preferred_tokens = [
            "outbound - final mile",
            "outbound - linehaul",
            "carrier market breakdown",
            "scbps",
            "addresses and rm",
        ]
        selected = [
            sheet
            for sheet in clean_names
            if any(token in sheet.casefold() for token in preferred_tokens)
        ]
        return selected[:8] or clean_names[:1], "Carrier mapping profile tabs"

    if tag_key == "allocation history":
        selected = [
            sheet
            for sheet in clean_names
            if any(token in sheet.casefold() for token in ["allocation", "dc1", "daily", "tracker"])
            or parse_date_sheet_name(str(sheet)) is not None
        ]
        return selected[-6:] or clean_names[-3:] or clean_names[:1], "Allocation history recent working tabs"

    if tag_key == "rfp cost":
        selected = [
            sheet
            for sheet in clean_names
            if any(token in sheet.casefold() for token in ["linehaul", "final mile", "inbound", "pricing", "rate", "cost"])
        ]
        return selected[:8] or clean_names[:2], "RFP lane and cost tabs"

    return clean_names[:1], "first sheet only"


def fetch_google_sheet_snapshot(spreadsheet_id: str, tag: str = "Other") -> dict[str, object]:
    sheets_service, drive_service, activity_service = get_google_services()
    spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    file_info = drive_service.files().get(
        fileId=spreadsheet_id,
        fields="id,name,modifiedTime,webViewLink,owners(displayName,emailAddress)",
    ).execute()
    try:
        permissions = drive_service.permissions().list(
            fileId=spreadsheet_id,
            fields="permissions(id,type,emailAddress,displayName,role)",
        ).execute().get("permissions", [])
    except Exception:
        permissions = []
    try:
        activity = activity_service.activity().query(
            body={"itemName": f"items/{spreadsheet_id}", "pageSize": 10}
        ).execute().get("activities", [])
    except Exception:
        activity = []

    sheet_props = []
    for sheet in spreadsheet.get("sheets", []):
        props = sheet.get("properties", {})
        sheet_props.append(
            {
                "sheet_name": props.get("title", ""),
                "grid": props.get("gridProperties", {}),
            }
        )

    selected_sheets, fetch_reason = sheets_to_fetch_for_tag(tag, [sheet["sheet_name"] for sheet in sheet_props])
    values_by_sheet = {}
    if selected_sheets:
        ranges = [quote_google_sheet_range(sheet_name) for sheet_name in selected_sheets]
        batch = sheets_service.spreadsheets().values().batchGet(
            spreadsheetId=spreadsheet_id,
            ranges=ranges,
            valueRenderOption="FORMATTED_VALUE",
            dateTimeRenderOption="FORMATTED_STRING",
        ).execute()
        for sheet_name, value_range in zip(selected_sheets, batch.get("valueRanges", [])):
            values_by_sheet[sheet_name] = value_range.get("values", [])

    metadata_sheets = []
    for sheet in sheet_props:
        sheet_name = sheet["sheet_name"]
        grid = sheet["grid"]
        values = values_by_sheet.get(sheet_name, [])
        headers = values[0] if values else []
        values_by_sheet[sheet_name] = values
        metadata_sheets.append(
            {
                "sheet_name": sheet_name,
                "row_count": len(values),
                "column_count": max([len(row) for row in values], default=0),
                "grid_rows": grid.get("rowCount", 0),
                "grid_columns": grid.get("columnCount", 0),
                "columns": [str(col) for col in headers],
                "values_fetched": sheet_name in selected_sheets,
            }
        )

    return {
        "spreadsheet_id": spreadsheet_id,
        "name": file_info.get("name", spreadsheet.get("properties", {}).get("title", "Google Sheet")),
        "source_url": file_info.get("webViewLink", f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"),
        "last_modified_time": file_info.get("modifiedTime", ""),
        "owners": file_info.get("owners", []),
        "permissions": permissions,
        "activity": activity,
        "metadata": {"sheets": metadata_sheets, "fetch_reason": fetch_reason, "fetched_sheets": selected_sheets},
        "values": values_by_sheet,
    }


def save_google_sheet_connection(source_url: str, tag: str, notes: str) -> None:
    spreadsheet_id = parse_google_sheet_id(source_url)
    if not spreadsheet_id:
        raise ValueError("Paste a valid Google Sheets URL or spreadsheet ID.")
    snapshot = fetch_google_sheet_snapshot(spreadsheet_id, tag)
    now = now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO google_sheet_connections (
                spreadsheet_id,
                name,
                source_url,
                tag,
                notes,
                created_at,
                last_synced_at,
                last_modified_time,
                metadata_json,
                values_json,
                permissions_json,
                activity_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(spreadsheet_id) DO UPDATE SET
                name = excluded.name,
                source_url = excluded.source_url,
                tag = excluded.tag,
                notes = excluded.notes,
                last_synced_at = excluded.last_synced_at,
                last_modified_time = excluded.last_modified_time,
                metadata_json = excluded.metadata_json,
                values_json = excluded.values_json,
                permissions_json = excluded.permissions_json,
                activity_json = excluded.activity_json
            """,
            (
                snapshot["spreadsheet_id"],
                snapshot["name"],
                snapshot["source_url"],
                tag,
                notes,
                now,
                now,
                snapshot["last_modified_time"],
                json.dumps(snapshot["metadata"]),
                json.dumps(snapshot["values"]),
                json.dumps(snapshot["permissions"]),
                json.dumps(snapshot["activity"]),
            ),
        )


def list_google_sheet_connections() -> pd.DataFrame:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            """
            SELECT
                id,
                spreadsheet_id,
                name,
                source_url,
                tag,
                notes,
                created_at,
                last_synced_at,
                last_modified_time,
                metadata_json,
                values_json,
                permissions_json,
                activity_json
            FROM google_sheet_connections
            ORDER BY datetime(last_synced_at) DESC, id DESC
            """,
            conn,
        )


def refresh_google_sheet_types(workbook_types: list[str]) -> list[str]:
    messages = []
    for workbook_type in workbook_types:
        connection = latest_google_sheet_by_type(workbook_type)
        if connection is None:
            messages.append(f"{workbook_type}: no connected Google Sheet found")
            continue
        save_google_sheet_connection(
            str(connection["source_url"]),
            str(connection["tag"]),
            str(connection["notes"]),
        )
        refreshed = latest_google_sheet_by_type(workbook_type)
        synced_at = str(refreshed["last_synced_at"]) if refreshed is not None else now_iso()
        messages.append(f"{workbook_type}: refreshed at {synced_at}")
    return messages


def refresh_google_sheet_connections(connections: pd.DataFrame | None = None) -> list[str]:
    active_connections = list_google_sheet_connections() if connections is None else connections
    if active_connections.empty:
        return ["No connected Google Sheets found"]

    messages = []
    for _, connection in active_connections.iterrows():
        name = str(connection.get("name", "Google Sheet"))
        try:
            save_google_sheet_connection(
                str(connection["source_url"]),
                str(connection["tag"]),
                str(connection["notes"]),
            )
            refreshed = latest_google_sheet_by_type(str(connection["tag"]))
            synced_at = str(refreshed["last_synced_at"]) if refreshed is not None else now_iso()
            messages.append(f"{name}: refreshed at {synced_at}")
        except Exception as exc:
            messages.append(f"{name}: refresh failed - {exc}")
    return messages


def google_sheet_seed_secrets() -> list[dict[str, str]]:
    try:
        configured = st.secrets.get("google_sheets", [])
    except Exception:
        return []
    if isinstance(configured, dict):
        configured = [configured]
    seeds = []
    for row in configured:
        row_dict = dict(row)
        source_url = str(row_dict.get("source_url", "")).strip()
        tag = str(row_dict.get("tag", "")).strip()
        if source_url and tag:
            seeds.append(
                {
                    "source_url": source_url,
                    "tag": tag,
                    "notes": str(row_dict.get("notes", "")).strip(),
                }
            )
    return seeds


def seed_google_sheet_connections_from_secrets() -> list[str]:
    seeds = google_sheet_seed_secrets()
    if not seeds:
        return []

    existing = list_google_sheet_connections()
    existing_ids = set(existing["spreadsheet_id"].astype(str).tolist()) if not existing.empty else set()
    messages = []
    for seed in seeds:
        spreadsheet_id = parse_google_sheet_id(seed["source_url"])
        if not spreadsheet_id:
            messages.append(f"{seed['tag']}: invalid Google Sheet URL in secrets")
            continue
        if spreadsheet_id in existing_ids:
            continue
        try:
            save_google_sheet_connection(seed["source_url"], seed["tag"], seed["notes"])
            existing_ids.add(spreadsheet_id)
            messages.append(f"{seed['tag']}: seeded from Streamlit secrets")
        except Exception as exc:
            messages.append(f"{seed['tag']}: seed failed - {exc}")
    return messages


def scheduled_google_refresh_slot(now: datetime | None = None) -> tuple[str, datetime] | None:
    current = now or datetime.now()
    due_hours = [hour for hour in GOOGLE_REFRESH_SCHEDULE_HOURS if current.hour >= hour]
    if not due_hours:
        return None
    slot_hour = max(due_hours)
    scheduled_at = current.replace(hour=slot_hour, minute=0, second=0, microsecond=0)
    return f"{scheduled_at:%Y-%m-%d-%H}", scheduled_at


def google_refresh_slot_has_run(slot_key: str) -> bool:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT 1 FROM google_sheet_refresh_runs WHERE slot_key = ?",
            (slot_key,),
        ).fetchone()
    return row is not None


def record_google_refresh_run(slot_key: str, scheduled_at: datetime, status: str, messages: list[str]) -> None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO google_sheet_refresh_runs (
                slot_key,
                scheduled_at,
                ran_at,
                status,
                message_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                slot_key,
                scheduled_at.isoformat(timespec="seconds"),
                now_iso(),
                status,
                json.dumps(messages),
            ),
        )


def list_google_refresh_runs(limit: int = 10) -> pd.DataFrame:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            """
            SELECT slot_key, scheduled_at, ran_at, status, message_json
            FROM google_sheet_refresh_runs
            ORDER BY datetime(scheduled_at) DESC
            LIMIT ?
            """,
            conn,
            params=(limit,),
        )


def run_scheduled_google_refresh_if_due() -> list[str]:
    slot = scheduled_google_refresh_slot()
    if slot is None:
        return []
    slot_key, scheduled_at = slot
    if google_refresh_slot_has_run(slot_key):
        return []

    try:
        messages = refresh_google_sheet_connections()
        status = "success" if not any("failed" in message.casefold() for message in messages) else "partial"
    except Exception as exc:
        messages = [f"Scheduled Google Sheet refresh failed - {exc}"]
        status = "failed"
    record_google_refresh_run(slot_key, scheduled_at, status, messages)
    return messages


def install_google_refresh_timer() -> None:
    delay_ms = AUTO_REFRESH_CHECK_MINUTES * 60 * 1000
    components.html(
        f"""
        <script>
          window.setTimeout(function() {{
            try {{
              window.parent.location.reload();
            }} catch (error) {{
              window.location.reload();
            }}
          }}, {delay_ms});
        </script>
        """,
        height=0,
    )


def update_google_sheet_connection_rows(rows: list[dict[str, object]]) -> None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        for row in rows:
            conn.execute(
                "UPDATE google_sheet_connections SET tag = ?, notes = ? WHERE id = ?",
                (str(row.get("tag", "Other")), str(row.get("notes", "")), int(row["id"])),
            )


def save_ship_allocation_batch(
    batch_name: str,
    records: pd.DataFrame,
    export: pd.DataFrame,
    source_groups: list[str],
    file_blob: bytes,
    notes: str = "",
) -> None:
    init_db()
    source_files = (
        records["source_file"].dropna().astype(str).drop_duplicates().sort_values().tolist()
        if "source_file" in records.columns and not records.empty
        else []
    )
    ready_count = int(records["ship_status"].eq("Ready").sum()) if "ship_status" in records.columns else len(export)
    issue_count = int(records["ship_status"].ne("Ready").sum()) if "ship_status" in records.columns else 0
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO ship_allocation_batches (
                batch_name,
                created_at,
                source_files,
                source_groups,
                row_count,
                ready_count,
                issue_count,
                notes,
                records_json,
                export_json,
                file_blob
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch_name,
                now_iso(),
                json.dumps(source_files),
                json.dumps(source_groups),
                len(records),
                ready_count,
                issue_count,
                notes,
                df_to_json(records),
                df_to_json(export),
                file_blob,
            ),
        )


def list_ship_allocation_batches() -> pd.DataFrame:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            """
            SELECT
                id,
                batch_name,
                created_at,
                source_files,
                source_groups,
                row_count,
                ready_count,
                issue_count,
                notes
            FROM ship_allocation_batches
            ORDER BY id DESC
            """,
            conn,
        )


def load_ship_allocation_batch(batch_id: int) -> tuple[str, bytes] | None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT batch_name, file_blob FROM ship_allocation_batches WHERE id = ?",
            (batch_id,),
        ).fetchone()
    if row is None:
        return None
    return row[0], row[1]


def load_saved_ship_allocation_records() -> pd.DataFrame:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT batch_name, created_at, records_json
            FROM ship_allocation_batches
            ORDER BY datetime(created_at) DESC, id DESC
            """
        ).fetchall()
    frames: list[pd.DataFrame] = []
    for batch_name, created_at, records_json in rows:
        records = df_from_json(records_json)
        if records.empty:
            continue
        records["batch_name"] = batch_name
        records["batch_created_at"] = created_at
        records["record_scope"] = "Saved History"
        frames.append(records)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    for col in ["pick_date", "ship_date", "delivery_date", "batch_created_at"]:
        if col in combined.columns:
            combined[col] = pd.to_datetime(combined[col], errors="coerce")
    return combined


def load_allocation(file: BytesIO) -> tuple[pd.DataFrame, pd.DataFrame]:
    carrier_summary = pd.read_excel(file, sheet_name="Carrier Summary")
    file.seek(0)
    site_summary = pd.read_excel(file, sheet_name="Site Summary")

    carrier_summary = clean_columns(carrier_summary)
    site_summary = clean_columns(site_summary)
    return carrier_summary, site_summary


def load_tender_pipeline(files: list[BytesIO]) -> dict[str, pd.DataFrame]:
    frames: list[pd.DataFrame] = []

    for file in files:
        file.seek(0)
        source_name = getattr(file, "name", "Uploaded Tender File")
        if source_name.lower().endswith(".csv"):
            workbook = {"CSV Upload": pd.read_csv(file)}
        else:
            workbook = pd.read_excel(file, sheet_name=None)
        for sheet_name, raw in workbook.items():
            normalized = normalize_tender_sheet(raw, source_name, sheet_name)
            if not normalized.empty:
                frames.append(normalized)

    if not frames:
        empty = pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS)
        return {
            "records": empty,
            "ready": empty,
            "issues": empty,
            "duplicates": empty,
            "conflicts": empty,
            "export": pd.DataFrame(columns=TENDER_EXPORT_COLUMNS),
        }

    records = pd.concat(frames, ignore_index=True)
    records = classify_tender_records(records)
    ready = records[records["validation_status"].eq("Ready")].copy()
    issues = records[records["validation_status"].ne("Ready")].copy()
    duplicates = records[records["validation_status"].eq("Duplicate")].copy()
    conflicts = records[records["validation_status"].eq("Conflict")].copy()
    export = build_uber_freight_export(ready)

    return {
        "records": records,
        "ready": ready,
        "issues": issues,
        "duplicates": duplicates,
        "conflicts": conflicts,
        "export": export,
    }


def load_ship_allocation_records(files: list[BytesIO]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    for file in files:
        file.seek(0)
        source_name = getattr(file, "name", "Uploaded Allocation File")
        if source_name.lower().endswith(".csv"):
            workbook = {"CSV Upload": pd.read_csv(file)}
        else:
            workbook = pd.read_excel(file, sheet_name=None)

        for sheet_name, raw in workbook.items():
            normalized = normalize_tender_sheet(raw, source_name, sheet_name)
            if normalized.empty:
                continue
            normalized["source_group"] = infer_ship_allocation_source(source_name, sheet_name)
            frames.append(normalized)

    if not frames:
        return pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS + ["source_group"])

    return pd.concat(frames, ignore_index=True).reset_index(drop=True)


def infer_ship_allocation_source(source_name: str, sheet_name: str) -> str:
    text = f"{source_name} {sheet_name}".lower()
    if "dc1" in text:
        return "DC1"
    if "dc2" in text:
        return "DC2"
    if "alc" in text or "alcohol" in text:
        return "ALC"
    if "inbound" in text:
        return "Inbound"
    if "coremark" in text or "core mark" in text:
        return "CoreMark"
    if "southern" in text:
        return "Southern G"
    return "Unknown"


def infer_default_scac(carrier: object) -> str:
    text = str(carrier).upper()
    if "MISFIT" in text:
        return "IMQF"
    if "GOFLEET" in text:
        return "GOB2"
    if "WARP" in text or "TAZMANIAN" in text:
        return "WTCH"
    if "GOPUFF" in text or "GOB" in text:
        return "GOB2"
    return ""


def infer_default_origin_external_id(carrier: object) -> str:
    text = str(carrier).upper().replace("_", " ")
    if "GOFLEET" in text:
        return "1179"
    if "MISFIT" in text:
        tokens = [token for token in re.split(r"[^A-Z0-9]+", text) if token]
        market = tokens[-1] if tokens else ""
        if market == "BWI":
            return "MISFITS DCA-BWI"
        if market:
            return f"MISFITS {market}"
    if "WARP" in text or "TAZMANIAN" in text:
        tokens = [token for token in re.split(r"[^A-Z0-9]+", text) if token]
        for market in ["LAX", "SAN", "MIA", "DEN"]:
            if market in tokens:
                return f"WARP {market}"
    return ""


def rebuild_tender_pipeline(records: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if records.empty:
        empty = pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS)
        return {
            "records": empty,
            "ready": empty,
            "issues": empty,
            "duplicates": empty,
            "conflicts": empty,
            "export": pd.DataFrame(columns=TENDER_EXPORT_COLUMNS),
        }

    classified = classify_tender_records(records)
    ready = classified[classified["validation_status"].eq("Ready")].copy()
    issues = classified[classified["validation_status"].ne("Ready")].copy()
    duplicates = classified[classified["validation_status"].eq("Duplicate")].copy()
    conflicts = classified[classified["validation_status"].eq("Conflict")].copy()
    export = build_uber_freight_export(ready)
    return {
        "records": classified,
        "ready": ready,
        "issues": issues,
        "duplicates": duplicates,
        "conflicts": conflicts,
        "export": export,
    }


def apply_tender_mapping(
    records: pd.DataFrame,
    default_origin_external_id: str,
    carrier_vendor_map: pd.DataFrame,
) -> pd.DataFrame:
    mapped = records.copy()
    if mapped.empty:
        return mapped

    if default_origin_external_id:
        missing_origin = mapped["origin_external_id"].astype(str).str.strip().eq("")
        mapped.loc[missing_origin, "origin_external_id"] = default_origin_external_id.strip()

    if not carrier_vendor_map.empty and {"carrier", "vendor_external_id"}.issubset(carrier_vendor_map.columns):
        vendor_lookup = {
            str(row["carrier"]).strip(): str(row["vendor_external_id"]).strip()
            for _, row in carrier_vendor_map.iterrows()
            if str(row.get("vendor_external_id", "")).strip()
        }
        missing_vendor = mapped["vendor_external_id"].astype(str).str.strip().eq("")
        mapped.loc[missing_vendor, "vendor_external_id"] = mapped.loc[missing_vendor, "carrier"].map(vendor_lookup).fillna("")

    mapped["row_fingerprint"] = mapped.apply(build_tender_fingerprint, axis=1)
    return mapped


def normalize_tender_sheet(raw: pd.DataFrame, source_name: str, sheet_name: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()

    df = clean_columns(raw)
    df = df.dropna(how="all")
    if df.empty:
        return pd.DataFrame()

    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    normalized_columns = {col: normalize_header(col) for col in df.columns}
    df = df.rename(columns=normalized_columns)

    if not has_any_column(df, ["to_number", "primary_reference", "material_transfer_order_number"]):
        return pd.DataFrame()

    result = pd.DataFrame()
    result["source_file"] = source_name
    result["source_sheet"] = sheet_name
    result["carrier"] = get_first_available(df, ["carrier"])
    result["to_number"] = get_first_available(
        df,
        ["to_number", "primary_reference", "po_number", "material_transfer_order_number"],
    )
    result["primary_reference"] = get_first_available(df, ["primary_reference", "to_number"])
    result["po_number"] = get_first_available(df, ["po_number", "to_number"])
    result["material_transfer_order_number"] = get_first_available(
        df,
        ["material_transfer_order_number", "to_number"],
    )
    result["business_unit"] = get_first_available(df, ["business_unit_type", "gopuff_bevmo", "gopuff_bevmo_"])
    result["location_name"] = get_first_available(df, ["location", "gopuff_site_location", "location_name"])
    result["site_id"] = get_first_available(df, ["site_id", "location_id", "destination_external_id"])
    result["units"] = get_numeric_series(df, ["units", "quantity"])
    result["lines"] = get_numeric_series(df, ["lines"])
    result["pick_date"] = get_first_available(df, ["pick_date", "planned_pick_date"])
    result["ship_date"] = get_first_available(df, ["ship_date", "planned_ship_date"])
    result["delivery_date"] = get_first_available(df, ["delivery_date"])
    result["pallets"] = get_numeric_series(df, ["pallets_final", "pallets"])
    result["water_weight"] = get_numeric_series(df, ["water_weight", "water_24pck_of_pallets"])
    result["non_water_weight"] = get_numeric_series(df, ["non_water_weight", "non_water_weight_"])
    result["total_weight"] = get_numeric_series(df, ["total_weight"])
    result["vendor_external_id"] = clean_text_series(get_first_available(df, ["vendor_external_id"]))
    result["origin_external_id"] = clean_text_series(get_first_available(df, ["origin_external_id"]))
    result["destination_external_id"] = clean_text_series(
        get_first_available(df, ["destination_external_id", "site_id", "location_id"])
    )
    result["action"] = clean_text_series(get_first_available(df, ["action"])).replace("", "ADD")

    result["to_number"] = clean_text_series(result["to_number"])
    result["carrier"] = clean_text_series(result["carrier"])
    result["business_unit"] = clean_text_series(result["business_unit"]).str.upper()
    result["location_name"] = clean_text_series(result["location_name"])
    result["site_id"] = clean_text_series(result["site_id"])
    result["primary_reference"] = clean_text_series(result["primary_reference"])
    result["po_number"] = clean_text_series(result["po_number"])
    result["material_transfer_order_number"] = clean_text_series(result["material_transfer_order_number"])

    for col in ["pick_date", "ship_date", "delivery_date"]:
        result[col] = pd.to_datetime(result[col], errors="coerce")

    result["total_weight"] = result["total_weight"].fillna(
        result["water_weight"].fillna(0) + result["non_water_weight"].fillna(0)
    )
    result["row_fingerprint"] = result.apply(build_tender_fingerprint, axis=1)
    result = result[result["to_number"].str.strip().ne("")]
    result["source_file"] = source_name
    result["source_sheet"] = sheet_name
    return result.reset_index(drop=True)


def normalize_header(value: object) -> str:
    text = str(value).strip().lower()
    text = text.replace("#", "number")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    replacements = {
        "to_number": "to_number",
        "to": "to_number",
        "gopuff_site_location": "gopuff_site_location",
        "gopuff_bevmo": "gopuff_bevmo",
        "gopuff_bevmo_": "gopuff_bevmo",
        "pallets_final": "pallets_final",
        "water_24pck_number_of_pallets": "water_24pck_of_pallets",
        "pickup_earliest_datetime": "pickup_earliest_datetime",
        "pickup_latest_datetime": "pickup_latest_datetime",
        "delivery_earliest_datetime": "delivery_earliest_datetime",
        "delivery_latest_datetime": "delivery_latest_datetime",
        "business_unit_type": "business_unit_type",
        "primary_reference": "primary_reference",
        "po_number": "po_number",
        "material_transfer_order_number": "material_transfer_order_number",
    }
    return replacements.get(text, text)


def has_any_column(df: pd.DataFrame, columns: list[str]) -> bool:
    return any(col in df.columns for col in columns)


def get_first_available(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    for col in columns:
        if col in df.columns:
            value = df[col]
            if isinstance(value, pd.DataFrame):
                return value.iloc[:, 0]
            return value
    return pd.Series([pd.NA] * len(df), index=df.index)


def get_numeric_series(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    return pd.to_numeric(get_first_available(df, columns), errors="coerce")


def clean_text_series(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().replace({"nan": "", "NaT": "", "#N/A": ""})


def build_tender_fingerprint(row: pd.Series) -> str:
    fields = [
        "to_number",
        "carrier",
        "site_id",
        "ship_date",
        "delivery_date",
        "pallets",
        "total_weight",
        "vendor_external_id",
        "origin_external_id",
        "destination_external_id",
    ]
    return "|".join(str(row.get(field, "") or "") for field in fields)


def classify_tender_records(records: pd.DataFrame) -> pd.DataFrame:
    classified = records.copy()
    issue_lists = classified.apply(validate_tender_row, axis=1)
    classified["validation_issues"] = issue_lists.apply(lambda issues: "; ".join(issues))
    classified["validation_status"] = issue_lists.apply(lambda issues: "Ready" if not issues else "Needs Review")

    duplicate_mask = classified.duplicated(subset=["to_number", "row_fingerprint"], keep="first")
    classified.loc[duplicate_mask, "validation_status"] = "Duplicate"
    classified.loc[duplicate_mask, "validation_issues"] = "Duplicate row ignored; identical TO and key fields already loaded."

    conflicting_to = (
        classified.groupby("to_number")["row_fingerprint"]
        .nunique(dropna=True)
        .loc[lambda values: values > 1]
        .index
    )
    conflict_mask = classified["to_number"].isin(conflicting_to) & ~duplicate_mask
    classified.loc[conflict_mask, "validation_status"] = "Conflict"
    classified.loc[conflict_mask, "validation_issues"] = (
        "Conflicting update; same TO appears with different key fields."
    )

    return classified


def validate_tender_row(row: pd.Series) -> list[str]:
    issues: list[str] = []
    required = {
        "to_number": "Missing TO / primary reference",
        "site_id": "Missing destination/site ID",
        "ship_date": "Missing ship/pickup date",
        "delivery_date": "Missing delivery date",
        "pallets": "Missing pallets",
        "total_weight": "Missing total weight",
    }
    for field, message in required.items():
        value = row.get(field)
        if pd.isna(value) or str(value).strip() == "" or str(value).strip().upper() == "#N/A":
            issues.append(message)

    if not row.get("origin_external_id"):
        issues.append("Missing origin external ID")
    if not row.get("vendor_external_id"):
        issues.append("Missing vendor external ID")
    if pd.notna(row.get("pallets")) and float(row.get("pallets") or 0) <= 0:
        issues.append("Pallet count is zero")
    if pd.notna(row.get("total_weight")) and float(row.get("total_weight") or 0) <= 0:
        issues.append("Total weight is zero")
    return issues


def build_uber_freight_export(records: pd.DataFrame) -> pd.DataFrame:
    if records.empty:
        return pd.DataFrame(columns=TENDER_EXPORT_COLUMNS)

    export = pd.DataFrame()
    export["ACTION"] = records["action"].replace("", "ADD")
    export["PRIMARY_REFERENCE"] = records["primary_reference"]
    export["PO NUMBER"] = records["po_number"]
    export["MATERIAL TRANSFER ORDER NUMBER"] = records["material_transfer_order_number"]
    export["BUSINESS_UNIT_TYPE"] = records["business_unit"].replace("", "GOPUFF")
    export["PICKUP_EARLIEST_DATETIME"] = records["ship_date"].dt.strftime("%m/%d/%Y")
    export["PICKUP_LATEST_DATETIME"] = records["ship_date"].dt.strftime("%m/%d/%Y")
    export["DELIVERY_EARLIEST_DATETIME"] = records["delivery_date"].dt.strftime("%m/%d/%Y")
    export["DELIVERY_LATEST_DATETIME"] = records["delivery_date"].dt.strftime("%m/%d/%Y")
    export["VENDOR_EXTERNAL_ID"] = records["vendor_external_id"]
    export["ORIGIN_EXTERNAL_ID"] = records["origin_external_id"]
    export["DESTINATION_EXTERNAL_ID"] = records["destination_external_id"]
    export["CUSTOMER_LINE_ITEM_ID"] = 1
    export["QUANTITY"] = records["units"].fillna(0).round(0).astype(int)
    export["LINES"] = records["lines"].fillna(0).round(0).astype(int)
    export["PALLETS"] = records["pallets"].fillna(0).round(0).astype(int)
    export["WATER_WEIGHT"] = records["water_weight"].fillna(0).round(0).astype(int)
    export["NON_WATER_WEIGHT"] = records["non_water_weight"].fillna(0).round(0).astype(int)
    export["TOTAL_WEIGHT"] = records["total_weight"].fillna(0).round(0).astype(int)
    return export[TENDER_EXPORT_COLUMNS]


def apply_ship_allocation_mapping(
    records: pd.DataFrame,
    carrier_map: pd.DataFrame,
    default_origin_external_id: str,
    default_equipment_type: str,
    default_mode_type: str,
    default_order_type: str,
) -> pd.DataFrame:
    mapped = records.copy()
    if mapped.empty:
        return mapped

    mapped["origin_external_id"] = clean_text_series(mapped.get("origin_external_id", pd.Series(index=mapped.index)))
    if default_origin_external_id:
        missing_origin = mapped["origin_external_id"].str.strip().eq("")
        mapped.loc[missing_origin, "origin_external_id"] = default_origin_external_id.strip()

    mapped["equipment_type"] = default_equipment_type
    mapped["mode_type"] = default_mode_type
    mapped["order_type"] = default_order_type
    mapped["scac"] = ""

    if not carrier_map.empty and "carrier" in carrier_map.columns:
        for optional_col in ["origin_external_id", "scac", "equipment_type", "mode_type", "order_type"]:
            if optional_col not in carrier_map.columns:
                carrier_map[optional_col] = ""
        lookup = {
            str(row["carrier"]).strip(): row
            for _, row in carrier_map.iterrows()
            if str(row.get("carrier", "")).strip()
        }
        for idx, row in mapped.iterrows():
            carrier = str(row.get("carrier", "")).strip()
            if carrier not in lookup:
                continue
            map_row = lookup[carrier]
            for field in ["origin_external_id", "scac", "equipment_type", "mode_type", "order_type"]:
                value = str(map_row.get(field, "")).strip()
                if value:
                    mapped.at[idx, field] = value

    mapped["water_pallets"] = (mapped["water_weight"].fillna(0) / 2400).round(0).astype(int)
    mapped["handling_unit"] = mapped["pallets"].fillna(0).round(0).astype(int)
    return classify_ship_allocation_records(mapped)


def classify_ship_allocation_records(records: pd.DataFrame) -> pd.DataFrame:
    classified = records.copy()
    issue_lists = classified.apply(validate_ship_allocation_row, axis=1)
    classified["ship_issues"] = issue_lists.apply(lambda issues: "; ".join(issues))
    classified["ship_status"] = issue_lists.apply(lambda issues: "Ready" if not issues else "Needs Review")

    duplicate_mask = classified.duplicated(subset=["to_number", "row_fingerprint"], keep="first")
    classified.loc[duplicate_mask, "ship_status"] = "Duplicate"
    classified.loc[duplicate_mask, "ship_issues"] = "Duplicate row ignored; identical TO and key fields already loaded."

    conflicting_to = (
        classified.groupby("to_number")["row_fingerprint"]
        .nunique(dropna=True)
        .loc[lambda values: values > 1]
        .index
    )
    conflict_mask = classified["to_number"].isin(conflicting_to) & ~duplicate_mask
    classified.loc[conflict_mask, "ship_status"] = "Conflict"
    classified.loc[conflict_mask, "ship_issues"] = "Conflicting update; same TO appears with different key fields."
    return classified


def validate_ship_allocation_row(row: pd.Series) -> list[str]:
    issues: list[str] = []
    required = {
        "to_number": "Missing TO / primary reference",
        "site_id": "Missing destination/site ID",
        "ship_date": "Missing pickup/ship date",
        "delivery_date": "Missing delivery date",
        "units": "Missing quantity/units",
        "lines": "Missing lines",
        "pallets": "Missing pallets",
        "total_weight": "Missing weight",
        "origin_external_id": "Missing origin external ID",
        "scac": "Missing SCAC",
    }
    for field, message in required.items():
        value = row.get(field)
        if pd.isna(value) or str(value).strip() == "" or str(value).strip().upper() == "#N/A":
            issues.append(message)
    if pd.notna(row.get("pallets")) and float(row.get("pallets") or 0) <= 0:
        issues.append("Pallet count is zero")
    if pd.notna(row.get("total_weight")) and float(row.get("total_weight") or 0) <= 0:
        issues.append("Weight is zero")
    return issues


def build_ship_bulk_upload_export(records: pd.DataFrame) -> pd.DataFrame:
    ready = records[records["ship_status"].eq("Ready")].copy()
    if ready.empty:
        return pd.DataFrame(columns=SHIP_BULK_UPLOAD_COLUMNS)

    export = pd.DataFrame()
    export["ACTION"] = ready["action"].replace("", "ADD")
    export["PRIMARY REFERENCE"] = ready["primary_reference"]
    export["PO NUMBER"] = ready["po_number"]
    export["MATERIAL TRANSFER ORDER NUMBER"] = ready["material_transfer_order_number"]
    export["BUSINESS_UNIT_TYPE"] = ready["business_unit"].replace("", "GOPUFF")
    export["PICKUP_EARLIEST_DATETIME"] = ready["ship_date"].dt.strftime("%Y-%m-%d")
    export["PICKUP_LATEST_DATETIME"] = ready["ship_date"].dt.strftime("%Y-%m-%d")
    export["DELIVERY_EARLIEST_DATETIME"] = ready["delivery_date"].dt.strftime("%Y-%m-%d")
    export["DELIVERY_LATEST_DATETIME"] = ready["delivery_date"].dt.strftime("%Y-%m-%d")
    export["VENDOR_EXTERNAL_ID"] = ready["vendor_external_id"]
    export["ORIGIN_EXTERNAL_ID"] = ready["origin_external_id"]
    export["DESTINATION_EXTERNAL_ID"] = ready["destination_external_id"]
    export["CUSTOMER_LINE_ITEM_ID"] = 1
    export["QUANTITY"] = ready["units"].fillna(0).round(0).astype(int)
    export["QUANTITY_UOM"] = "CA"
    export["LINES"] = ready["lines"].fillna(0).round(0).astype(int)
    export["WEIGHT"] = ready["total_weight"].fillna(0).round(0).astype(int)
    export["WEIGHT_UOM"] = "LBS"
    export["WATER_WEIGHT"] = ready["water_weight"].fillna(0).round(0).astype(int)
    export["EQUIPMENT_TYPE"] = ready["equipment_type"].replace("", "26 FT DRYVAN")
    export["SCAC"] = ready["scac"]
    export["MODE_TYPE"] = ready["mode_type"].replace("", "LTL")
    export["ORDER_TYPE"] = ready["order_type"].replace("", "TRANSFER")
    export["HANDLING_UNIT"] = ready["handling_unit"].fillna(0).round(0).astype(int)
    export["HANDLING_UNIT_UOM"] = "PLT"
    export["WATER_PALLETS"] = ready["water_pallets"].fillna(0).round(0).astype(int)
    export["LTL_CLASS"] = ""
    export["TOP_OPERATIONAL_COMMENTS"] = ""
    export["TOP_CARRIER_COMMENTS"] = ""
    return export[SHIP_BULK_UPLOAD_COLUMNS]


def dataframe_download_payload(df: pd.DataFrame, file_format: str, sheet_name: str) -> tuple[bytes, str]:
    if file_format == "XLSX":
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
        return output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    return df.to_csv(index=False).encode("utf-8"), "text/csv"


def export_filename(prefix: str, file_format: str) -> str:
    extension = "xlsx" if file_format == "XLSX" else "csv"
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M')}.{extension}"


def classify_carrier_signal(message: str, selected_carrier: str, selected_channel: str) -> dict[str, str | int]:
    text = message.strip()
    lowered = text.lower()
    to_matches = re.findall(r"\b(?:GUSTO|BEVTO)-\d+\b", text, flags=re.IGNORECASE)
    site_matches = re.findall(r"\b(?:site\s*)?(\d{2,5})\b", lowered)

    signal_type = "General Update"
    urgency = "Low"
    suggested_action = "Review message and determine whether it affects the tender or delivery plan."

    keyword_rules = [
        (
            "Receiving Constraint",
            ["cannot take", "can't take", "no space", "space", "store", "hold"],
            "Confirm receiving capacity with Ops and decide whether to hold, reschedule, or split the impacted freight.",
            "High",
        ),
        (
            "Water / Pallet Issue",
            ["water pallet", "water", "pallet"],
            "Check allocation row for water pallets and confirm whether the site can receive or needs an alternate plan.",
            "Medium",
        ),
        (
            "Reschedule Request",
            ["monday", "tomorrow", "reschedule", "push", "deliver later", "before 2"],
            "Confirm revised delivery timing, update tender notes, and verify if TMS or OpenDock needs adjustment.",
            "High",
        ),
        (
            "Pickup / Delivery Delay",
            ["late", "delay", "delayed", "eta", "driver", "missed"],
            "Request current ETA and compare against delivery window / OTP risk before escalating.",
            "High",
        ),
        (
            "Compliance / Audit",
            ["audit", "check call", "tracking", "opendock", "compliance"],
            "Verify compliance status and document whether carrier follow-up is needed.",
            "Medium",
        ),
        (
            "Shipment Exception",
            ["short", "damaged", "wrong site", "refused", "cannot receive"],
            "Match the issue to a TO/site and create an exception note for follow-up.",
            "High",
        ),
    ]

    for candidate_type, keywords, action, candidate_urgency in keyword_rules:
        if any(keyword in lowered for keyword in keywords):
            signal_type = candidate_type
            suggested_action = action
            urgency = candidate_urgency
            break

    return {
        "Carrier": selected_carrier,
        "Channel": selected_channel,
        "Signal Type": signal_type,
        "Urgency": urgency,
        "Status": "Open",
        "Matched TOs": ", ".join(dict.fromkeys(match.upper() for match in to_matches)),
        "Possible Site IDs": ", ".join(dict.fromkeys(site_matches[:5])),
        "Suggested Action": suggested_action,
        "Source Message": text,
    }


def match_signal_to_tenders(signal: dict[str, str | int], records: pd.DataFrame) -> pd.DataFrame:
    if records.empty:
        return pd.DataFrame()

    matched = records.copy()
    to_values = [value.strip() for value in str(signal.get("Matched TOs", "")).split(",") if value.strip()]
    site_values = [value.strip() for value in str(signal.get("Possible Site IDs", "")).split(",") if value.strip()]

    mask = pd.Series(False, index=matched.index)
    if to_values and "to_number" in matched.columns:
        mask = mask | matched["to_number"].astype(str).isin(to_values)
    if site_values and "site_id" in matched.columns:
        mask = mask | matched["site_id"].astype(str).isin(site_values)
    carrier = str(signal.get("Carrier", "")).lower()
    if carrier and carrier != "unknown" and "carrier" in matched.columns:
        carrier_mask = matched["carrier"].astype(str).str.lower().str.contains(carrier, regex=False, na=False)
        if mask.any():
            mask = mask & carrier_mask
        else:
            mask = carrier_mask

    return matched[mask].copy()


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = [str(col).strip() for col in cleaned.columns]
    return cleaned


def load_ops_performance(file: BytesIO) -> dict[str, pd.DataFrame]:
    file.seek(0)
    excel = pd.ExcelFile(file)
    daily_sheets = [sheet for sheet in excel.sheet_names if parse_date_sheet_name(sheet) is not None]
    latest_sheets = daily_sheets[-OPS_LOOKBACK_DAYS:]

    daily_frames: list[pd.DataFrame] = []
    for sheet_name in latest_sheets:
        raw = pd.read_excel(excel, sheet_name=sheet_name, header=None)
        parsed = parse_ops_daily_sheet(raw, sheet_name)
        if not parsed.empty:
            daily_frames.append(parsed)

    daily = pd.concat(daily_frames, ignore_index=True) if daily_frames else pd.DataFrame()
    weekly = load_ops_weekly_trend(excel)

    return {
        "daily": daily,
        "weekly": weekly,
    }


def parse_date_sheet_name(sheet_name: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"\s*(\d{1,2})\.(\d{1,2})\s*", sheet_name)
    if not match:
        return None
    month = int(match.group(1))
    day = int(match.group(2))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return month, day


def parse_ops_daily_sheet(raw: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()

    header = raw.iloc[0].fillna("").astype(str).str.strip()
    name_cols = [idx for idx, value in header.items() if normalize_label(value) == "name"]
    frames: list[pd.DataFrame] = []

    for position, start_col in enumerate(name_cols):
        end_col = name_cols[position + 1] if position + 1 < len(name_cols) else raw.shape[1]
        block_headers = header.iloc[start_col:end_col].tolist()
        block = raw.iloc[1:, start_col:end_col].copy()
        block_type = infer_ops_block_type(block_headers)
        block.columns = [normalize_ops_column(col, i) for i, col in enumerate(block_headers)]

        if "Name" not in block.columns:
            continue

        block = block.dropna(subset=["Name"], how="all")
        block = block[block["Name"].astype(str).str.strip().ne("")]
        block = block[~block["Name"].apply(lambda value: isinstance(value, (int, float)))]

        if block.empty:
            continue

        block = standardize_ops_block(block)
        block["Sheet"] = sheet_name
        block["Work Date"] = sheet_name
        block["Metric Type"] = block_type
        frames.append(block)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def normalize_label(value: object) -> str:
    return str(value).strip().lower()


def normalize_ops_column(value: object, position: int) -> str:
    label = str(value).strip()
    compact = re.sub(r"\s+", " ", label).lower()
    if position == 0 and compact == "name":
        return "Name"
    if "active uph" in compact:
        return "UPH"
    if "total uph" in compact or compact == "uph":
        return "UPH"
    if "total lbi units" in compact:
        return "Units"
    if "lbi hours" in compact or "total lbi hours" in compact:
        return "Hours"
    if compact == "bridge":
        return "Bridge"
    if "accepted" in compact:
        return "Accepted"
    return label or f"Column {position + 1}"


def infer_ops_block_type(columns: list[object] | pd.Index) -> str:
    column_text = " ".join(str(col).lower() for col in columns)
    if "bridge" in column_text or "accepted" in column_text:
        return "Bridge Exceptions"
    if "active" in column_text:
        return "Active UPH"
    return "Total UPH"


def standardize_ops_block(block: pd.DataFrame) -> pd.DataFrame:
    standardized = block.copy()
    result = pd.DataFrame()
    result["Name"] = first_column(standardized, "Name") if "Name" in standardized.columns else pd.Series(dtype=str)
    for col in ["UPH", "Units", "Hours"]:
        if col in standardized.columns:
            result[col] = pd.to_numeric(first_column(standardized, col), errors="coerce")
        else:
            result[col] = pd.NA

    for col in ["Bridge", "Accepted"]:
        if col not in standardized.columns:
            result[col] = ""
        else:
            result[col] = first_column(standardized, col).fillna("").astype(str).str.strip()

    return result[["Name", "UPH", "Units", "Hours", "Bridge", "Accepted"]]


def first_column(df: pd.DataFrame, column_name: str) -> pd.Series:
    column = df[column_name]
    if isinstance(column, pd.DataFrame):
        return column.iloc[:, 0]
    return column


def load_ops_weekly_trend(excel: pd.ExcelFile) -> pd.DataFrame:
    if "Pack UPH WoW" not in excel.sheet_names:
        return pd.DataFrame()

    weekly = pd.read_excel(excel, sheet_name="Pack UPH WoW")
    weekly = clean_columns(weekly)
    if "Week of" in weekly.columns:
        weekly["Week of"] = pd.to_datetime(weekly["Week of"], errors="coerce")
    for col in ["UPH (actual)", "UPH (avg)", "OA Units Avg (week)", "OAUnits Avg (day)"]:
        if col in weekly.columns:
            weekly[col] = pd.to_numeric(weekly[col], errors="coerce")
    weekly = weekly.dropna(how="all")
    return weekly


def load_otp_bridges(files: list[BytesIO]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    for file in files:
        file.seek(0)
        workbook = pd.read_excel(file, sheet_name=None, header=None)
        source_name = getattr(file, "name", "Uploaded OTP Bridge")

        for sheet_name, raw in workbook.items():
            header_idx = find_otp_header_row(raw)
            if header_idx is None:
                continue

            headers = raw.iloc[header_idx].fillna("").astype(str).str.strip().tolist()
            available_cols = min(len(headers), len(OTP_COLUMNS))
            data = raw.iloc[header_idx + 1 :, :available_cols].copy()
            data.columns = headers[:available_cols]

            required_cols = [col for col in OTP_COLUMNS if col in data.columns]
            data = data[required_cols]

            if "TO #" not in data.columns:
                continue

            data = data.dropna(subset=["TO #"], how="all")
            data = data[data["TO #"].astype(str).str.strip().ne("")]

            if data.empty:
                continue

            data["Source File"] = source_name
            data["Week"] = sheet_name.strip()
            frames.append(data)

    if not frames:
        return pd.DataFrame(columns=OTP_COLUMNS + ["Source File", "Week"])

    bridge = pd.concat(frames, ignore_index=True)
    bridge = normalize_otp_bridge(bridge)
    return bridge


def find_otp_header_row(raw: pd.DataFrame) -> int | None:
    for idx, row in raw.iterrows():
        values = {str(value).strip() for value in row.dropna().tolist()}
        if "MEID" in values and "TO #" in values:
            return int(idx)
    return None


def normalize_otp_bridge(bridge: pd.DataFrame) -> pd.DataFrame:
    normalized = bridge.copy()

    for col in OTP_COLUMNS:
        if col not in normalized.columns:
            normalized[col] = pd.NA

    normalized["Deliver By"] = pd.to_datetime(normalized["Deliver By"], errors="coerce")
    normalized["Actual Delivery Arrival"] = pd.to_datetime(
        normalized["Actual Delivery Arrival"], errors="coerce"
    )
    normalized["Pallets"] = pd.to_numeric(normalized["Pallets"], errors="coerce").fillna(0)
    normalized["On-Time Status"] = normalized["On-Time Status"].fillna("Unknown").astype(str).str.strip()
    normalized["Detailed Bridge"] = normalized["Detailed Bridge"].fillna("").astype(str).str.strip()
    normalized["Minutes Late"] = (
        (normalized["Actual Delivery Arrival"] - normalized["Deliver By"])
        .dt.total_seconds()
        .div(60)
        .round()
    )
    normalized["Delay Minutes"] = normalized["Minutes Late"].clip(lower=0)
    normalized["Bridge Bucket"] = normalized["Detailed Bridge"].apply(bucket_bridge_reason)
    return normalized


def bucket_bridge_reason(note: str) -> str:
    text = note.lower()
    if not text:
        return "No Detail Provided"
    if "missing check" in text:
        return "Missing Check Call"
    if "on time" in text or "delivery window" in text:
        return "On-Time Dispute"
    if "recovery driver" in text:
        return "Recovery Driver Needed"
    if "previous" in text or "delayed at" in text:
        return "Delayed at Previous Stop"
    if "traffic" in text:
        return "Traffic"
    if "short staff" in text or "staff" in text:
        return "Staffing / Capacity"
    if "rfp" in text:
        return "Route / Planning Issue"
    return "Other"


def format_number(value: float | int | None) -> str:
    if pd.isna(value) or value is None:
        return "0"
    return f"{int(round(float(value))):,}"


def format_percent(value: float | int | None) -> str:
    if pd.isna(value) or value is None:
        return "0.0%"
    return f"{float(value):.1%}"


def summarize_ops_daily(ops_daily: pd.DataFrame) -> pd.DataFrame:
    if ops_daily.empty:
        return pd.DataFrame()

    summary = (
        ops_daily.groupby(["Work Date", "Metric Type"], dropna=False)
        .agg(
            People=("Name", "count"),
            Units=("Units", "sum"),
            Hours=("Hours", "sum"),
            Avg_UPH=("UPH", "mean"),
            Bridge_Count=("Bridge", lambda values: values.astype(str).str.strip().ne("").sum()),
            Accepted_Bridges=("Accepted", lambda values: values.astype(str).str.upper().eq("Y").sum()),
        )
        .reset_index()
    )
    summary["Calculated UPH"] = summary["Units"] / summary["Hours"].replace(0, pd.NA)
    summary = summary.rename(
        columns={
            "Avg_UPH": "Avg UPH",
            "Bridge_Count": "Bridge Count",
            "Accepted_Bridges": "Accepted Bridges",
        }
    )
    return summary


def summarize_ops_overall(ops_data: dict[str, pd.DataFrame]) -> dict[str, float | int | str | None]:
    daily = ops_data.get("daily", pd.DataFrame())
    weekly = ops_data.get("weekly", pd.DataFrame())
    result: dict[str, float | int | str | None] = {
        "latest_date": None,
        "latest_units": 0,
        "latest_hours": 0,
        "latest_uph": None,
        "bridge_count": 0,
        "accepted_bridge_count": 0,
        "weekly_uph": None,
        "prior_week_uph": None,
    }

    if not daily.empty:
        latest_date = daily["Work Date"].dropna().astype(str).iloc[-1]
        latest = daily[daily["Work Date"].astype(str).eq(latest_date)]
        primary = latest[latest["Metric Type"].isin(["Total UPH", "Active UPH"])]
        if primary.empty:
            primary = latest
        bridge_rows = latest[latest["Metric Type"].eq("Bridge Exceptions")]
        bridge_count = int(bridge_rows["Bridge"].astype(str).str.strip().ne("").sum())
        accepted_bridge_count = int(bridge_rows["Accepted"].astype(str).str.upper().eq("Y").sum())

        result["latest_date"] = latest_date
        result["latest_units"] = float(primary["Units"].sum(skipna=True))
        result["latest_hours"] = float(primary["Hours"].sum(skipna=True))
        if result["latest_hours"]:
            result["latest_uph"] = float(result["latest_units"]) / float(result["latest_hours"])
        result["bridge_count"] = bridge_count
        result["accepted_bridge_count"] = accepted_bridge_count

    if not weekly.empty and "UPH (actual)" in weekly.columns:
        valid = weekly.dropna(subset=["UPH (actual)"])
        if not valid.empty:
            result["weekly_uph"] = float(valid.iloc[-1]["UPH (actual)"])
            if len(valid) > 1:
                result["prior_week_uph"] = float(valid.iloc[-2]["UPH (actual)"])

    return result


def compute_health(
    command_center: dict[str, int],
    carrier_status: pd.DataFrame,
    site_summary: pd.DataFrame,
    otp_bridge: pd.DataFrame,
    ops_data: dict[str, pd.DataFrame],
) -> HealthResult:
    score = 0
    drivers: list[str] = []

    created_vs_forecast = command_center.get("created_vs_forecast", 0)
    dt_over_60 = command_center.get("dt_over_60", 0)

    if created_vs_forecast > 250:
        score += 1
        drivers.append(f"Demand is above forecast by {created_vs_forecast:,} orders.")
    if dt_over_60 > 1500:
        score += 2
        drivers.append(f"DT > 60m is elevated at {dt_over_60:,}.")
    elif dt_over_60 > 750:
        score += 1
        drivers.append(f"DT > 60m needs monitoring at {dt_over_60:,}.")

    if not carrier_status.empty:
        risk_count = carrier_status["Status"].isin(["At Risk", "Escalated"]).sum()
        confirmed_count = carrier_status["Status"].eq("Confirmed").sum()
        confirmation_rate = confirmed_count / len(carrier_status)

        if risk_count:
            score += min(2, int(risk_count))
            drivers.append(f"{risk_count} carrier(s) are marked At Risk or Escalated.")
        if confirmation_rate < 0.75:
            score += 1
            drivers.append(f"Carrier confirmation rate is {confirmation_rate:.0%}.")

    if "Delivery Date" in site_summary.columns and "Ship Date" in site_summary.columns:
        ship_dates = pd.to_datetime(site_summary["Ship Date"], errors="coerce")
        delivery_dates = pd.to_datetime(site_summary["Delivery Date"], errors="coerce")
        long_lead = ((delivery_dates - ship_dates).dt.days > 3).sum()
        if long_lead:
            score += 1
            drivers.append(f"{long_lead} order(s) have ship-to-delivery lead time above 3 days.")

    if not otp_bridge.empty and "On-Time Status" in otp_bridge.columns:
        otp_summary = summarize_otp(otp_bridge)
        if not otp_summary.empty:
            weaker = otp_summary[otp_summary["OTP %"] < 0.9]
            if not weaker.empty:
                score += 1
                carrier_list = ", ".join(weaker["SCAC"].head(3).astype(str).tolist())
                drivers.append(f"Recent OTP bridge shows sub-90% performance for {carrier_list}.")

    ops_summary = summarize_ops_overall(ops_data)
    latest_uph = ops_summary.get("latest_uph")
    weekly_uph = ops_summary.get("weekly_uph")
    if latest_uph and weekly_uph and latest_uph < float(weekly_uph) * 0.9:
        score += 1
        drivers.append(
            f"Latest Ops productivity is below weekly trend: {format_number(latest_uph)} UPH vs {format_number(weekly_uph)} weekly."
        )
    if int(ops_summary.get("bridge_count") or 0) >= 5:
        score += 1
        drivers.append(f"Ops productivity bridge has {ops_summary['bridge_count']} recent exception note(s).")

    if score >= 4:
        label = "Red"
    elif score >= 2:
        label = "Yellow"
    else:
        label = "Green"

    if not drivers:
        drivers.append("No major demand, tendering, or lead-time risks detected.")

    return HealthResult(label=label, score=score, drivers=drivers)


def make_leadership_brief(
    health: HealthResult,
    command_center: dict[str, int],
    carrier_summary: pd.DataFrame,
    carrier_status: pd.DataFrame,
    site_summary: pd.DataFrame,
    otp_bridge: pd.DataFrame,
    ops_data: dict[str, pd.DataFrame],
) -> str:
    total_orders = len(site_summary)
    total_pallets = site_summary.get("Pallets Final", pd.Series(dtype=float)).sum()
    total_weight = (
        site_summary.get("Water Weight", pd.Series(dtype=float)).sum()
        + site_summary.get("Non-Water Weight", pd.Series(dtype=float)).sum()
    )

    top_carrier_line = "No carrier data loaded."
    if not carrier_summary.empty and "Carrier" in carrier_summary.columns:
        pallet_col = "Total Pallet Estimate"
        if pallet_col in carrier_summary.columns:
            top = carrier_summary.sort_values(pallet_col, ascending=False).head(3)
            top_carrier_line = "; ".join(
                f"{row['Carrier']} ({format_number(row[pallet_col])} pallets)"
                for _, row in top.iterrows()
            )

    risk_line = "No carriers currently marked At Risk or Escalated."
    if not carrier_status.empty:
        risky = carrier_status[carrier_status["Status"].isin(["At Risk", "Escalated"])]
        if not risky.empty:
            risk_line = "; ".join(
                f"{row['Carrier']} - {row['Status']}" for _, row in risky.iterrows()
            )

    otp_line = "No OTP bridge files loaded."
    if not otp_bridge.empty:
        otp_summary = summarize_otp(otp_bridge)
        total_shipments = len(otp_bridge)
        late_shipments = int(otp_bridge["On-Time Status"].str.lower().eq("late").sum())
        if not otp_summary.empty:
            weakest = otp_summary.sort_values(["OTP %", "Late Shipments"], ascending=[True, False]).head(3)
            weakest_line = "; ".join(
                f"{row['SCAC']} {format_percent(row['OTP %'])} OTP"
                for _, row in weakest.iterrows()
            )
            otp_line = (
                f"{total_shipments:,} bridge shipment records loaded; "
                f"{late_shipments:,} marked late. Watch list: {weakest_line}."
            )

    ops_line = "No Ops productivity workbook loaded."
    ops_summary = summarize_ops_overall(ops_data)
    if ops_summary.get("latest_date"):
        bridge_count = int(ops_summary.get("bridge_count") or 0)
        accepted_count = int(ops_summary.get("accepted_bridge_count") or 0)
        ops_line = (
            f"Latest Ops sheet {ops_summary['latest_date']}: "
            f"{format_number(ops_summary.get('latest_units'))} units / "
            f"{format_number(ops_summary.get('latest_hours'))} hours / "
            f"{format_number(ops_summary.get('latest_uph'))} UPH. "
            f"{bridge_count} bridge note(s), {accepted_count} accepted."
        )

    drivers = " ".join(health.drivers)
    updated = command_center.get("last_updated", "not provided")

    return (
        f"DC1 Supply Chain Health | {updated}\n\n"
        f"Overall Status: {health.label}\n\n"
        f"Demand: Created orders are {command_center.get('created', 0):,}; "
        f"cancelled orders are {command_center.get('cancelled', 0):,}; "
        f"created vs forecast is {command_center.get('created_vs_forecast', 0):+,}.\n\n"
        f"Transportation: {total_orders:,} orders / {format_number(total_pallets)} pallets / "
        f"{format_number(total_weight)} lbs planned. Highest-volume carriers: {top_carrier_line}.\n\n"
        f"Risk Drivers: {drivers}\n\n"
        f"Carrier Exceptions: {risk_line}\n\n"
        f"OTP Bridge: {otp_line}\n\n"
        f"Ops Productivity: {ops_line}\n\n"
        "Next Action: Confirm carrier capacity and pickup windows for any Yellow/Red lanes before the next leadership sync."
    )


def make_transportation_report(
    command_center: dict[str, int],
    tender_pipeline: dict[str, pd.DataFrame],
    carrier_status: pd.DataFrame,
    otp_bridge: pd.DataFrame,
) -> str:
    records = tender_pipeline.get("records", pd.DataFrame())
    ready = tender_pipeline.get("ready", pd.DataFrame())
    issues = tender_pipeline.get("issues", pd.DataFrame())
    duplicates = tender_pipeline.get("duplicates", pd.DataFrame())
    conflicts = tender_pipeline.get("conflicts", pd.DataFrame())
    open_signals = pd.DataFrame(st.session_state.get("carrier_signals", []))
    if not open_signals.empty:
        open_signals = open_signals[open_signals["Status"].isin(["Open", "Escalated"])]

    otp_line = "OTP bridge not loaded."
    if not otp_bridge.empty:
        otp_summary = summarize_otp(otp_bridge)
        if not otp_summary.empty:
            weakest = otp_summary.sort_values(["OTP %", "Late Shipments"], ascending=[True, False]).head(2)
            otp_line = "; ".join(f"{row['SCAC']} {format_percent(row['OTP %'])} OTP" for _, row in weakest.iterrows())

    risky_carriers = "No carrier status exceptions marked."
    if not carrier_status.empty:
        risky = carrier_status[carrier_status["Status"].isin(["At Risk", "Escalated"])]
        if not risky.empty:
            risky_carriers = "; ".join(f"{row['Carrier']} - {row['Status']}" for _, row in risky.iterrows())

    return (
        f"Transportation Snapshot | {command_center.get('last_updated', 'not provided')}\n\n"
        f"Tender Pipeline: {len(records):,} rows loaded; {len(ready):,} ready; {len(issues):,} need review; "
        f"{len(duplicates):,} duplicates; {len(conflicts):,} conflicts.\n\n"
        f"Carrier Status: {risky_carriers}\n\n"
        f"Carrier Signals: {len(open_signals):,} open/escalated signal(s).\n\n"
        f"OTP Context: {otp_line}\n\n"
        "Recommended Follow-Up: Resolve tender validation exceptions, confirm carrier risks, and push ready loads through Uber Freight once mapping is clean."
    )


def make_operations_report(ops_data: dict[str, pd.DataFrame], command_center: dict[str, int]) -> str:
    ops_summary = summarize_ops_overall(ops_data)
    if not ops_summary.get("latest_date"):
        ops_line = "Ops productivity workbook not loaded."
    else:
        ops_line = (
            f"Latest sheet {ops_summary['latest_date']}: {format_number(ops_summary.get('latest_units'))} units; "
            f"{format_number(ops_summary.get('latest_hours'))} hours; {format_number(ops_summary.get('latest_uph'))} UPH; "
            f"{format_number(ops_summary.get('bridge_count'))} bridge note(s)."
        )

    return (
        f"Operations Snapshot | {command_center.get('last_updated', 'not provided')}\n\n"
        f"Demand Signal: {command_center.get('created', 0):,} created orders; "
        f"{command_center.get('created_vs_forecast', 0):+,} vs forecast; "
        f"DT > 60m at {command_center.get('dt_over_60', 0):,}.\n\n"
        f"Productivity: {ops_line}\n\n"
        "Recommended Follow-Up: Compare throughput to outbound volume, bridge productivity exceptions, and identify whether DC capacity is supporting pickup readiness."
    )


def make_finance_report_placeholder(
    tender_pipeline: dict[str, pd.DataFrame],
    command_center: dict[str, int],
) -> str:
    records = tender_pipeline.get("records", pd.DataFrame())
    total_weight = records.get("total_weight", pd.Series(dtype=float)).sum()
    total_pallets = records.get("pallets", pd.Series(dtype=float)).sum()

    return (
        f"Finance Snapshot Placeholder | {command_center.get('last_updated', 'not provided')}\n\n"
        f"Current Freight Base: {len(records):,} tender row(s); {format_number(total_pallets)} pallets; "
        f"{format_number(total_weight)} lbs.\n\n"
        "Finance Inputs Pending: linehaul rate, fuel surcharge per mile, accessorials, spot vs contract cost, benchmark lane rate, and invoice variance.\n\n"
        "Future Output: cost per pallet, cost per lb, cost per lane, carrier cost variance, fuel impact, and savings opportunities by lane/carrier.\n\n"
        "Recommended Follow-Up: Add finance-owned cost file or approved TMS rate export once stakeholders are ready."
    )


def summarize_otp(otp_bridge: pd.DataFrame) -> pd.DataFrame:
    if otp_bridge.empty or "SCAC" not in otp_bridge.columns:
        return pd.DataFrame()

    bridge = otp_bridge.copy()
    bridge["SCAC"] = bridge["SCAC"].fillna("Unknown").astype(str).str.strip()
    bridge["Is Late"] = bridge["On-Time Status"].str.lower().eq("late")
    bridge["Is On Time"] = bridge["On-Time Status"].str.lower().isin(["on time", "on-time", "ontime"])

    summary = (
        bridge.groupby("SCAC", dropna=False)
        .agg(
            Shipments=("TO #", "count"),
            Late_Shipments=("Is Late", "sum"),
            On_Time_Shipments=("Is On Time", "sum"),
            Late_Pallets=("Pallets", lambda values: values[bridge.loc[values.index, "Is Late"]].sum()),
            Avg_Delay_Minutes=("Delay Minutes", "mean"),
        )
        .reset_index()
    )
    summary["OTP %"] = 1 - (summary["Late_Shipments"] / summary["Shipments"]).fillna(0)
    summary = summary.rename(
        columns={
            "Late_Shipments": "Late Shipments",
            "Late_Pallets": "Late Pallets",
            "Avg_Delay_Minutes": "Avg Delay Minutes",
        }
    )
    return summary.sort_values(["OTP %", "Shipments"], ascending=[True, False])


def render_status_badge(label: str) -> None:
    colors = {
        "Green": ("#1f7a4d", "#e8f5ef"),
        "Yellow": ("#946200", "#fff5cc"),
        "Red": ("#a12d2d", "#fde8e8"),
    }
    fg, bg = colors[label]
    st.markdown(
        f"""
        <div style="background:{bg};border:1px solid {fg};border-radius:8px;padding:16px 18px;">
          <div style="font-size:14px;color:{fg};font-weight:700;">Overall Health</div>
          <div style="font-size:42px;color:{fg};font-weight:800;line-height:1;">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_saved_file_library(category: str, empty_message: str) -> None:
    saved_files = list_uploaded_files(category)
    if saved_files.empty:
        st.info(empty_message)
        return

    display_files = saved_files.copy()
    display_files["file_size"] = display_files["file_size"].apply(
        lambda size: f"{size / 1024:,.1f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):,.2f} MB"
    )
    display_files = display_files.rename(
        columns={
            "filename": "File Name",
            "content_type": "Type",
            "file_size": "Size",
            "created_at": "Saved At",
        }
    )
    st.dataframe(
        display_files[["File Name", "Type", "Size", "Saved At"]],
        use_container_width=True,
        hide_index=True,
    )

    selected_file_id = st.selectbox(
        "Select saved file",
        saved_files["id"].tolist(),
        format_func=lambda file_id: saved_files.loc[saved_files["id"].eq(file_id), "filename"].iloc[0],
        key=f"{category}_file_selector",
    )
    loaded_file = load_uploaded_file(int(selected_file_id))
    if loaded_file:
        filename, content_type, payload = loaded_file
        st.download_button(
            "Download selected file",
            data=payload,
            file_name=filename,
            mime=content_type,
            key=f"{category}_download_button",
        )


def latest_timestamp(values: list[str]) -> str:
    cleaned = [value for value in values if isinstance(value, str) and value.strip()]
    if not cleaned:
        return ""
    return max(cleaned)


def render_data_input_health(
    ship_allocation_records: pd.DataFrame,
    otp_bridge: pd.DataFrame,
    ops_data: dict[str, pd.DataFrame],
) -> None:
    reference_sheets = list_reference_sheets()
    google_sheets = list_google_sheet_connections()
    presentations = list_uploaded_files("presentation")
    pdfs = list_uploaded_files("pdf")
    saved_batches = list_ship_allocation_batches()
    command_history = list_command_center_snapshots(limit=1)

    rows = [
        {
            "Input": "Command Center snapshots",
            "Status": "Ignored" if LIVE_GOOGLE_ONLY else "Loaded" if not command_history.empty else "Manual default",
            "Detail": (
                "Live Google Sheet mode is on"
                if LIVE_GOOGLE_ONLY
                else
                f"Latest: {command_history.iloc[0]['snapshot_time']}"
                if not command_history.empty
                else "No saved Command Center history yet"
            ),
            "Last Updated": "" if LIVE_GOOGLE_ONLY else str(command_history.iloc[0]["uploaded_at"]) if not command_history.empty else "",
        },
        {
            "Input": "Daily allocation file",
            "Status": "Loaded" if not ship_allocation_records.empty else "Missing",
            "Detail": f"{len(ship_allocation_records):,} normalized row(s)" if not ship_allocation_records.empty else "Upload daily allocation file from sidebar",
            "Last Updated": "",
        },
        {
            "Input": "OTP bridge",
            "Status": "Loaded" if not otp_bridge.empty else "Missing",
            "Detail": f"{len(otp_bridge):,} OTP row(s)" if not otp_bridge.empty else "Upload weekly bridge workbook(s)",
            "Last Updated": "",
        },
        {
            "Input": "Ops productivity",
            "Status": "Loaded" if not ops_data.get("daily", pd.DataFrame()).empty else "Missing",
            "Detail": (
                f"{len(ops_data.get('daily', pd.DataFrame())):,} daily productivity row(s)"
                if not ops_data.get("daily", pd.DataFrame()).empty
                else "Upload OA productivity workbook"
            ),
            "Last Updated": "",
        },
        {
            "Input": "Connected Google Sheets",
            "Status": "Loaded" if not google_sheets.empty else "Missing",
            "Detail": f"{len(google_sheets):,} connected live sheet(s)" if not google_sheets.empty else "Connect shared Google Sheet URLs",
            "Last Updated": latest_timestamp(google_sheets.get("last_synced_at", pd.Series(dtype=str)).astype(str).tolist())
            if not google_sheets.empty
            else "",
        },
        {
            "Input": "Uploaded reference cache",
            "Status": "Ignored" if LIVE_GOOGLE_ONLY else "Loaded" if not reference_sheets.empty else "Missing",
            "Detail": "Live Google Sheet mode is on" if LIVE_GOOGLE_ONLY else f"{len(reference_sheets):,} active workbook(s)" if not reference_sheets.empty else "Upload shared reference workbook exports",
            "Last Updated": "" if LIVE_GOOGLE_ONLY else latest_timestamp(reference_sheets.get("created_at", pd.Series(dtype=str)).astype(str).tolist())
            if not reference_sheets.empty
            else "",
        },
        {
            "Input": "Saved BulkUploads",
            "Status": "Loaded" if not saved_batches.empty else "Missing",
            "Detail": f"{len(saved_batches):,} saved generated file(s)" if not saved_batches.empty else "Save generated BulkUpload after validation",
            "Last Updated": latest_timestamp(saved_batches.get("created_at", pd.Series(dtype=str)).astype(str).tolist())
            if not saved_batches.empty
            else "",
        },
        {
            "Input": "Presentations",
            "Status": "Archived" if not presentations.empty else "Optional",
            "Detail": f"{len(presentations):,} saved file(s)" if not presentations.empty else "No saved presentations",
            "Last Updated": latest_timestamp(presentations.get("created_at", pd.Series(dtype=str)).astype(str).tolist())
            if not presentations.empty
            else "",
        },
        {
            "Input": "PDFs",
            "Status": "Archived" if not pdfs.empty else "Optional",
            "Detail": f"{len(pdfs):,} saved file(s)" if not pdfs.empty else "No saved PDFs",
            "Last Updated": latest_timestamp(pdfs.get("created_at", pd.Series(dtype=str)).astype(str).tolist())
            if not pdfs.empty
            else "",
        },
    ]

    st.subheader("Data Inputs Health")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_ship_validation_summary(mapped_ship_records: pd.DataFrame, ship_export: pd.DataFrame) -> None:
    ready_count = int(mapped_ship_records["ship_status"].eq("Ready").sum()) if "ship_status" in mapped_ship_records.columns else 0
    review_count = int(mapped_ship_records["ship_status"].eq("Needs Review").sum()) if "ship_status" in mapped_ship_records.columns else 0
    duplicate_count = int(mapped_ship_records["ship_status"].eq("Duplicate").sum()) if "ship_status" in mapped_ship_records.columns else 0
    conflict_count = int(mapped_ship_records["ship_status"].eq("Conflict").sum()) if "ship_status" in mapped_ship_records.columns else 0

    st.subheader("BulkUpload Validation Summary")
    metric_cols = st.columns(6)
    metric_cols[0].metric("Rows Loaded", format_number(len(mapped_ship_records)))
    metric_cols[1].metric("Ready", format_number(ready_count))
    metric_cols[2].metric("Needs Review", format_number(review_count))
    metric_cols[3].metric("Duplicates", format_number(duplicate_count))
    metric_cols[4].metric("Conflicts", format_number(conflict_count))
    metric_cols[5].metric("Export Rows", format_number(len(ship_export)))

    issue_rows = mapped_ship_records[mapped_ship_records.get("ship_status", pd.Series(dtype=str)).ne("Ready")].copy()
    if issue_rows.empty:
        st.success("All selected rows are ready for the Uber Freight BulkUpload export.")
        return

    issue_counts: dict[str, int] = {}
    for issue_text in issue_rows.get("ship_issues", pd.Series(dtype=str)).fillna("").astype(str):
        for issue in [item.strip() for item in issue_text.split(";") if item.strip()]:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1

    if issue_counts:
        st.warning("Review these issues before uploading to Uber Freight.")
        issue_summary = pd.DataFrame(
            [{"Issue": issue, "Rows": count} for issue, count in sorted(issue_counts.items(), key=lambda item: item[1], reverse=True)]
        )
        st.dataframe(issue_summary, use_container_width=True, hide_index=True)


def site_market_prefix(location_name: object) -> str:
    text = str(location_name or "").strip().upper()
    match = re.match(r"^([A-Z0-9]+)_", text)
    return match.group(1) if match else ""


def prepare_mfc_site_records(current_records: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if not current_records.empty:
        current = current_records.copy()
        current["batch_name"] = "Current Upload"
        current["batch_created_at"] = now_iso()
        current["record_scope"] = "Current Upload"
        frames.append(current)
    saved = load_saved_ship_allocation_records()
    if not saved.empty:
        frames.append(saved)
    if not frames:
        return pd.DataFrame()

    records = pd.concat(frames, ignore_index=True)
    for col in ["ship_date", "delivery_date", "pick_date", "batch_created_at"]:
        if col in records.columns:
            records[col] = pd.to_datetime(records[col], errors="coerce")
    records["activity_date"] = records.get("ship_date", pd.Series(index=records.index, dtype="datetime64[ns]"))
    records["activity_date"] = records["activity_date"].fillna(records.get("delivery_date", pd.Series(index=records.index, dtype="datetime64[ns]")))
    records["activity_date"] = records["activity_date"].fillna(records.get("pick_date", pd.Series(index=records.index, dtype="datetime64[ns]")))
    records["activity_date"] = records["activity_date"].fillna(records.get("batch_created_at", pd.Series(index=records.index, dtype="datetime64[ns]")))
    records["location_name"] = records.get("location_name", pd.Series(index=records.index, dtype=object)).fillna("").astype(str)
    records["site_id"] = records.get("site_id", pd.Series(index=records.index, dtype=object)).fillna("").astype(str)
    records["site_key"] = records["site_id"].where(records["site_id"].str.strip().ne(""), records["location_name"])
    records["market_prefix"] = records["location_name"].apply(site_market_prefix)
    records["market_name"] = records["market_prefix"].map(lambda prefix: MFC_MARKET_COORDS.get(prefix, (None, None, "Unmapped"))[2])
    records["latitude"] = records["market_prefix"].map(lambda prefix: MFC_MARKET_COORDS.get(prefix, (None, None, ""))[0])
    records["longitude"] = records["market_prefix"].map(lambda prefix: MFC_MARKET_COORDS.get(prefix, (None, None, ""))[1])
    records["pallets"] = pd.to_numeric(records.get("pallets", 0), errors="coerce").fillna(0)
    records["units"] = pd.to_numeric(records.get("units", 0), errors="coerce").fillna(0)
    records["to_number"] = records.get("to_number", pd.Series(index=records.index, dtype=object)).fillna("").astype(str)
    records["carrier"] = records.get("carrier", pd.Series(index=records.index, dtype=object)).fillna("").astype(str)
    if "row_fingerprint" in records.columns:
        dedupe_cols = ["row_fingerprint"]
    else:
        dedupe_cols = ["source_file", "to_number", "site_key", "activity_date"]
        dedupe_cols = [col for col in dedupe_cols if col in records.columns]
    if dedupe_cols:
        records = records.drop_duplicates(subset=dedupe_cols)
    return records


def filter_site_records_by_period(records: pd.DataFrame, period: str) -> pd.DataFrame:
    if records.empty or "activity_date" not in records.columns:
        return records
    dated = records.dropna(subset=["activity_date"]).copy()
    if dated.empty or period == "All Time":
        return dated if not dated.empty else records
    latest_date = dated["activity_date"].max()
    if period == "Week":
        start_date = latest_date - pd.Timedelta(days=6)
    elif period == "Month":
        start_date = latest_date - pd.DateOffset(months=1) + pd.Timedelta(days=1)
    elif period == "Quarter":
        start_date = latest_date - pd.DateOffset(months=3) + pd.Timedelta(days=1)
    else:
        return dated
    return dated[dated["activity_date"].between(start_date, latest_date)]


def summarize_mfc_sites(records: pd.DataFrame) -> pd.DataFrame:
    if records.empty:
        return pd.DataFrame()
    grouped = (
        records.groupby(["site_key", "site_id", "location_name", "market_prefix", "market_name", "latitude", "longitude"], dropna=False)
        .agg(
            orders=("to_number", "nunique"),
            rows=("to_number", "size"),
            pallets=("pallets", "sum"),
            units=("units", "sum"),
            carriers=("carrier", lambda values: ", ".join(sorted(set(v for v in values.astype(str) if v))[:4])),
            latest_ship_date=("activity_date", "max"),
        )
        .reset_index()
    )
    grouped["orders"] = grouped["orders"].where(grouped["orders"].gt(0), grouped["rows"])
    grouped["latest_ship_date"] = pd.to_datetime(grouped["latest_ship_date"], errors="coerce").dt.date.astype(str)
    return grouped.sort_values(["orders", "pallets"], ascending=False)


def mfc_period_leaderboards(records: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        period: summarize_mfc_sites(filter_site_records_by_period(records, period)).head(15)
        for period in ["Week", "Month", "Quarter", "All Time"]
    }


def render_mfc_site_map(ship_allocation_records: pd.DataFrame) -> None:
    st.subheader("MFC Site Map")
    st.caption(
        "Uses uploaded daily allocation files and saved Ship Allocation Builder history. Map points are approximate market coordinates derived from the site prefix in each location name."
    )
    site_records = prepare_mfc_site_records(ship_allocation_records)
    if site_records.empty:
        st.info("Upload daily allocation files from the sidebar, or save a generated BulkUpload, to populate the MFC site map.")
        return

    period = st.selectbox("Map period", ["Week", "Month", "Quarter", "All Time"], index=0)
    period_records = filter_site_records_by_period(site_records, period)
    site_summary = summarize_mfc_sites(period_records)
    mapped_sites = site_summary.dropna(subset=["latitude", "longitude"]).copy()

    total_sites = int(site_summary["site_key"].nunique()) if not site_summary.empty else 0
    total_orders = int(site_summary["orders"].sum()) if not site_summary.empty else 0
    total_pallets = float(site_summary["pallets"].sum()) if not site_summary.empty else 0
    unmapped_count = int(site_summary["latitude"].isna().sum()) if not site_summary.empty else 0
    metric_cols = st.columns(4)
    metric_cols[0].metric("MFC Sites", format_number(total_sites))
    metric_cols[1].metric("Allocated Orders", format_number(total_orders))
    metric_cols[2].metric("Allocated Pallets", format_number(total_pallets))
    metric_cols[3].metric("Unmapped Prefixes", format_number(unmapped_count))

    if mapped_sites.empty:
        st.warning("No mapped site prefixes were found in the current allocation data.")
    else:
        fig = px.scatter_geo(
            mapped_sites,
            lat="latitude",
            lon="longitude",
            size="orders",
            color="pallets",
            hover_name="location_name",
            hover_data={
                "site_id": True,
                "market_name": True,
                "orders": ":,.0f",
                "pallets": ":,.0f",
                "units": ":,.0f",
                "carriers": True,
                "latitude": False,
                "longitude": False,
            },
            text="orders",
            scope="usa",
            color_continuous_scale="Blues",
            size_max=38,
        )
        fig.update_traces(
            texttemplate="%{text:,.0f}",
            textposition="top center",
            textfont=dict(size=18, color="#ffffff", family="Arial Black, Arial, sans-serif"),
            marker=dict(line=dict(width=2.5, color="#ffffff"), opacity=0.88),
            mode="markers+text",
        )
        fig.update_layout(
            height=560,
            margin=dict(l=0, r=0, t=10, b=0),
            geo=dict(
                bgcolor="#f7fbff",
                lakecolor="#e7f6ff",
                landcolor="#f7fbff",
                subunitcolor="#b8cad8",
                countrycolor="#9fb5c7",
                coastlinecolor="#9fb5c7",
            ),
            paper_bgcolor="#f7fbff",
            plot_bgcolor="#f7fbff",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top Allocated Sites")
    leaderboard_tabs = st.tabs(["Week", "Month", "Quarter", "All Time"])
    leaderboards = mfc_period_leaderboards(site_records)
    display_cols = ["location_name", "site_id", "market_name", "orders", "pallets", "units", "carriers", "latest_ship_date"]
    for tab, period_name in zip(leaderboard_tabs, leaderboards):
        with tab:
            period_leaders = leaderboards[period_name]
            if period_leaders.empty:
                st.caption(f"No allocated site data found for {period_name.lower()}.")
            else:
                st.dataframe(
                    period_leaders[[col for col in display_cols if col in period_leaders.columns]],
                    use_container_width=True,
                    hide_index=True,
                )

    unmapped = site_summary[site_summary["latitude"].isna()].copy()
    if not unmapped.empty:
        with st.expander("Unmapped site prefixes to add later"):
            st.dataframe(
                unmapped[["market_prefix", "location_name", "site_id", "orders", "pallets"]]
                .sort_values(["orders", "pallets"], ascending=False),
                use_container_width=True,
                hide_index=True,
            )


def safe_text(value: object, fallback: str = "") -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "nat", "none"}:
        return fallback
    return text or fallback


def placard_id_part(value: object) -> str:
    text = safe_text(value, "UNK").upper()
    text = re.sub(r"[^A-Z0-9]+", "-", text).strip("-")
    return text[:34] or "UNK"


def build_placard_rows(records: pd.DataFrame) -> pd.DataFrame:
    if records.empty:
        return pd.DataFrame()

    placard_source = records.copy()
    for col in ["pick_date", "ship_date", "delivery_date"]:
        if col in placard_source.columns:
            placard_source[col] = pd.to_datetime(placard_source[col], errors="coerce")

    placard_source["pallets"] = (
        pd.to_numeric(placard_source.get("pallets", pd.Series(1, index=placard_source.index)), errors="coerce")
        .fillna(1)
        .clip(lower=1)
        .round()
        .astype(int)
    )
    placard_source["units"] = pd.to_numeric(placard_source.get("units", 0), errors="coerce").fillna(0)
    placard_source["lines"] = pd.to_numeric(placard_source.get("lines", 0), errors="coerce").fillna(0)
    placard_source["total_weight"] = pd.to_numeric(placard_source.get("total_weight", 0), errors="coerce").fillna(0)

    placard_rows: list[dict[str, object]] = []
    for _, row in placard_source.iterrows():
        total_pallets = int(row.get("pallets", 1) or 1)
        to_number = safe_text(row.get("to_number"), safe_text(row.get("primary_reference"), "UNKNOWN-TO"))
        source_group = safe_text(row.get("source_group"), "Unknown")
        carrier = safe_text(row.get("carrier"), "Unassigned Carrier")
        location_name = safe_text(row.get("location_name"), "Unknown Location")
        market_prefix = site_market_prefix(location_name) or "MFC"
        site_id = safe_text(row.get("site_id"), "Unknown")

        for pallet_number in range(1, total_pallets + 1):
            placard_id = "-".join(
                [
                    placard_id_part(source_group),
                    placard_id_part(carrier),
                    placard_id_part(market_prefix),
                    placard_id_part(to_number),
                    str(pallet_number),
                ]
            )
            placard_rows.append(
                {
                    "pallet_id": placard_id,
                    "source_group": source_group,
                    "source_file": safe_text(row.get("source_file")),
                    "to_number": to_number,
                    "primary_reference": safe_text(row.get("primary_reference"), to_number),
                    "location_name": location_name,
                    "site_id": site_id,
                    "carrier": carrier,
                    "market": market_prefix,
                    "business_unit": safe_text(row.get("business_unit")),
                    "pick_date": row.get("pick_date"),
                    "ship_date": row.get("ship_date"),
                    "delivery_date": row.get("delivery_date"),
                    "pallet_number": pallet_number,
                    "total_pallets": total_pallets,
                    "units": float(row.get("units", 0) or 0),
                    "lines": float(row.get("lines", 0) or 0),
                    "total_weight": float(row.get("total_weight", 0) or 0),
                }
            )

    placards = pd.DataFrame(placard_rows)
    if placards.empty:
        return placards
    placards["ship_date"] = pd.to_datetime(placards["ship_date"], errors="coerce")
    placards["pick_date"] = pd.to_datetime(placards["pick_date"], errors="coerce")
    placards["delivery_date"] = pd.to_datetime(placards["delivery_date"], errors="coerce")
    return placards.sort_values(["ship_date", "carrier", "location_name", "pallet_number"], na_position="last")


def build_placard_print_html(placards: pd.DataFrame, title: str) -> str:
    card_html = []
    for _, row in placards.iterrows():
        ship_date = pd.to_datetime(row.get("ship_date"), errors="coerce")
        delivery_date = pd.to_datetime(row.get("delivery_date"), errors="coerce")
        ship_text = ship_date.strftime("%m/%d/%Y") if pd.notna(ship_date) else "No ship date"
        delivery_text = delivery_date.strftime("%m/%d/%Y") if pd.notna(delivery_date) else "No delivery date"
        card_html.append(
            f"""
            <section class="placard">
                <div class="placard-topline">
                    <span>{html.escape(safe_text(row.get("source_group"), "Allocation"))}</span>
                    <span>PALLET {int(row.get("pallet_number", 1))} OF {int(row.get("total_pallets", 1))}</span>
                </div>
                <h1>{html.escape(safe_text(row.get("location_name"), "Unknown Location"))}</h1>
                <div class="site-id">SITE {html.escape(safe_text(row.get("site_id"), "Unknown"))}</div>
                <div class="detail-grid">
                    <div><strong>TO</strong><span>{html.escape(safe_text(row.get("to_number"), "Unknown"))}</span></div>
                    <div><strong>Carrier</strong><span>{html.escape(safe_text(row.get("carrier"), "Unassigned"))}</span></div>
                    <div><strong>Ship Date</strong><span>{html.escape(ship_text)}</span></div>
                    <div><strong>Delivery Date</strong><span>{html.escape(delivery_text)}</span></div>
                    <div><strong>Units</strong><span>{format_number(row.get("units"))}</span></div>
                    <div><strong>Lines</strong><span>{format_number(row.get("lines"))}</span></div>
                </div>
                <footer>{html.escape(safe_text(row.get("pallet_id"), ""))}</footer>
            </section>
            """
        )

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
    @page {{ size: letter; margin: 0.35in; }}
    * {{ box-sizing: border-box; }}
    body {{
        margin: 0;
        font-family: Arial, Helvetica, sans-serif;
        color: #10131a;
        background: #ffffff;
    }}
    .sheet {{
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 0.22in;
    }}
    .placard {{
        min-height: 3.95in;
        border: 4px solid #10131a;
        border-radius: 12px;
        padding: 0.22in;
        page-break-inside: avoid;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }}
    .placard-topline {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        font-weight: 800;
        color: #0076d6;
        letter-spacing: 0.03em;
        text-transform: uppercase;
    }}
    h1 {{
        font-size: 31px;
        line-height: 1.05;
        margin: 18px 0 10px;
    }}
    .site-id {{
        font-size: 54px;
        font-weight: 900;
        letter-spacing: 0.02em;
        border-top: 3px solid #10131a;
        border-bottom: 3px solid #10131a;
        padding: 8px 0;
    }}
    .detail-grid {{
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 10px 18px;
        margin-top: 14px;
    }}
    .detail-grid div {{
        display: flex;
        flex-direction: column;
        min-width: 0;
    }}
    strong {{
        color: #5d6778;
        font-size: 11px;
        text-transform: uppercase;
    }}
    span {{
        font-size: 15px;
        font-weight: 700;
        overflow-wrap: anywhere;
    }}
    footer {{
        margin-top: 14px;
        border-top: 2px solid #d5dde6;
        padding-top: 8px;
        font-size: 12px;
        font-weight: 800;
        color: #5d6778;
        overflow-wrap: anywhere;
    }}
</style>
</head>
<body>
<main class="sheet">
{''.join(card_html)}
</main>
</body>
</html>"""


def render_placard_preview(placards: pd.DataFrame, limit: int = 12) -> None:
    preview = placards.head(limit)
    cards = []
    for _, row in preview.iterrows():
        delivery_date = pd.to_datetime(row.get("delivery_date"), errors="coerce")
        delivery_text = delivery_date.strftime("%m/%d/%Y") if pd.notna(delivery_date) else "No delivery date"
        cards.append(
            f"""
            <div class="gp-placard-card">
                <div class="gp-placard-kicker">{html.escape(safe_text(row.get("source_group"), "Allocation"))} | Pallet {int(row.get("pallet_number", 1))} of {int(row.get("total_pallets", 1))}</div>
                <div class="gp-placard-location">{html.escape(safe_text(row.get("location_name"), "Unknown Location"))}</div>
                <div class="gp-placard-site">SITE {html.escape(safe_text(row.get("site_id"), "Unknown"))}</div>
                <div class="gp-placard-meta">
                    <span>TO {html.escape(safe_text(row.get("to_number"), "Unknown"))}</span>
                    <span>{html.escape(safe_text(row.get("carrier"), "Unassigned"))}</span>
                    <span>Deliver {html.escape(delivery_text)}</span>
                </div>
            </div>
            """
        )
    components.html(
        f"""
        <style>
            .gp-placard-grid {{
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 14px;
                font-family: Arial, Helvetica, sans-serif;
            }}
            .gp-placard-card {{
                min-height: 220px;
                border: 3px solid #10131a;
                border-radius: 8px;
                background: #ffffff;
                color: #10131a;
                padding: 18px;
                box-shadow: 0 10px 22px rgba(16, 19, 26, 0.12);
            }}
            .gp-placard-kicker {{
                color: #0076d6;
                font-weight: 900;
                font-size: 13px;
                text-transform: uppercase;
            }}
            .gp-placard-location {{
                font-size: 24px;
                font-weight: 900;
                line-height: 1.05;
                margin-top: 12px;
            }}
            .gp-placard-site {{
                font-size: 44px;
                font-weight: 900;
                border-top: 2px solid #10131a;
                border-bottom: 2px solid #10131a;
                margin: 12px 0;
                padding: 6px 0;
            }}
            .gp-placard-meta {{
                display: grid;
                gap: 5px;
                color: #4d596b;
                font-weight: 800;
            }}
        </style>
        <div class="gp-placard-grid">{''.join(cards)}</div>
        """,
        height=min(760, max(260, ((len(preview) + 1) // 2) * 255)),
        scrolling=True,
    )


def render_placard_builder(ship_allocation_records: pd.DataFrame) -> None:
    st.subheader("Placard Builder")
    st.caption(
        "Builds printable pallet placards from the uploaded daily allocation files. Each allocated pallet becomes one placard."
    )
    placards = build_placard_rows(ship_allocation_records)
    if placards.empty:
        st.info("Upload daily allocation files in the sidebar to generate placards.")
        return

    filter_cols = st.columns([1, 1, 1])
    available_dates = sorted(
        date.date()
        for date in pd.to_datetime(placards["ship_date"], errors="coerce").dropna().drop_duplicates()
    )
    selected_dates = filter_cols[0].multiselect("Ship date", available_dates, default=available_dates[-1:] if available_dates else [])
    available_sources = sorted(placards["source_group"].dropna().astype(str).unique().tolist())
    selected_sources = filter_cols[1].multiselect("Source", available_sources, default=available_sources)
    available_carriers = sorted(placards["carrier"].dropna().astype(str).unique().tolist())
    selected_carriers = filter_cols[2].multiselect("Carrier", available_carriers, default=available_carriers)

    filtered = placards.copy()
    if selected_dates:
        filtered = filtered[filtered["ship_date"].dt.date.isin(selected_dates)]
    if selected_sources:
        filtered = filtered[filtered["source_group"].isin(selected_sources)]
    if selected_carriers:
        filtered = filtered[filtered["carrier"].isin(selected_carriers)]

    metric_cols = st.columns(4)
    metric_cols[0].metric("Placards", format_number(len(filtered)))
    metric_cols[1].metric("Orders", format_number(filtered["to_number"].nunique() if not filtered.empty else 0))
    metric_cols[2].metric("Sites", format_number(filtered["site_id"].nunique() if not filtered.empty else 0))
    metric_cols[3].metric("Carriers", format_number(filtered["carrier"].nunique() if not filtered.empty else 0))

    if filtered.empty:
        st.warning("No placards match the current filters.")
        return

    st.subheader("Print Preview")
    render_placard_preview(filtered)

    export_cols = [
        "pallet_id",
        "source_group",
        "to_number",
        "location_name",
        "site_id",
        "carrier",
        "pick_date",
        "ship_date",
        "delivery_date",
        "pallet_number",
        "total_pallets",
        "units",
        "lines",
        "total_weight",
        "source_file",
    ]
    placard_export = filtered[[col for col in export_cols if col in filtered.columns]].copy()
    for col in ["pick_date", "ship_date", "delivery_date"]:
        if col in placard_export.columns:
            placard_export[col] = pd.to_datetime(placard_export[col], errors="coerce").dt.date.astype(str)

    action_cols = st.columns([1, 1, 2])
    title_date = selected_dates[-1].strftime("%m-%d-%Y") if selected_dates else datetime.now().strftime("%m-%d-%Y")
    print_html = build_placard_print_html(filtered, f"{title_date} Placards")
    action_cols[0].download_button(
        "Download Print-Ready Placards HTML",
        data=print_html.encode("utf-8"),
        file_name=f"{title_date}_placards.html",
        mime="text/html",
        key="download_placard_html",
    )
    placard_xlsx, placard_mime = dataframe_download_payload(placard_export, "XLSX", "Placards")
    action_cols[1].download_button(
        "Download Placard Log XLSX",
        data=placard_xlsx,
        file_name=f"{title_date}_placard_log.xlsx",
        mime=placard_mime,
        key="download_placard_log_xlsx",
    )

    st.subheader("Placard Log")
    st.dataframe(placard_export, use_container_width=True, hide_index=True)


def render_reference_sheet_intake() -> None:
    catalog = reference_catalog()
    st.subheader("Reference Sheet Intake")
    st.caption(
        "Uploaded shared workbooks are classified here first, then reused across the specialized Transportation and Operations views."
    )
    if catalog.empty:
        st.info("Upload shared workbook exports from the sidebar to start the intake catalog.")
        return

    type_order = [
        "OTP",
        "SDT Schedule",
        "OB TO Tracker",
        "Fill Rate",
        "Core-Mark",
        "RFP Cost",
        "Tender Template",
        "Allocation History",
        "Transportation Schedule",
        "Other",
    ]
    metrics = st.columns(4)
    metrics[0].metric("Active Workbooks", format_number(len(catalog)))
    metrics[1].metric("Detected Types", format_number(catalog["workbook_type"].nunique()))
    metrics[2].metric("Sheets Indexed", format_number(catalog["sheet_count"].sum()))
    metrics[3].metric("Preview Rows", format_number(catalog["preview_rows"].sum()))

    st.markdown('<div class="gp-reference-card-grid">', unsafe_allow_html=True)
    for workbook_type in type_order:
        group = catalog[catalog["workbook_type"].eq(workbook_type)]
        if group.empty:
            continue
        latest = group.iloc[0]
        st.markdown(
            f"""
            <div class="gp-reference-card">
              <div class="gp-reference-card__type">{html.escape(workbook_type)}</div>
              <div class="gp-reference-card__title">{html.escape(str(latest["filename"]))}</div>
              <div class="gp-reference-card__meta">{len(group):,} saved version(s) | {int(latest["sheet_count"]):,} sheet(s)</div>
              <div class="gp-reference-card__cols">{html.escape(str(latest.get("preview_columns", "")))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    display = catalog[
        [
            "filename",
            "workbook_type",
            "tag",
            "created_at",
            "replaced_at",
            "replacement_count",
            "sheet_count",
            "preview_rows",
        ]
    ].copy()
    st.dataframe(display, use_container_width=True, hide_index=True)


def render_schedule_sync(ship_allocation_records: pd.DataFrame) -> None:
    st.subheader("Schedule Sync")
    st.caption(
        "Matches SDT shipping time windows to live OB TO Tracker progress. This is the first backend view meant to power the Daily Health Check page."
    )
    with st.expander("Live Refresh Controls", expanded=True):
        refresh_cols = st.columns([1, 1, 2])
        if refresh_cols[0].button("Refresh SDT + OB Tracker", type="primary", use_container_width=True):
            try:
                messages = refresh_google_sheet_types(["SDT Schedule", "OB TO Tracker", "Fill Rate"])
                for message in messages:
                    st.success(message)
                st.rerun()
            except Exception as exc:
                st.error(f"Live refresh failed: {exc}")

        auto_refresh = refresh_cols[1].toggle("Auto page refresh", value=False)
        refresh_minutes = refresh_cols[2].number_input(
            "Refresh interval minutes",
            min_value=5,
            max_value=60,
            value=10,
            step=5,
            help="This reloads the app page. Use the button for an immediate Google Sheet data pull; timed refresh is intentionally conservative to avoid Google API quota issues.",
        )
        if auto_refresh:
            components.html(
                f"""
                <script>
                  setTimeout(function() {{
                    window.parent.location.reload();
                  }}, {int(refresh_minutes) * 60 * 1000});
                </script>
                """,
                height=0,
            )
            st.caption(f"Page will reload about every {int(refresh_minutes)} minutes. Click the refresh button after a new Google tab is added.")

    context = load_daily_health_context()
    sdt = context.sdt
    sdt_source = context.sdt_source
    trans_ref, trans_schedule = read_reference_type_table("Transportation Schedule", ["Fill This Out Daily", "Sheet1"])

    if sdt.empty:
        st.info("Upload the DC1 SDT schedule workbook as a reference sheet to populate route schedule timing.")
    else:
        route_col = first_matching_column(sdt, [["route"], ["carrier"]])
        day_col = first_matching_column(sdt, [["day"]])
        ready_col = first_matching_column(sdt, [["load", "ready"], ["start", "time"]])
        depart_col = first_matching_column(sdt, [["departure"], ["end", "time"]])
        door_col = first_matching_column(sdt, [["dock", "door"], ["door"]])
        schedule_cols = [col for col in [day_col, route_col, ready_col, depart_col, door_col] if col]
        st.subheader("Route Schedule")
        if sdt_source:
            st.caption(f"Source: {sdt_source}")
        st.dataframe(sdt[schedule_cols].head(80) if schedule_cols else sdt.head(80), use_container_width=True, hide_index=True)

    st.subheader("SDT Window x OB Tracker Progress")
    st.caption(
        f"Target working day: {context.ob_target_day.strftime('%m/%d/%Y')} | Active OB tab: {context.ob_sheet or 'Not found'}"
        + (f" ({context.ob_reason})" if context.ob_reason else "")
        + (f" | OB source: {context.ob_source}" if context.ob_source else "")
    )
    if context.ob_tracker.empty:
        st.info(
            "Connect or upload the DC1 OB TO Tracker. The engine will use the previous working day tab, such as Monday 5/25 using tab 5.22."
        )
    elif sdt.empty:
        st.info("Connect or upload the DC1 SDT schedule before matching OB progress to route shipping windows.")
    else:
        progress = context.progress
        matched_columns = context.matched_columns
        if progress.empty:
            st.warning("The app could not match SDT routes to OB Tracker carriers yet. Check that both files are tagged correctly and include route/carrier columns.")
            st.json(matched_columns)
        else:
            if context.fill_source:
                st.caption(f"Fill Rate source: {context.fill_source}")
            render_schedule_progress_visual(progress, context.ob_target_day, context.ob_sheet, context.ob_source)
            open_loads = int(progress["Open TOs"].sum()) if "Open TOs" in progress.columns else 0
            loaded = int(progress["Loaded"].sum()) if "Loaded" in progress.columns else 0
            tos = int(progress["TOs"].sum()) if "TOs" in progress.columns else 0
            unmatched = int(progress["Timing Risk"].eq("Missing SDT Window").sum()) if "Timing Risk" in progress.columns else 0
            metric_cols = st.columns(4)
            metric_cols[0].metric("Routes", format_number(len(progress)))
            metric_cols[1].metric("TO Progress", f"{loaded:,} / {tos:,}")
            metric_cols[2].metric("Open TOs", format_number(open_loads))
            metric_cols[3].metric("Missing Windows", format_number(unmatched))

            if "Progress %" in progress.columns:
                st.dataframe(
                    progress,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Progress %": st.column_config.ProgressColumn(
                            "Progress %",
                            format="%.0f%%",
                            min_value=0,
                            max_value=1,
                        )
                    },
                )
            else:
                st.dataframe(progress, use_container_width=True, hide_index=True)

            csv = progress.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download Schedule Sync CSV",
                csv,
                file_name=f"dc1_schedule_sync_{context.ob_target_day.strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )

    if not ship_allocation_records.empty:
        allocations = ship_allocation_records.copy()
        for col in ["pick_date", "ship_date", "delivery_date"]:
            if col in allocations.columns:
                allocations[col] = pd.to_datetime(allocations[col], errors="coerce")
        today = pd.Timestamp.now(tz=None).normalize()
        tomorrow = today + pd.Timedelta(days=1)
        priority = allocations[
            allocations.get("ship_date", pd.Series(index=allocations.index, dtype="datetime64[ns]")).dt.normalize().isin([today, tomorrow])
        ].copy()
        if priority.empty:
            priority = allocations.sort_values("ship_date").head(75)
        st.subheader("Today / Tomorrow Tendering Priorities")
        summary = (
            priority.groupby(["source_group", "carrier", "ship_date"], dropna=False)
            .agg(
                orders=("to_number", "nunique"),
                pallets=("pallets", "sum"),
                units=("units", "sum"),
            )
            .reset_index()
            .sort_values(["ship_date", "orders"], ascending=[True, False])
        )
        st.dataframe(summary, use_container_width=True, hide_index=True)

    if not trans_schedule.empty:
        st.subheader("Transportation Daily Cadence")
        st.dataframe(trans_schedule.head(30), use_container_width=True, hide_index=True)


def render_outbound_to_control() -> None:
    st.subheader("Outbound TO Control")
    st.caption("Uses the OB TO Tracker workbook to surface status, remaining work, and pick/ship date risk before tendering.")
    ref, tracker = read_reference_type_table("OB TO Tracker", ["MASTER"])
    if tracker.empty:
        st.info("Upload DC1 OB TO Tracker.xlsx as a reference sheet to populate this view.")
        return

    carrier_col = first_matching_column(tracker, [["carrier"]])
    status_col = first_matching_column(tracker, [["status"]])
    to_col = first_matching_column(tracker, [["to"]])
    lines_col = first_matching_column(tracker, [["lines", "remaining"], ["lines"]])
    units_col = first_matching_column(tracker, [["units"]])
    pick_col = first_matching_column(tracker, [["planned", "pick"], ["pick", "date"]])
    ship_col = first_matching_column(tracker, [["planned", "ship"], ["ship", "date"]])
    work = tracker.copy()
    if lines_col:
        work["lines_remaining_num"] = pd.to_numeric(work[lines_col], errors="coerce").fillna(0)
    else:
        work["lines_remaining_num"] = 0
    if units_col:
        work["units_num"] = pd.to_numeric(work[units_col], errors="coerce").fillna(0)
    else:
        work["units_num"] = 0
    if pick_col:
        work["planned_pick_dt"] = pd.to_datetime(work[pick_col], errors="coerce")
    else:
        work["planned_pick_dt"] = pd.NaT
    if ship_col:
        work["planned_ship_dt"] = pd.to_datetime(work[ship_col], errors="coerce")
    else:
        work["planned_ship_dt"] = pd.NaT
    today = pd.Timestamp.now(tz=None).normalize()
    work["risk"] = "Normal"
    work.loc[work["planned_pick_dt"].notna() & work["planned_pick_dt"].dt.normalize().le(today + pd.Timedelta(days=1)) & work["lines_remaining_num"].gt(0), "risk"] = "Pick Risk"
    work.loc[work["planned_ship_dt"].notna() & work["planned_ship_dt"].dt.normalize().le(today + pd.Timedelta(days=1)) & work["lines_remaining_num"].gt(0), "risk"] = "Ship Risk"

    metrics = st.columns(4)
    metrics[0].metric("TOs", format_number(work[to_col].nunique() if to_col else len(work)))
    metrics[1].metric("Lines Remaining", format_number(work["lines_remaining_num"].sum()))
    metrics[2].metric("Units", format_number(work["units_num"].sum()))
    metrics[3].metric("Risk Loads", format_number(work["risk"].ne("Normal").sum()))

    if carrier_col:
        group_cols = [carrier_col]
        if status_col:
            group_cols.append(status_col)
        summary = work.groupby(group_cols, dropna=False).agg(
            tos=(to_col if to_col else work.columns[0], "nunique"),
            lines_remaining=("lines_remaining_num", "sum"),
            units=("units_num", "sum"),
            risk_loads=("risk", lambda values: int((values != "Normal").sum())),
        ).reset_index()
        st.subheader("TO Status by Carrier")
        st.dataframe(summary, use_container_width=True, hide_index=True)

    st.subheader("Loads Needing Attention")
    detail_cols = [col for col in [carrier_col, status_col, to_col, lines_col, units_col, pick_col, ship_col, "risk"] if col]
    st.dataframe(work[detail_cols].sort_values("risk", ascending=False).head(150), use_container_width=True, hide_index=True)


def render_daily_pallet_completion_visual() -> None:
    values, source = load_daily_pallet_count_values()
    pallets, selected_date = parse_daily_pallet_counts(values)
    if pallets.empty:
        st.info("Daily Pallet Counts is connected, but the PO-detail pallet block could not be parsed yet.")
        return

    target_day = previous_working_day()
    selected_label = selected_date.strftime("%m/%d/%Y") if selected_date is not None else "Selected sheet date"
    crossdock_summary, mfc_summary = summarize_crossdock_pallet_completion(pallets)
    total_pallets = len(pallets)
    complete_pallets = int(pallets["Complete"].sum())
    open_pallets = total_pallets - complete_pallets
    completion_rate = complete_pallets / total_pallets if total_pallets else 0
    total_weight = float(pallets["Pallet Weight"].sum())
    if selected_date is not None and selected_date != target_day:
        status = "Yellow"
    elif completion_rate >= 0.9:
        status = "Green"
    elif completion_rate >= 0.5:
        status = "Yellow"
    else:
        status = "Red"
    render_enterprise_module_header(
        "Pallet Completion Control",
        "Cross-Dock Pallet Completion",
        "Completion by MFC/Gusto from the Daily Pallet Counts tab, using each pallet's weight and DZL assignment.",
        status,
        f"{selected_label} | Source: {source or 'Fill Rate'}",
    )

    if selected_date is not None and selected_date != target_day:
        st.warning(
            f"Daily Pallet Counts is currently filtered to {selected_label}. "
            f"Previous working day is {target_day.strftime('%m/%d/%Y')}."
        )

    render_enterprise_kpi_grid(
        [
            {"label": "Pallet Completion", "value": format_percent(completion_rate), "delta": f"{complete_pallets:,} of {total_pallets:,}", "accent": "green" if completion_rate >= 0.9 else "yellow"},
            {"label": "Open Pallets", "value": format_number(open_pallets), "delta": "Not yet DZL complete", "accent": "yellow" if open_pallets else "green"},
            {"label": "Cross-Docks", "value": format_number(crossdock_summary["Cross-Dock"].nunique()), "delta": "Active ship ranges", "accent": "neutral"},
            {"label": "Gustos", "value": format_number(pallets["Gusto"].nunique()), "delta": "POs in view", "accent": "neutral"},
            {"label": "MFCs", "value": format_number(pallets["MFC"].nunique()), "delta": "Locations in view", "accent": "neutral"},
            {"label": "Pallet Weight", "value": format_number(total_weight), "delta": "Total lbs in view", "accent": "neutral"},
        ],
        columns=6,
    )

    visual_cols = st.columns([1.15, 1])
    with visual_cols[0]:
        st.markdown('<div class="gp-section-label">Cross-Dock Completion Rate</div>', unsafe_allow_html=True)
        chart_df = crossdock_summary.copy()
        chart_df["Completion Label"] = chart_df["Completed"].astype(int).astype(str) + " of " + chart_df["Pallets"].astype(int).astype(str)
        chart_df["Completion Status"] = pd.cut(
            chart_df["Completion %"].fillna(0),
            bins=[-0.01, 0.5, 0.9, 1.0],
            labels=["Behind", "In Progress", "Complete"],
        ).astype(str)
        fig = px.bar(
            chart_df.sort_values("Completion %", ascending=True),
            x="Completion %",
            y="Cross-Dock",
            orientation="h",
            color="Completion Status",
            text="Completion Label",
            color_discrete_map={"Complete": "#1f7a4d", "In Progress": "#a16207", "Behind": "#b42318"},
            hover_data=["Gustos", "MFCs", "Pallets", "Completed", "Open Pallets", "Weight"],
        )
        fig.update_xaxes(tickformat=".0%", range=[0, 1])
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(
            height=max(340, 34 * len(chart_df)),
            margin=dict(l=10, r=90, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#1f2937"),
            legend=dict(orientation="h", y=-0.12),
        )
        st.plotly_chart(fig, use_container_width=True)

    with visual_cols[1]:
        st.markdown('<div class="gp-section-label">Completed vs Open Pallets</div>', unsafe_allow_html=True)
        status_counts = pallets.groupby("Completion Status", dropna=False).agg(Pallets=("Pallet", "count"), Weight=("Pallet Weight", "sum")).reset_index()
        fig_status = px.pie(
            status_counts,
            names="Completion Status",
            values="Pallets",
            hole=0.58,
            color="Completion Status",
            color_discrete_map={"Complete": "#1f7a4d", "Open": "#a16207"},
            hover_data=["Weight"],
        )
        fig_status.update_layout(
            height=340,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#1f2937"),
            legend=dict(orientation="h", y=-0.08),
        )
        st.plotly_chart(fig_status, use_container_width=True)

    st.markdown('<div class="gp-section-label">MFC / Gusto Completion Detail</div>', unsafe_allow_html=True)
    mfc_display_cols = [
        "Cross-Dock",
        "MFC",
        "Location Name",
        "Gusto",
        "Route",
        "Pallet Progress",
        "Completion %",
        "Open Pallets",
        "Weight",
    ]
    st.dataframe(
        mfc_summary[[col for col in mfc_display_cols if col in mfc_summary.columns]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Completion %": st.column_config.ProgressColumn("Completion %", format="%.0f%%", min_value=0, max_value=1),
            "Weight": st.column_config.NumberColumn("Weight", format="%,.0f"),
        },
    )

    st.markdown('<div class="gp-section-label">Pallet-Level Completion Ledger</div>', unsafe_allow_html=True)
    selected_crossdocks = st.multiselect(
        "Filter cross-docks",
        sorted(pallets["Cross-Dock"].dropna().astype(str).unique()),
        default=[],
        help="Leave blank to show the full previous-day pallet ledger.",
    )
    detail = pallets.copy()
    if selected_crossdocks:
        detail = detail[detail["Cross-Dock"].astype(str).isin(selected_crossdocks)]
    detail_cols = [
        "Cross-Dock",
        "MFC",
        "Location Name",
        "Gusto",
        "Pallet Label",
        "Pallet Weight",
        "Pallet Status",
        "Completion Status",
        "Assign",
    ]
    st.dataframe(
        detail[[col for col in detail_cols if col in detail.columns]].sort_values(["Cross-Dock", "Gusto", "Pallet Label"]),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Pallet Weight": st.column_config.NumberColumn("Pallet Weight", format="%,.0f"),
        },
    )

    st.markdown('<div class="gp-section-label">Expandable GUSTO Shipment Contents</div>', unsafe_allow_html=True)
    gusto_summary = (
        detail.groupby(["Cross-Dock", "Gusto", "Location Name", "Route"], dropna=False)
        .agg(
            Pallets=("Pallet", "count"),
            Completed=("Complete", "sum"),
            Weight=("Pallet Weight", "sum"),
        )
        .reset_index()
    )
    gusto_summary["Open Pallets"] = gusto_summary["Pallets"] - gusto_summary["Completed"]
    gusto_summary["Completion %"] = gusto_summary["Completed"] / gusto_summary["Pallets"].replace(0, pd.NA)
    gusto_summary = gusto_summary.sort_values(["Open Pallets", "Weight"], ascending=[False, False])
    for _, gusto in gusto_summary.head(40).iterrows():
        label = (
            f"{gusto['Gusto']} | {gusto['Cross-Dock']} | "
            f"{int(gusto['Completed'])} of {int(gusto['Pallets'])} complete | "
            f"{format_number(gusto['Weight'])} lbs"
        )
        with st.expander(label, expanded=False):
            st.write(f"Location: {gusto['Location Name']}")
            st.write(f"Route: {gusto['Route']}")
            gusto_rows = detail[detail["Gusto"].astype(str).eq(str(gusto["Gusto"]))].copy()
            gusto_cols = ["Pallet Label", "Pallet Weight", "Pallet Status", "Completion Status", "Assign", "Location Name"]
            st.dataframe(
                gusto_rows[[col for col in gusto_cols if col in gusto_rows.columns]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Pallet Weight": st.column_config.NumberColumn("Pallet Weight", format="%,.0f"),
                },
            )


def render_fill_rate_pallet_ops() -> None:
    st.subheader("Fill Rate / Pallet Ops")
    st.caption("Uses Operation Fill Rate sheets to track pallet usage, dock activity, pallet ID issues, and manifest support.")
    render_daily_pallet_completion_visual()

    ref, raw_pif = read_google_sheet_type_table(
        "Fill Rate",
        ["Raw Airtable PIF", "Last 7 Days Raw Airtable PIF", "Daily Dashboard"],
    )
    if raw_pif.empty:
        st.info("Connect or refresh [DC1] Operation Fill Rate as a Google Sheet to populate the live pallet operations detail.")
        return

    to_col = first_matching_column(raw_pif, [["to", "number"], ["to"]])
    pallet_col = first_matching_column(raw_pif, [["pallet", "id"]])
    dock_col = first_matching_column(raw_pif, [["dock", "door"]])
    ts_col = first_matching_column(raw_pif, [["timestamp"], ["time"]])
    consolidation_col = first_matching_column(raw_pif, [["needs", "consolidation"], ["consolidation"]])

    work = raw_pif.copy()
    work["missing_pallet_id"] = work[pallet_col].isna() | work[pallet_col].astype(str).str.strip().eq("") if pallet_col else True
    if consolidation_col:
        work["needs_consolidation"] = work[consolidation_col].astype(str).str.lower().isin(["true", "yes", "y", "1"])
    else:
        work["needs_consolidation"] = False
    metrics = st.columns(4)
    metrics[0].metric("Pallet Rows", format_number(len(work)))
    metrics[1].metric("TOs", format_number(work[to_col].nunique() if to_col else 0))
    metrics[2].metric("Pallet ID Issues", format_number(work["missing_pallet_id"].sum()))
    metrics[3].metric("Needs Consolidation", format_number(work["needs_consolidation"].sum()))

    if dock_col:
        st.subheader("Dock Door Activity")
        dock_summary = work.groupby(dock_col, dropna=False).size().reset_index(name="Pallet Rows").sort_values("Pallet Rows", ascending=False)
        st.dataframe(dock_summary, use_container_width=True, hide_index=True)

    st.subheader("Consolidation / Discrepancy Queue")
    issue_rows = work[work["missing_pallet_id"] | work["needs_consolidation"]].copy()
    issue_cols = [col for col in [to_col, pallet_col, dock_col, ts_col, consolidation_col] if col]
    st.dataframe(issue_rows[issue_cols].head(150) if issue_cols else issue_rows.head(150), use_container_width=True, hide_index=True)

    if ref is not None:
        metadata = json.loads(ref.get("metadata_json") or "{}")
        manifest_sheets = [
            sheet.get("sheet_name", "")
            for sheet in metadata.get("sheets", [])
            if "manifest" in str(sheet.get("sheet_name", "")).lower() or "email helper" in str(sheet.get("sheet_name", "")).lower()
        ]
        if manifest_sheets:
            st.subheader("WARP Manifest / Send-Log Support Sheets")
            st.write(", ".join(manifest_sheets))


def render_core_mark_view() -> None:
    st.subheader("Core-Mark")
    st.caption("Tracks open PO pickup/delivery schedule, location status, temp category, and schedule exceptions.")
    ref, tracker = read_reference_type_table("Core-Mark", ["Tracker"])
    if tracker.empty:
        st.info("Upload Core-Mark Pickup Tracker.xlsx as a reference sheet to populate this view.")
        return

    po_col = first_matching_column(tracker, [["po", "number"], ["purchase", "order"]])
    status_col = first_matching_column(tracker, [["status"]])
    units_col = first_matching_column(tracker, [["units"]])
    pickup_col = first_matching_column(tracker, [["pickup", "date"]])
    delivery_col = first_matching_column(tracker, [["delivery", "date"]])
    location_col = first_matching_column(tracker, [["location", "name"], ["gopuff", "location"]])
    temp_col = first_matching_column(tracker, [["temp", "category"], ["fridge"], ["freezer"]])
    work = tracker.copy()
    work["units_num"] = pd.to_numeric(work[units_col], errors="coerce").fillna(0) if units_col else 0
    if pickup_col:
        work["pickup_dt"] = pd.to_datetime(work[pickup_col], errors="coerce")
    else:
        work["pickup_dt"] = pd.NaT
    if delivery_col:
        work["delivery_dt"] = pd.to_datetime(work[delivery_col], errors="coerce")
    else:
        work["delivery_dt"] = pd.NaT
    today = pd.Timestamp.now(tz=None).normalize()
    complete_mask = work[status_col].astype(str).str.lower().str.contains("complete|delivered|closed") if status_col else pd.Series(False, index=work.index)
    exception_mask = (~complete_mask) & (
        work["pickup_dt"].isna()
        | work["delivery_dt"].isna()
        | work["pickup_dt"].dt.normalize().le(today + pd.Timedelta(days=1))
    )
    metrics = st.columns(4)
    metrics[0].metric("POs", format_number(work[po_col].nunique() if po_col else len(work)))
    metrics[1].metric("Open POs", format_number((~complete_mask).sum()))
    metrics[2].metric("Units", format_number(work["units_num"].sum()))
    metrics[3].metric("Exceptions", format_number(exception_mask.sum()))

    if status_col:
        st.subheader("Status by Location")
        group_cols = [col for col in [location_col, status_col] if col]
        summary = work.groupby(group_cols, dropna=False).agg(pos=(po_col if po_col else work.columns[0], "nunique"), units=("units_num", "sum")).reset_index()
        st.dataframe(summary, use_container_width=True, hide_index=True)

    st.subheader("Schedule Exceptions")
    detail_cols = [col for col in [po_col, status_col, location_col, temp_col, pickup_col, delivery_col, units_col] if col]
    st.dataframe(work.loc[exception_mask, detail_cols].head(150), use_container_width=True, hide_index=True)


def filter_by_lane(df: pd.DataFrame, lane: str) -> pd.DataFrame:
    if df.empty or not lane:
        return pd.DataFrame()
    lane_col = first_matching_column(df, [["lane"], ["route"], ["carrier"]])
    if not lane_col:
        return pd.DataFrame()
    return df[df[lane_col].astype(str).str.casefold().str.contains(str(lane).casefold(), regex=False, na=False)].copy()


def load_sdt_windows_for_lane(lane: str) -> pd.DataFrame:
    sdt_google = latest_google_sheet_by_type("SDT Schedule")
    sdt_sheets = list_google_sheet_names(sdt_google)
    selected_sdt_sheet = next((sheet for sheet in sdt_sheets if sheet.casefold() in {"sheet1", "sdt"}), sdt_sheets[0] if sdt_sheets else "")
    sdt = read_google_sheet_named_table(sdt_google, selected_sdt_sheet) if selected_sdt_sheet else pd.DataFrame()
    if sdt.empty:
        return pd.DataFrame()
    route_col = first_matching_column(sdt, [["route"], ["carrier"]])
    if not route_col:
        return pd.DataFrame()
    matches = sdt[sdt[route_col].astype(str).str.casefold().str.contains(str(lane).casefold(), regex=False, na=False)].copy()
    if matches.empty:
        return matches
    day_col = first_matching_column(matches, [["day"]])
    ready_col = first_matching_column(matches, [["load", "ready"], ["ready", "time"], ["start", "time"]])
    depart_col = first_matching_column(matches, [["departure"], ["depart"], ["end", "time"]])
    door_col = first_matching_column(matches, [["dock", "door"], ["door"]])
    display = matches[[col for col in [route_col, day_col, ready_col, depart_col, door_col] if col]].drop_duplicates()
    return display.rename(
        columns={
            route_col: "SDT Route",
            day_col or "": "SDT Day",
            ready_col or "": "Load Ready Time",
            depart_col or "": "Departure Time",
            door_col or "": "Dock Door",
        }
    )


def render_market_profile_result_links(filtered: pd.DataFrame, search: str) -> None:
    if filtered.empty:
        st.info("No market profile matches found.")
        return
    embed_mode = get_site_embed_mode()
    lane_cards = []
    for _, row in filtered[["Lane"]].dropna().drop_duplicates().head(8).iterrows():
        lane = cell_text(row.get("Lane"))
        if not lane:
            continue
        lane_rows = filtered[filtered["Lane"].astype(str).eq(lane)]
        href = app_href("Operations", "Market Profiles", profile_type="lane", profile_key=lane, profile_search=search, site_embed=embed_mode)
        lane_cards.append(
            f'<a class="gp-profile-link-card" href="{href}" target="_self"><span>Lane</span><strong>{html.escape(lane)}</strong>'
            f'<small>{len(lane_rows):,} MFC(s) | {format_number(lane_rows.get("Avg Pallets", pd.Series(dtype=float)).sum())} avg pallets</small></a>'
        )
    mfc_cards = []
    for _, row in filtered.head(12).iterrows():
        location_name = cell_text(row.get("Location Name"))
        if not location_name:
            continue
        href = app_href("Operations", "Market Profiles", profile_type="mfc", profile_key=location_name, profile_search=search, site_embed=embed_mode)
        mfc_cards.append(
            f'<a class="gp-profile-link-card" href="{href}" target="_self"><span>MFC Profile</span><strong>{html.escape(cell_text(row.get("Site")) or location_name)}</strong>'
            f'<small>{html.escape(location_name)} | Lane {html.escape(cell_text(row.get("Lane")))}</small></a>'
        )
    if lane_cards or mfc_cards:
        st.markdown('<div class="gp-section-label">Clickable Profile Results</div>', unsafe_allow_html=True)
        st.markdown('<div class="gp-profile-link-grid">' + "".join(lane_cards + mfc_cards) + "</div>", unsafe_allow_html=True)


def render_field_table(title: str, values: dict[str, object]) -> None:
    rows = [{"Field": field, "Value": cell_text(value)} for field, value in values.items() if cell_text(value)]
    if rows:
        st.markdown(f'<div class="gp-section-label">{html.escape(title)}</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def first_nonblank(row: pd.Series, columns: list[str], default: str = "") -> str:
    for col in columns:
        value = cell_text(row.get(col))
        if value:
            return value
    return default


def render_profile_panel_grid(panels: list[dict[str, object]]) -> None:
    cards = []
    for panel in panels:
        title = cell_text(panel.get("title"))
        items = panel.get("items") or {}
        if not isinstance(items, dict):
            continue
        rows = []
        for label, value in items.items():
            display = cell_text(value)
            if display:
                rows.append(
                    f'<div class="gp-profile-panel__row"><span>{html.escape(str(label))}</span>'
                    f"<strong>{html.escape(display)}</strong></div>"
                )
        if not rows:
            continue
        cards.append(
            f'<section class="gp-profile-panel"><div class="gp-profile-panel__title">{html.escape(title)}</div>'
            + "".join(rows)
            + "</section>"
        )
    if cards:
        st.markdown('<div class="gp-profile-panel-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)


def render_profile_source_fields(row: pd.Series, source_prefixes: list[str]) -> None:
    rows = []
    for col, value in row.items():
        if not any(str(col).startswith(prefix) for prefix in source_prefixes):
            continue
        display = cell_text(value)
        if display:
            rows.append({"Field": str(col), "Value": display})
    if rows:
        with st.expander("Additional source fields", expanded=False):
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def profile_search_terms(search: str) -> list[str]:
    return [term for term in re.findall(r"[a-z0-9]+", cell_text(search).casefold()) if len(term) >= 2]


def score_market_profile_rows(profile: pd.DataFrame, search: str) -> pd.Series:
    query = compact_location_key(search)
    if not query or profile.empty:
        return pd.Series(0.0, index=profile.index)
    terms = profile_search_terms(search)
    searchable_cols = [
        col
        for col in [
            "Lane",
            "Site",
            "Location Name",
            "Location ID",
            "Current 3PL",
            "Previous 3PL",
            "SCBP",
            "Slack Channel",
            "City",
            "State",
            "Market",
            "Full Address",
            "Site Leader",
            "Regional Manager",
            "Site Type",
            "Site Status",
            "Network Role",
            "Active GUSTO",
            "Active Lane",
            "Hypercare Status",
            "Hypercare Action",
        ]
        if col in profile.columns
    ]
    if not searchable_cols:
        return pd.Series(0.0, index=profile.index)

    haystack = profile[searchable_cols].fillna("").astype(str).agg(" | ".join, axis=1)
    compact_haystack = haystack.map(compact_location_key)
    scores = pd.Series(0.0, index=profile.index)
    scores += compact_haystack.str.contains(query, regex=False, na=False).astype(float) * 80

    for term in terms:
        scores += compact_haystack.str.contains(term, regex=False, na=False).astype(float) * 10
        exact_col_match = pd.Series(False, index=profile.index)
        for col in searchable_cols:
            exact_col_match = exact_col_match | profile[col].astype(str).map(compact_location_key).eq(term)
        scores += exact_col_match.astype(float) * 25

    numeric_terms = [term for term in terms if term.isdigit()]
    for term in numeric_terms:
        for col in ["Location ID", "Site", "Location Name", "Full Address"]:
            if col in profile.columns:
                scores += profile[col].astype(str).str.contains(term, regex=False, na=False).astype(float) * 24

    # Lightweight fuzzy pass for typos and partial location names.
    for index, text in compact_haystack.items():
        if scores.at[index] > 0:
            continue
        tokens = set(text.split())
        best = max((SequenceMatcher(None, query, token).ratio() for token in tokens), default=0)
        if best >= 0.82:
            scores.at[index] = best * 18
    return scores


def append_site_information_profiles(profile: pd.DataFrame, site_info: pd.DataFrame) -> pd.DataFrame:
    if site_info.empty:
        return profile
    base = profile.copy()
    if "_site_id_key" not in base.columns:
        base["_site_id_key"] = base.get("Location ID", pd.Series("", index=base.index)).map(compact_site_id)
    if "_location_key" not in base.columns:
        base["_location_key"] = base.get("Location Name", pd.Series("", index=base.index)).map(compact_location_key)

    existing_site_keys = set(base["_site_id_key"].astype(str).str.strip())
    existing_location_keys = set(base["_location_key"].astype(str).str.strip())
    additions = []
    for _, source in site_info.iterrows():
        site_key = cell_text(source.get("_site_id_key"))
        location_key = cell_text(source.get("_location_key"))
        if (site_key and site_key in existing_site_keys) or (location_key and location_key in existing_location_keys):
            continue
        location = first_nonblank(source, ["Site Info Location Name", "Active Location", "Hypercare Location"])
        location_id = first_nonblank(source, ["Site Info Location ID", "Active Site ID", "Hypercare Site ID"])
        lane = first_nonblank(source, ["Site Info Lane", "Active Lane"])
        if not any([location, location_id, lane, cell_text(source.get("Full Address"))]):
            continue
        row = source.to_dict()
        row.update(
            {
                "Lane": lane,
                "Location Name": location or cell_text(source.get("Full Address")) or f"Site {location_id}",
                "Location ID": location_id,
                "Site": format_mfc_site_label(location) or (f"Site {location_id}" if location_id else lane),
                "Delivery Day": "",
                "Delivery Window": "",
                "Avg Pallets": 0,
                "Avg Weight": 0,
                "Profile Source": "Site Information",
                "_site_id_key": site_key,
                "_location_key": location_key,
            }
        )
        additions.append(row)
    if not additions:
        return base
    added = pd.DataFrame(additions)
    all_columns = list(dict.fromkeys([*base.columns, *added.columns]))
    return pd.concat([base.reindex(columns=all_columns), added.reindex(columns=all_columns)], ignore_index=True)


def render_embed_catalog() -> None:
    rows = [
        {"Embed Target": key, "Google Sites Placement": label, "URL Parameter": f"?site_embed={key}&embed=true"}
        for key, label in EMBED_TARGETS.items()
    ]
    st.subheader("Google Sites Embed Targets")
    st.caption("Use these focused views when placing Streamlit modules into Google Sites.")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def compact_location_key(value: object) -> str:
    text = cell_text(value).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def compact_site_id(value: object) -> str:
    text = cell_text(value)
    if not text:
        return ""
    parsed = parse_mfc_number(text)
    if parsed:
        return parsed
    match = re.search(r"\b(\d{1,5})\b", text)
    return match.group(1) if match else ""


def read_google_sheet_best_table(
    workbook_type: str,
    preferred_tokens: list[str] | None = None,
) -> tuple[pd.Series | None, pd.DataFrame, str]:
    connection = latest_google_sheet_by_type(workbook_type)
    if connection is None:
        return None, pd.DataFrame(), ""
    values_by_sheet = json.loads(connection.get("values_json") or "{}")
    if not values_by_sheet:
        return connection, pd.DataFrame(), ""
    preferred_tokens = [token.casefold() for token in (preferred_tokens or [])]
    candidates: list[tuple[int, int, str, pd.DataFrame]] = []
    for sheet_name, values in values_by_sheet.items():
        if not values:
            continue
        table = infer_header_table(pd.DataFrame(values))
        if table.empty:
            continue
        token_score = int(any(token in str(sheet_name).casefold() for token in preferred_tokens))
        candidates.append((token_score, len(table), str(sheet_name), table))
    if not candidates:
        return connection, pd.DataFrame(), ""
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    _, _, sheet_name, table = candidates[0]
    return connection, table, sheet_name


def build_site_information_context() -> tuple[pd.DataFrame, str]:
    connection, site_info, sheet_name = read_google_sheet_best_table(
        "Site Information",
        ["site", "market", "information"],
    )
    if site_info.empty:
        connection, site_info, sheet_name = read_google_sheet_best_table("Other", ["site", "market", "information"])
    if site_info.empty:
        return pd.DataFrame(), ""

    location_col = first_matching_column(site_info, [["location", "name"], ["site", "name"]])
    site_id_col = first_matching_column(site_info, [["location", "id"], ["site", "id"]])
    lane_col = first_matching_column(site_info, [["market"], ["lane"]])
    keep_map = {
        "Site Info Lane": lane_col,
        "Site Info Location Name": location_col,
        "Site Info Location ID": site_id_col,
        "Site Leader": first_matching_column(site_info, [["site", "leader"]]),
        "Regional Manager": first_matching_column(site_info, [["regional", "manager"]]),
        "Full Address": first_matching_column(site_info, [["full", "address"]]),
        "SCBP": first_matching_column(site_info, [["scbp"]]),
        "Site Type": first_matching_column(site_info, [["site", "type"], ["location", "type"], ["type"]]),
        "Site Status": first_matching_column(site_info, [["status"], ["site", "status"]]),
        "Network Role": first_matching_column(site_info, [["network", "role"], ["role"]]),
        "City": first_matching_column(site_info, [["city"]]),
        "State": first_matching_column(site_info, [["state"]]),
        "Postal Code": first_matching_column(site_info, [["postal"], ["zip"]]),
    }
    keep_cols = list(dict.fromkeys(col for col in keep_map.values() if col))
    if not keep_cols:
        return pd.DataFrame(), sheet_name
    result = site_info[keep_cols].copy()
    result = result.rename(columns={source: target for target, source in keep_map.items() if source})
    result["_site_id_key"] = result.get("Site Info Location ID", pd.Series("", index=result.index)).map(compact_site_id)
    result["_location_key"] = result.get("Site Info Location Name", pd.Series("", index=result.index)).map(compact_location_key)
    return result.drop_duplicates(["_site_id_key", "_location_key"]), sheet_name


def build_allocation_operating_context() -> tuple[pd.DataFrame, str]:
    connection, allocations, sheet_name = read_google_sheet_best_table(
        "Allocation History",
        ["allocation", "dc1", "daily"],
    )
    if allocations.empty:
        return pd.DataFrame(), ""

    location_col = first_matching_column(allocations, [["location", "name"], ["destination"], ["mfc"]])
    site_id_col = first_matching_column(allocations, [["site", "id"], ["location", "id"]])
    gusto_col = first_matching_column(allocations, [["gusto"], ["po", "number"], ["to", "number"], ["order"]])
    lane_col = first_matching_column(allocations, [["lane"], ["route"], ["carrier"]])
    status_col = first_matching_column(allocations, [["status"], ["assign"]])
    pallet_col = first_matching_column(allocations, [["pallet", "count"], ["pallets"], ["pallet"]])
    weight_col = first_matching_column(allocations, [["weight"]])
    date_col = first_matching_column(allocations, [["ship", "date"], ["planned", "ship"], ["date"]])
    keep_map = {
        "Active GUSTO": gusto_col,
        "Active Location": location_col,
        "Active Site ID": site_id_col,
        "Active Lane": lane_col,
        "Active Status": status_col,
        "Active Pallets": pallet_col,
        "Active Weight": weight_col,
        "Active Ship Date": date_col,
    }
    keep_cols = list(dict.fromkeys(col for col in keep_map.values() if col))
    if not keep_cols:
        return pd.DataFrame(), sheet_name
    result = allocations[keep_cols].copy()
    result = result.rename(columns={source: target for target, source in keep_map.items() if source})
    result["_site_id_key"] = result.get("Active Site ID", pd.Series("", index=result.index)).map(compact_site_id)
    if not result["_site_id_key"].astype(str).str.strip().any():
        result["_site_id_key"] = result.get("Active Location", pd.Series("", index=result.index)).map(compact_site_id)
    result["_location_key"] = result.get("Active Location", pd.Series("", index=result.index)).map(compact_location_key)
    result["_has_order"] = result.get("Active GUSTO", pd.Series("", index=result.index)).astype(str).str.strip().ne("")
    result = result[result["_has_order"]].copy() if result["_has_order"].any() else result
    return result.drop_duplicates(["_site_id_key", "_location_key"], keep="last"), sheet_name


def build_sop_hypercare_context() -> tuple[pd.DataFrame, str]:
    connection, hypercare, sheet_name = read_google_sheet_best_table("S&OP", ["hypercare", "dashboard", "site"])
    if hypercare.empty:
        return pd.DataFrame(), ""
    location_col = first_matching_column(hypercare, [["location", "name"], ["site"], ["mfc"]])
    site_id_col = first_matching_column(hypercare, [["location", "id"], ["site", "id"]])
    status_col = first_matching_column(hypercare, [["status"], ["health"], ["risk"]])
    action_col = first_matching_column(hypercare, [["action"], ["next", "step"], ["note"]])
    keep_map = {
        "Hypercare Location": location_col,
        "Hypercare Site ID": site_id_col,
        "Hypercare Status": status_col,
        "Hypercare Action": action_col,
        "Hypercare SCBP": first_matching_column(hypercare, [["scbp"]]),
        "Hypercare Site Leader": first_matching_column(hypercare, [["site", "leader"], ["leader"]]),
        "Hypercare Regional Manager": first_matching_column(hypercare, [["regional", "manager"]]),
        "Hypercare Owner": first_matching_column(hypercare, [["owner"]]),
        "Hypercare Priority": first_matching_column(hypercare, [["priority"]]),
    }
    metric_tokens = ["metric", "score", "rate", "orders", "units", "pallet", "volume", "late", "miss", "risk", "nyp", "fill", "dt", "sla"]
    for col in hypercare.columns:
        if col in keep_map.values():
            continue
        col_text = str(col).casefold()
        numeric_ratio = pd.to_numeric(hypercare[col], errors="coerce").notna().mean()
        if numeric_ratio >= 0.35 or any(token in col_text for token in metric_tokens):
            keep_map[f"S&OP {col}"] = col
        if len([key for key in keep_map if key.startswith("S&OP ")]) >= 10:
            break
    keep_cols = list(dict.fromkeys(col for col in keep_map.values() if col))
    if not keep_cols:
        return pd.DataFrame(), sheet_name
    result = hypercare[keep_cols].copy()
    result = result.rename(columns={source: target for target, source in keep_map.items() if source})
    result["_site_id_key"] = result.get("Hypercare Site ID", pd.Series("", index=result.index)).map(compact_site_id)
    result["_location_key"] = result.get("Hypercare Location", pd.Series("", index=result.index)).map(compact_location_key)
    return result.drop_duplicates(["_site_id_key", "_location_key"], keep="last"), sheet_name


def fill_context_by_profile_keys(base: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    """Fill profile rows from another sheet using site number first, location text second."""
    if context.empty:
        return base
    result = base.copy()
    context_cols = [col for col in context.columns if col not in {"_site_id_key", "_location_key", "_has_order"}]
    for col in context_cols:
        if col not in result.columns:
            result[col] = ""

    def blank_mask(series: pd.Series) -> pd.Series:
        text = series.astype(str).str.strip()
        return series.isna() | text.eq("") | text.str.casefold().isin({"nan", "none", "nat"})

    for key_col in ["_site_id_key", "_location_key"]:
        if key_col not in result.columns or key_col not in context.columns:
            continue
        keyed_context = context[context[key_col].astype(str).str.strip().ne("")].copy()
        if keyed_context.empty:
            continue
        keyed_context = keyed_context.drop_duplicates(key_col, keep="last").set_index(key_col)
        row_keys = result[key_col].astype(str)
        for col in context_cols:
            if col not in keyed_context.columns:
                continue
            mapped = row_keys.map(keyed_context[col])
            result[col] = result[col].where(~blank_mask(result[col]), mapped)
    return result


def enrich_market_profile_operating_context(profile: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    enriched = profile.copy()
    enriched["_site_id_key"] = enriched.get("Location ID", pd.Series("", index=enriched.index)).map(compact_site_id)
    enriched["_location_key"] = enriched.get("Location Name", pd.Series("", index=enriched.index)).map(compact_location_key)
    context_sources: dict[str, str] = {}

    site_info, site_sheet = build_site_information_context()
    if not site_info.empty:
        context_sources["Site Information"] = site_sheet
        enriched = fill_context_by_profile_keys(enriched, site_info)

    allocations, allocation_sheet = build_allocation_operating_context()
    if not allocations.empty:
        context_sources["Allocation History"] = allocation_sheet
        enriched = fill_context_by_profile_keys(enriched, allocations.drop(columns=["_has_order"], errors="ignore"))

    hypercare, hypercare_sheet = build_sop_hypercare_context()
    if not hypercare.empty:
        context_sources["S&OP Hypercare"] = hypercare_sheet
        enriched = fill_context_by_profile_keys(enriched, hypercare)

    return enriched.drop(columns=["_site_id_key", "_location_key"], errors="ignore"), context_sources


def render_operating_profile_gallery(filtered: pd.DataFrame, search: str) -> None:
    if filtered.empty:
        return
    embed_mode = get_site_embed_mode()
    cards = []
    for _, row in filtered.head(18).iterrows():
        location_name = cell_text(row.get("Location Name"))
        if not location_name:
            continue
        href = app_href("Operations", "Market Profiles", profile_type="mfc", profile_key=location_name, profile_search=search, site_embed=embed_mode)
        gusto = cell_text(row.get("Active GUSTO")) or "No active GUSTO"
        status = cell_text(row.get("Active Status")) or "Reference profile"
        lane = cell_text(row.get("Lane"))
        leader = cell_text(row.get("Site Leader")) or cell_text(row.get("SCBP"))
        cards.append(
            f'<a class="gp-operating-card" href="{href}" target="_self">'
            f'<div class="gp-operating-card__eyebrow">{html.escape(cell_text(row.get("Site")) or "MFC")}</div>'
            f'<div class="gp-operating-card__title">{html.escape(location_name)}</div>'
            f'<div class="gp-operating-card__meta">Lane {html.escape(lane or "Unmapped")} | {html.escape(status)}</div>'
            f'<div class="gp-operating-card__gusto">{html.escape(gusto)}</div>'
            f'<div class="gp-operating-card__footer">{html.escape(leader or "Owner not listed")}</div>'
            f'</a>'
        )
    if cards:
        st.markdown('<div class="gp-section-label">MFC Operating Gallery</div>', unsafe_allow_html=True)
        st.markdown('<div class="gp-operating-gallery">' + "".join(cards) + "</div>", unsafe_allow_html=True)


def mfc_profile_market_prefix(row: pd.Series) -> str:
    for col in ["Location Name", "Site Info Location Name", "Active Location", "Site"]:
        prefix = site_market_prefix(row.get(col))
        if prefix:
            return prefix
    for col in ["Lane", "Active Lane", "Site Info Lane"]:
        text = cell_text(row.get(col)).upper()
        for token in MFC_MARKET_COORDS:
            if re.search(rf"\b{re.escape(token)}\b", text):
                return token
    return ""


def build_mfc_profile_map_data(profile: pd.DataFrame, focus: pd.DataFrame | None = None) -> pd.DataFrame:
    if profile.empty:
        return pd.DataFrame()
    focus = focus if focus is not None else pd.DataFrame()
    nodes = profile.copy()
    nodes["market_prefix"] = nodes.apply(mfc_profile_market_prefix, axis=1)
    nodes = nodes[nodes["market_prefix"].isin(MFC_MARKET_COORDS)].copy()
    if nodes.empty:
        return nodes

    nodes["latitude"] = nodes["market_prefix"].map(lambda prefix: MFC_MARKET_COORDS[prefix][0])
    nodes["longitude"] = nodes["market_prefix"].map(lambda prefix: MFC_MARKET_COORDS[prefix][1])
    nodes["Market Node"] = nodes["market_prefix"].map(lambda prefix: MFC_MARKET_COORDS[prefix][2])
    nodes["Node Label"] = nodes.get("Site", pd.Series("", index=nodes.index)).map(cell_text)
    nodes["Node Label"] = nodes["Node Label"].where(nodes["Node Label"].str.strip().ne(""), nodes.get("Location Name", pd.Series("", index=nodes.index)).map(cell_text))
    nodes["Active GUSTO Display"] = nodes.get("Active GUSTO", pd.Series("", index=nodes.index)).map(cell_text).replace("", "No active GUSTO")
    nodes["Carrier / Lane"] = nodes.get("Lane", pd.Series("", index=nodes.index)).map(cell_text)
    nodes["Carrier / Lane"] = nodes["Carrier / Lane"].where(nodes["Carrier / Lane"].str.strip().ne(""), nodes.get("Active Lane", pd.Series("", index=nodes.index)).map(cell_text))

    nodes["_map_key"] = nodes.get("Location Name", pd.Series("", index=nodes.index)).map(compact_location_key)
    nodes["_site_key"] = nodes.get("Location ID", pd.Series("", index=nodes.index)).map(compact_site_id)
    focus_keys = set()
    focus_site_keys = set()
    if focus is not None and not focus.empty:
        focus_keys = {
            key
            for key in focus.get("Location Name", pd.Series("", index=focus.index)).map(compact_location_key)
            if key
        }
        focus_site_keys = {
            key
            for key in focus.get("Location ID", pd.Series("", index=focus.index)).map(compact_site_id)
            if key
        }

    has_active = nodes.get("Active GUSTO", pd.Series("", index=nodes.index)).map(cell_text).str.strip().ne("")
    is_focus = nodes["_map_key"].isin(focus_keys) | nodes["_site_key"].isin(focus_site_keys)
    nodes["Map Status"] = "Reference Node"
    nodes.loc[has_active, "Map Status"] = "Active GUSTO"
    nodes.loc[is_focus, "Map Status"] = "Focused Result"
    nodes["Node Size"] = 10
    nodes.loc[has_active, "Node Size"] = 18
    nodes.loc[is_focus, "Node Size"] = 26

    nodes["_rank"] = nodes.groupby("market_prefix").cumcount()
    nodes["latitude"] = nodes["latitude"] + ((nodes["_rank"] % 5) - 2) * 0.08
    nodes["longitude"] = nodes["longitude"] + (((nodes["_rank"] // 5) % 5) - 2) * 0.11
    return nodes


def render_mfc_network_map(profile: pd.DataFrame, focus: pd.DataFrame | None = None, title: str = "MFC Network Map") -> None:
    map_data = build_mfc_profile_map_data(profile, focus)
    st.markdown(f'<div class="gp-section-label">{html.escape(title)}</div>', unsafe_allow_html=True)
    if map_data.empty:
        st.info("MFC map is waiting on market/location fields from the Training Cheat Sheet or Site Information sheet.")
        return

    focus_data = map_data[map_data["Map Status"].eq("Focused Result")].copy()
    center_source = focus_data if not focus_data.empty else map_data
    projection_scale = 4.0 if focus is not None and not focus.empty else 2.4
    hover_data = {
        "Location Name": True,
        "Carrier / Lane": True,
        "Active GUSTO Display": True,
        "latitude": False,
        "longitude": False,
        "Node Size": False,
    }
    for optional_col in ["Active Status", "Active Pallets", "Active Ship Date", "Full Address"]:
        if optional_col in map_data.columns:
            hover_data[optional_col] = True
    fig = px.scatter_geo(
        map_data,
        lat="latitude",
        lon="longitude",
        size="Node Size",
        color="Map Status",
        hover_name="Node Label",
        hover_data=hover_data,
        color_discrete_map={
            "Focused Result": "#b42318",
            "Active GUSTO": "#2f6f4e",
            "Reference Node": "#64748b",
        },
        scope="usa",
    )
    fig.update_traces(marker=dict(line=dict(width=1.5, color="#ffffff"), opacity=0.88))
    fig.update_layout(
        height=430,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=-0.04),
        geo=dict(
            bgcolor="rgba(0,0,0,0)",
            landcolor="#edf2f7",
            lakecolor="#dbeafe",
            subunitcolor="#cbd5e1",
            center=dict(lat=float(center_source["latitude"].mean()), lon=float(center_source["longitude"].mean())),
            projection=dict(scale=projection_scale),
        ),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Map nodes use MFC market prefixes with available site/profile enrichment; active GUSTO context comes from the Allocation History connection when present.")


def render_market_profile_detail(
    profile: pd.DataFrame,
    linehaul: pd.DataFrame,
    market_breakdown: pd.DataFrame,
    selected_type: str,
    selected_key: str,
) -> None:
    back_href = app_href(
        "Operations",
        "Market Profiles",
        profile_search=get_query_param("profile_search"),
        site_embed=get_site_embed_mode(),
    )
    selected_type = selected_type.casefold()
    selected_key = cell_text(selected_key)
    if selected_type == "lane":
        lane_rows = profile[profile["Lane"].astype(str).str.casefold().eq(selected_key.casefold())].copy()
        if lane_rows.empty:
            lane_rows = profile[profile["Lane"].astype(str).str.casefold().str.contains(selected_key.casefold(), regex=False, na=False)].copy()
        if lane_rows.empty:
            st.warning("That lane profile was not found in the Training Cheat Sheet cache.")
            st.markdown(f'<a class="gp-profile-back-link" href="{back_href}" target="_self">Back to Market Profiles</a>', unsafe_allow_html=True)
            return
        lane = cell_text(lane_rows["Lane"].iloc[0])
        st.markdown(
            f'<div class="gp-profile-hero"><div><span>Lane Profile</span><strong>{html.escape(lane)}</strong>'
            f'<small>{len(lane_rows):,} MFC(s) connected to this lane</small></div>'
            f'<a href="{back_href}" target="_self">Back to Search</a></div>',
            unsafe_allow_html=True,
        )
        render_enterprise_kpi_grid(
            [
                {"label": "MFCs", "value": format_number(len(lane_rows)), "delta": "Final-mile sites", "accent": "neutral"},
                {"label": "Active GUSTOs", "value": format_number(lane_rows.get("Active GUSTO", pd.Series(dtype=str)).astype(str).str.strip().ne("").sum()), "delta": "Current allocation matches", "accent": "green"},
                {"label": "Avg Pallets", "value": format_number(lane_rows.get("Avg Pallets", pd.Series(dtype=float)).sum()), "delta": "YTD per delivery", "accent": "green"},
                {"label": "Avg Weight", "value": format_number(lane_rows.get("Avg Weight", pd.Series(dtype=float)).sum()), "delta": "YTD per delivery", "accent": "green"},
            ],
            columns=4,
        )
        render_mfc_network_map(profile, lane_rows, "Lane MFC Node Map")
        active_cols = ["Site", "Location Name", "Active GUSTO", "Active Status", "Active Pallets", "Active Weight", "Active Ship Date", "Hypercare Status"]
        active_rows = lane_rows[lane_rows.get("Active GUSTO", pd.Series("", index=lane_rows.index)).astype(str).str.strip().ne("")].copy()
        if not active_rows.empty:
            st.markdown('<div class="gp-section-label">Active GUSTOs In This Lane</div>', unsafe_allow_html=True)
            st.dataframe(active_rows[[col for col in active_cols if col in active_rows.columns]], use_container_width=True, hide_index=True)
        sdt_windows = load_sdt_windows_for_lane(lane)
        if not sdt_windows.empty:
            st.markdown('<div class="gp-section-label">SDT Shipping Windows</div>', unsafe_allow_html=True)
            st.dataframe(sdt_windows, use_container_width=True, hide_index=True)
        linehaul_rows = filter_by_lane(linehaul, lane)
        if not linehaul_rows.empty:
            st.markdown('<div class="gp-section-label">Linehaul Profile</div>', unsafe_allow_html=True)
            st.dataframe(linehaul_rows, use_container_width=True, hide_index=True)
        market_rows = filter_by_lane(market_breakdown, lane)
        if not market_rows.empty:
            st.markdown('<div class="gp-section-label">Carrier / Market Breakdown</div>', unsafe_allow_html=True)
            st.dataframe(market_rows, use_container_width=True, hide_index=True)
        display_cols = ["Site", "Location Name", "Location ID", "Delivery Day", "Delivery Window", "Avg Pallets", "Avg Weight", "Full Address", "City", "State", "Region", "Market"]
        st.markdown('<div class="gp-section-label">MFCs Serviced By This Lane</div>', unsafe_allow_html=True)
        st.dataframe(lane_rows[[col for col in display_cols if col in lane_rows.columns]], use_container_width=True, hide_index=True)
        return

    if selected_type == "mfc":
        mfc_rows = profile[
            profile["Location Name"].astype(str).str.casefold().eq(selected_key.casefold())
            | profile["Site"].astype(str).str.casefold().eq(selected_key.casefold())
        ].copy()
        if mfc_rows.empty:
            mfc_rows = profile[profile["Location Name"].astype(str).str.casefold().str.contains(selected_key.casefold(), regex=False, na=False)].copy()
        if mfc_rows.empty:
            scores = score_market_profile_rows(profile, selected_key)
            mfc_rows = profile[scores > 0].assign(_search_score=scores[scores > 0]).sort_values("_search_score", ascending=False).head(1)
        if mfc_rows.empty:
            st.warning("That MFC profile was not found in the connected profile sources.")
            st.markdown(f'<a class="gp-profile-back-link" href="{back_href}" target="_self">Back to Market Profiles</a>', unsafe_allow_html=True)
            return
        row = mfc_rows.iloc[0]
        lane = first_nonblank(row, ["Lane", "Active Lane", "Site Info Lane"])
        location_name = first_nonblank(row, ["Location Name", "Site Info Location Name", "Active Location", "Hypercare Location"], "MFC profile")
        site_label = first_nonblank(row, ["Site", "Location ID", "Site Info Location ID"])
        active_gusto = first_nonblank(row, ["Active GUSTO"], "No active GUSTO")
        active_status = first_nonblank(row, ["Active Status", "Hypercare Status", "Site Status"], "Reference profile")
        address = first_nonblank(row, ["Full Address", "Street Address"])
        st.markdown(
            f'<div class="gp-profile-hero"><div><span>MFC Profile</span><strong>{html.escape(location_name)}</strong>'
            f'<small>{html.escape(site_label or "Site")} | Lane {html.escape(lane or "Unmapped")}</small></div>'
            f'<a href="{back_href}" target="_self">Back to Search</a></div>',
            unsafe_allow_html=True,
        )
        render_enterprise_kpi_grid(
            [
                {"label": "Lane", "value": lane or "Unmapped", "delta": "Shipping region", "accent": "neutral"},
                {"label": "Active GUSTO", "value": active_gusto, "delta": active_status, "accent": "green" if active_gusto != "No active GUSTO" else "neutral"},
                {"label": "Avg Pallets", "value": format_number(row.get("Avg Pallets")), "delta": "Training profile", "accent": "yellow"},
                {"label": "Hypercare", "value": first_nonblank(row, ["Hypercare Status"], "Not flagged"), "delta": first_nonblank(row, ["Hypercare Priority", "Hypercare Owner"], "S&OP context"), "accent": "red" if cell_text(row.get("Hypercare Status")) else "green"},
            ],
            columns=4,
        )
        render_profile_panel_grid(
            [
                {
                    "title": "Operating Now",
                    "items": {
                        "GUSTO / Order": row.get("Active GUSTO"),
                        "Allocation Status": row.get("Active Status"),
                        "Pallets": row.get("Active Pallets"),
                        "Weight": row.get("Active Weight"),
                        "Planned Ship Date": row.get("Active Ship Date"),
                        "Current Lane": first_nonblank(row, ["Active Lane", "Lane"]),
                    },
                },
                {
                    "title": "People",
                    "items": {
                        "Site Leader": first_nonblank(row, ["Site Leader", "Hypercare Site Leader"]),
                        "Regional Manager": first_nonblank(row, ["Regional Manager", "Hypercare Regional Manager"]),
                        "SCBP": first_nonblank(row, ["SCBP", "Hypercare SCBP"]),
                        "Slack Channel": row.get("Slack Channel"),
                    },
                },
                {
                    "title": "Location",
                    "items": {
                        "Address": address,
                        "City / State": ", ".join(part for part in [cell_text(row.get("City")), cell_text(row.get("State"))] if part),
                        "Hours": row.get("Hours of Operation"),
                        "Site Type": row.get("Site Type"),
                        "Network Role": row.get("Network Role"),
                    },
                },
                {
                    "title": "S&OP Signal",
                    "items": {
                        "Status": row.get("Hypercare Status"),
                        "Action": row.get("Hypercare Action"),
                        "Owner": row.get("Hypercare Owner"),
                        "Priority": row.get("Hypercare Priority"),
                    },
                },
            ]
        )
        render_mfc_network_map(profile, mfc_rows.head(1), "MFC Node Focus")
        sdt_windows = load_sdt_windows_for_lane(lane)
        if not sdt_windows.empty:
            st.markdown('<div class="gp-section-label">Lane SDT Shipping Windows</div>', unsafe_allow_html=True)
            st.dataframe(sdt_windows, use_container_width=True, hide_index=True)
        lane_rows = profile[profile["Lane"].astype(str).str.casefold().eq(lane.casefold())].copy()
        if not lane_rows.empty:
            cols = ["Site", "Location Name", "Delivery Day", "Delivery Window", "Full Address"]
            st.markdown('<div class="gp-section-label">Other MFCs In This Lane</div>', unsafe_allow_html=True)
            st.dataframe(lane_rows[[col for col in cols if col in lane_rows.columns]].drop_duplicates().head(100), use_container_width=True, hide_index=True)
        render_profile_source_fields(row, ["S&OP ", "Hypercare", "Site Info", "Active "])


def render_market_profiles() -> None:
    st.subheader("Market Profiles")
    st.caption("Lookup profiles from the Training Cheat Sheet: MFC/site, lane, final-mile, linehaul, carrier owner, SCBP, and delivery window context.")
    training = latest_google_sheet_by_type("Carrier Mapping")
    if training is None:
        st.info("Connect the Training Cheat Sheet as a Carrier Mapping Google Sheet to populate market profiles.")
        return

    final_mile = read_google_sheet_named_table(training, "Outbound - Final Mile")
    linehaul = read_google_sheet_named_table(training, "Outbound - Linehaul")
    market_breakdown = read_google_sheet_named_table(training, "Carrier Market Breakdown")
    scbps = read_google_sheet_named_table(training, "SCBPs")
    addresses = read_google_sheet_named_table(training, "Addresses and RM")
    if final_mile.empty:
        st.info("Refresh the Training Cheat Sheet connection so Outbound - Final Mile is available in the live cache.")
        return

    lane_col = first_matching_column(final_mile, [["lane"]])
    location_col = first_matching_column(final_mile, [["location", "name"]])
    location_id_col = first_matching_column(final_mile, [["location", "id"]])
    delivery_day_col = first_matching_column(final_mile, [["delivery", "day"]])
    delivery_window_col = first_matching_column(final_mile, [["delivery", "window"]])
    pallet_col = first_matching_column(final_mile, [["average", "pallet"], ["pallet"]])
    weight_col = first_matching_column(final_mile, [["average", "weight"], ["weight"]])

    profile = final_mile.copy()
    profile["Lane"] = profile[lane_col].astype(str).str.strip() if lane_col else ""
    profile["Location Name"] = profile[location_col].astype(str).str.strip() if location_col else ""
    profile["Site"] = profile["Location Name"].map(format_mfc_site_label)
    profile["Location ID"] = profile[location_id_col].astype(str).str.strip() if location_id_col else ""
    profile["Delivery Day"] = profile[delivery_day_col].astype(str).str.strip() if delivery_day_col else ""
    profile["Delivery Window"] = profile[delivery_window_col].astype(str).str.strip() if delivery_window_col else ""
    profile["Avg Pallets"] = pd.to_numeric(profile[pallet_col], errors="coerce") if pallet_col else 0
    profile["Avg Weight"] = pd.to_numeric(profile[weight_col], errors="coerce") if weight_col else 0
    profile["Profile Source"] = "Training Cheat Sheet"

    if not market_breakdown.empty:
        market_lane_col = first_matching_column(market_breakdown, [["fm"], ["lane"]])
        owner_col = first_matching_column(market_breakdown, [["current", "3pl"], ["current", "owner"], ["current"]])
        previous_col = first_matching_column(market_breakdown, [["previous", "3pl"], ["previous"]])
        ppc_col = first_matching_column(market_breakdown, [["current", "ppc"]])
        if market_lane_col:
            market = market_breakdown.copy()
            market["_lane_key"] = market[market_lane_col].astype(str).str.upper().str.strip()
            profile["_lane_key"] = profile["Lane"].astype(str).str.upper().str.strip()
            keep = ["_lane_key"]
            rename = {}
            for source_col, target_col in [(owner_col, "Current 3PL"), (previous_col, "Previous 3PL"), (ppc_col, "Current PPC")]:
                if source_col:
                    keep.append(source_col)
                    rename[source_col] = target_col
            profile = profile.merge(market[keep].rename(columns=rename).drop_duplicates("_lane_key"), on="_lane_key", how="left")
            profile = profile.drop(columns=["_lane_key"], errors="ignore")

    if not linehaul.empty:
        lh_lane_col = first_matching_column(linehaul, [["lane"]])
        dest_city_col = first_matching_column(linehaul, [["destination", "city"]])
        dest_state_col = first_matching_column(linehaul, [["destination", "state"]])
        freq_col = first_matching_column(linehaul, [["frequency"], ["frequencies"]])
        if lh_lane_col:
            lh = linehaul.copy()
            lh["_lane_key"] = lh[lh_lane_col].astype(str).str.upper().str.strip()
            city = (
                lh[dest_city_col].fillna("").astype(str).str.strip()
                if dest_city_col
                else pd.Series("", index=lh.index)
            )
            state = (
                lh[dest_state_col].fillna("").astype(str).str.strip()
                if dest_state_col
                else pd.Series("", index=lh.index)
            )
            lh["Linehaul Destination"] = city + state.map(lambda value: f", {value}" if value else "")
            keep = ["_lane_key", "Linehaul Destination"] + ([freq_col] if freq_col else [])
            profile["_lane_key"] = profile["Lane"].astype(str).str.upper().str.strip()
            profile = profile.merge(
                lh[keep].rename(columns={freq_col: "Linehaul Frequency"} if freq_col else {}).drop_duplicates("_lane_key"),
                on="_lane_key",
                how="left",
            ).drop(columns=["_lane_key"], errors="ignore")

    if not scbps.empty:
        scbp_location_col = first_matching_column(scbps, [["location", "name"]])
        scbp_name_col = first_matching_column(scbps, [["scbp", "name"]])
        slack_col = first_matching_column(scbps, [["slack", "channel", "name"], ["slack", "channel"]])
        if scbp_location_col:
            scbp = scbps.copy()
            scbp["_location_key"] = scbp[scbp_location_col].astype(str).str.strip()
            keep = ["_location_key"]
            rename = {}
            for source_col, target_col in [(scbp_name_col, "SCBP"), (slack_col, "Slack Channel")]:
                if source_col:
                    keep.append(source_col)
                    rename[source_col] = target_col
            profile["_location_key"] = profile["Location Name"]
            profile = profile.merge(scbp[keep].rename(columns=rename).drop_duplicates("_location_key"), on="_location_key", how="left")
            profile = profile.drop(columns=["_location_key"], errors="ignore")

    if not addresses.empty:
        address_location_col = first_matching_column(addresses, [["location", "name"]])
        address_id_col = first_matching_column(addresses, [["location", "id"]])
        if address_location_col or address_id_col:
            address = addresses.copy()
            if address_location_col:
                address["_location_key"] = address[address_location_col].astype(str).str.strip()
                profile["_location_key"] = profile["Location Name"]
            elif address_id_col:
                address["_location_key"] = address[address_id_col].astype(str).str.strip()
                profile["_location_key"] = profile["Location ID"]
            keep = ["_location_key"]
            rename = {}
            for source_col, target_col in [
                (first_matching_column(address, [["full", "address"]]), "Full Address"),
                (first_matching_column(address, [["street", "address"]]), "Street Address"),
                (first_matching_column(address, [["city"]]), "City"),
                (first_matching_column(address, [["state"]]), "State"),
                (first_matching_column(address, [["postal"]]), "Postal Code"),
                (first_matching_column(address, [["region", "name"]]), "Region"),
                (first_matching_column(address, [["market", "name"]]), "Market"),
                (first_matching_column(address, [["hours"]]), "Hours of Operation"),
            ]:
                if source_col:
                    keep.append(source_col)
                    rename[source_col] = target_col
            profile = profile.merge(address[keep].rename(columns=rename).drop_duplicates("_location_key"), on="_location_key", how="left")
            profile = profile.drop(columns=["_location_key"], errors="ignore")

    site_information_profiles, _ = build_site_information_context()
    profile = append_site_information_profiles(profile, site_information_profiles)
    profile, operating_sources = enrich_market_profile_operating_context(profile)
    if operating_sources:
        source_text = " | ".join(f"{name}: {sheet}" for name, sheet in operating_sources.items() if sheet)
        if source_text:
            st.caption(f"Live profile enrichment: {source_text}")

    selected_type = get_query_param("profile_type")
    selected_key = get_query_param("profile_key")
    if selected_type and selected_key:
        render_market_profile_detail(profile, linehaul, market_breakdown, selected_type, selected_key)
        return

    with st.form("market_profile_search", clear_on_submit=False):
        search_cols = st.columns([6, 1])
        search = search_cols[0].text_input(
            "Search market, site, location, or carrier owner",
            value=get_query_param("profile_search"),
            placeholder="Example: DC1, 1515, MCO 117, Orlando, WARP, Misfits",
        )
        search_cols[1].markdown("<div style='height: 1.78rem'></div>", unsafe_allow_html=True)
        search_cols[1].form_submit_button("Search", use_container_width=True)
    filtered = profile.copy()
    if search.strip():
        scores = score_market_profile_rows(profile, search)
        filtered = profile[scores > 0].assign(Search_Relevance=scores[scores > 0])
        sort_cols = ["Search_Relevance"]
        if "Active GUSTO" in filtered.columns:
            sort_cols.append("Active GUSTO")
        filtered = filtered.sort_values(sort_cols, ascending=[False] * len(sort_cols))
        if filtered.empty:
            st.info("No direct profile matches found. Try a site number, address fragment, lane code, city, carrier, or leader name.")

    metric_cols = st.columns(4)
    metric_cols[0].metric("Matched MFCs", format_number(len(filtered)))
    metric_cols[1].metric("Markets", format_number(filtered["Lane"].nunique()))
    metric_cols[2].metric("Active GUSTOs", format_number(filtered.get("Active GUSTO", pd.Series("", index=filtered.index)).astype(str).str.strip().ne("").sum()))
    metric_cols[3].metric("Avg Pallets", format_number(filtered["Avg Pallets"].sum()))

    render_mfc_network_map(profile, filtered if search.strip() else pd.DataFrame(), "MFC Network Map")
    render_operating_profile_gallery(filtered, search)
    render_market_profile_result_links(filtered, search)

    display_cols = [
        "Site",
        "Location Name",
        "Lane",
        "Active GUSTO",
        "Active Status",
        "Active Pallets",
        "Delivery Day",
        "Delivery Window",
        "Avg Pallets",
        "Avg Weight",
        "Site Leader",
        "Regional Manager",
        "Hypercare Status",
        "Current 3PL",
        "Previous 3PL",
        "Current PPC",
        "Linehaul Destination",
        "Linehaul Frequency",
        "Full Address",
        "City",
        "State",
        "Site Type",
        "Site Status",
        "Network Role",
        "SCBP",
        "Slack Channel",
        "Profile Source",
    ]
    st.dataframe(
        filtered[[col for col in display_cols if col in filtered.columns]].head(250),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Avg Pallets": st.column_config.NumberColumn("Avg Pallets", format="%,.1f"),
            "Avg Weight": st.column_config.NumberColumn("Avg Weight", format="%,.0f"),
        },
    )


def empty_ops_data() -> dict[str, pd.DataFrame]:
    return {"daily": pd.DataFrame(), "weekly": pd.DataFrame()}


def empty_tender_pipeline() -> dict[str, pd.DataFrame]:
    return {
        "records": pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS),
        "ready": pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS),
        "issues": pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS),
        "duplicates": pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS),
        "conflicts": pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS),
        "export": pd.DataFrame(columns=TENDER_EXPORT_COLUMNS),
    }


def render_embed_transportation_control(context: DailyHealthContext) -> None:
    status = "Waiting"
    if not context.progress.empty:
        status = str(summarize_daily_health_progress(context.progress)["status"])
    render_enterprise_module_header(
        "Transportation Control",
        "DC1 Shipping Window Control",
        "Focused Google Sites module for SDT window, OB Tracker, and carrier progress signals.",
        status,
        f"OB tab {context.ob_sheet or 'not selected'} | {datetime.now().strftime('%m/%d/%Y %I:%M %p')}",
    )
    if context.progress.empty:
        st.info("Transportation Control is waiting on SDT Schedule and OB TO Tracker data.")
        return

    summary = summarize_daily_health_progress(context.progress)
    render_enterprise_kpi_grid(
        [
            {"label": "Routes", "value": format_number(summary["total_routes"]), "delta": "Matched carrier lanes", "accent": "neutral"},
            {"label": "Loaded TOs", "value": f"{format_number(summary['loaded'])} / {format_number(summary['total_tos'])}", "delta": format_percent(summary["completion"]), "accent": "green" if float(summary["completion"]) >= 0.9 else "yellow"},
            {"label": "Open TOs", "value": format_number(summary["open_tos"]), "delta": "Remaining load work", "accent": "yellow" if int(summary["open_tos"]) else "green"},
            {"label": "Past Departure", "value": format_number(summary["past"]), "delta": "Routes beyond SDT", "accent": "red" if int(summary["past"]) else "green"},
        ],
        columns=4,
    )
    st.markdown('<div class="gp-section-label">Carrier Window Progress</div>', unsafe_allow_html=True)
    display_cols = [
        "Carrier",
        "Window Status",
        "Load Ready Time",
        "Departure Time",
        "TOs",
        "Loaded",
        "Open TOs",
        "Lines_Remaining",
        "Progress %",
        "Timing Risk",
    ]
    display = context.progress[[col for col in display_cols if col in context.progress.columns]].copy()
    if "Open TOs" in display.columns:
        display = display.sort_values("Open TOs", ascending=False)
    st.dataframe(
        display.head(25),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Progress %": st.column_config.ProgressColumn("Progress %", format="%.0f%%", min_value=0, max_value=1),
        },
    )


def render_google_sites_embed(embed_mode: str) -> None:
    st.markdown('<div class="gp-embed-shell">', unsafe_allow_html=True)
    install_google_refresh_timer()
    if "google_sheet_secret_seed_checked" not in st.session_state:
        seed_google_sheet_connections_from_secrets()
        st.session_state["google_sheet_secret_seed_checked"] = True
    run_scheduled_google_refresh_if_due()

    context = load_daily_health_context()
    command_center = latest_command_center_snapshot()
    ops_data = empty_ops_data()
    health = compute_health(
        command_center,
        pd.DataFrame(columns=["Carrier", "Status", "Notes"]),
        pd.DataFrame(),
        pd.DataFrame(),
        ops_data,
    )

    if embed_mode in {"home_live_metrics", "live_metrics"}:
        render_live_update(context)
    elif embed_mode == "daily_health":
        render_executive_briefs_view(context, health, ops_data)
    elif embed_mode in {"daily_ops_labor", "daily_health_ops", "operations_labor"}:
        render_daily_ops_labor_embed(context)
    elif embed_mode in {"transportation_control", "transportation_allocations"}:
        render_embed_transportation_control(context)
    elif embed_mode in {"executive_brief", "executive_briefs"}:
        render_executive_briefs_view(context, health, ops_data)
    elif embed_mode in {"executive_summary", "executive_brief_summary"}:
        render_executive_summary_embed(context, health, ops_data)
    elif embed_mode in {"executive_watchlist", "executive_route_watchlist"}:
        render_executive_watchlist_embed(context)
    elif embed_mode in {"executive_pallets", "executive_pallet_readiness"}:
        render_executive_pallet_embed(context)
    elif embed_mode in {"executive_note", "leadership_brief"}:
        render_executive_note_embed(context, health, ops_data)
    elif embed_mode in {"market_profiles", "mfc_lookup", "mfc_profiles", "mfc_network_map", "resource_library"}:
        render_market_profiles()
    else:
        render_embed_catalog()
    st.markdown("</div>", unsafe_allow_html=True)


def render_cost_lane_intelligence() -> None:
    st.subheader("Cost & Lane Intelligence")
    st.caption("Read-only prototype using the RFP workbook. Designed for future finance handoff and validation.")
    ref = latest_reference_by_type("RFP Cost")
    if ref is None:
        st.info("Upload the RFP Cost workbook as a reference sheet to populate this view.")
        return

    loaded = load_reference_sheet(int(ref["id"]))
    if loaded is None:
        st.warning("Saved RFP workbook could not be opened.")
        return
    filename, _, payload = loaded
    excel = pd.ExcelFile(BytesIO(payload))
    target_sheets = [sheet for sheet in excel.sheet_names if any(token in sheet.lower() for token in ["linehaul", "final mile", "inbound", "current pricing"])]
    summary_rows = []
    previews: dict[str, pd.DataFrame] = {}
    for sheet in target_sheets[:8]:
        table = infer_header_table(pd.read_excel(excel, sheet_name=sheet, header=None))
        previews[sheet] = table
        lane_col = first_matching_column(table, [["lane"], ["location"]])
        carrier_col = first_matching_column(table, [["carrier"]])
        bid_cols = [col for col in table.columns if "bid" in str(col).lower() or "rate" in str(col).lower() or "cost" in str(col).lower()]
        summary_rows.append(
            {
                "Sheet": sheet,
                "Rows": len(table),
                "Lane Count": table[lane_col].nunique() if lane_col else 0,
                "Carrier Count": table[carrier_col].nunique() if carrier_col else 0,
                "Pricing Columns": ", ".join(str(col) for col in bid_cols[:6]),
            }
        )
    st.subheader("RFP Workbook Coverage")
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    if previews:
        selected_sheet = st.selectbox("Preview lane sheet", list(previews.keys()))
        preview = previews[selected_sheet]
        lane_col = first_matching_column(preview, [["lane"], ["location"]])
        display_cols = [col for col in preview.columns if col in [lane_col] or any(token in str(col).lower() for token in ["carrier", "bid", "rate", "cost", "origin", "destination", "frequency"])]
        st.dataframe(preview[display_cols].head(100) if display_cols else preview.head(100), use_container_width=True, hide_index=True)


def make_executive_snapshot(
    health: HealthResult,
    command_center: dict[str, int],
    carrier_summary: pd.DataFrame,
    site_summary: pd.DataFrame,
    ship_allocation_records: pd.DataFrame,
) -> str:
    total_orders = len(site_summary)
    total_pallets = site_summary.get("Pallets Final", pd.Series(dtype=float)).sum()
    top_carriers = "No carrier volume loaded."
    if not carrier_summary.empty and "Total Pallet Estimate" in carrier_summary.columns:
        top = carrier_summary.sort_values("Total Pallet Estimate", ascending=False).head(3)
        top_carriers = "; ".join(
            f"{row['Carrier']} ({format_number(row['Total Pallet Estimate'])} pallets)"
            for _, row in top.iterrows()
        )

    source_files = "No daily allocation file loaded."
    if not ship_allocation_records.empty and "source_file" in ship_allocation_records.columns:
        source_files = ", ".join(
            ship_allocation_records["source_file"].dropna().astype(str).drop_duplicates().head(5).tolist()
        )

    drivers = " ".join(health.drivers)
    return (
        f"DC1 Executive Snapshot | {command_center.get('last_updated', 'not provided')}\n\n"
        f"Overall Status: {health.label}\n"
        f"Demand: {command_center.get('created', 0):,} created orders; "
        f"{command_center.get('created_vs_forecast', 0):+,} vs forecast; "
        f"DT > 60m at {command_center.get('dt_over_60', 0):,}.\n"
        f"Allocation Load: {total_orders:,} order row(s), {format_number(total_pallets)} pallet(s). Source: {source_files}.\n"
        f"Top Carrier Volume: {top_carriers}.\n"
        f"Primary Drivers: {drivers}\n\n"
        "Next Action: validate BulkUpload readiness, confirm carrier constraints, and resolve any rows marked Needs Review before TMS upload."
    )


def render_database_backup() -> None:
    st.subheader("Prototype Backup")
    st.caption("Downloads the current local SQLite database so saved batches, signals, files, and reference metadata can be backed up before sharing or moving machines.")
    if not DB_PATH.exists():
        st.info("No SQLite database has been created yet.")
        return
    st.download_button(
        "Download SQLite Backup",
        data=DB_PATH.read_bytes(),
        file_name=f"dc1_health_board_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.sqlite",
        mime="application/octet-stream",
    )


def render_lean_5s_workspace() -> None:
    st.subheader("LEAN/5S Projects")
    st.caption("Create small improvement project spaces with purpose, current state, target state, wins, next steps, and supporting files.")

    with st.expander("Create a New Project", expanded=False):
        new_col_a, new_col_b = st.columns(2)
        project_name = new_col_a.text_input("Project name", key="lean_new_project_name")
        owner = new_col_b.text_input("Owner / lead", key="lean_new_owner")
        area = new_col_a.text_input("Area", placeholder="Dock, pick line, staging, carrier handoff...", key="lean_new_area")
        status = new_col_b.selectbox(
            "Status",
            ["Planning", "Active", "Testing", "Sustained", "Closed"],
            key="lean_new_status",
        )
        purpose = st.text_area("Project purpose", key="lean_new_purpose")
        current_state = st.text_area("Current state", key="lean_new_current")
        target_state = st.text_area("Target state", key="lean_new_target")
        wins = st.text_area("Project wins", key="lean_new_wins")
        next_steps = st.text_area("Next steps", key="lean_new_next")
        if st.button("Create LEAN/5S Project", type="primary"):
            if not project_name.strip():
                st.warning("Add a project name before creating the project.")
            else:
                project_id = create_lean_project(
                    {
                        "project_name": project_name,
                        "status": status,
                        "owner": owner,
                        "area": area,
                        "purpose": purpose,
                        "current_state": current_state,
                        "target_state": target_state,
                        "wins": wins,
                        "next_steps": next_steps,
                    }
                )
                st.session_state["selected_lean_project_id"] = project_id
                st.success(f"Created {project_name}.")

    projects = list_lean_projects()
    if projects.empty:
        st.info("No LEAN/5S projects yet. Create the first one above.")
        return

    card_rows = projects[["id", "project_name", "status", "owner", "area", "updated_at"]].copy()
    st.subheader("Current LEAN/5S Projects")
    st.dataframe(card_rows, use_container_width=True, hide_index=True)

    selected_project_id = st.selectbox(
        "Open project",
        projects["id"].tolist(),
        index=(
            projects["id"].tolist().index(st.session_state["selected_lean_project_id"])
            if st.session_state.get("selected_lean_project_id") in projects["id"].tolist()
            else 0
        ),
        format_func=lambda project_id: projects.loc[projects["id"].eq(project_id), "project_name"].iloc[0],
        key="lean_project_selector",
    )
    st.session_state["selected_lean_project_id"] = selected_project_id
    project = load_lean_project(int(selected_project_id))
    if project is None:
        st.warning("Selected project could not be loaded.")
        return

    st.subheader(str(project["project_name"]))
    st.caption(f"{project['status']} | {project['area']} | Lead: {project['owner'] or 'Unassigned'}")
    tool_options = ["Project Profile", "Matrix Builder", "Flowchart Builder", "File Locker"]
    tool_key = f"lean_tool_{selected_project_id}"
    pending_tool_key = f"{tool_key}_pending"
    if pending_tool_key in st.session_state:
        st.session_state[tool_key] = st.session_state.pop(pending_tool_key)
    if tool_key not in st.session_state:
        st.session_state[tool_key] = "Project Profile"

    st.markdown(
        f"""
        <div class="gp-project-action-strip">
          <div>
            <div class="gp-project-action-strip__title">Project Workspace Tools</div>
            <div class="gp-project-action-strip__meta">Open the saved profile, ownership matrix, process flowchart, or file locker for {str(project["project_name"])}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    tool_cols = st.columns(4)
    for idx, tool_name in enumerate(tool_options):
        button_type = "primary" if st.session_state[tool_key] == tool_name else "secondary"
        if tool_cols[idx].button(tool_name, key=f"lean_tool_button_{selected_project_id}_{idx}", type=button_type, use_container_width=True):
            st.session_state[tool_key] = tool_name
            st.rerun()

    selected_tool = st.session_state[tool_key]

    if selected_tool == "Project Profile":
        edit_col_a, edit_col_b = st.columns(2)
        edited_name = edit_col_a.text_input("Project name", value=str(project["project_name"]), key=f"lean_name_{selected_project_id}")
        edited_owner = edit_col_b.text_input("Owner / lead", value=str(project["owner"]), key=f"lean_owner_{selected_project_id}")
        edited_area = edit_col_a.text_input("Area", value=str(project["area"]), key=f"lean_area_{selected_project_id}")
        status_options = ["Planning", "Active", "Testing", "Sustained", "Closed"]
        current_status = str(project["status"]) if str(project["status"]) in status_options else "Planning"
        edited_status = edit_col_b.selectbox(
            "Status",
            status_options,
            index=status_options.index(current_status),
            key=f"lean_status_{selected_project_id}",
        )

        profile_col, wins_col = st.columns(2)
        edited_purpose = profile_col.text_area(
            "Purpose",
            value=str(project["purpose"]),
            height=140,
            key=f"lean_purpose_{selected_project_id}",
        )
        edited_current = profile_col.text_area(
            "Current state",
            value=str(project["current_state"]),
            height=160,
            key=f"lean_current_{selected_project_id}",
        )
        edited_target = profile_col.text_area(
            "Target state",
            value=str(project["target_state"]),
            height=160,
            key=f"lean_target_{selected_project_id}",
        )
        edited_wins = wins_col.text_area(
            "Project wins",
            value=str(project["wins"]),
            height=200,
            key=f"lean_wins_{selected_project_id}",
        )
        edited_next = wins_col.text_area(
            "Next steps",
            value=str(project["next_steps"]),
            height=200,
            key=f"lean_next_{selected_project_id}",
        )
        if st.button("Save Project Profile", type="primary"):
            update_lean_project(
                int(selected_project_id),
                {
                    "project_name": edited_name,
                    "status": edited_status,
                    "owner": edited_owner,
                    "area": edited_area,
                    "purpose": edited_purpose,
                    "current_state": edited_current,
                    "target_state": edited_target,
                    "wins": edited_wins,
                    "next_steps": edited_next,
                },
            )
            st.success("Saved LEAN/5S project profile.")

    elif selected_tool == "Matrix Builder":
        st.subheader("Ownership & Deadline Matrix")
        st.caption("Track project work areas, owners, and deadlines. Risk color is based on days left from today.")
        matrix_rows = list_lean_matrix_items(int(selected_project_id))
        if matrix_rows.empty:
            matrix_rows = default_lean_matrix_rows(project)
        matrix_rows["deadline"] = pd.to_datetime(matrix_rows["deadline"], errors="coerce").dt.date
        edited_matrix = st.data_editor(
            matrix_rows,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "deadline": st.column_config.DateColumn("Deadline", format="YYYY-MM-DD"),
                "status": st.column_config.SelectboxColumn("Status", options=LEAN_MATRIX_STATUS_OPTIONS),
                "area": st.column_config.TextColumn("Area / ownership lane"),
                "owner": st.column_config.TextColumn("Owner"),
                "notes": st.column_config.TextColumn("Notes"),
            },
            key=f"lean_matrix_editor_{selected_project_id}",
        )
        if st.button("Save Matrix", type="primary", key=f"lean_matrix_save_{selected_project_id}"):
            replace_lean_matrix_items(int(selected_project_id), edited_matrix)
            st.success("Saved ownership matrix.")

        preview_matrix = edited_matrix.copy()
        risk_pairs = preview_matrix["deadline"].apply(classify_deadline) if "deadline" in preview_matrix else []
        if len(preview_matrix):
            preview_matrix["deadline_risk"] = [risk for risk, _ in risk_pairs]
            preview_matrix["days_left"] = [days if days is not None else "" for _, days in risk_pairs]
            st.dataframe(
                preview_matrix.style.apply(style_lean_matrix, axis=1),
                use_container_width=True,
                hide_index=True,
            )

    elif selected_tool == "Flowchart Builder":
        st.subheader("Flowchart Builder")
        st.caption("Build a saved project process map from warehouse, carrier handoff, and LEAN/5S step types. The preview uses a Mermaid diagram.")
        with st.expander("Warehouse / LEAN step palette", expanded=False):
            st.dataframe(
                pd.DataFrame(
                    {
                        "Type": LEAN_FLOW_NODE_TYPES,
                        "Use": [
                            "Project start, stop, or handoff boundary",
                            "Standard process step",
                            "Yes/no or route choice",
                            "Dock door or dock process",
                            "Material movement",
                            "Pallet build, staging, or review",
                            "Physical staging lane",
                            "Inventory holding or count point",
                            "Carrier pickup, drop, or communication handoff",
                            "Quality, audit, or check step",
                            "Remove unneeded material/process waste",
                            "Organize the right items in the right place",
                            "Clean, inspect, and restore the work area",
                            "Document the standard",
                            "Audit and hold the gain",
                        ],
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )
        nodes, edges = load_lean_flowchart(int(selected_project_id), project)
        node_options = nodes["node_id"].dropna().astype(str).tolist()
        flow_col_a, flow_col_b = st.columns([3, 2])
        with flow_col_a:
            edited_nodes = st.data_editor(
                nodes,
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                column_config={
                    "node_id": st.column_config.TextColumn("Node ID"),
                    "label": st.column_config.TextColumn("Step label"),
                    "node_type": st.column_config.SelectboxColumn("Type", options=LEAN_FLOW_NODE_TYPES),
                    "lane": st.column_config.TextColumn("Lane / area"),
                    "notes": st.column_config.TextColumn("Notes"),
                },
                key=f"lean_flow_nodes_{selected_project_id}",
            )
        with flow_col_b:
            edited_edges = st.data_editor(
                edges,
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                column_config={
                    "from_node": st.column_config.SelectboxColumn("From", options=node_options),
                    "to_node": st.column_config.SelectboxColumn("To", options=node_options),
                    "label": st.column_config.TextColumn("Connector label"),
                },
                key=f"lean_flow_edges_{selected_project_id}",
            )

        if st.button("Save Flowchart", type="primary", key=f"lean_flow_save_{selected_project_id}"):
            save_lean_flowchart(int(selected_project_id), edited_nodes, edited_edges)
            st.success("Saved project flowchart.")

        mermaid_code = build_mermaid_flowchart(edited_nodes, edited_edges)
        components.html(
            f"""
            <div class="mermaid">{mermaid_code}</div>
            <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
            <script>mermaid.initialize({{startOnLoad: true, theme: "base"}});</script>
            """,
            height=420,
            scrolling=True,
        )
        with st.expander("Mermaid export"):
            st.code(mermaid_code, language="mermaid")
            st.download_button(
                "Download Flowchart Mermaid File",
                data=mermaid_code.encode("utf-8"),
                file_name=f"{str(project['project_name']).replace(' ', '_')}_flowchart.mmd",
                mime="text/plain",
                key=f"lean_flow_download_{selected_project_id}",
            )

    else:
        st.subheader("Project File Locker")
        project_files = st.file_uploader(
            "Upload files to this project",
            accept_multiple_files=True,
            key=f"lean_project_upload_{selected_project_id}",
        )
        if project_files:
            saved_count = sum(save_lean_project_file(int(selected_project_id), file) for file in project_files)
            duplicate_count = len(project_files) - saved_count
            if saved_count:
                st.success(f"Saved {saved_count} project file(s).")
            if duplicate_count:
                st.caption(f"{duplicate_count} file(s) were already saved for this project.")

        saved_files = list_lean_project_files(int(selected_project_id))
        if saved_files.empty:
            st.caption("No files uploaded to this project yet.")
            return

        display_files = saved_files.copy()
        display_files["file_size"] = display_files["file_size"].apply(
            lambda size: f"{size / 1024:,.1f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):,.2f} MB"
        )
        st.dataframe(display_files, use_container_width=True, hide_index=True)
        selected_file_id = st.selectbox(
            "Download project file",
            saved_files["id"].tolist(),
            format_func=lambda file_id: saved_files.loc[saved_files["id"].eq(file_id), "filename"].iloc[0],
            key=f"lean_file_selector_{selected_project_id}",
        )
        loaded_file = load_lean_project_file(int(selected_file_id))
        if loaded_file:
            filename, content_type, payload = loaded_file
            st.download_button(
                "Download selected project file",
                data=payload,
                file_name=filename,
                mime=content_type,
                key=f"lean_file_download_{selected_project_id}",
            )


def main() -> None:
    init_db()
    st.set_page_config(page_title=APP_TITLE, page_icon=str(LOGO_PATH), layout="wide")
    inject_brand_styles()
    embed_mode = get_site_embed_mode()
    if embed_mode:
        render_google_sites_embed(embed_mode)
        return
    render_sidebar_brand()
    render_brand_header()
    st.title(APP_TITLE)
    st.caption("Local MVP for DC1 allocation visibility, Command Center snapshots, and executive health checks.")
    install_google_refresh_timer()
    if "google_sheet_secret_seed_checked" not in st.session_state:
        seed_messages = seed_google_sheet_connections_from_secrets()
        st.session_state["google_sheet_secret_seed_checked"] = True
        if seed_messages:
            with st.sidebar.expander("Google Sheet secret seeding", expanded=False):
                for message in seed_messages:
                    st.write(message)
    scheduled_refresh_messages = run_scheduled_google_refresh_if_due()
    if scheduled_refresh_messages:
        st.sidebar.success("Scheduled Google Sheet refresh completed.")
        with st.sidebar.expander("Latest scheduled refresh", expanded=False):
            for message in scheduled_refresh_messages:
                st.write(message)

    if "carrier_signals" not in st.session_state:
        st.session_state["carrier_signals"] = load_saved_signals()
    if "tender_pipeline" not in st.session_state:
        st.session_state["tender_pipeline"] = {
            "records": pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS),
            "ready": pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS),
            "issues": pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS),
            "duplicates": pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS),
            "conflicts": pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS),
            "export": pd.DataFrame(columns=TENDER_EXPORT_COLUMNS),
        }
    if "ship_allocation_records" not in st.session_state:
        st.session_state["ship_allocation_records"] = pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS + ["source_group"])

    st.sidebar.subheader("Operational Inputs")
    otp_files = st.sidebar.file_uploader(
        "Upload OTP bridge workbook(s)",
        type=["xlsx"],
        accept_multiple_files=True,
        help="Weekly carrier OTP bridge files shared between Gopuff and carriers.",
    )
    ops_file = st.sidebar.file_uploader(
        "Upload Ops productivity workbook",
        type=["xlsx"],
        help="Operations productivity workbook used for throughput, UPH, and bridge notes.",
    )
    ship_allocation_files = st.sidebar.file_uploader(
        "Upload daily allocation file",
        type=["xlsx", "xlsm", "csv"],
        accept_multiple_files=True,
        help="Daily allocation files used by the Ship Allocation Builder to generate Uber Freight BulkUpload workbooks.",
    )
    st.sidebar.subheader("File Lockers")
    presentation_files = st.sidebar.file_uploader(
        "Upload a Presentation",
        type=PRESENTATION_FILE_TYPES,
        accept_multiple_files=True,
        help="Saves presentation files into the Presentation Locker.",
    )
    pdf_files = st.sidebar.file_uploader(
        "Upload a PDF",
        type=PDF_FILE_TYPES,
        accept_multiple_files=True,
        help="Saves PDF files into the PDF Locker.",
    )
    st.sidebar.subheader("Reference & Snapshot Inputs")
    reference_files = st.sidebar.file_uploader(
        "Upload shared reference workbook(s)",
        type=["xlsx", "xlsm", "csv"],
        accept_multiple_files=True,
        help="Shared Google Sheet exports or workbook references that should be available for synchronization and lookup.",
    )
    command_center_file = st.sidebar.file_uploader(
        "Upload Command Center snapshot history",
        type=["xlsx", "xlsm", "csv"],
        help="Optional CSV/XLSX with Created, Cancelled, Created vs Forecast, DT > 50m, DT > 60m, and a timestamp/date column.",
    )
    if LIVE_GOOGLE_ONLY:
        st.sidebar.caption("Live Google Sheet mode is on. Cached reference workbooks and Command Center uploads are ignored.")
        if reference_files:
            st.sidebar.warning("Reference workbook uploads are ignored while Live Google Sheet mode is on.")
        if command_center_file:
            st.sidebar.warning("Command Center snapshot uploads are ignored while Live Google Sheet mode is on.")
        reference_files = []
        command_center_file = None
        if not ship_allocation_files:
            st.session_state["ship_allocation_records"] = pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS + ["source_group"])

    carrier_summary = pd.DataFrame()
    site_summary = pd.DataFrame()
    otp_bridge = pd.DataFrame()
    tender_pipeline = {
        "records": pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS),
        "ready": pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS),
        "issues": pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS),
        "duplicates": pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS),
        "conflicts": pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS),
        "export": pd.DataFrame(columns=TENDER_EXPORT_COLUMNS),
    }
    ops_data = {
        "daily": pd.DataFrame(),
        "weekly": pd.DataFrame(),
    }

    if otp_files:
        otp_bridge = load_otp_bridges(otp_files)

    if ops_file:
        ops_data = load_ops_performance(ops_file)

    tender_pipeline = st.session_state["tender_pipeline"]

    if ship_allocation_files:
        upload_signature = tuple(file.name for file in ship_allocation_files)
        if upload_signature != st.session_state.get("ship_allocation_upload_signature"):
            st.session_state["main_section"] = "Transportation"
            st.session_state["main_view"] = "Ship Allocation Builder"
            st.session_state["ship_allocation_upload_signature"] = upload_signature
        st.session_state["ship_allocation_records"] = load_ship_allocation_records(ship_allocation_files)

    ship_allocation_records = st.session_state.get("ship_allocation_records", pd.DataFrame())
    if not ship_allocation_records.empty:
        site_summary = ship_allocation_records.rename(
            columns={
                "carrier": "Carrier",
                "to_number": "TO Number",
                "location_name": "goPuff Site Location",
                "site_id": "Site ID",
                "units": "UNITS",
                "lines": "LINES",
                "pick_date": "Pick Date",
                "ship_date": "Ship Date",
                "delivery_date": "Delivery Date",
                "pallets": "Pallets Final",
                "water_weight": "Water Weight",
                "non_water_weight": "Non-Water Weight",
                "total_weight": "Total Weight",
            }
        )
        carrier_summary = (
            site_summary.groupby("Carrier", dropna=False)
            .agg(
                **{
                    "Total Pallet Estimate": ("Pallets Final", "sum"),
                    "Total Water Pallets": ("Water Weight", lambda values: round(values.fillna(0).sum() / 2400)),
                    "Total Weight": ("Total Weight", "sum"),
                }
            )
            .reset_index()
        )

    if presentation_files:
        saved_count = sum(save_uploaded_file("presentation", file) for file in presentation_files)
        duplicate_count = len(presentation_files) - saved_count
        if saved_count:
            st.sidebar.success(f"Saved {saved_count} presentation file(s).")
        if duplicate_count:
            st.sidebar.caption(f"{duplicate_count} presentation file(s) already saved.")

    if pdf_files:
        saved_count = sum(save_uploaded_file("pdf", file) for file in pdf_files)
        duplicate_count = len(pdf_files) - saved_count
        if saved_count:
            st.sidebar.success(f"Saved {saved_count} PDF file(s).")
        if duplicate_count:
            st.sidebar.caption(f"{duplicate_count} PDF file(s) already saved.")

    if reference_files:
        save_results = [save_reference_sheet(file) for file in reference_files]
        saved_count = save_results.count("saved")
        replaced_count = save_results.count("replaced")
        st.session_state["main_section"] = "Operations"
        st.session_state["main_view"] = "Reference Sheets"
        if saved_count:
            st.sidebar.success(f"Saved {saved_count} new reference workbook(s).")
        if replaced_count:
            st.sidebar.success(f"Replaced {replaced_count} existing reference workbook(s).")

    if command_center_file:
        command_signature = (command_center_file.name, command_center_file.size)
        if command_signature != st.session_state.get("command_center_upload_signature"):
            command_snapshots = parse_command_center_snapshots(command_center_file)
            saved_rows = save_command_center_snapshots(command_snapshots, "Bulk upload")
            st.session_state["command_center_upload_signature"] = command_signature
            if saved_rows:
                st.sidebar.success(f"Saved {saved_rows} Command Center snapshot row(s).")
            else:
                st.sidebar.warning("No Command Center snapshot rows were detected in that file.")

    command_center = latest_command_center_snapshot()

    st.sidebar.subheader("Manual Snapshot Fallback")
    with st.sidebar.expander("Enter Command Center metrics only if live data is unavailable", expanded=False):
        st.caption("Blank fields are ignored. Manual entries should be used only as a backup when the live pipeline is down.")
        command_center_inputs = {
            "created": st.text_input("Created orders", value="", key="manual_created_orders"),
            "cancelled": st.text_input("Cancelled orders", value="", key="manual_cancelled_orders"),
            "created_vs_forecast": st.text_input("Created vs forecast", value="", key="manual_created_vs_forecast"),
            "dt_over_50": st.text_input("DT > 50m", value="", key="manual_dt_over_50"),
            "dt_over_60": st.text_input("DT > 60m", value="", key="manual_dt_over_60"),
        }
        command_snapshot_time = st.text_input("Snapshot time", value="", key="manual_snapshot_time")
        command_notes = st.text_input("Snapshot notes", value="", key="manual_snapshot_notes")
        manual_button_cols = st.columns(2)
        if manual_button_cols[0].button("Save Manual Fallback", use_container_width=True):
            parsed_values = {
                key: parse_optional_int(value)
                for key, value in command_center_inputs.items()
            }
            if not str(command_snapshot_time).strip():
                st.error("Add a snapshot time before saving a manual fallback.")
            elif all(value is None for value in parsed_values.values()):
                st.error("Enter at least one manual metric before saving.")
            else:
                manual_snapshot = pd.DataFrame(
                    [
                        {
                            "snapshot_time": command_snapshot_time.strip(),
                            "source_name": "Manual Entry",
                            "source_sheet": "",
                            **{key: (value if value is not None else 0) for key, value in parsed_values.items()},
                        }
                    ]
                )
                save_command_center_snapshots(manual_snapshot, command_notes)
                st.success("Saved manual fallback snapshot.")
        if manual_button_cols[1].button("Clear Manual", use_container_width=True):
            deleted = delete_manual_command_center_snapshots()
            st.success(f"Cleared {deleted} manual fallback snapshot(s).")

    if not carrier_summary.empty and "Carrier" in carrier_summary.columns:
        tracker = carrier_summary[["Carrier"]].copy()
        tracker["Status"] = "Not Tendered"
        tracker["Notes"] = ""
        carrier_status = st.data_editor(
            tracker,
            column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=STATUS_OPTIONS),
                "Notes": st.column_config.TextColumn("Notes"),
            },
            hide_index=True,
            use_container_width=True,
            key="carrier_status_editor",
        )
    else:
        carrier_status = pd.DataFrame(columns=["Carrier", "Status", "Notes"])

    health = compute_health(command_center, carrier_status, site_summary, otp_bridge, ops_data)

    query_section = get_query_param("section")
    query_view = get_query_param("view")
    active_section = query_section or st.session_state.get("main_section", "Home")
    if active_section not in NAVIGATION:
        active_section = "Home"
    view = query_view or st.session_state.get("main_view", NAVIGATION[active_section][0])
    if view not in NAVIGATION[active_section]:
        view = NAVIGATION[active_section][0]
    st.session_state["main_section"] = active_section
    st.session_state["main_view"] = view
    active_section, view = render_navigation_menu(active_section, view)
    daily_health_context = load_daily_health_context() if view in {"Live Update", "Executive Briefs"} else None

    if view == "Executive Overview":
        col_status, col_demand, col_transport, col_lead = st.columns([1.1, 1, 1, 1])

        with col_status:
            render_status_badge(health.label)

        with col_demand:
            st.metric("Created", format_number(command_center["created"]), f"{command_center['created_vs_forecast']:+,} vs forecast")
            st.metric("Cancelled", format_number(command_center["cancelled"]))

        with col_transport:
            st.metric("Orders", format_number(len(site_summary)))
            st.metric("Pallets", format_number(site_summary.get("Pallets Final", pd.Series(dtype=float)).sum()))

        with col_lead:
            st.metric("DT > 50m", format_number(command_center["dt_over_50"]))
            st.metric("DT > 60m", format_number(command_center["dt_over_60"]))

        render_data_input_health(ship_allocation_records, otp_bridge, ops_data)

        with st.expander("Copy-Ready Executive Snapshot", expanded=False):
            snapshot_text = make_executive_snapshot(
                health,
                command_center,
                carrier_summary,
                site_summary,
                ship_allocation_records,
            )
            st.text_area("Snapshot text", value=snapshot_text, height=240)

        command_history = list_command_center_snapshots(limit=250)
        if not command_history.empty:
            with st.expander("Command Center Snapshot History", expanded=False):
                st.dataframe(command_history, use_container_width=True, hide_index=True)
                chart_history = command_history.copy()
                chart_history["snapshot_time"] = pd.to_datetime(chart_history["snapshot_time"], errors="coerce")
                chart_history = chart_history.dropna(subset=["snapshot_time"]).sort_values("snapshot_time")
                if len(chart_history) > 1:
                    trend_cols = ["created", "cancelled", "dt_over_50", "dt_over_60"]
                    trend = chart_history.melt(
                        id_vars=["snapshot_time"],
                        value_vars=trend_cols,
                        var_name="Metric",
                        value_name="Value",
                    )
                    fig = px.line(trend, x="snapshot_time", y="Value", color="Metric", markers=True)
                    fig.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10))
                    st.plotly_chart(fig, use_container_width=True)

        ops_summary = summarize_ops_overall(ops_data)
        if ops_summary.get("latest_date"):
            st.subheader("Ops Productivity Snapshot")
            ops_col_units, ops_col_hours, ops_col_uph, ops_col_bridge = st.columns(4)
            ops_col_units.metric("Ops Units", format_number(ops_summary.get("latest_units")))
            ops_col_hours.metric("Ops Hours", format_number(ops_summary.get("latest_hours")))
            ops_col_uph.metric("Ops UPH", format_number(ops_summary.get("latest_uph")))
            ops_col_bridge.metric("Ops Bridge Notes", format_number(ops_summary.get("bridge_count")))

        st.subheader("Health Drivers")
        for driver in health.drivers:
            st.write(f"- {driver}")

        signal_rows = pd.DataFrame(st.session_state.get("carrier_signals", []))
        if not signal_rows.empty:
            active_signals = signal_rows[signal_rows["Status"].isin(["Open", "Escalated"])]
            if not active_signals.empty:
                st.subheader("Carrier Signal Watchlist")
                st.dataframe(
                    active_signals[
                        [
                            "Carrier",
                            "Channel",
                            "Signal Type",
                            "Urgency",
                            "Status",
                            "Possible Site IDs",
                            "Suggested Action",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

        if not carrier_summary.empty and "Carrier" in carrier_summary.columns:
            st.subheader("Carrier Volume")
            pallet_col = "Total Pallet Estimate"
            if pallet_col in carrier_summary.columns:
                chart_df = carrier_summary.sort_values(pallet_col, ascending=True)
                fig = px.bar(
                    chart_df,
                    x=pallet_col,
                    y="Carrier",
                    orientation="h",
                    color=pallet_col,
                    color_continuous_scale="Tealgrn",
                    text=pallet_col,
                    labels={pallet_col: "Pallets"},
                )
                fig.update_traces(
                    texttemplate="%{text:,.0f}",
                    textposition="outside",
                    textangle=-90,
                    textfont=dict(size=18, color="#151922"),
                    cliponaxis=False,
                )
                fig.update_layout(
                    height=420,
                    margin=dict(l=10, r=60, t=20, b=10),
                    uniformtext=dict(minsize=18, mode="show"),
                    xaxis=dict(range=[0, chart_df[pallet_col].max() * 1.18]),
                )
                st.plotly_chart(fig, use_container_width=True)

    if view == "Live Update":
        render_live_update(daily_health_context or load_daily_health_context())

    if view == "Executive Briefs":
        render_executive_briefs_view(daily_health_context or load_daily_health_context(), health, ops_data)

    if view == "MFC Site Map":
        render_mfc_site_map(ship_allocation_records)

    if view == "Schedule Sync":
        render_schedule_sync(ship_allocation_records)

    if view == "Outbound TO Control":
        render_outbound_to_control()

    if view == "Cost & Lane Intelligence":
        render_cost_lane_intelligence()

    if view == "Allocation Detail":
        st.subheader("Carrier Summary")
        st.dataframe(carrier_summary, use_container_width=True, hide_index=True)

        st.subheader("Site Summary")
        st.dataframe(site_summary, use_container_width=True, hide_index=True)

    if view == "Tender Pipeline":
        records = tender_pipeline["records"]
        if not records.empty:
            st.subheader("TMS Mapping Controls")
            map_col_origin, map_col_hint = st.columns([1, 2])
            with map_col_origin:
                default_origin_external_id = st.text_input(
                    "Default origin external ID",
                    value="1486",
                    help="Used only when uploaded rows do not already include an origin external ID.",
                )
            with map_col_hint:
                st.caption(
                    "Fill vendor IDs for carriers that arrive from allocation files without TMS-ready vendor mapping."
                )

            carrier_map_seed = (
                records[["carrier"]]
                .dropna()
                .drop_duplicates()
                .sort_values("carrier")
                .assign(vendor_external_id="")
            )
            carrier_vendor_map = st.data_editor(
                carrier_map_seed,
                hide_index=True,
                use_container_width=True,
                key="carrier_vendor_map_editor",
            )
            mapped_records = apply_tender_mapping(records, default_origin_external_id, carrier_vendor_map)
            tender_pipeline = rebuild_tender_pipeline(mapped_records)
            st.session_state["tender_pipeline"] = tender_pipeline

        records = tender_pipeline["records"]
        ready = tender_pipeline["ready"]
        issues = tender_pipeline["issues"]
        duplicates = tender_pipeline["duplicates"]
        conflicts = tender_pipeline["conflicts"]
        export = tender_pipeline["export"]

        if records.empty:
            st.info(
                "No advanced tender batch is loaded. Use Ship Allocation Builder for the daily allocation workflow, or load a saved tender batch below."
            )
        else:
            col_total, col_ready, col_review, col_dupes, col_conflict = st.columns(5)
            col_total.metric("Rows Loaded", format_number(len(records)))
            col_ready.metric("Ready", format_number(len(ready)))
            col_review.metric("Needs Review", format_number(len(issues)))
            col_dupes.metric("Duplicates", format_number(len(duplicates)))
            col_conflict.metric("Conflicts", format_number(len(conflicts)))

            st.subheader("Clean Intake Export")
            export_format = st.radio(
                "Download format",
                ["CSV", "XLSX"],
                horizontal=True,
                key="tender_export_format",
            )
            clean_view_cols = [
                "validation_status",
                "validation_issues",
                "source_file",
                "source_sheet",
                "to_number",
                "carrier",
                "business_unit",
                "site_id",
                "location_name",
                "pick_date",
                "ship_date",
                "delivery_date",
                "units",
                "lines",
                "pallets",
                "water_weight",
                "non_water_weight",
                "total_weight",
                "vendor_external_id",
                "origin_external_id",
                "destination_external_id",
            ]
            clean_export = records[[col for col in clean_view_cols if col in records.columns]].copy()
            clean_payload, clean_mime = dataframe_download_payload(
                clean_export,
                export_format,
                "Clean Intake",
            )
            st.download_button(
                f"Download clean normalized intake {export_format}",
                data=clean_payload,
                file_name=export_filename("clean_tender_intake", export_format),
                mime=clean_mime,
            )

            st.subheader("Uber Freight Upload Export")
            if export.empty:
                st.warning("No rows are ready to export yet. Review validation issues below.")
            else:
                upload_payload, upload_mime = dataframe_download_payload(
                    export,
                    export_format,
                    "Uber Upload",
                )
                st.download_button(
                    f"Download Uber Freight upload {export_format}",
                    data=upload_payload,
                    file_name=export_filename("uber_freight_bulk_upload", export_format),
                    mime=upload_mime,
                )
                reference_list = ",".join(ready["to_number"].dropna().astype(str).unique().tolist())
                st.text_area("Copy-ready reference list for TMS search/error correction", reference_list, height=120)

            batch_name = st.text_input(
                "Batch name",
                value=f"Tender Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            )
            if st.button("Save Tender Batch to SQLite"):
                save_tender_batch(batch_name, tender_pipeline)
                st.success(f"Saved {batch_name}.")

            st.subheader("Validation Queue")
            queue_cols = [
                "validation_status",
                "validation_issues",
                "source_file",
                "source_sheet",
                "to_number",
                "carrier",
                "site_id",
                "location_name",
                "ship_date",
                "delivery_date",
                "pallets",
                "total_weight",
                "vendor_external_id",
                "origin_external_id",
                "destination_external_id",
            ]
            st.dataframe(
                records[[col for col in queue_cols if col in records.columns]],
                use_container_width=True,
                hide_index=True,
            )

            with st.expander("Preview Uber Freight export columns"):
                st.dataframe(export, use_container_width=True, hide_index=True)

        st.subheader("Saved Tender Batches")
        saved_batches = list_tender_batches()
        if saved_batches.empty:
            st.caption("No saved tender batches yet.")
        else:
            st.dataframe(saved_batches, use_container_width=True, hide_index=True)
            selected_batch_id = st.selectbox(
                "Load saved batch",
                saved_batches["id"].tolist(),
                format_func=lambda batch_id: saved_batches.loc[
                    saved_batches["id"].eq(batch_id), "batch_name"
                ].iloc[0],
            )
            if st.button("Load Selected Tender Batch"):
                st.session_state["tender_pipeline"] = load_tender_batch(int(selected_batch_id))
                st.success("Loaded selected tender batch. Refresh if the table does not update immediately.")

    if view == "Ship Allocation Builder":
        st.subheader("Daily Allocation to Uber Freight BulkUpload")
        st.caption(
            "Phase 1 rebuilds the Ship Allocations Template workflow inside the app: upload daily allocation files, map carrier fields, validate rows, and generate the TMS-ready workbook."
        )

        ship_records = st.session_state.get(
            "ship_allocation_records",
            pd.DataFrame(columns=TENDER_VALIDATION_COLUMNS + ["source_group"]),
        )
        if ship_records.empty:
            st.info("Upload daily allocation file from the sidebar to build a BulkUpload file.")
        else:
            available_groups = [
                group
                for group in SHIP_ALLOCATION_SOURCE_OPTIONS
                if group in ship_records["source_group"].dropna().astype(str).unique().tolist()
            ]
            selected_groups = st.multiselect(
                "Source groups to include",
                available_groups or SHIP_ALLOCATION_SOURCE_OPTIONS,
                default=available_groups or ["DC1", "DC2"],
            )
            filtered_records = ship_records[ship_records["source_group"].isin(selected_groups)].copy()

            default_origin_external_id = st.text_input(
                "Default origin external ID for blank rows",
                value="1486",
                key="ship_default_origin_external_id",
            )
            default_cols = st.columns(3)
            default_equipment_type = default_cols[0].text_input(
                "Default equipment",
                value="26 FT DRYVAN",
                key="ship_default_equipment",
            )
            default_mode_type = default_cols[1].text_input(
                "Default mode",
                value="LTL",
                key="ship_default_mode",
            )
            default_order_type = default_cols[2].text_input(
                "Default order type",
                value="TRANSFER",
                key="ship_default_order",
            )

            carrier_seed = (
                filtered_records[["carrier"]]
                .dropna()
                .drop_duplicates()
                .sort_values("carrier")
                .assign(
                    origin_external_id=lambda df: df["carrier"].apply(infer_default_origin_external_id),
                    scac=lambda df: df["carrier"].apply(infer_default_scac),
                    equipment_type="",
                    mode_type="",
                    order_type="",
                )
            )
            st.subheader("Carrier Mapping")
            st.caption("Use this to override origin ID or SCAC by carrier before generating the BulkUpload workbook.")
            carrier_map = st.data_editor(
                carrier_seed,
                hide_index=True,
                use_container_width=True,
                key="ship_carrier_map_editor",
            )

            mapped_ship_records = apply_ship_allocation_mapping(
                filtered_records,
                carrier_map,
                default_origin_external_id,
                default_equipment_type,
                default_mode_type,
                default_order_type,
            )
            ship_export = build_ship_bulk_upload_export(mapped_ship_records)
            render_ship_validation_summary(mapped_ship_records, ship_export)

            output_source_label = st.text_input("BulkUpload source label", value="_".join(selected_groups) or "ALLOC")
            current_run_date = local_today()
            current_run_date_key = current_run_date.isoformat()
            if st.session_state.get("ship_bulk_upload_date_anchor") != current_run_date_key:
                st.session_state["ship_bulk_upload_date"] = current_run_date
                st.session_state["ship_bulk_upload_date_anchor"] = current_run_date_key
            output_date = st.date_input(
                "BulkUpload run date",
                key="ship_bulk_upload_date",
                help="Defaults to the computer's current local date each new day. Change only when intentionally backdating a run.",
            )
            output_filename = f"{output_date.strftime('%m-%d-%Y')} BulkUpload {output_source_label}.xlsx"
            run_notes = st.text_input(
                "Daily run notes",
                placeholder="Optional: note missing mappings, carrier exceptions, or why rows were held back.",
            )

            if ship_export.empty:
                st.warning("No rows are ready to export yet. Resolve required mapping or validation issues below.")
            else:
                ship_payload, ship_mime = dataframe_download_payload(ship_export, "XLSX", "Sheet1")
                st.download_button(
                    "Download Uber Freight BulkUpload XLSX",
                    data=ship_payload,
                    file_name=output_filename,
                    mime=ship_mime,
                )
                if st.button("Save Generated BulkUpload to SQLite"):
                    save_ship_allocation_batch(
                        output_filename,
                        mapped_ship_records,
                        ship_export,
                        selected_groups,
                        ship_payload,
                        run_notes,
                    )
                    st.success(f"Saved {output_filename}.")

            st.subheader("Validation Queue")
            validation_cols = [
                "ship_status",
                "ship_issues",
                "source_group",
                "source_file",
                "source_sheet",
                "to_number",
                "carrier",
                "site_id",
                "location_name",
                "ship_date",
                "delivery_date",
                "units",
                "lines",
                "pallets",
                "total_weight",
                "origin_external_id",
                "destination_external_id",
                "scac",
            ]
            st.dataframe(
                mapped_ship_records[[col for col in validation_cols if col in mapped_ship_records.columns]],
                use_container_width=True,
                hide_index=True,
            )

            with st.expander("Preview generated BulkUpload columns"):
                st.dataframe(ship_export, use_container_width=True, hide_index=True)

        st.subheader("Saved Daily Run History")
        saved_ship_batches = list_ship_allocation_batches()
        if saved_ship_batches.empty:
            st.caption("No saved ship allocation batches yet.")
        else:
            display_batches = saved_ship_batches.copy()
            for col in ["source_files", "source_groups"]:
                display_batches[col] = display_batches[col].apply(
                    lambda payload: ", ".join(json.loads(payload)) if isinstance(payload, str) and payload else ""
                )
            st.dataframe(display_batches, use_container_width=True, hide_index=True)
            selected_ship_batch_id = st.selectbox(
                "Download saved BulkUpload",
                saved_ship_batches["id"].tolist(),
                format_func=lambda batch_id: saved_ship_batches.loc[
                    saved_ship_batches["id"].eq(batch_id), "batch_name"
                ].iloc[0],
                key="saved_ship_batch_selector",
            )
            loaded_batch = load_ship_allocation_batch(int(selected_ship_batch_id))
            if loaded_batch:
                saved_name, saved_payload = loaded_batch
                st.download_button(
                    "Download saved BulkUpload XLSX",
                    data=saved_payload,
                    file_name=saved_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="saved_ship_batch_download",
                )

    if view == "Carrier Signals":
        st.subheader("Manual Carrier Signal Intake")
        carrier = st.selectbox("Carrier", list(CARRIER_CHANNELS.keys()) + ["Unknown"])
        default_channel = CARRIER_CHANNELS.get(carrier, "")
        channel = st.text_input("Slack channel", value=default_channel)
        message = st.text_area(
            "Paste carrier Slack message or thread excerpt",
            height=180,
            placeholder="Example: Site 379 cannot take the water pallet today. Maybe deliver Monday?",
        )

        signal_col_add, signal_col_clear = st.columns([1, 4])
        with signal_col_add:
            if st.button("Add Signal", type="primary"):
                if message.strip():
                    new_signal = classify_carrier_signal(message, carrier, channel)
                    insert_signal(new_signal)
                    st.session_state["carrier_signals"] = load_saved_signals()
                else:
                    st.warning("Paste a message before adding a signal.")
        with signal_col_clear:
            if st.button("Clear Session Signals"):
                st.session_state["carrier_signals"] = []

        signals = pd.DataFrame(st.session_state["carrier_signals"])
        if signals.empty:
            st.info("No carrier signals added yet. This tab is read-only decision support and will not message carriers.")
        else:
            edited_signals = st.data_editor(
                signals,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Status": st.column_config.SelectboxColumn("Status", options=SIGNAL_STATUSES),
                    "Urgency": st.column_config.SelectboxColumn("Urgency", options=["Low", "Medium", "High"]),
                },
                key="carrier_signal_editor",
            )
            st.session_state["carrier_signals"] = edited_signals.to_dict("records")
            if st.button("Save Signal Updates to SQLite"):
                replace_signals(st.session_state["carrier_signals"])
                st.success("Saved carrier signal updates.")

            open_signals = edited_signals[edited_signals["Status"].isin(["Open", "Escalated"])]
            st.metric("Open / Escalated Signals", format_number(len(open_signals)))

            if not tender_pipeline["records"].empty:
                st.subheader("Possible Tender Matches")
                latest_signal = edited_signals.iloc[-1].to_dict()
                matches = match_signal_to_tenders(latest_signal, tender_pipeline["records"])
                if matches.empty:
                    st.caption("No tender rows matched the latest signal yet.")
                else:
                    match_cols = [
                        "to_number",
                        "carrier",
                        "site_id",
                        "location_name",
                        "ship_date",
                        "delivery_date",
                        "pallets",
                        "water_weight",
                        "validation_status",
                    ]
                    st.dataframe(
                        matches[[col for col in match_cols if col in matches.columns]],
                        use_container_width=True,
                        hide_index=True,
                    )

    if view == "Carrier OTP Bridge":
        if otp_bridge.empty:
            st.info("Upload one or more weekly OTP bridge workbooks to populate carrier performance.")
        else:
            otp_summary = summarize_otp(otp_bridge)
            late_count = int(otp_bridge["On-Time Status"].str.lower().eq("late").sum())
            total_shipments = len(otp_bridge)
            overall_otp = 1 - (late_count / total_shipments if total_shipments else 0)
            missing_check_calls = int((otp_bridge["Bridge Bucket"] == "Missing Check Call").sum())
            late_pallets = otp_bridge.loc[
                otp_bridge["On-Time Status"].str.lower().eq("late"), "Pallets"
            ].sum()

            col_otp, col_late, col_pallets, col_check = st.columns(4)
            col_otp.metric("Overall OTP", format_percent(overall_otp))
            col_late.metric("Late Shipments", format_number(late_count))
            col_pallets.metric("Late Pallets", format_number(late_pallets))
            col_check.metric("Missing Check Calls", format_number(missing_check_calls))

            st.subheader("Carrier Reliability")
            reliability_display = otp_summary.copy()
            if "OTP %" in reliability_display.columns:
                reliability_display["OTP %"] = reliability_display["OTP %"].apply(format_percent)
            st.dataframe(
                reliability_display,
                use_container_width=True,
                hide_index=True,
            )

            chart_col, bucket_col = st.columns([1.35, 1])
            with chart_col:
                st.subheader("OTP by SCAC")
                fig = px.bar(
                    otp_summary.sort_values("OTP %"),
                    x="OTP %",
                    y="SCAC",
                    orientation="h",
                    color="OTP %",
                    color_continuous_scale="RdYlGn",
                    range_color=[0.75, 1],
                )
                fig.update_layout(height=420, margin=dict(l=10, r=10, t=20, b=10))
                st.plotly_chart(fig, use_container_width=True)

            with bucket_col:
                st.subheader("Bridge Reason Buckets")
                bucket_summary = (
                    otp_bridge["Bridge Bucket"]
                    .value_counts()
                    .rename_axis("Bridge Bucket")
                    .reset_index(name="Count")
                )
                fig = px.pie(bucket_summary, values="Count", names="Bridge Bucket", hole=0.45)
                fig.update_layout(height=420, margin=dict(l=10, r=10, t=20, b=10))
                st.plotly_chart(fig, use_container_width=True)

            st.subheader("Late Shipment Detail")
            late_detail = otp_bridge[otp_bridge["On-Time Status"].str.lower().eq("late")].copy()
            detail_cols = [
                "Week",
                "SCAC",
                "TO #",
                "Origin",
                "Destination",
                "Deliver By",
                "Actual Delivery Arrival",
                "Pallets",
                "Delay Minutes",
                "Bridge Bucket",
                "Detailed Bridge",
            ]
            st.dataframe(
                late_detail[[col for col in detail_cols if col in late_detail.columns]],
                use_container_width=True,
                hide_index=True,
            )

    if view == "Operations Productivity":
        ops_daily = ops_data.get("daily", pd.DataFrame())
        ops_weekly = ops_data.get("weekly", pd.DataFrame())
        if ops_daily.empty and ops_weekly.empty:
            st.info("Upload the DC1 OA performance workbook to populate operations productivity.")
        else:
            ops_summary = summarize_ops_overall(ops_data)
            col_units, col_hours, col_uph, col_bridges = st.columns(4)
            col_units.metric("Latest Units", format_number(ops_summary.get("latest_units")))
            col_hours.metric("Latest Hours", format_number(ops_summary.get("latest_hours")))
            col_uph.metric(
                "Latest UPH",
                format_number(ops_summary.get("latest_uph")),
                delta=(
                    f"vs {format_number(ops_summary.get('weekly_uph'))} weekly"
                    if ops_summary.get("weekly_uph")
                    else None
                ),
            )
            col_bridges.metric(
                "Bridge Notes",
                format_number(ops_summary.get("bridge_count")),
                f"{format_number(ops_summary.get('accepted_bridge_count'))} accepted",
            )

            if not ops_weekly.empty and "Week of" in ops_weekly.columns and "UPH (actual)" in ops_weekly.columns:
                st.subheader("Weekly Pack UPH Trend")
                trend = ops_weekly.dropna(subset=["Week of", "UPH (actual)"]).copy()
                if not trend.empty:
                    fig = px.line(
                        trend,
                        x="Week of",
                        y="UPH (actual)",
                        markers=True,
                        labels={"UPH (actual)": "UPH"},
                    )
                    fig.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10))
                    st.plotly_chart(fig, use_container_width=True)

            if not ops_daily.empty:
                st.subheader("Recent Daily Productivity Summary")
                daily_summary = summarize_ops_daily(ops_daily)
                display_summary = daily_summary.copy()
                for col in ["Units", "Hours", "Avg UPH", "Calculated UPH"]:
                    if col in display_summary.columns:
                        display_summary[col] = display_summary[col].round(1)
                st.dataframe(display_summary, use_container_width=True, hide_index=True)

                bridge_rows = ops_daily[
                    ops_daily["Metric Type"].eq("Bridge Exceptions")
                    & ops_daily["Bridge"].astype(str).str.strip().ne("")
                ].copy()
                if not bridge_rows.empty:
                    st.subheader("Ops Bridge Detail")
                    st.dataframe(
                        bridge_rows[
                            ["Work Date", "Name", "UPH", "Units", "Hours", "Bridge", "Accepted"]
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )

    if view == "Placard Builder":
        render_placard_builder(ship_allocation_records)

    if view == "Fill Rate / Pallet Ops":
        render_fill_rate_pallet_ops()

    if view == "Core-Mark":
        render_core_mark_view()

    if view == "Market Profiles":
        render_market_profiles()

    if view == "Reference Sheets":
        st.subheader("Shared Reference Sheets")
        st.caption(
            "Use this as a staging area for shared Google Sheet exports. The app stores the original file, detects tabs/columns, and lets you tag each workbook before it becomes deeper app functionality."
        )
        render_reference_sheet_intake()
        ready, google_message = google_credentials_ready()
        with st.expander("Connect Google Sheet", expanded=False):
            if ready:
                st.success(google_message)
            else:
                st.warning(google_message)
                st.caption(
                    "Create a Google Cloud OAuth desktop client, download it as google_credentials.json, place it in this project folder, then run pip install -r requirements.txt."
                )

            google_url = st.text_input(
                "Google Sheet URL or spreadsheet ID",
                placeholder="https://docs.google.com/spreadsheets/d/...",
            )
            google_cols = st.columns([1, 2])
            google_tag = google_cols[0].selectbox("Reference tag", REFERENCE_SHEET_TAGS, key="google_sheet_tag")
            google_notes = google_cols[1].text_input("Notes", key="google_sheet_notes")
            if st.button("Connect / Refresh Google Sheet"):
                if not ready:
                    st.error(google_message)
                else:
                    try:
                        save_google_sheet_connection(google_url, google_tag, google_notes)
                        st.success("Google Sheet synced to the local dashboard cache.")
                    except Exception as exc:
                        st.error(f"Google Sheet sync failed: {exc}")

        google_connections = list_google_sheet_connections()
        if not google_connections.empty:
            st.subheader("Connected Google Sheets")
            current_slot = scheduled_google_refresh_slot()
            next_schedule = "4:00 AM today" if datetime.now().hour < 4 else "4:00 PM today" if datetime.now().hour < 16 else "4:00 AM tomorrow"
            schedule_caption = (
                f"Auto-refresh is active. The app checks every {AUTO_REFRESH_CHECK_MINUTES} minutes while the Streamlit server is running "
                f"and refreshes once after each 4:00 AM / 4:00 PM slot. Next slot: {next_schedule}."
            )
            if current_slot and google_refresh_slot_has_run(current_slot[0]):
                schedule_caption += f" Current slot {current_slot[0]} has already refreshed."
            st.info(schedule_caption)
            editable_google = google_connections[
                ["id", "name", "tag", "notes", "last_synced_at", "last_modified_time", "source_url"]
            ].copy()
            edited_google = st.data_editor(
                editable_google,
                hide_index=True,
                use_container_width=True,
                disabled=["id", "name", "last_synced_at", "last_modified_time", "source_url"],
                column_config={
                    "tag": st.column_config.SelectboxColumn("Tag", options=REFERENCE_SHEET_TAGS),
                    "notes": st.column_config.TextColumn("Notes"),
                    "source_url": st.column_config.LinkColumn("Source URL"),
                },
                key="google_sheet_connection_editor",
            )
            google_button_cols = st.columns([1, 1, 4])
            if google_button_cols[0].button("Save Google Sheet Tags"):
                update_google_sheet_connection_rows(edited_google.to_dict("records"))
                st.success("Saved Google Sheet tags and notes.")
            if google_button_cols[2].button("Refresh All Connected Google Sheets"):
                messages = refresh_google_sheet_connections(google_connections)
                st.success("All connected Google Sheets refresh attempted.")
                for message in messages:
                    st.write(message)
            selected_google_id = google_button_cols[1].selectbox(
                "Inspect connected sheet",
                google_connections["id"].tolist(),
                format_func=lambda row_id: google_connections.loc[
                    google_connections["id"].eq(row_id), "name"
                ].iloc[0],
                key="google_sheet_selector",
            )
            selected_google = google_connections[google_connections["id"].eq(selected_google_id)].iloc[0]
            if google_button_cols[0].button("Refresh Selected Google Sheet"):
                try:
                    save_google_sheet_connection(
                        selected_google["source_url"],
                        selected_google["tag"],
                        selected_google["notes"],
                    )
                    st.success("Selected Google Sheet refreshed.")
                except Exception as exc:
                    st.error(f"Refresh failed: {exc}")

            refresh_runs = list_google_refresh_runs(limit=6)
            if not refresh_runs.empty:
                with st.expander("Scheduled Google Sheet refresh history", expanded=False):
                    display_runs = refresh_runs.copy()
                    display_runs["messages"] = display_runs["message_json"].map(
                        lambda value: "; ".join(json.loads(value or "[]")[:4])
                    )
                    st.dataframe(
                        display_runs[["scheduled_at", "ran_at", "status", "messages"]],
                        use_container_width=True,
                        hide_index=True,
                    )

            google_metadata = json.loads(selected_google["metadata_json"] or "{}")
            google_permissions = json.loads(selected_google["permissions_json"] or "[]")
            google_activity = json.loads(selected_google["activity_json"] or "[]")

            sheet_rows = []
            for sheet in google_metadata.get("sheets", []):
                columns = sheet.get("columns", [])
                sheet_rows.append(
                    {
                        "Sheet": sheet.get("sheet_name", ""),
                        "Synced Rows": sheet.get("row_count", 0),
                        "Synced Columns": sheet.get("column_count", 0),
                        "Column Names": ", ".join(columns[:12]) + (" ..." if len(columns) > 12 else ""),
                    }
                )
            st.subheader("Connected Sheet Structure")
            st.dataframe(pd.DataFrame(sheet_rows), use_container_width=True, hide_index=True)

            permission_rows = [
                {
                    "Name": permission.get("displayName", ""),
                    "Email": permission.get("emailAddress", ""),
                    "Type": permission.get("type", ""),
                    "Role": permission.get("role", ""),
                }
                for permission in google_permissions
            ]
            st.subheader("Shared Users / Permissions")
            st.dataframe(pd.DataFrame(permission_rows), use_container_width=True, hide_index=True)

            activity_rows = []
            for item in google_activity:
                actors = item.get("actors", [])
                actor_names = []
                for actor in actors:
                    user = actor.get("user", {}).get("knownUser", {})
                    actor_names.append(user.get("personName", user.get("isCurrentUser", "")))
                activity_rows.append(
                    {
                        "Time": item.get("timestamp", item.get("timeRange", {}).get("endTime", "")),
                        "Actor": ", ".join(str(name) for name in actor_names if name),
                        "Primary Action": ", ".join(item.get("primaryActionDetail", {}).keys()),
                    }
                )
            st.subheader("Recent Drive Activity")
            if activity_rows:
                st.dataframe(pd.DataFrame(activity_rows), use_container_width=True, hide_index=True)
            else:
                st.caption("No recent Drive Activity returned for this file.")

        reference_sheets = list_reference_sheets()
        if reference_sheets.empty:
            st.info("Upload shared reference workbook exports from the sidebar to start building the synchronization layer.")
        else:
            editable_refs = reference_sheets[
                [
                    "id",
                    "filename",
                    "tag",
                    "notes",
                    "created_at",
                    "replaced_at",
                    "replacement_count",
                    "file_size",
                ]
            ].copy()
            editable_refs["file_size"] = editable_refs["file_size"].apply(
                lambda size: f"{size / 1024:,.1f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):,.2f} MB"
            )
            edited_refs = st.data_editor(
                editable_refs,
                hide_index=True,
                use_container_width=True,
                disabled=["id", "filename", "created_at", "replaced_at", "replacement_count", "file_size"],
                column_config={
                    "tag": st.column_config.SelectboxColumn("Tag", options=REFERENCE_SHEET_TAGS),
                    "notes": st.column_config.TextColumn("Notes"),
                },
                key="reference_sheet_editor",
            )
            if st.button("Save Reference Sheet Tags"):
                update_reference_sheets(edited_refs.to_dict("records"))
                st.success("Saved reference sheet tags and notes.")

            selected_reference_id = st.selectbox(
                "Inspect saved reference workbook",
                reference_sheets["id"].tolist(),
                format_func=lambda file_id: reference_sheets.loc[
                    reference_sheets["id"].eq(file_id), "filename"
                ].iloc[0],
                key="reference_sheet_selector",
            )
            selected_ref = reference_sheets[reference_sheets["id"].eq(selected_reference_id)].iloc[0]
            metadata = json.loads(selected_ref["metadata_json"] or "{}")
            metadata_rows = []
            for sheet in metadata.get("sheets", []):
                columns = sheet.get("columns", [])
                metadata_rows.append(
                    {
                        "Sheet": sheet.get("sheet_name", ""),
                        "Preview Rows": sheet.get("row_count", 0),
                        "Columns": sheet.get("column_count", 0),
                        "Column Names": ", ".join(columns[:12]) + (" ..." if len(columns) > 12 else ""),
                    }
                )
            st.subheader("Detected Workbook Structure")
            st.dataframe(pd.DataFrame(metadata_rows), use_container_width=True, hide_index=True)

            loaded_reference = load_reference_sheet(int(selected_reference_id))
            if loaded_reference:
                filename, content_type, payload = loaded_reference
                st.download_button(
                    "Download selected reference workbook",
                    data=payload,
                    file_name=filename,
                    mime=content_type,
                    key="reference_sheet_download",
                )

    if view == "LEAN/5S":
        render_lean_5s_workspace()

    if view == "Presentation Locker":
        st.subheader("Saved Presentations")
        st.caption(
            "Presentation files are stored as-is for later access. Supported formats include PowerPoint, Keynote, and OpenDocument presentation files."
        )
        render_saved_file_library(
            "presentation",
            "Upload presentation files from the sidebar to save them here for later use.",
        )

    if view == "PDF Locker":
        st.subheader("Saved PDFs")
        st.caption("PDF files are stored as-is for later access and download.")
        render_saved_file_library(
            "pdf",
            "Upload PDF files from the sidebar to save them here for later use.",
        )

    if view == "Reports":
        st.subheader("Snapshot Report Generator")
        st.caption("Generates copy-ready report text only. Email sending and scheduling are future controlled integrations.")

        transportation_report = make_transportation_report(
            command_center=command_center,
            tender_pipeline=tender_pipeline,
            carrier_status=carrier_status,
            otp_bridge=otp_bridge,
        )
        operations_report = make_operations_report(
            ops_data=ops_data,
            command_center=command_center,
        )
        finance_report = make_finance_report_placeholder(
            tender_pipeline=tender_pipeline,
            command_center=command_center,
        )
        executive_report = (
            f"{make_leadership_brief(health, command_center, carrier_summary, carrier_status, site_summary, otp_bridge, ops_data)}\n\n"
            "---\n\n"
            f"{transportation_report}\n\n"
            "---\n\n"
            f"{operations_report}\n\n"
            "---\n\n"
            f"{finance_report}"
        )

        report_options = {
            "Executive Combined": executive_report,
            "Transportation": transportation_report,
            "Operations": operations_report,
            "Finance Placeholder": finance_report,
        }
        selected_report = st.selectbox("Report type", list(report_options.keys()))
        st.text_area("Copy-ready report", value=report_options[selected_report], height=460)

        with st.expander("Future email/report automation design"):
            st.write(
                "Future versions can create email drafts or scheduled reports after access and approval are clear. "
                "Recommended first step is draft-only email generation, then optional scheduled send after review controls are in place."
            )
            st.write(
                "Suggested report cadence: Transportation daily tender closeout, Ops daily productivity/cycle time, "
                "Finance weekly cost and variance review."
            )

        render_database_backup()

    if view == "Leadership Brief":
        brief = make_leadership_brief(
            health=health,
            command_center=command_center,
            carrier_summary=carrier_summary,
            carrier_status=carrier_status,
            site_summary=site_summary,
            otp_bridge=otp_bridge,
            ops_data=ops_data,
        )
        st.text_area("Copy-ready leadership brief", value=brief, height=360)


if __name__ == "__main__":
    main()
