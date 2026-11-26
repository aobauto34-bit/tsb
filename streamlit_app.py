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
    from unicodedata import normalize, combining

    def folded(value):
        value = str(value or "").casefold().replace("ı", "i")
        return " ".join("".join(c for c in normalize("NFD", value) if not combining(c))
                        .replace("-", " ").split())

    # Branch publications combine premium and count in one workbook.
    def policy_counts(source, branch):
        book = load_workbook(io.BytesIO(tsb_client._read(tsb_client.TSB + source["FilePath"])),
                             read_only=True, data_only=True)
        result = {}
        try:
            for sheet in book:
                rows = iter(sheet.values)
                headers = []
                name_cols = []
                for row in rows:
                    headers.append(row)
                    labels = [folded(cell) for cell in row]
                    name_cols = [i for i, label in enumerate(labels)
                                 if label in {"sirket", "sirket adi", "sirket unvani", "sirketler"}]
                    if name_cols:
                        break
                    if len(headers) >= 24:
                        break
                if not name_cols:
                    continue
                from itertools import islice, chain
                extra = list(islice(rows, 5))
                metadata = headers + [row for row in extra if not isinstance(row[name_cols[0]], str)
                                      or not row[name_cols[0]].strip()]
                cols = []
                for col in range(len(headers[-1])):
                    labels = [folded(row[col]) for row in metadata if col < len(row)]
                    if not any(label in {"police adedi", "police sayisi", "yazilan police adedi",
                                         "toplam police adedi", "police adet"} for label in labels):
                        continue
                    # Merged period headers apply until the next period starts.
                    periods = [str(cell).strip() for row in metadata for cell in row[:col+1]
                               if isinstance(cell, str) and len(cell.strip()) == 7
                               and cell.strip()[4] == "-" and cell.strip()[:4].isdigit()]
                    if periods and periods[-1] != period:
                        continue
                    cols.append(col)
                if len(cols) != 1:
                    continue
                company_col, value_col = name_cols[0], cols[0]
                companies = {}
                for row in chain(extra, rows):
                    if max(company_col, value_col) >= len(row):
                        continue
                    name, value = row[company_col], row[value_col]
                    if not isinstance(name, str) or not isinstance(value, (float, int)) or int(value) != value:
                        continue
                    name = name.strip()
                    if folded(name) in {"toplam", "genel toplam", "sektor toplami"}:
                        name = "SEKTÖR TOPLAMI"
                    if name in companies:
                        companies = {}
                        break
                    companies[name] = int(value)
                target = branch or sheet.title
                if companies and "SEKTÖR TOPLAMI" in companies:
                    # Only take a branch total from its own sheet or an explicit company summary.
                    if branch and folded(sheet.title) not in {folded(branch), "genel toplam", "ozet", "sirket bazinda", "toplam"}:
                        continue
                    result[target] = companies
            return result
        finally:
            book.close()

    sources = {}
    for file in files:
        if (file.get("PeriodYear"), file.get("PeriodMonth")) != (month.year, month.month):
            continue
        title = folded(file.get("FileName"))
        if not file.get("FilePath", "").lower().endswith(".xlsx"):
            continue
        if "police adet" in title:
            branch = None
        elif "prim" in title and "adet" in title and ("kasko" in title or "trafik" in title):
            branch = "Kasko" if "kasko" in title else "Trafik"
        else:
            continue
        if branch not in sources or file.get("CreatedDate", "") > sources[branch].get("CreatedDate", ""):
            sources[branch] = file
    for branch, source in sources.items():
        try:
            for key, values in policy_counts(source, branch).items():
                counts.setdefault(key, {}).update(values)
        except Exception:
            logging.getLogger(__name__).exception("TSB adet dosyası %s", source.get("FileName"))
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
