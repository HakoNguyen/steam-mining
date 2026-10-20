"""Định dạng số theo ngôn ngữ đang chọn.
Tiếng Việt: dấu chấm ngăn nghìn, dấu phẩy thập phân ("1,34 triệu"). Tiếng Anh: "1.34M"."""
import math

import pandas as pd

from lib.i18n import lang

UNITS = {"vi": ((1e9, " tỷ"), (1e6, " triệu"), (1e3, " nghìn")),
         "en": ((1e9, "B"), (1e6, "M"), (1e3, "K"))}


def _ok(x):
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def separators():
    """Ký tự thập phân + ngăn nghìn cho Plotly."""
    return ",." if lang() == "vi" else ".,"


def num(x, decimals=0):
    if not _ok(x):
        return "—"
    s = f"{x:,.{decimals}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".") if lang() == "vi" else s


def compact(x):
    """1.335.473 -> '1,34 triệu' / '1.34M'; 225.000 -> '225 nghìn' / '225K'."""
    if not _ok(x):
        return "—"
    a = abs(x)
    dec = "," if lang() == "vi" else "."
    for limit, unit in UNITS[lang()]:
        if a >= limit:
            v = x / limit
            s = num(v, 2 if abs(v) < 10 else 1 if abs(v) < 100 else 0)
            if dec in s:
                s = s.rstrip("0").rstrip(dec)  # "20,0" -> "20", "1,50" -> "1,5"
            return f"{s}{unit}"
    return num(x)


def short_date(x):
    """'2026-10-22' / Timestamp -> '22/10' (vi) / '22 Oct' (en)."""
    if not _ok(x) or x == "":
        return "—"
    d = pd.Timestamp(x)
    return f"{d:%d/%m}" if lang() == "vi" else f"{d:%d %b}"


def vnd(x):
    return f"{num(x)} ₫" if _ok(x) else "—"


def pct(x, decimals=1, signed=False):
    """x là phần trăm (12.3 -> '12,3%' / '12.3%')."""
    if not _ok(x):
        return "—"
    s = num(x, decimals) + "%"
    return ("+" + s) if signed and x > 0 else s
