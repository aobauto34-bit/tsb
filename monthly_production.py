"""Import the TSB cumulative premium ranking workbook into a report snapshot."""
import hashlib
import io
import json
import math
from pathlib import Path

from openpyxl import load_workbook

import tsb_client


def snapshot(source):
    url = tsb_client.TSB + source["FilePath"]
    return parse(tsb_client._read(url), source)


def parse(content, source):
    book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    period = f"{source['PeriodYear']}-{source['PeriodMonth']:02}"
    tables = {}
    try:
        for sheet in list(book)[1:]:
            rows = list(sheet.values)
            if period not in rows[4] or rows[5][2] != "Şirket Kodu":
                raise ValueError(f"Beklenmeyen dönem veya kolonlar: {sheet.title}")
            entries = [r for r in rows[6:] if isinstance(r[0], int)]
            total, = [r for r in rows if r[1] == "SEKTÖR TOPLAMI"]
            for col in (3, 6):
                if not math.isclose(sum(r[col] or 0 for r in entries), total[col], abs_tol=1):
                    raise ValueError(f"Şirket toplamı uyuşmuyor: {sheet.title}")
            tables[sheet.title] = [[r[1], r[3], r[6], r[9], r[4]] for r in [total, *entries]]
    finally:
        book.close()
    return dict(period=period, source=source, sha256=hashlib.sha256(content).hexdigest(), tables=tables)


if __name__ == "__main__":
    import sys
    source = json.loads(Path(sys.argv[1]).read_text())
    result = snapshot(source)
    Path(__file__).with_name("data").joinpath("monthly.json").write_text(
        json.dumps(result, ensure_ascii=False, allow_nan=False), encoding="utf-8")
