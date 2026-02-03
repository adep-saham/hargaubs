# app.py
# =========================================
# UBS Lifestyle - Ambil Data Grafik (admin-ajax.php)
# Berdasarkan payload DevTools:
#   action = get_harga_emas_hari_ini
#   path   = ajax/chart_interval_jual/GOLD/365
#
# Output: DataFrame(tanggal, harga) + Download CSV/Excel
# =========================================
# Requirements:
#   streamlit
#   requests
#   pandas
#   openpyxl
# =========================================

import json
from io import BytesIO
from datetime import datetime, timedelta

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
        "Chrome/120.0.0.0 Safari/537.36"
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

def to_excel_bytes(df: pd.DataFrame, sheet_name: str) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])  # batas Excel 31 char
    buf.seek(0)
    return buf.getvalue()

def fetch_chart(path_value: str):
    """
    POST admin-ajax.php with:
      action = get_harga_emas_hari_ini
      path   = <path_value>
    Return JSON object.
    """
    payload = {
        "action": ACTION_FIXED,
        "path": path_value,
    }

    r = requests.post(AJAX_URL, headers=HEADERS, data=payload, timeout=30)
    status = r.status_code
    ct = r.headers.get("content-type", "")
    txt = r.text

    if status != 200:
        raise RuntimeError(f"HTTP {status} | CT={ct}\nSnippet:\n{txt[:1200]}")

    # kadang content-type bukan json tapi body json
    try:
        return r.json()
    except Exception:
        if looks_like_html(txt):
            raise RuntimeError(f"Response HTML (kemungkinan diblok/format berubah). Snippet:\n{txt[:1200]}")
        return json.loads(txt)

def parse_ubs_series(js):
    """
    Format yang kamu tunjuk:
    [
      {
        "name":"GOLD",
        "data":[
          [ start_ts_ms, price1, price2, ... ]
        ]
      }
    ]
    """
    if not isinstance(js, list) or not js:
        raise RuntimeError("JSON kosong / bukan list")

    s0 = js[0]
    if not isinstance(s0, dict) or "data" not in s0:
        raise RuntimeError("JSON tidak punya key 'data' pada elemen pertama")

    block = s0["data"]
    if not isinstance(block, list) or not block or not isinstance(block[0], list) or len(block[0]) < 2:
        raise RuntimeError("Format data tidak sesuai (harus data[0] = [start_ts, harga...])")

    data_block = block[0]
    start_ts = data_block[0]
    prices = data_block[1:]

    start_date = datetime.fromtimestamp(start_ts / 1000).date()

    rows = []
    for i, p in enumerate(prices):
        rows.append({
            "tanggal": start_date + timedelta(days=i),
            "harga": int(p),
        })

    df = pd.DataFrame(rows).sort_values("tanggal").reset_index(drop=True)
    return df

# =========================
# UI input (kita bentuk path)
# =========================
c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.2, 1.2])

with c1:
    mode = st.selectbox("Mode", ["jual", "buyback"], index=0)
with c2:
    series = st.selectbox("Series", ["GOLD"], index=0)
with c3:
    days = st.selectbox("Range", [7, 30, 90, 180, 365], index=4)
with c4:
    st.caption("Payload fixed: action=get_harga_emas_hari_ini")

# mapping path mengikuti payload kamu:
# ajax/chart_interval_jual/GOLD/365
path_value = f"ajax/chart_interval_{mode}/{series}/{days}"

show_debug = st.checkbox("Tampilkan debug", value=False)

if st.button("📥 Ambil data grafik"):
    try:
        js = fetch_chart(path_value)
        df = parse_ubs_series(js)

        st.success(f"Berhasil! Total data: {len(df)}")
        st.dataframe(df, use_container_width=True)

        colA, colB = st.columns(2)
        with colA:
            st.download_button(
                "⬇️ Download CSV",
                data=df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"ubs_{mode}_{series}_{days}d.csv",
                mime="text/csv",
            )
        with colB:
            st.download_button(
                "⬇️ Download Excel",
                data=to_excel_bytes(df, sheet_name=f"{mode}_{days}d"),
                file_name=f"ubs_{mode}_{series}_{days}d.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        if show_debug:
            st.subheader("Debug: path yang dipakai")
            st.code(path_value)
            st.subheader("Debug: JSON snippet")
            st.code(json.dumps(js, indent=2)[:2000])

    except Exception as e:
        st.error(str(e))
        if show_debug:
            st.code(f"path={path_value}")
