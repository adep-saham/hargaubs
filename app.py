import json
import time
import re
from io import BytesIO
from datetime import datetime, timedelta

import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="UBS Chart Downloader", layout="wide")
st.title("📈 UBS Lifestyle – Ambil Data Grafik (admin-ajax.php)")

AJAX_URL = "https://ubslifestyle.com/wp-admin/admin-ajax.php"
REFERER = "https://ubslifestyle.com/harga-buyback-hari-ini/"

# === Isi sesuai DevTools Payload ===
DEFAULT_ACTION = "PASTE_ACTION_DARI_PAYLOAD"
DEFAULT_TYPE = "sell"     # atau "buyback"
DEFAULT_RANGE = "1year"   # atau "365" / "1y"

def looks_like_html(text: str) -> bool:
    t = (text or "").lstrip().lower()
    return t.startswith("<!doctype html") or t.startswith("<html") or "<title>" in t[:400]

def to_excel_bytes(df: pd.DataFrame, sheet_name="UBS_Chart") -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    buf.seek(0)
    return buf.getvalue()

def fetch_ubs_raw(action: str, tipe: str, rng: str, key_range: str = "range"):
    """
    Return: (status_code, content_type, text, json_obj_or_none)
    """
    headers = {
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

    payload = {
        "action": action,
        "type": tipe,
        key_range: rng,  # range / period / days
    }

    # retry ringan
    last = None
    for attempt in range(1, 4):
        try:
            r = requests.post(AJAX_URL, headers=headers, data=payload, timeout=30)
            ct = r.headers.get("content-type", "")
            txt = r.text
            js = None

            if r.status_code == 200 and ("application/json" in ct or txt.strip().startswith("[") or txt.strip().startswith("{")):
                try:
                    js = r.json()
                except Exception:
                    # kadang json tapi content-type aneh
                    try:
                        js = json.loads(txt)
                    except Exception:
                        js = None

            return r.status_code, ct, txt, js

        except Exception as e:
            last = e
            time.sleep(1.5 * attempt)

    raise RuntimeError(f"Gagal request setelah retry: {last}")

def parse_to_df(js):
    """
    Expect format dari screenshot kamu:
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
        raise RuntimeError("JSON bukan list / kosong")

    series0 = js[0]
    if not isinstance(series0, dict) or "data" not in series0:
        raise RuntimeError("JSON tidak punya key 'data' pada elemen pertama")

    block = series0["data"]
    if not isinstance(block, list) or not block or not isinstance(block[0], list) or len(block[0]) < 2:
        raise RuntimeError("Format data[0] tidak sesuai (harus list: [start_ts, harga...])")

    data_block = block[0]
    start_ts = data_block[0]
    prices = data_block[1:]

    start_date = datetime.fromtimestamp(start_ts / 1000).date()

    rows = []
    for i, price in enumerate(prices):
        rows.append({
            "tanggal": start_date + timedelta(days=i),
            "harga": int(price),
        })

    df = pd.DataFrame(rows).sort_values("tanggal").reset_index(drop=True)
    return df

# =========================
# UI
# =========================
c1, c2, c3, c4 = st.columns([2, 1.5, 1.5, 1.5])
with c1:
    action = st.text_input("action (dari Payload)", value=DEFAULT_ACTION)
with c2:
    tipe = st.selectbox("type", ["sell", "buyback"], index=0 if DEFAULT_TYPE == "sell" else 1)
with c3:
    rng = st.text_input("range value", value=DEFAULT_RANGE)
with c4:
    key_range = st.selectbox("nama parameter range", ["range", "period", "days"], index=0)

show_debug = st.checkbox("Tampilkan debug response", value=True)

if st.button("📥 Ambil data grafik"):
    status, ct, txt, js = fetch_ubs_raw(action, tipe, rng, key_range=key_range)

    st.write(f"**HTTP Status:** {status}")
    st.write(f"**Content-Type:** {ct}")

    # Kalau diblok (sering 403 + HTML)
    if status != 200 or js is None:
        if looks_like_html(txt):
            st.error(
                "Server mengembalikan HTML (kemungkinan diblok WAF/Cloudflare/anti-bot, sering terjadi di Streamlit Cloud). "
                "Coba: ganti User-Agent/headers via Copy as cURL, atau jalankan fetch di lokal/GitHub Actions."
            )
        else:
            st.error("Response bukan JSON / gagal parse JSON.")

        if show_debug:
            st.subheader("Response snippet")
            st.code(txt[:2000])
        st.stop()

    # Parse ke dataframe
    try:
        df = parse_to_df(js)
    except Exception as e:
        st.error(f"Gagal parse format chart: {e}")
        if show_debug:
            st.subheader("JSON (snippet)")
            st.code(json.dumps(js, indent=2)[:2000])
        st.stop()

    st.success(f"Berhasil! Total data: {len(df)}")
    st.dataframe(df, use_container_width=True)

    colA, colB = st.columns(2)
    with colA:
        st.download_button(
            "⬇️ Download CSV",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"ubs_chart_{tipe}_{rng}.csv",
            mime="text/csv",
        )
    with colB:
        st.download_button(
            "⬇️ Download Excel",
            data=to_excel_bytes(df, sheet_name=f"{tipe}_{rng}"),
            file_name=f"ubs_chart_{tipe}_{rng}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
