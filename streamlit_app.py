import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime

# 基本页面设置 - 必须是第一个Streamlit命令
st.set_page_config(page_title="投资监测面板", layout="wide")

# 调试输出 - 开始
st.write("🚀 应用开始启动...")
st.write("📦 正在导入配置模块...")

from config import DEFAULT_THRESHOLDS, Thresholds

st.write("📦 正在导入数据源模块...")
from data_sources.fred_client import FredClient
from data_sources.ism_te import fetch_ism_pmi_te
from data_sources.ism_scraper import fetch_ism_pmi_scrape
from data_sources.eps_fetcher import fetch_spx_eps_quarterly, compute_eps_yoy
from data_sources.cape_fetcher import fetch_shiller_cape  # 新增: CAPE 数据源

st.write("📦 正在导入逻辑模块...")
from logic.signals import evaluate_signals
from logic.report import plot_series, export_excel, export_pdf, latest_non_nan

st.write("📦 正在导入集成模块...")
from integrations.notifications import maybe_send_slack, maybe_send_email  # 新增: 告警

st.write("✅ 所有模块导入完成！")

# 加载环境变量 (.env)
st.write("🔧 正在加载环境变量...")
load_dotenv()
st.write("✅ 环境变量加载完成！")

# 页面标题和说明
st.write("🎨 正在设置页面内容...")
st.title("📊 投资监测面板 (2000–至今)")
st.caption(
    "自动拉取宏观/市场指标，硬编码信号判定与月报导出 —— 仅供研究，不构成投资建议。"
)
st.write("✅ 页面内容设置完成！")

# —— 侧栏阈值设置 —— #
st.write("⚙️ 正在设置侧栏...")
st.sidebar.header("⚙️ 阈值/参数设置")
cape_sell = st.sidebar.number_input("CAPE 卖出阈值 >", value=DEFAULT_THRESHOLDS.cape_sell, step=1.0)
cape_buy = st.sidebar.number_input("CAPE 买入阈值 <", value=DEFAULT_THRESHOLDS.cape_buy, step=1.0)
ffr_trend_m = st.sidebar.number_input(
    "FFR 趋势窗口（月）", value=DEFAULT_THRESHOLDS.ffr_trend_months, step=1
)
hy_widen = st.sidebar.number_input(
    "HY OAS 3月走阔阈值 (bps)", value=DEFAULT_THRESHOLDS.hy_oas_widen_bps, step=5.0
)
hy_narrow = st.sidebar.number_input(
    "HY OAS 回落阈值 (bps)", value=DEFAULT_THRESHOLDS.hy_oas_narrow_bps, step=5.0
)
pmi_floor = st.sidebar.number_input(
    "PMI 关键位", value=DEFAULT_THRESHOLDS.pmi_floor, step=0.5
)
pmi_near = st.sidebar.number_input(
    "PMI 逼近位", value=DEFAULT_THRESHOLDS.pmi_near_floor, step=0.5
)
pmi_cons = st.sidebar.number_input(
    "PMI 连续月数", value=DEFAULT_THRESHOLDS.pmi_consecutive, step=1
)
st.write("✅ 侧栏设置完成！")

# 根据侧栏设置生成阈值对象
st.write("🔧 正在生成阈值对象...")
th = Thresholds(
    cape_sell=cape_sell,
    cape_buy=cape_buy,
    ffr_trend_months=int(ffr_trend_m),
    hy_oas_widen_bps=hy_widen,
    hy_oas_narrow_bps=hy_narrow,
    pmi_floor=pmi_floor,
    pmi_near_floor=pmi_near,
    pmi_consecutive=int(pmi_cons),
)
st.write("✅ 阈值对象生成完成！")

# —— 数据拉取 —— #
st.write("📊 开始数据拉取流程...")
with st.spinner("⏳ 正在拉取数据 ..."):
    errors: list[str] = []
    
    # FRED 数据
    st.write("📈 正在拉取 FRED 数据...")
    try:
        fred = FredClient()
        st.write("✅ FRED 客户端创建成功")
        fedfunds = fred.fedfunds()
        st.write("✅ 联邦基金利率数据获取成功")
        m2 = fred.m2()
        st.write("✅ M2 数据获取成功")
        m2_yoy = fred.compute_m2_yoy(m2)
        st.write("✅ M2 同比计算完成")
        unrate = fred.unrate()
        st.write("✅ 失业率数据获取成功")
        hy_oas = fred.hy_oas()
        st.write("✅ HY OAS 数据获取成功")
    except Exception as e:
        st.error(f"❌ FRED 获取失败: {e}")
        errors.append(f"FRED 获取失败: {e}")
        fedfunds = pd.Series(dtype=float)
        m2_yoy = pd.Series(dtype=float)
        unrate = pd.Series(dtype=float)
        hy_oas = pd.Series(dtype=float)

    # CAPE 数据
    st.write("📈 正在拉取 CAPE 数据...")
    try:
        cape = fetch_shiller_cape()
        st.write("✅ CAPE 数据获取成功")
    except Exception as e:
        st.error(f"❌ CAPE 获取失败: {e}")
        errors.append(f"CAPE 获取失败: {e}")
        cape = pd.Series(dtype=float)

    # PMI 数据
    st.write("📈 正在拉取 PMI 数据...")
    try:
        pmi = fetch_ism_pmi_te()
        st.write("✅ TradingEconomics PMI 数据获取成功")
    except Exception as e:
        st.warning(f"⚠️ TradingEconomics PMI 获取失败: {e}")
        errors.append(f"TradingEconomics PMI 获取失败: {e}")
        try:
            st.write("🔄 尝试备选 PMI 数据源...")
            pmi = fetch_ism_pmi_scrape()
            st.write("✅ ISM 抓取备选数据获取成功")
        except Exception as e2:
            st.error(f"❌ ISM 抓取备选失败: {e2}")
            errors.append(f"ISM 抓取备选失败: {e2}")
            pmi = pd.Series(dtype=float)

    # EPS 数据
    st.write("📈 正在拉取 EPS 数据...")
    try:
        eps_q = fetch_spx_eps_quarterly()
        st.write("✅ SPX EPS 季度数据获取成功")
        eps_yoy = compute_eps_yoy(eps_q)
        st.write("✅ EPS 同比计算完成")
    except Exception as e:
        st.error(f"❌ EPS 获取失败: {e}")
        errors.append(f"EPS 获取失败: {e}")
        eps_yoy = pd.Series(dtype=float)

st.write("✅ 数据拉取流程完成！")

# —— 信号计算与总览 —— #
col1, col2, col3, col4 = st.columns(4, gap="small")

def status_text(n_buy: int, n_sell: int) -> str:
    """Determine state text based on number of buy and sell hits."""
    if n_sell >= 2 and n_buy == 0:
        return "🔴 卖出风偏下降"
    if n_buy >= 2 and n_sell == 0:
        return "🟢 买入风偏上升"
    return "🟡 中性/观望"

sig = evaluate_signals(cape=cape, ffr=fedfunds, hy_oas=hy_oas, pmi=pmi, thresholds=th)
with col1:
    st.metric("买入命中数", sig.buy_hits)
with col2:
    st.metric("卖出命中数", sig.sell_hits)
with col3:
    st.metric("状态", status_text(sig.buy_hits, sig.sell_hits))
with col4:
    st.json(sig.details)

st.divider()

# —— 可视化 —— #
plots: dict[str, any] = {}
series_dict: dict[str, pd.Series] = {}

def show(name: str, s: pd.Series) -> None:
    """Helper to render a time series plot and store it for export."""
    if s is None or len(s.dropna()) == 0:
        st.warning(f"{name}: 暂无数据")
        return
    fig = plot_series(s, name)
    st.plotly_chart(fig, use_container_width=True)
    plots[name] = fig
    series_dict[name] = s

with st.expander("📈 估值", expanded=True):
    show("Shiller CAPE（月频）", cape)
with st.expander("💵 利率与流动性", expanded=True):
    show("联邦基金利率（FEDFUNDS, FRED）", fedfunds)
    show("M2 同比 (YoY, %)", m2_yoy)
with st.expander("🧱 信用利差", expanded=True):
    show("ICE BofA US High Yield OAS（BAMLH0A0HYM2, FRED）", hy_oas)
with st.expander("🏭 经济周期", expanded=True):
    show("ISM 制造业 PMI", pmi)
    show("美国失业率（UNRATE, FRED）", unrate)
with st.expander("💰 盈利", expanded=False):
    show("标普500 EPS YoY（季度）", eps_yoy)

# —— 最新快照 + 导出 —— #
latest = {
    "CAPE": latest_non_nan(cape),
    "FEDFUNDS": latest_non_nan(fedfunds),
    "M2_YoY_%": latest_non_nan(m2_yoy),
    "HY_OAS": latest_non_nan(hy_oas),
    "PMI": latest_non_nan(pmi),
    "UNRATE": latest_non_nan(unrate),
    "SPX_EPS_YoY_%": latest_non_nan(eps_yoy),
    "Buy hits": sig.buy_hits,
    "Sell hits": sig.sell_hits,
}
latest_df = pd.DataFrame([latest])
st.subheader("📌 最新快照")
st.dataframe(latest_df, use_container_width=True)

st.subheader("📤 导出")
c1, c2 = st.columns(2)
if c1.button("导出 Excel"):
    out = os.path.join(
        "assets", f"monitor_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )
    export_excel(out, latest_df, series_dict)
    with open(out, "rb") as f:
        st.download_button("下载 Excel", f, file_name=os.path.basename(out))
if c2.button("导出 PDF"):
    out = os.path.join(
        "assets", f"monitor_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    )
    try:
        export_pdf(out, latest_df, plots)
        with open(out, "rb") as f:
            st.download_button("下载 PDF", f, file_name=os.path.basename(out))
    except Exception as e:
        st.error(f"PDF 导出失败：{e}（请确认已安装 reportlab）")

# —— 自动告警 —— #
if sig.sell_hits >= 2 or sig.buy_hits >= 2:
    text = (
        f"[Monitor] 买入命中={sig.buy_hits} 卖出命中={sig.sell_hits} 详情={sig.details}"
    )
    s1 = maybe_send_slack(text)
    s2 = maybe_send_email("Monitor 信号触发", text)
    st.info(f"已尝试告警：{s1}, {s2}")

# —— 错误提示 —— #
if 'errors' in locals() and errors:
    st.warning("数据拉取提示：\n- " + "\n- ".join(str(e) for e in errors))