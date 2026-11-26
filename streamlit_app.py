"""Run with: streamlit run streamlit_app.py (Python 3.12)."""
import hashlib
import copy
import json
import logging
from pathlib import Path

import streamlit as st
import tsb_client

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Sigorta Pusula", page_icon="◈", layout="wide", initial_sidebar_state="collapsed")


@st.cache_data(show_spinner=False)
def bootstrap():
    catalog = json.loads((ROOT / "data/catalog.json").read_text("utf-8"))
    data = {}
    for path in sorted((ROOT / "data").glob("20*Q*.json")):
        value = json.loads(path.read_text("utf-8"))
        value["status"] = "snapshot"
        data[path.stem] = value
    monthly = json.loads((ROOT / "data/monthly.json").read_text("utf-8"))
    options = {branch: [row[0] for row in rows] for branch, rows in monthly["tables"].items()}
    return dict(monthlyOptions=options, periods=catalog, data=data, latest=next(p["key"] for p in catalog if p["key"] in data))


@st.cache_data(ttl=21600, max_entries=1, show_spinner=False)
def live_catalog():
    return tsb_client.discover()


@st.cache_data(ttl=21600, max_entries=16, show_spinner=False)
def live_period(key):
    return tsb_client.load_period(tsb_client.get_period(key))


@st.cache_data(ttl=21600, max_entries=60, show_spinner=False)
def monthly_totals(period):
    from datetime import date
    import io
    from openpyxl import load_workbook

    month = date.fromisoformat(period + "-01")
    saved = json.loads((ROOT / "data/monthly.json").read_text("utf-8"))
    premiums = {name: {r[0]: r[1] for r in rows} for name, rows in saved["tables"].items()} if saved["period"] == period else {}
    params = dict(periodYear=month.year, periodMonth=month.month,
                  statisticCategoryId=1, statisticSubCategoryId=1, statisticPeriodId=0)
    files = []
    page = 1
    while True:
        try:
            result = tsb_client._json("/Statistic/GetStatistics", {**params, "pageId": page})
        except Exception:
            if premiums:
                return dict(premiums=premiums, counts={})
            raise
        rows = result.get("Result") or []
        files.extend(rows)
        if not rows or page * 10 >= result.get("TotalCount", 0):
            break
        page += 1
    candidates = [f for f in files if f.get("PeriodYear") == month.year and
                  f.get("PeriodMonth") == month.month and "prim üretimleri sıralama" in
                  f.get("FileName", "").lower() and f["FilePath"].lower().endswith(".xlsx")]
    def read_totals(source, counts=False):
        book = load_workbook(io.BytesIO(tsb_client._read(tsb_client.TSB + source["FilePath"])),
                             read_only=True, data_only=True)
        totals = {}
        try:
            for sheet in book:
                rows = iter(sheet.values)
                headers = [next(rows, ()) for _ in range(12)]
                # Locate the current period in the workbook, including merged group headers.
                columns = [i for row in headers for i, cell in enumerate(row) if cell == period]
                if not columns:
                    continue
                col = columns[0]
                name_col = next((i for row in headers for i, label in enumerate(row)
                                 if str(label).strip().casefold() in {"şirket adı", "şirket ünvanı", "şirket unvanı", "şirket"}), None)
                if name_col is None:
                    name_col = 1  # Company name in the TSB ranking layout.
                from itertools import chain
                companies = {}
                for row in chain(headers, rows):
                    if max(col, name_col) >= len(row):
                        continue
                    name, value = row[name_col], row[col]
                    if not isinstance(name, str) or not name.strip():
                        continue
                    if name.strip() != "SEKTÖR TOPLAMI" and not isinstance(row[0], int):
                        continue
                    if isinstance(value, (float, int)) and (not counts or int(value) == value):
                        companies[name.strip()] = value
                if companies:
                    totals[sheet.title] = companies
            return totals
        finally:
            book.close()

    if not premiums and candidates:
        premiums = read_totals(max(candidates, key=lambda f: f.get("CreatedDate") or ""))
    counts = {}
    count_files = [f for f in files if f.get("PeriodYear") == month.year and
                   f.get("PeriodMonth") == month.month and "poliçe adet" in
                   f.get("FileName", "").lower() and f.get("FilePath", "").lower().endswith(".xlsx")]
    if count_files:
        try:
            counts = read_totals(max(count_files, key=lambda f: f.get("CreatedDate") or ""), counts=True)
        except Exception:
            logging.getLogger(__name__).exception("TSB aylık poliçe adedi %s", period)
    return dict(premiums=premiums, counts=counts)


def api(request):
    kind = request.get("kind")
    refresh = request.get("refresh") is True
    if kind == "monthly":
        if refresh:
            monthly_totals.clear(request["period"])
        return monthly_totals(request["period"])
    if kind == "catalog":
        try:
            if refresh:
                live_catalog.clear()
            periods = live_catalog()
            st.session_state["last_catalog"] = periods
            return dict(periods=periods, status="TSB katalog bağlantısı başarılı.")
        except Exception as exc:
            logging.getLogger(__name__).warning("TSB catalog: %s", exc)
            return dict(periods=st.session_state.get("last_catalog", bootstrap()["periods"]), status="Canlı katalog alınamadı; kayıtlı dönem listesi gösteriliyor.")
    if kind != "data":
        raise ValueError("Desteklenmeyen veri isteği.")
    key = request.get("period", "")
    try:
        if refresh:
            live_period.clear(key)
        value = live_period(key)
        st.session_state.setdefault("last_live", {})[key] = value
        return value
    except Exception as exc:
        logging.getLogger(__name__).warning("TSB period %s: %s", key, exc)
        saved = st.session_state.get("last_live", {}).get(key) or bootstrap()["data"].get(key)
        if saved is None:
            raise ValueError("Bu dönem için TSB bağlantısı kurulamadı ve kayıtlı veri bulunmuyor. Yeniden deneyin.") from exc
        saved = copy.deepcopy(saved)
        saved.update(status="snapshot", error="TSB canlı kaynağına şu anda erişilemiyor. Tarihi belirtilen son doğrulanmış kayıt gösteriliyor.")
        return saved


def receive_request():
    request = st.session_state.get("pusula", {}).get("request")
    if not isinstance(request, dict) or not isinstance(request.get("id"), str):
        return
    if st.session_state.get("handled_request") == request["id"]:
        return
    st.session_state["handled_request"] = request["id"]
    try:
        reply = dict(id=request["id"], ok=True, body=api(request))
    except Exception as exc:
        reply = dict(id=request["id"], ok=False, body=dict(error=str(exc)))
    st.session_state["reply"] = reply


def assets():
    return ((ROOT / "frontend/component.js").read_text("utf-8"),
        (ROOT / "frontend/component.css").read_text("utf-8"))


js, css = assets()
# Leave Streamlit's service controls accessible. Only remove the document gutters.
st.html("""<style>
  [data-testid="stMainBlockContainer"]{padding:0!important;max-width:none!important}
  [data-testid="stVerticalBlock"]{gap:0}
  [data-testid="stHeader"]{background:transparent;pointer-events:none}
  [data-testid="stToolbar"]{pointer-events:auto}
  [data-testid="stAppViewContainer"]{background:#f4f7f6}
  @media print{[data-testid="stHeader"], [data-testid="stToolbar"]{display:none!important}
    [data-testid="stMain"]{overflow:visible!important}}
</style>""")
asset_version = hashlib.sha256((js + css).encode("utf-8")).hexdigest()[:16]
dashboard = st.components.v2.component(f"sigorta_pusula_{asset_version}", html='''
  <div id="app"><div class="boot"><h1>Sigorta Pusula</h1><p>TSB verileri hazırlanıyor…</p></div></div>
  <div id="toast" role="status" aria-live="polite"></div>
''', css=css, js=js, isolate_styles=True)
dashboard(key="pusula", data=dict(bootstrap=bootstrap(), reply=st.session_state.get("reply")),
    on_request_change=receive_request, height="content")
