import requests
import pandas as pd
from datetime import datetime, timedelta

# =============================
# KONFIGURASI
# =============================
AJAX_URL = "https://ubslifestyle.com/wp-admin/admin-ajax.php"

ACTION = "PASTE_ACTION_DARI_PAYLOAD"  # contoh: get_gold_chart
TYPE   = "sell"                       # harga jual / buyback
RANGE  = "1year"                      # 1 Tahun

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://ubslifestyle.com",
    "Referer": "https://ubslifestyle.com/harga-buyback-hari-ini/",
    "X-Requested-With": "XMLHttpRequest",
}

# =============================
# FETCH DATA
# =============================
def fetch_ubs_chart():
    payload = {
        "ACTION": ACTION,
        "type": TYPE,
        "range": RANGE
    }

    r = requests.post(AJAX_URL, headers=HEADERS, data=payload, timeout=30)
    r.raise_for_status()
    raw = r.json()

    # === VALIDASI FORMAT ===
    if not isinstance(raw, list):
        raise RuntimeError("Format response bukan list")

    series = raw[0]
    data_block = series["data"][0]

    start_ts = data_block[0]
    prices = data_block[1:]

    start_date = datetime.fromtimestamp(start_ts / 1000).date()

    rows = []
    for i, price in enumerate(prices):
        rows.append({
            "tanggal": start_date + timedelta(days=i),
            "harga_buyback": int(price)
        })

    df = pd.DataFrame(rows)
    return df

# =============================
# MAIN
# =============================
if __name__ == "__main__":
    df = fetch_ubs_chart()

    print(df.head())
    print("Total data:", len(df))

    # CSV
    df.to_csv("ubs_buyback_1tahun.csv", index=False, encoding="utf-8-sig")

    # EXCEL
    df.to_excel("ubs_buyback_1tahun.xlsx", index=False)

    print("✅ File berhasil dibuat:")
    print("- ubs_buyback_1tahun.csv")
    print("- ubs_buyback_1tahun.xlsx")
