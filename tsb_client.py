"""TSB public financial workbooks. Missing accounts remain None, never zero."""
from __future__ import annotations

import io
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlencode, urljoin, urlparse, quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from openpyxl import load_workbook

TSB = "https://www.tsb.org.tr"
MAX_BYTES = 20_000_000


def _read(url: str) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "www.tsb.org.tr":
        raise ValueError("Beklenmeyen kaynak adresi.")
    parts = urlsplit(url)
    url = urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe="/%"), parts.query, ""))
    request = Request(url, headers={"User-Agent": "SigortaPusula/1.0", "Accept": "*/*"})
    with urlopen(request, timeout=45) as response:
        if urlparse(response.url).hostname != "www.tsb.org.tr":
            raise ValueError("Beklenmeyen kaynak yönlendirmesi.")
        content = response.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError("Kaynak dosyası beklenen boyutu aşıyor.")
    return content


def _json(path, params):
    return json.loads(_read(TSB + path + "?" + urlencode(params)))


def periods_from(files):
    periods = {}
    for file in files:
        year, quarter = file.get("PeriodYear"), file.get("StatisticPeriodId")
        if not year or quarter not in (1, 2, 3, 4):
            continue
        key = f"{year}Q{quarter}"
        period = periods.setdefault(key, dict(key=key, year=year, quarter=quarter,
            label=f"{year} / {quarter * 3} ay", files=[], revision=""))
        period["files"].append(file)
        period["revision"] = max(period["revision"], file.get("CreatedDate") or "")
    return sorted((p for p in periods.values()
        if any(re.match(r"^4\s", f["FileName"]) for f in p["files"])),
        key=lambda p: p["key"], reverse=True)


def discover():
    params = dict(CategoryUrl="finansal-tablolar", SubCategoryUrl="sirket-bazinda-mali-ve-teknik-tablolar")
    first = _json("/Statistic/GetAllStatistics", {**params, "pageId": 1})
    count = min(12, math.ceil(first.get("TotalCount", 10) / 10))
    files = first.get("Result") or []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(lambda page: _json("/Statistic/GetAllStatistics", {**params, "pageId": page}), range(2, count + 1)):
            files.extend(result.get("Result") or [])
    periods = periods_from(files)
    if not periods:
        raise ValueError("TSB kataloğunda mali tablo bulunamadı.")
    return periods


def get_period(key):
    if not isinstance(key, str) or not re.fullmatch(r"20\d{2}Q[1-4]", key):
        raise ValueError("Geçersiz dönem.")
    year, quarter = int(key[:4]), int(key[-1])
    if not 2015 <= year <= datetime.now(timezone.utc).year:
        raise ValueError("Desteklenmeyen dönem.")
    params = dict(periodYear=year, statisticPeriodId=quarter, periodMonth=0,
        statisticCategoryId=5, statisticSubCategoryId=14)
    files = []
    for page in range(1, 4):
        result = _json("/Statistic/GetStatistics", {**params, "pageId": page})
        files.extend(result.get("Result") or [])
        if page * 10 >= result.get("TotalCount", 0):
            break
    period = next((p for p in periods_from(files) if p["key"] == key), None)
    if period is None:
        raise ValueError("TSB'de bu dönem için gelir tablosu bulunamadı.")
    return period


def _number(value):
    return value if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) else None


def _code(value):
    return re.sub(r"\.0$", "", str(value if value is not None else "").strip())


def _sum(*values):
    return None if any(v is None for v in values) else sum(values)


def _neg(value):
    return None if value is None else -value


def _table(sheet):
    rows = sheet.iter_rows(values_only=True)
    headers = next((r for i, r in enumerate(rows) if i == 4), None)
    if not headers:
        return []
    positions = {_code(v): i for i, v in enumerate(headers)}
    next(rows, None)  # row 6: human-readable headings
    output = []
    for raw in rows:
        if len(raw) < 3 or not (str(raw[2]).strip() == "HD" or _code(raw[1]) == "9000"):
            continue
        values = {k: _number(raw[i]) if i < len(raw) else None for k, i in positions.items()}
        output.append(dict(id=_code(raw[1]), name=str(raw[0] or "").strip(), values=values, raw=raw))
    return output


def parse_income(content):
    rows = []
    book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        for sheet in book:
            if sheet.title in ("MALI", "HAYAT", "EMEKLILIK"):
                continue
            for row in _table(sheet):
                v = row["values"].get
                if "60001" not in row["values"]:
                    continue
                rows.append(dict(id=row["id"], name=row["name"], branch=sheet.title,
                    gwp=v("60001"), gep=_sum(*(v(k) for k in ("60001", "60003", "60101", "60103", "60201"))),
                    claim=_neg(_sum(v("61001"), v("61101"))), expense=_neg(v("614")),
                    tech=_sum(v("60"), v("61")), transfer=v("603"), nep=_sum(v("600"), v("601"), v("602")),
                    netClaim=_neg(_sum(v("610"), v("611"))), netWritten=v("600"),
                    paid=_neg(v("61001")), outstanding=_neg(v("611011"))))
        totals = {r["id"]: r for r in rows if r["branch"] == "HAYATDISI"}
        if "MALI" in book:
            for row in _table(book["MALI"]):
                if row["id"] in totals:
                    v = row["values"].get
                    totals[row["id"]].update(netProfit=v("69"), investmentIncome=v("64"), investmentExpense=v("65"))
        if "9000" not in totals:
            raise ValueError("TSB şeması değişmiş olabilir: HD sektör satırı bulunamadı.")
    finally:
        book.close()
    return rows


def parse_balance(content):
    book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        passive = {r["id"]: r["values"] for r in _table(book["Pasif Ozet"])}
        output = []
        for row in _table(book["Aktif Ozet"]):
            v, p = row["values"].get, passive.get(row["id"], {}).get
            output.append(dict(id=row["id"], name=row["name"], branch="HAYATDISI",
                assets=_sum(v("1"), v("2")), equity=p("5"), currentAssets=v("1"), currentLiabilities=p("3"),
                cash=v("10"), currentInvestments=v("11"), investments=_sum(v("11"), v("25")),
                receivables=v("12"), reserves=_sum(p("35"), p("45"))))
        return output
    finally:
        book.close()


def parse_channels(content):
    book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        return [dict(id=r["id"], name=r["name"], branch="HAYATDISI",
            values=[_number(v) for v in r["raw"][3:8]], total=_number(r["raw"][8]))
            for r in _table(book["HAYATDISI"])]
    finally:
        book.close()


def parse_loss(content):
    book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        if "HAYATDISI" not in book:
            return None
        row = next((r for r in _table(book["HAYATDISI"]) if r["id"] == "9000"), None)
        if not row:
            return None
        raw = row["raw"]
        return dict(gep=_number(raw[22]), nep=_number(raw[23]), claim=_neg(_number(raw[24])),
            netClaim=_neg(_number(raw[25])), lr=_number(raw[26]), nlr=_number(raw[27]))
    finally:
        book.close()


def load_period(period):
    warnings, sources, parsed = [], [], {}
    for prefix, parser in ((4, parse_income), (1, parse_balance), (8, parse_channels), (5, parse_loss)):
        file = next((f for f in period["files"] if re.match(rf"^{prefix}\s", f["FileName"])), None)
        if file is None:
            if prefix == 4:
                raise ValueError("Gelir tablosu yayımlanmamış.")
            warnings.append(f"{prefix} numaralı TSB tablosu yayımlanmamış.")
            continue
        try:
            url = urljoin(TSB, file["FilePath"])
            if not urlparse(url).path.startswith("/content/Statistics/"):
                raise ValueError("Beklenmeyen kaynak adresi.")
            parsed[prefix] = parser(_read(url))
            sources.append(dict(id=file["Id"], name=file["FileName"], url=url, published=file["CreatedDate"]))
        except Exception as exc:
            if prefix == 4:
                raise
            warnings.append(f"{file['FileName']}: {exc}")
    rows, balances, channels, loss = parsed[4], parsed.get(1, []), parsed.get(8, []), parsed.get(5)
    totals = {r["id"]: r for r in rows if r["branch"] == "HAYATDISI"}
    for balance in balances:
        if balance["id"] in totals:
            totals[balance["id"]].update(balance)
    sector, checks = totals["9000"], []
    def check(name, actual, expected):
        difference = None if actual is None or expected is None else actual - expected
        checks.append(dict(name=name, actual=actual, expected=expected, difference=difference,
            ok=difference is not None and abs(difference) <= max(1, abs(expected) * 1e-7)))
    check("Şirket primleri / HD sektör toplamı", _sum(*(r["gwp"] for k, r in totals.items() if k != "9000")), sector["gwp"])
    channel = next((r for r in channels if r["id"] == "9000"), None)
    if channel:
        check("Dağıtım kanalları / brüt prim", _sum(*channel["values"]), sector["gwp"])
    if loss:
        for name, key in (("Brüt kazanılmış prim", "gep"), ("Brüt hasar", "claim"), ("Net kazanılmış prim", "nep")):
            check(name + " / Hasar-Prim dosyası", sector[key], loss[key])
    if any(not c["ok"] for c in checks):
        warnings.append("Kaynaklar arası mutabakat farkı var. Veri merkezi kontrollerini inceleyin.")
    return dict(period=period, fetchedAt=datetime.now(timezone.utc).isoformat(), source="Türkiye Sigorta Birliği",
        status="live", rows=rows, balances=balances, channels=channels, sources=sources, checks=checks, warnings=warnings)
