import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import os

# ======== 頁面設定 ========
st.set_page_config(page_title="市場熱力圖", layout="wide")
st.title("每日市場熱力圖（yfinance 版）")
st.markdown("資料來源：Yahoo Finance，自動生成主要資產的漲跌熱力表。")

# ======== 資產清單 ========
ASSETS = {
    "美元指數": "DX-Y.NYB",
    "2年美債收益率": "^IRX",
    "10年美債收益率": "^TNX",
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
start_of_fetch = st.sidebar.date_input(
    "最早抓取日期", 
    value=date.today() - timedelta(days=400),
    min_value=date.today() - timedelta(days=1000),
    max_value=date.today()
)
save_folder = st.sidebar.text_input("CSV 存放資料夾", value="data")
os.makedirs(save_folder, exist_ok=True)

# ======== 工具函式 ========
@st.cache_data(ttl=3600, show_spinner=False)  # 快取 1 小時
def fetch_history(tickers, start_date):
    data = {}
    for tk in tickers:
        try:
            ticker = yf.Ticker(tk)
            hist = ticker.history(start=start_date, end=date.today() + timedelta(days=1), raise_errors=False)
            if hist.empty:
                st.warning(f"無資料：{tk}")
            data[tk] = hist
        except Exception as e:
            st.warning(f"抓取 {tk} 失敗：{e}")
            data[tk] = pd.DataFrame()
    return data

def nearest_price(hist_df, target_date):
    if hist_df is None or hist_df.empty:
        return np.nan
    target = pd.to_datetime(target_date)
    past_dates = hist_df.index[hist_df.index <= target]
    if len(past_dates) == 0:
        return np.nan
    return hist_df.loc[past_dates.max(), "Close"]

def pct_change(cur, prev):
    if pd.isna(cur) or pd.isna(prev) or prev == 0:
        return np.nan
    return (cur / prev - 1) * 100

def quarter_start(today):
    month = today.month
    q = (month - 1) // 3 + 1
    return date(today.year, 3*(q-1) + 1, 1)

# ======== 計算漲跌幅 ========
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
        if hist.empty or "Close" not in hist.columns:
            latest = p_1d = p_1w = p_1m = p_1y = p_qtd = p_ytd = np.nan
        else:
            latest = hist["Close"].iloc[-1]
            p_1d = nearest_price(hist, one_day)
            p_1w = nearest_price(hist, one_week)
            p_1m = nearest_price(hist, one_month)
            p_1y = nearest_price(hist, one_year)
            p_qtd = nearest_price(hist, q_start)
            p_ytd = nearest_price(hist, y_start)

        rows.append({
            "資產": name,
            "Ticker": tk,
            "收盤": round(latest, 4) if pd.notna(latest) else np.nan,
            "1日": pct_change(latest, p_1d),
            "1週": pct_change(latest, p_1w),
            "1月": pct_change(latest, p_1m),
            "1年": pct_change(latest, p_1y),
            "QTD": pct_change(latest, p_qtd),
            "YTD": pct_change(latest, p_ytd)
        })
    
    df = pd.DataFrame(rows)
    df = df.set_index("資產")
    return df

# ======== 熱力圖顏色 ========
def colorize(val):
    if pd.isna(val):
        return "background-color: #cccccc; color: #666666;"
    try:
        v = float(val)
        if v > 0:
            intensity = min(abs(v) / 10, 1)  # 根據漲幅調整顏色深淺
            green = int(167 + (255-167) * intensity)
            return f"background-color: rgba(0, {green}, 0, 0.3); color: green;"
        elif v < 0:
            intensity = min(abs(v) / 10, 1)
            red = int(255 - (255-255) * intensity)
            return f"background-color: rgba({red}, 100, 100, 0.3); color: red;"
        else:
            return "background-color: #f0f0f0; color: #333333;"
    except:
        return "background-color: #cccccc; color: #666666;"

# ======== 主程式 ========
if st.button("生成市場熱力圖", type="primary"):
    with st.spinner("正在從 Yahoo Finance 抓取資料..."):
        tickers = list(ASSETS.values())
        hist_map = fetch_history(tickers, start_of_fetch)
        df = compute_changes(hist_map)

    # 樣式套用
    style_cols = ["1日", "1週", "1月", "1年", "QTD", "YTD"]
    styled_df = (
        df.style
        .applymap(colorize, subset=style_cols)
        .format({
            "收盤": "{:.4f}",
            "1日": "{:.2f}%", "1週": "{:.2f}%", "1月": "{:.2f}%",
            "1年": "{:.2f}%", "QTD": "{:.2f}%", "YTD": "{:.2f}%"
        }, na_rep="N/A")
        .set_properties(**{'text-align': 'center'}, subset=style_cols)
    )

    st.subheader(f"市場表現（{date.today().strftime('%Y-%m-%d')}）")
    st.dataframe(styled_df, use_container_width=True)

    # 儲存 CSV
    csv_filename = f"market_heatmap_{date.today().isoformat()}.csv"
    csv_path = os.path.join(save_folder, csv_filename)
    df.to_csv(csv_path, encoding="utf-8-sig", float_format="%.4f")

    st.success(f"已儲存：`{csv_path}`")
    
    with open(csv_path, "rb") as f:
        st.download_button(
            label="下載 CSV 檔案",
            data=f,
            file_name=csv_filename,
            mime="text/csv",
            type="secondary"
        )
else:
    st.info("點擊上方按鈕生成最新市場熱力圖。")

# ======== 說明 ========
st.markdown("""
---
**說明**  
- **顏色**：綠色上漲，紅色下跌，灰色無資料  
- **% 變化**：以最新收盤價計算  
- **資料時間**：美股收盤後更新（可能有延遲）  
- **CSV 自動儲存**：可於側欄設定資料夾  
""")
