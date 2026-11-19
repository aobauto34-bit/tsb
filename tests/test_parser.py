"""Financial regression: compare Python XLSX parsing to the validated snapshot.

python tests/test_parser.py PATH_TO_TSB_XLSX_DIRECTORY
Expected official files: 5637.xlsx, 5642.xlsx, 5633.xlsx, 5636.xlsx.
"""
import json
import io
import math
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tsb_client as tsb

source = Path(sys.argv[1])
reference = json.loads((ROOT / "data/2026Q3.json").read_text("utf-8"))
count = 0


def compare(actual, expected, path=""):
    global count
    if isinstance(expected, dict):
        for key, value in expected.items():
            compare(actual[key], value, path + "." + key)
    elif isinstance(expected, list):
        assert len(actual) == len(expected), path
        for i, value in enumerate(expected):
            compare(actual[i], value, path + f"[{i}]")
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        assert math.isclose(actual, expected, rel_tol=1e-9, abs_tol=.01), (path, actual, expected)
        count += 1
    else:
        assert actual == expected, (path, actual, expected)
        count += 1


def download(url):
    file = next(f for f in reference["period"]["files"] if tsb.urljoin(tsb.TSB, f["FilePath"]) == url)
    return (source / f"{file['Id']}.xlsx").read_bytes()


with patch.object(tsb, "_read", side_effect=download):
    parsed = tsb.load_period(reference["period"])
for key in ("rows", "balances", "channels"):
    actual = sorted(parsed[key], key=lambda r: (r["branch"], r["id"]))
    expected = sorted(reference[key], key=lambda r: (r["branch"], r["id"]))
    compare(actual, expected, key)
assert all(c["ok"] for c in parsed["checks"])
assert parsed["status"] == "live" and not parsed["warnings"]
for invalid in ("../../etc/passwd", "2026Q5", "1999Q1", None):
    try:
        tsb.get_period(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid period accepted")
assert tsb._sum(3, None) is None and tsb._number("42") is None

class Response(io.BytesIO):
    url = "https://www.tsb.org.tr/content/Statistics/test.xlsx"

with patch.object(tsb, "urlopen", return_value=Response(b"workbook")) as opening:
    assert tsb._read("https://www.tsb.org.tr/content/Statistics/Özet 2026.xlsx") == b"workbook"
    assert opening.call_args.args[0].full_url.endswith("/%C3%96zet%202026.xlsx")
try:
    tsb._read("https://example.com/file.xlsx")
except ValueError:
    pass
else:
    raise AssertionError("Unapproved source host accepted")
print(f"PASS: {count:,} financial and schema values match the validated TSB snapshot; 5 reconciliations passed.")
