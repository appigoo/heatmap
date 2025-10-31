import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import os

st.set_page_config(page_title="市場熱力圖", layout="wide")
st.title("📊 每日市場熱力圖（yfinance 版）")
st.markdown("資料來源：Yahoo Finance，自動生成主要資產的漲跌熱力表。")

# ======== 資產清單（貼近你圖片的版本） ========
ASSETS = {
    "美元指數": "DX-Y.NYB",       # 美元指數
    "2年美債收益率": "^IRX",       # 近似短債利率
    "10年美債收益率": "^TNX",      # 10年美債利率
    "TLT(長期美債ETF)": "TLT",
    "S&P500": "^GSPC",
    "那斯達克": "^IXIC",
    "道瓊工業": "^DJI",
    "羅素2000": "^RUT",
    "VIX(恐慌指數)": "^VIX",
    "黃金期貨": "GC=F",
    "WTI原油": "CL=F",
    "REITs指數ETF": "VNQ",
    "科技ETF": "XLK",
    "醫療ETF": "XLV",
    "金融ETF": "XLF",
    "能源ETF": "XLE",
    "非必需消費ETF": "XLY",
    "公用事業ETF": "XLU",
    "必需消費ETF": "XLP",
    "標普成長ETF": "SPYG",
    "標普價值ETF": "SPYV",
    "標普500 ETF": "SPY",
    "那斯達克100(大型科技)": "QQQ"
}

# ======== 側欄設定 ========
st.sidebar.header("設定")
start_of_fetch = st.sidebar.date_input("最早抓取日期", value=date.today() - timedelta(days=400))
save_folder = st.sidebar.text_input("CSV 存放資料夾", value="data")
os.makedirs(save_folder, exist_ok=True)

# ======== 工具函式 ========
def fetch_history(tickers, start_date):
    data = {}
    for tk in tickers:
        try:
            hist = yf.Ticker(tk).history(start=start_date, end=date.today() + timedelta(days=1))
            data[tk] = hist
        except Exception as e:
            st.warning(f"⚠️ 抓取 {tk} 失敗：{e}")
            data[tk] = pd.DataFrame()
    return data

def nearest_price(hist_df, target_date):
    if hist_df is None or hist_df.empty:
        return np.nan
    idx = hist_df.index
    le = idx[idx <= pd.to_datetime(target_date)]
    if len(le) == 0:
        return np.nan
    return hist_df.loc[le.max(), "Close"]

def pct_change(cur, prev):
    if pd.isna(cur) or pd.isna(prev) or prev == 0:
        return np.nan
    return (cur / prev - 1) * 100

def quarter_start(today):
    q = (today.month - 1) // 3 + 1
    return date(today.year, 3*(q-1)+1, 1)

def compute_changes(hist_map):
    rows = []
    today = date.today()
    one_day = today - timedelta(days=1)
    one_week = today - timedelta(days=7)
    one_month = today - timedelta(days=30)
    one_year = today - timedelta(days=365)
    q_start = quarter_start(today)
    y_start = date(today.year, 1, 1)

    for name, tk in ASSETS.items():
        hist = hist_map.get(tk, pd.DataFrame())
        latest = hist["Close"].iloc[-1] if not hist.empty else np.nan
        p_1d = nearest_price(hist, one_day)
        p_1w = nearest_price(hist, one_week)
        p_1m = nearest_price(hist, one_month)
        p_1y = nearest_price(hist, one_year)
        p_qtd = nearest_price(hist, q_start)
        p_ytd = nearest_price(hist, y_start)
        rows.append({
            "資產": name,
            "Ticker": tk,
            "收盤": round(latest, 2) if pd.notna(latest) else np.nan,
            "1日": pct_change(latest, p_1d),
            "1週": pct_change(latest, p_1w),
            "1月": pct_change(latest, p_1m),
            "1年": pct_change(latest, p_1y),
            "QTD": pct_change(latest, p_qtd),
            "YTD": pct_change(latest, p_ytd)
        })
    df = pd.DataFrame(rows).set_index("資產")
    return df

# ======== 主程式 ========
if st.button("🚀 生成市場熱力圖"):
    with st.spinner("抓取 yfinance 資料中..."):
        hist_map = fetch_history(list(ASSETS.values()), start_of_fetch)
        df = compute_changes(hist_map)

    # ======== 熱力顏色樣式 ========
    def colorize(val):
        try:
            if pd.isna(val):
                return "background-color: #cccccc"
            v = float(val)
            if v > 0:
                return "background-color: #a7f3a7"  # 綠
            elif v < 0:
                return "background-color: #f4b183"  # 橘
            else:
                return "background-color: #eeeeee"
        except:
            return "background-color: #cccccc"

    style_cols = ["1日", "1週", "1月", "1年", "QTD", "YTD"]
    styled_df = df.style.applymap(colorize, subset=style_cols).format("{:.2f}", na_rep="N/A")

    st.subheader(f"📅 {date.today().isoformat()} 市場表現")
    st.dataframe(styled_df, use_container_width=True)

    # 儲存 CSV
    csv_filename = f"market_heatmap_{date.today().isoformat()}.csv"
    csv_path = os.path.join(save_folder, csv_filename)
    df.to_csv(csv_path, encoding="utf-8-sig", float_format="%.4f")

    st.success(f"✅ 已儲存 CSV：{csv_path}")
    with open(csv_path, "rb") as f:
        st.download_button("下載 CSV", f, file_name=csv_filename, mime="text/csv")
else:
    st.info("點擊上方按鈕生成最新市場熱力圖。")

st.markdown("""
---
📘 **說明**
- 顏色說明：🟩上漲、🟧下跌、灰色＝無資料。  
- Tickers 取自 Yahoo Finance，部分可能更新有延遲。  
- 每日執行後自動產生 CSV 檔案（路徑可於側欄設定）。
""")
