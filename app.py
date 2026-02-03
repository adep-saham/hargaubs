# app.py
# =========================================
# UBS Lifestyle - Ambil Data Grafik (admin-ajax.php)
# Payload DevTools:
#   action = get_harga_emas_hari_ini
#   path   = ajax/chart_interval_jual/GOLD/365
# Response format (contoh):
# [
#   {
#     "name":"GOLD",
#     "data":[
#       [timestamp_ms, v1, v2, v3, v4],
#       [timestamp_ms, v1, v2, v3, v4],
#       ...
#     ]
#   }
# ]
# =========================================

import json
from io import BytesIO
from datetime import datetime

import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="UBS Lifestyle - Grafik", layout="wide")
st.title("📈 UBS Lifestyle – Ambil Data Grafik (admin-ajax.php)")

AJAX_URL = "https://ubslifestyle.com/wp-admin/admin-ajax.php"
REFERER = "https://ubslifestyle.com/harga-buyback-hari-ini/"
ACTION_FIXED = "get_harga_emas_hari_ini"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/144.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://ubslifestyle.com",
    "Referer": REFERER,
    "X-Requested-With": "XMLHttpRequest",
}

def looks_like_html(text: str) -> bool:
    t = (text or "").lstrip().lower()
    return t.startswith("<!doctype html") or t.startswith("<html") or "<title>" in t[:400]

def fetch_chart(path_value: str):
    payload = {"action": ACTION_FIXED, "path": path_value}
    r = requests.post(AJAX_URL, headers=HEADERS, data=payload, timeout=30)

    if r.status_code != 200:
        raise RuntimeError(
            f"HTTP {r.status_code} | CT={r.headers.get('content-type','')}\n"
            f"Snippet:\n{r.text[:1200]}"
        )

    try:
        return r.json()
    except Exception:
        if looks_like_html(r.text):
            raise RuntimeError(f"Response HTML (bukan JSON). Snippet:\n{r.text[:1200]}")
        return json.loads(r.text)

def parse_ubs_points(js, pick_index: int = 1) -> pd.DataFrame:
    """
    pick_index = 1 artinya ambil nilai pertama setelah timestamp (v1).
    Format point: [ts_ms, v1, v2, v3, v4]
    """
    if not isinstance(js, list) or not js:
        raise RuntimeError("JSON kosong / bukan list")

    series = js[0]
    if not isinstance(series, dict) or "data" not in series:
        raise RuntimeError("Format JSON tidak sesuai: elemen pertama tidak punya key 'data'")

    points = series["data"]
    if not isinstance(points, list) or len(points) == 0:
        raise RuntimeError("Key 'data' kosong / bukan list")

    rows = []
    for p in points:
        if not isinstance(p, list) or len(p) < 2:
            continue

        ts = p[0]
        # validasi timestamp
        if not isinstance(ts, (int, float)):
            continue

        # ambil nilai harga sesuai index
        # p[1] = v1, p[2] = v2, p[3] = v3, p[4] = v4
        if pick_index >= len(p):
            val = p[1]
        else:
            val = p[pick_index]

        # convert ke date
        dt = datetime.fromtimestamp(ts / 1000).date()

        rows.append({"tanggal": dt, "harga": int(val)})

    df = pd.DataFrame(rows).sort_values("tanggal").reset_index(drop=True)
    return df

def to_excel_bytes(df: pd.DataFrame, sheet_name: str) -> bytes:
    """
    Excel export.
    Prefer openpyxl. Jika openpyxl tidak ada di Streamlit Cloud, user perlu install.
    """
    buf = BytesIO()
    try:
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
        buf.seek(0)
        return buf.getvalue()
    except ModuleNotFoundError as e:
        # openpyxl tidak ada
        raise ModuleNotFoundError(
            "openpyxl belum ter-install di environment. "
            "Tambahkan `openpyxl` ke requirements.txt lalu redeploy."
        ) from e

# =========================
# UI
# =========================
c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.2, 1.4])

with c1:
    mode = st.selectbox("Mode", ["jual", "buyback"], index=0)
with c2:
    series_name = st.selectbox("Series", ["GOLD"], index=0)
with c3:
    days = st.selectbox("Range", [7, 30, 90, 180, 365], index=4)
with c4:
    pick = st.selectbox(
        "Pilih kolom harga",
        options=[
            ("v1 (index 1)", 1),
            ("v2 (index 2)", 2),
            ("v3 (index 3)", 3),
            ("v4 (index 4)", 4),
        ],
        index=0,
        format_func=lambda x: x[0],
    )

show_debug = st.checkbox("Tampilkan debug", value=False)

path_value = f"ajax/chart_interval_{mode}/{series_name}/{days}"

if st.button("📥 Ambil data grafik"):
    try:
        js = fetch_chart(path_value)

        # parse semua points
        df = parse_ubs_points(js, pick_index=pick[1])

        st.success(f"Berhasil! Total data: {len(df)}")
        st.dataframe(df, use_container_width=True)

        colA, colB = st.columns(2)

        with colA:
            st.download_button(
                "⬇️ Download CSV",
                data=df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"ubs_{mode}_{series_name}_{days}d.csv",
                mime="text/csv",
            )

        with colB:
            try:
                xbytes = to_excel_bytes(df, sheet_name=f"{mode}_{days}d")
                st.download_button(
                    "⬇️ Download Excel",
                    data=xbytes,
                    file_name=f"ubs_{mode}_{series_name}_{days}d.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            except ModuleNotFoundError as e:
                st.warning(str(e))

        if show_debug:
            st.subheader("Debug: payload")
            st.code({"action": ACTION_FIXED, "path": path_value})
            st.subheader("Debug: JSON snippet (awal)")
            st.code(json.dumps(js, indent=2)[:2500])

    except Exception as e:
        st.error(str(e))
        if show_debug:
            st.code(f"path={path_value}")
