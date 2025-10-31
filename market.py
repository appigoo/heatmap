import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64

# -------------------------------------------------
# 1. 配置页面
# -------------------------------------------------
st.set_page_config(page_title="每日金融市场快照", layout="wide")
st.title("每日金融市场快照")
st.caption(f"数据更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# -------------------------------------------------
# 2. Tickers 映射（与您表格保持一致）
# -------------------------------------------------
tickers = {
    "美元指数": "DX-Y.NYB",
    "2年美债收益率": "^IRX",      # 近似 13 周国债
    "10年美债收益率": "^TNX",
    "VIX": "^VIX",
    "黄金": "GC=F",
    "WTI原油": "CL=F",
    "标普500": "^GSPC",
    "纳指": "^IXIC",
    "道指": "^DJI",
    "罗素2000": "^RUT",
    "比特币": "BTC-USD",
    "上证综指": "000001.SS",
    "中证300": "000300.SS",
    "REITs": "VNQ",
    "医疗": "XLV",
    "公用事业": "XLU",
    # 如需更多自行添加
}

# -------------------------------------------------
# 3. 收益率计算函数
# -------------------------------------------------
def calc_returns(hist: pd.Series) -> dict:
    """返回 1d,1w,1m,1y,qtd,ytd 的百分比变化"""
    if len(hist) < 2:
        return {k: 0.0 for k in ["1d", "1w", "1m", "1y", "qtd", "ytd"]}

    close = hist.iloc[-1]
    out = {}

    # 1 天
    out["1d"] = (close - hist.iloc[-2]) / hist.iloc[-2] * 100 if len(hist) >= 2 else 0.0

    # 1 周 ≈ 5 个交易日
    out["1w"] = (close - hist.iloc[-6]) / hist.iloc[-6] * 100 if len(hist) >= 6 else 0.0

    # 1 月 ≈ 21 个交易日
    out["1m"] = (close - hist.iloc[-22]) / hist.iloc[-22] * 100 if len(hist) >= 22 else 0.0

    # 1 年 ≈ 252 个交易日
    out["1y"] = (close - hist.iloc[-252]) / hist.iloc[-252] * 100 if len(hist) >= 252 else 0.0

    # QTD（本季度第一天）
    today = datetime.now().date()
    q_start = today.replace(month=((today.month - 1) // 3) * 3 + 1, day=1)
    q_idx = hist.index.get_indexer([pd.Timestamp(q_start)], method="nearest")[0]
    out["qtd"] = (close - hist.iloc[q_idx]) / hist.iloc[q_idx] * 100 if q_idx >= 0 else 0.0

    # YTD（本年第一天）
    y_start = today.replace(month=1, day=1)
    y_idx = hist.index.get_indexer([pd.Timestamp(y_start)], method="nearest")[0]
    out["ytd"] = (close - hist.iloc[y_idx]) / hist.iloc[y_idx] * 100 if y_idx >= 0 else 0.0

    return out

# -------------------------------------------------
# 4. 缓存数据（避免每次刷新都重新下载）
# -------------------------------------------------
@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)  # 24h 缓存
def fetch_all():
    rows = []
    for name, ticker in tickers.items():
        try:
            # 2 年历史足够算所有周期
            df = yf.download(ticker, period="2y", progress=False, auto_adjust=True)
            if df.empty or "Close" not in df.columns:
                continue
            close_series = df["Close"].dropna()
            close = close_series.iloc[-1]
            ret = calc_returns(close_series)

            row = {
                "指标": name,
                "收盘": round(close, 2),
                "1天": f"{ret['1d']:.1f}%",
                "1周": f"{ret['1w']:.1f}%",
                "1月": f"{ret['1m']:.1f}%",
                "1年": f"{ret['1y']:.1f}%",
                "QTD": f"{ret['qtd']:.1f}%",
                "YTD": f"{ret['ytd']:.1f}%",
            }
            rows.append(row)
        except Exception as e:
            st.warning(f"{ticker} 获取失败: {e}")
    return pd.DataFrame(rows)

# -------------------------------------------------
# 5. 主逻辑
# -------------------------------------------------
df = fetch_all()

# 让收盘列保持数值（用于排序）
df["收盘"] = pd.to_numeric(df["收盘"], errors="coerce")

# 排序：先把常见指数放在前面
priority = ["美元指数", "10年美债收益率", "VIX", "黄金", "WTI原油",
            "标普500", "纳指", "道指", "罗素2000", "比特币"]
df["sort"] = df["指标"].apply(lambda x: priority.index(x) if x in priority else 999)
df = df.sort_values("sort").drop("sort", axis=1).reset_index(drop=True)

# -------------------------------------------------
# 6. 颜色函数（正绿 负红）
# -------------------------------------------------
def color_cell(val):
    try:
        v = float(val.rstrip("%"))
        color = "#90EE90" if v > 0 else "#FFB6C1" if v < 0 else "#FFFFFF"
        return f"background-color: {color}"
    except:
        return ""

# -------------------------------------------------
# 7. 展示表格
# -------------------------------------------------
st.subheader(f"数据日期：{datetime.now().strftime('%Y/%m/%d')}")
styled = df.style.applymap(color_cell, subset=["1天", "1周", "1月", "1年", "QTD", "YTD"])
st.dataframe(styled, use_container_width=True)

# -------------------------------------------------
# 8. 下载 CSV
# -------------------------------------------------
csv = df.to_csv(index=False, encoding="utf-8-sig").encode()
b64_csv = base64.b64encode(csv).decode()
href_csv = f'<a href="data:file/csv;base64,{b64_csv}" download="金融快照_{datetime.now().strftime("%Y%m%d")}.csv">下载 CSV</a>'
st.markdown(href_csv, unsafe_allow_html=True)

# -------------------------------------------------
# 9. 热力图 & 下载 PNG
# -------------------------------------------------
st.subheader("收益率热力图")
numeric = df.set_index("指标")[["1天", "1周", "1月", "1年", "QTD", "YTD"]]
numeric = numeric.replace("%", "", regex=True).astype(float)

fig, ax = plt.subplots(figsize=(12, 8))
sns.heatmap(
    numeric.T,
    annot=True,
    fmt=".1f",
    cmap="RdYlGn",
    center=0,
    cbar_kws={"label": "收益率 (%)"},
    ax=ax,
)
ax.set_title(f"金融市场收益率热力图 - {datetime.now().strftime('%Y/%m/%d')}")
ax.set_xlabel("指标")
ax.set_ylabel("周期")
plt.tight_layout()

st.pyplot(fig)

# ---- PNG 下载 ----
buf = io.BytesIO()
fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
buf.seek(0)
b64_png = base64.b64encode(buf.read()).decode()
href_png = f'<a href="data:image/png;base64,{b64_png}" download="热力图_{datetime.now().strftime("%Y%m%d")}.png">下载 PNG 热力图</a>'
st.markdown(href_png, unsafe_allow_html=True)

# -------------------------------------------------
# 10. 手动刷新按钮（可选）
# -------------------------------------------------
if st.button("强制刷新数据"):
    st.cache_data.clear()
    st.experimental_rerun()
