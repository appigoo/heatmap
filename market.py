import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import os

# ======== 頁面設定 ========
st.set_page_config(page_title="市場熱力圖", layout="wide")
st.title("每日市場熱力圖（yfinance 版）")
st.markdown("資料來源：Yahoo Finance，自動生成主要資產漲跌熱力表。")

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
    min_value=date(2000, 1, 1),
    max_value=date.today()
)
save_folder = st.sidebar.text_input("CSV 存放資料夾", value="data")
os.makedirs(save_folder, exist_ok=True)

# ======== 時區工具 ========
NY_TZ = 'America/New_York'

def to_ny_aware(dt):
    """將任何日期轉為 NY 時區感知的 datetime"""
    if dt is None:
        return None
    if isinstance(dt, str):
        dt = pd.to_datetime(dt)
    if isinstance(dt, date) and not isinstance(dt, datetime):
        dt = datetime(dt.year, dt.month, dt.day)
    if pd.isna(dt):
        return None
    if dt.tz is None:
        return pd.Timestamp(dt).tz_localize(NY_TZ)
    else:
        return pd.Timestamp(dt).tz_convert(NY_TZ)

# ======== 資料抓取（快取 + 時區統一）========
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_history(tickers, start_date):
    data = {}
    start_ny = to_ny_aware(start_date)
    end_ny = to_ny_aware(date.today() + timedelta(days=1))

    for tk in tickers:
        try:
            ticker = yf.Ticker(tk)
            hist = ticker.history(
                start=start_ny.date(),
                end=end_ny.date(),
                raise_errors=False
            )
            if hist.empty:
                st.warning(f"無資料：{tk}")
            else:
                # 強制轉為 NY 時區
                if hist.index.tz is None:
                    hist.index = hist.index.tz_localize(NY_TZ)
                else:
                    hist.index = hist.index.tz_convert(NY_TZ)
            data[tk] = hist
        except Exception as e:
            st.warning(f"抓取 {tk} 失敗：{e}")
            data[tk] = pd.DataFrame()
    return data

# ======== 最近價格查詢（時區安全）========
def nearest_price(hist_df, target_date):
    if hist_df is None or hist_df.empty:
        return np.nan

    target = to_ny_aware(target_date)
    if target is None:
        return np.nan

    idx = hist_df.index
    past_dates = idx[idx <= target]
    if past_dates.empty:
        return np.nan

    closest = past_dates.max()
    return hist_df.loc[closest, "Close"]

# ======== 計算漲跌幅 ========
def quarter_start(today):
    month = today.month
    q = (month - 1) // 3 + 1
    return date(today.year, 3 * (q - 1) + 1, 1)

def compute_changes(hist_map):
    rows = []
    today = date.today()
    today_ny = to_ny_aware(today)

    # 各期間基準日（均轉為 NY 時區）
    one_day = to_ny_aware(today - timedelta(days=1))
    one_week = to_ny_aware(today - timedelta(days=7))
    one_month = to_ny_aware(today - timedelta(days=30))
    one_year = to_ny_aware(today - timedelta(days=365))
    q_start = to_ny_aware(quarter_start(today))
    y_start = to_ny_aware(date(today.year, 1, 1))

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
            "1日": (lambda x, y: round((x / y - 1) * 100, 2) if pd.notna(x) and pd.notna(y) and y != 0 else np.nan)(latest, p_1d),
            "1週": (lambda x, y: round((x / y - 1) * 100, 2) if pd.notna(x) and pd.notna(y) and y != 0 else np.nan)(latest, p_1w),
            "1月": (lambda x, y: round((x / y - 1) * 100, 2) if pd.notna(x) and pd.notna(y) and y != 0 else np.nan)(latest, p_1m),
            "1年": (lambda x, y: round((x / y - 1) * 100, 2) if pd.notna(x) and pd.notna(y) and y != 0 else np.nan)(latest, p_1y),
            "QTD": (lambda x, y: round((x / y - 1) * 100, 2) if pd.notna(x) and pd.notna(y) and y != 0 else np.nan)(latest, p_qtd),
            "YTD": (lambda x, y: round((x / y - 1) * 100, 2) if pd.notna(x) and pd.notna(y) and y != 0 else np.nan)(latest, p_ytd),
        })

    df = pd.DataFrame(rows).set_index("資產")
    return df

# ======== 熱力圖顏色（動態深淺）========
def colorize(val):
    if pd.isna(val):
        return "background-color: #f0f0f0; color: #999;"
    try:
        v = float(val)
        if v > 0:
            intensity = min(abs(v) / 15, 1)
            g = int(180 + (255 - 180) * intensity)
            return f"background-color: rgba(0, {g}, 0, {0.15 + 0.25 * intensity}); color: green; font-weight: bold;"
        elif v < 0:
            intensity = min(abs(v) / 15, 1)
            r = int(255 - (255 - 200) * intensity)
            return f"background-color: rgba({r}, 100, 100, {0.15 + 0.25 * intensity}); color: red; font-weight: bold;"
        else:
            return "background-color: #ffffff; color: #333;"
    except:
        return "background-color: #f0f0f0; color: #999;"

# ======== 主程式 ========
if st.button("生成市場熱力圖", type="primary"):
    with st.spinner("正在從 Yahoo Finance 抓取資料..."):
        tickers = list(ASSETS.values())
        hist_map = fetch_history(tickers, start_of_fetch)
        df = compute_changes(hist_map)

    # 樣式
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
        .set_table_styles([
            {'selector': 'th', 'props': 'text-align: center;'},
            {'selector': 'td', 'props': 'padding: 8px;'}
        ])
    )

    st.subheader(f"市場表現（{date.today().strftime('%Y-%m-%d')}）")
    st.dataframe(styled_df, use_container_width=True)

    # 儲存 CSV
    csv_filename = f"market_heatmap_{date.today().isoformat()}.csv"
    csv_path = os.path.join(save_folder, csv_filename)
    df.to_csv(csv_path, encoding="utf-8-sig", float_format="%.4f")

    st.success(f"已儲存 CSV：`{csv_path}`")
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

# ======== 頁尾說明 ========
st.markdown("""
---
**說明**  
- **綠色**：上漲（越深越強）  
- **紅色**：下跌（越深越弱）  
- **灰色**：無資料  
- 所有時間以 **美東時間 (America/New_York)** 計算  
- 資料來源：`yfinance`（Yahoo Finance）  
- CSV 自動儲存於側欄設定的資料夾  
""")
