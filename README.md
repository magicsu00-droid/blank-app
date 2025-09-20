# 投资监测面板（Streamlit + FRED）

> 目标：熊市少亏、牛市平均收益、延续复利 —— 自动拉取宏观/市场指标，做月度/季度复盘与阈值告警。

## ✨ 功能概览
- 自动获取并更新：
  - 估值：Shiller CAPE（CAPE），标普500 PE/PS（可选）
  - 利率与流动性：联邦基金利率（FEDFUNDS, FRED），M2 同比（M2SL, FRED 衍生）
  - 信用利差：ICE BofA US High Yield OAS（BAMLH0A0HYM2, FRED）
  - 经济周期：ISM 制造业 PMI（TradingEconomics API / ISM 抓取备选），美国失业率（UNRATE, FRED）
  - 盈利：标普500 EPS YoY（multpl.com 抓取 / 备用适配器）
- 可视化：2000 年至今的折线图、红黄绿信号灯、总览仪表（命中条件数）
- 硬编码交易信号（可配置阈值）
- 月报导出（Excel / PDF）
- 告警（可选）：当命中≥2 条买入/卖出信号时，通过邮件 / Slack / 企业微信推送

## 🧰 技术栈
- Python 3.10+
- Streamlit
- fredapi
- requests / pandas
- plotly
- xlsxwriter
- reportlab
- python-dotenv

## ⚙️ 安装与运行
请参考文件中的说明。
