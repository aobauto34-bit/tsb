"""Run with: streamlit run streamlit_app.py (Python 3.12)."""
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
    return dict(periods=catalog, data=data, latest=next(p["key"] for p in catalog if p["key"] in data))


@st.cache_data(ttl=21600, max_entries=1, show_spinner=False)
def live_catalog():
    return tsb_client.discover()


@st.cache_data(ttl=21600, max_entries=16, show_spinner=False)
def live_period(key):
    return tsb_client.load_period(tsb_client.get_period(key))


def api(request):
    kind = request.get("kind")
    refresh = request.get("refresh") is True
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


@st.cache_data(show_spinner=False)
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
dashboard = st.components.v2.component("sigorta_pusula", html='''
  <div id="app"><div class="boot"><h1>Sigorta Pusula</h1><p>TSB verileri hazırlanıyor…</p></div></div>
  <div id="toast" role="status" aria-live="polite"></div>
''', css=css, js=js, isolate_styles=True)
monthly = json.loads((ROOT / "data/monthly.json").read_text("utf-8"))
production, financial = st.tabs(["Aylık prim üretimi", "Üç aylık mali ve teknik göstergeler"])
with production:
    st.subheader(f"Yılbaşından {monthly['period']} sonuna kadar prim üretimi")
    branch = st.selectbox("Branş veya sektör", monthly["tables"].keys())
    table = []
    for company, premium, prior, growth, share in monthly["tables"][branch]:
        percent = lambda value: None if not isinstance(value, (int, float)) else round(value * 100, 4)
        table.append({"Şirket": company, "Üretim (TL)": premium,
                      "Geçen yıl aynı dönem (TL)": prior, "Büyüme (%)": percent(growth),
                      "Pazar payı (%)": percent(share)})
    st.dataframe(table, hide_index=True)
    st.caption(f"TSB geçici üretim verileri · Kaynak revizyonu {monthly['source']['CreatedDate'][:10]}")
with financial:
    dashboard(key="pusula", data=dict(bootstrap=bootstrap(), reply=st.session_state.get("reply")),
        on_request_change=receive_request, height="content")
