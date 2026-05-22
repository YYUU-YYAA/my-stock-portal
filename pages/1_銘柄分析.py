"""銘柄分析 & バリュエーション電卓"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from urllib.parse import quote as url_quote

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from valuation import (
    ValuationResult, calc_dcf, calc_per_val, calc_pbr_val,
    calc_graham_val, calc_ddm_val, calc_ev_ebitda_val,
    dcf_sensitivity_matrix,
)
from utils import (
    EXAMPLES, SECTOR_BENCHMARKS, METHOD_DESCRIPTIONS,
    fmt_price, fmt_pct, to_tv_symbol, estimate_wacc,
    result_html, parse_news,
    load_data, search_tickers, load_prices_batch,
    render_tradingview_chart,
)

st.set_page_config(
    page_title="銘柄分析 | Stock Portal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.result-box{background:#f8f9fa;border-radius:12px;padding:24px;text-align:center;margin-top:8px}
.fair-value{font-size:2.4em;font-weight:bold;margin-bottom:4px}
.upside-up{color:#28a745;font-size:1.3em;font-weight:bold}
.upside-down{color:#dc3545;font-size:1.3em;font-weight:bold}
.upside-mid{color:#fd7e14;font-size:1.3em;font-weight:bold}
.nc{background:#fff;border:1px solid #e8e8e8;border-radius:8px;padding:12px;margin-bottom:6px}
.nc a{text-decoration:none;color:#111;font-weight:500;font-size:0.9em}
</style>
""", unsafe_allow_html=True)

# ============================================================
# サイドバー
# ============================================================
with st.sidebar:
    st.markdown("## 📊 銘柄分析")
    st.page_link("app.py", label="← ニュース & マーケット")
    st.page_link("pages/2_ウォッチリスト.py", label="⭐ ウォッチリスト")
    st.markdown("---")

    # 検索
    st.markdown("**🔍 銘柄検索**")
    search_q = st.text_input("", placeholder="Apple, AAPL, トヨタ...",
                              key="sq", label_visibility="collapsed")
    if search_q and len(search_q) >= 2:
        with st.spinner("検索中..."):
            suggestions = search_tickers(search_q)
        if suggestions:
            labels = [""] + [f"{r['symbol']}  {r['name']}" for r in suggestions]
            sel = st.selectbox("候補", labels, key="ssel",
                               label_visibility="collapsed")
            if sel:
                sel_ticker = sel.split("  ")[0].strip()
                if st.button(f"「{sel_ticker}」を分析", type="primary",
                             use_container_width=True):
                    st.session_state.active_ticker = sel_ticker
                    load_data.clear()
                    st.rerun()

    st.markdown("---")
    st.markdown("**クイック選択**")
    cols = st.columns(2)
    for i, (label, tkr) in enumerate(EXAMPLES.items()):
        if cols[i % 2].button(label, key=f"q_{tkr}", use_container_width=True):
            st.session_state.active_ticker = tkr
            load_data.clear()
            st.rerun()

    if "active_ticker" in st.session_state:
        st.markdown("---")
        st.info(f"表示中: **{st.session_state.active_ticker}**")

# ============================================================
# メインエリア
# ============================================================
if "active_ticker" not in st.session_state:
    st.markdown("""
## 📊 銘柄分析 & バリュエーション電卓

左サイドバーで銘柄を検索または選択してください。

| 市場 | 例 |
|------|-----|
| 🇺🇸 米国株 | AAPL, MSFT, NVDA, TSLA |
| 🇯🇵 日本株 | 7203.T, 6758.T, 7974.T |

**搭載バリュエーション手法:** DCF / PER / PBR / グレアム式 / DDM / EV/EBITDA
    """)
    st.stop()

ticker = st.session_state.active_ticker

with st.spinner(f"{ticker} のデータ取得中..."):
    data = load_data(ticker)

if not data or not data.get("current_price"):
    st.error(f"❌ {ticker} のデータを取得できませんでした。")
    st.stop()

cp = data["current_price"]
currency = data["currency"]
tv_sym = to_tv_symbol(ticker, data.get("exchange", ""))
company_name = data.get("company_name", ticker)

# ---- ヘッダー ----
c1, c2, c3, c4, c5 = st.columns([2.5, 1, 1, 1, 1.2])
with c1:
    st.markdown(f"## {company_name}")
    st.caption(f"{ticker}　|　{data.get('sector', '')} / {data.get('industry', '')}")
with c2:
    st.metric("現在株価", fmt_price(cp, currency))
with c3:
    w52h = data.get("week52_high")
    st.metric("52週高値", fmt_price(w52h, currency) if w52h else "N/A")
with c4:
    w52l = data.get("week52_low")
    st.metric("52週安値", fmt_price(w52l, currency) if w52l else "N/A")
with c5:
    mc = data.get("market_cap")
    if mc:
        mc_str = (f"¥{mc/1e12:.1f}兆" if currency == "JPY" and mc >= 1e12
                  else f"¥{mc/1e8:.0f}億" if currency == "JPY"
                  else f"${mc/1e12:.2f}T" if mc >= 1e12
                  else f"${mc/1e9:.1f}B")
        st.metric("時価総額", mc_str)

st.markdown("---")

# ---- チャート ----
st.markdown("### 📈 チャート　　<small style='color:#888;font-weight:normal'>インジケーターボタンで RSI / MACD などを追加できます</small>", unsafe_allow_html=True)
render_tradingview_chart(tv_sym, height=650)

# ---- 財務指標 ----
with st.expander("📋 財務指標サマリー"):
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    per_v, pbr_v = data.get("per"), data.get("pbr")
    m1.metric("PER", f"{per_v:.1f}x" if per_v else "N/A")
    m2.metric("PBR", f"{pbr_v:.2f}x" if pbr_v else "N/A")
    m3.metric("ROE", fmt_pct(data.get("roe")))
    m4.metric("ROA", fmt_pct(data.get("roa")))
    m5.metric("営業利益率", fmt_pct(data.get("operating_margin")))
    m6.metric("配当利回り", fmt_pct(data.get("dividend_yield")))

st.markdown("---")
st.markdown("### 🧮 バリュエーション計算")

# ---- 共通変数 ----
fcf_total = data.get("free_cash_flow") or 0
shares    = data.get("shares_outstanding") or 0
fcf_ps    = fcf_total / shares if (fcf_total > 0 and shares > 0) else 0.0
eps       = data.get("eps_ttm") or 0.0
bvps      = data.get("book_value_per_share") or 0.0
dps       = data.get("dividend_per_share") or 0.0
per_cur   = data.get("per") or 15.0
pbr_cur   = data.get("pbr") or 1.5
ev_cur    = data.get("ev_ebitda") or 12.0
ebitda    = data.get("ebitda") or 0.0
net_debt  = data.get("net_debt") or 0.0
eg        = data.get("earnings_growth") or 0.10
disc_def  = 0.07 if currency == "JPY" else estimate_wacc(data)
grow_def  = min(max(eg, 0.03), 0.20)
sector    = data.get("sector", "")
benchmark = SECTOR_BENCHMARKS.get(sector, {})

results_all: list[ValuationResult] = []

tab_dcf, tab_per, tab_pbr, tab_graham, tab_ddm, tab_ev = st.tabs([
    "📈 DCF", "💹 PER比較", "📚 PBR比較", "🧮 グレアム式", "💰 DDM配当", "🏢 EV/EBITDA",
])

# ---- DCF ----
with tab_dcf:
    with st.expander("💡 DCFとは？"):
        st.markdown(METHOD_DESCRIPTIONS["DCF"])
    if benchmark:
        st.info(f"**{sector} セクター参考値** — WACC: {benchmark['wacc']} ／ 成長率: {benchmark['growth']}")
    with st.expander("📊 この企業の参考データ", expanded=True):
        rc1, rc2, rc3, rc4 = st.columns(4)
        rc1.metric("推定WACC", f"{disc_def*100:.1f}%", help="β×ERP+RF で推定")
        rc2.metric("利益成長率", fmt_pct(data.get("earnings_growth")))
        rc3.metric("売上成長率", fmt_pct(data.get("revenue_growth")))
        rc4.metric("ROE", fmt_pct(data.get("roe")))
    l, r = st.columns(2)
    with l:
        dcf_growth = st.slider("成長率", 0.0, 30.0, round(grow_def*100, 1), 0.5, key="dg", format="%.1f%%") / 100
        dcf_term   = st.slider("永続成長率", 0.0, 5.0, 2.5, 0.1, key="dt", format="%.1f%%") / 100
        dcf_disc   = st.slider("割引率（WACC）", 4.0, 20.0, round(disc_def*100, 1), 0.1, key="dd", format="%.1f%%") / 100
        dcf_years  = st.slider("予測期間（年）", 5, 20, 10, key="dy")
        use_fcf = fcf_ps
        if fcf_ps <= 0:
            st.warning("⚠️ FCFデータなし — 手動入力")
            use_fcf = st.number_input(f"FCF/株 [{currency}]", min_value=0.01,
                                       value=1.0 if currency != "JPY" else 100.0,
                                       step=0.1 if currency != "JPY" else 1.0, key="dfcf")
        else:
            st.info(f"FCF/株（自動）: {fmt_price(fcf_ps, currency)}")
    with r:
        dcf_res = calc_dcf(cp, use_fcf, dcf_growth, dcf_term, dcf_disc, dcf_years)
        results_all.append(dcf_res)
        st.markdown(result_html(dcf_res, currency), unsafe_allow_html=True)
    with st.expander("🔬 感度分析ヒートマップ"):
        g_range = [g/100 for g in range(0, 26, 5)]
        r_range = [r/100 for r in range(5, 16)]
        matrix  = dcf_sensitivity_matrix(use_fcf, g_range, r_range, dcf_term, dcf_years)
        text_m  = [[fmt_price(v, currency) if v == v else "N/A" for v in row] for row in matrix]
        fig_h = go.Figure(go.Heatmap(
            z=matrix, x=[f"{g*100:.0f}%" for g in g_range], y=[f"{r*100:.0f}%" for r in r_range],
            colorscale="RdYlGn", zmid=cp,
            text=text_m, texttemplate="%{text}", textfont={"size": 10},
        ))
        fig_h.update_layout(title="DCF感度（縦:割引率 / 横:成長率）",
                            xaxis_title="成長率", yaxis_title="割引率", height=360)
        st.plotly_chart(fig_h, use_container_width=True)

# ---- PER ----
with tab_per:
    with st.expander("💡 PER倍率法とは？"):
        st.markdown(METHOD_DESCRIPTIONS["PER"])
    if benchmark:
        st.info(f"**{sector} 参考PER**: {benchmark['per']}倍")
    l, r = st.columns(2)
    with l:
        if per_cur: st.info(f"現在PER: {per_cur:.1f}x")
        per_target = st.slider("目標PER", 5.0, 80.0, float(min(max(per_cur or 15.0, 5.0), 80.0)),
                               0.5, key="pt", format="%.1fx")
        eps_in = st.number_input(f"EPS [{currency}]",
                                  value=float(eps) if eps > 0 else (1.0 if currency != "JPY" else 100.0),
                                  step=0.1 if currency != "JPY" else 1.0, key="pe")
    with r:
        per_res = calc_per_val(cp, eps_in, per_target)
        results_all.append(per_res)
        st.markdown(result_html(per_res, currency), unsafe_allow_html=True)
    if eps_in > 0:
        with st.expander("📊 PER感度グラフ"):
            fig_per = go.Figure()
            fig_per.add_trace(go.Scatter(x=list(range(5,55,5)),
                                          y=[eps_in*p for p in range(5,55,5)],
                                          mode="lines+markers", line=dict(color="#3B82F6")))
            fig_per.add_hline(y=cp, line_dash="dash", line_color="#dc3545",
                              annotation_text=f"現在値 {fmt_price(cp, currency)}")
            fig_per.update_layout(xaxis_title="PER", yaxis_title="理論株価",
                                  height=280, plot_bgcolor="white")
            st.plotly_chart(fig_per, use_container_width=True)

# ---- PBR ----
with tab_pbr:
    with st.expander("💡 PBR倍率法とは？"):
        st.markdown(METHOD_DESCRIPTIONS["PBR"])
    if benchmark:
        st.info(f"**{sector} 参考PBR**: {benchmark['pbr']}倍")
    l, r = st.columns(2)
    with l:
        if pbr_cur: st.info(f"現在PBR: {pbr_cur:.2f}x")
        pbr_target = st.slider("目標PBR", 0.5, 15.0, float(min(max(pbr_cur or 1.5, 0.5), 15.0)),
                               0.1, key="pbrt", format="%.2fx")
        bvps_in = st.number_input(f"1株純資産（BPS）[{currency}]",
                                   value=float(bvps) if bvps > 0 else (10.0 if currency != "JPY" else 1000.0),
                                   step=0.1 if currency != "JPY" else 1.0, key="bvpsi")
    with r:
        pbr_res = calc_pbr_val(cp, bvps_in, pbr_target)
        results_all.append(pbr_res)
        st.markdown(result_html(pbr_res, currency), unsafe_allow_html=True)

# ---- グレアム ----
with tab_graham:
    with st.expander("💡 グレアム式とは？"):
        st.markdown(METHOD_DESCRIPTIONS["グレアム"])
    l, r = st.columns(2)
    with l:
        g_grow = st.slider("期待成長率", 0.0, 30.0, round(grow_def*100, 1), 0.5, key="gg", format="%.1f%%")
        g_bond = st.slider("社債利回り（AAA）", 2.0, 8.0, 4.4, 0.1, key="gb", format="%.1f%%")
        g_eps  = st.number_input(f"EPS [{currency}]",
                                  value=float(eps) if eps > 0 else (1.0 if currency != "JPY" else 100.0),
                                  step=0.1 if currency != "JPY" else 1.0, key="geps")
    with r:
        graham_res = calc_graham_val(cp, g_eps, g_grow, g_bond)
        results_all.append(graham_res)
        st.markdown(result_html(graham_res, currency), unsafe_allow_html=True)

# ---- DDM ----
with tab_ddm:
    with st.expander("💡 DDM（配当割引モデル）とは？"):
        st.markdown(METHOD_DESCRIPTIONS["DDM"])
    if dps <= 0:
        st.warning("⚠️ 現在無配または配当データなし")
    l, r = st.columns(2)
    with l:
        ddm_dps = st.number_input(f"1株配当（DPS）[{currency}]",
                                   value=float(dps) if dps > 0 else (1.0 if currency != "JPY" else 50.0),
                                   step=0.01 if currency != "JPY" else 1.0, key="ddps")
        ddm_dg  = st.slider("配当成長率", 0.0, 15.0, 5.0, 0.1, key="ddg", format="%.1f%%") / 100
        ddm_rr  = st.slider("要求収益率", 4.0, 15.0, 8.0, 0.1, key="drr", format="%.1f%%") / 100
    with r:
        ddm_res = calc_ddm_val(cp, ddm_dps, ddm_dg, ddm_rr)
        results_all.append(ddm_res)
        st.markdown(result_html(ddm_res, currency), unsafe_allow_html=True)

# ---- EV/EBITDA ----
with tab_ev:
    with st.expander("💡 EV/EBITDA法とは？"):
        st.markdown(METHOD_DESCRIPTIONS["EV/EBITDA"])
    if ev_cur: st.info(f"現在EV/EBITDA: {ev_cur:.1f}x")
    l, r = st.columns(2)
    with l:
        ev_mult = st.slider("目標EV/EBITDA倍率", 4.0, 30.0,
                            float(min(max(ev_cur or 12.0, 4.0), 30.0)), 0.5, key="em", format="%.1fx")
        ev_ebi  = st.number_input("EBITDA", value=float(ebitda) if ebitda > 0 else 1e9,
                                   format="%.3e", key="eeb")
        ev_nd   = st.number_input("純負債", value=float(net_debt), format="%.3e", key="end")
        ev_sh   = st.number_input("発行済み株式数", value=float(shares) if shares > 0 else 1e9,
                                   format="%.3e", key="esh")
    with r:
        ev_res = calc_ev_ebitda_val(cp, ev_ebi, ev_nd, ev_sh, ev_mult)
        results_all.append(ev_res)
        st.markdown(result_html(ev_res, currency), unsafe_allow_html=True)

# ---- サマリーチャート ----
st.markdown("---")
st.markdown("### 📊 バリュエーション比較（全手法）")
valid = [r for r in results_all if r.is_valid and r.fair_value > 0]
if valid:
    fig = go.Figure(go.Bar(
        x=[r.method for r in valid], y=[r.fair_value for r in valid],
        marker_color=["#28a745" if r.fair_value > cp else "#dc3545" for r in valid],
        text=[fmt_price(r.fair_value, currency) for r in valid], textposition="outside",
    ))
    fig.add_hline(y=cp, line_dash="dash", line_color="#333",
                  annotation_text=f"現在値 {fmt_price(cp, currency)}", annotation_position="right")
    fig.update_layout(yaxis_title="理論株価", height=360, showlegend=False,
                      plot_bgcolor="white", margin=dict(t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)

# ---- DCFシナリオ ----
if use_fcf > 0:
    st.markdown("---")
    st.markdown("### 🎯 DCF シナリオ比較")
    scenarios = {
        "強気 🚀": {"g": min(dcf_growth+0.08, 0.30), "d": max(dcf_disc-0.02, 0.05), "t": dcf_term},
        "中立 ➡️":  {"g": dcf_growth, "d": dcf_disc, "t": dcf_term},
        "弱気 🐻": {"g": max(dcf_growth-0.05, 0.01), "d": min(dcf_disc+0.03, 0.18), "t": max(dcf_term-0.01, 0.01)},
    }
    sc1, sc2, sc3 = st.columns(3)
    for col, (name, p) in zip([sc1, sc2, sc3], scenarios.items()):
        res = calc_dcf(cp, use_fcf, p["g"], p["t"], p["d"], dcf_years)
        with col:
            if res.is_valid:
                sign = "+" if res.upside_pct >= 0 else ""
                color = "#28a745" if res.upside_pct > 0 else "#dc3545"
                st.markdown(f"""
                <div style="background:#f8f9fa;border-radius:10px;padding:20px;text-align:center">
                    <div style="font-weight:bold;margin-bottom:6px">{name}</div>
                    <div style="font-size:2em;font-weight:bold">{fmt_price(res.fair_value, currency)}</div>
                    <div style="color:{color};font-size:1.2em;font-weight:bold">{sign}{res.upside_pct:.1f}%</div>
                    <div style="color:#888;font-size:0.82em;margin-top:6px">
                        成長率{p['g']*100:.0f}% ／ 割引率{p['d']*100:.0f}%
                    </div>
                </div>
                """, unsafe_allow_html=True)

# ---- ニュース ----
st.markdown("---")
st.markdown("### 📰 関連ニュース & 動画")
yt_url = f"https://www.youtube.com/results?search_query={url_quote(company_name + ' 株価 分析')}"
gn_url = f"https://news.google.com/search?q={url_quote(company_name + ' ' + ticker)}&hl=ja"
c1, c2 = st.columns(2)
with c1:
    st.link_button("▶️ YouTube で検索", yt_url, use_container_width=True)
with c2:
    st.link_button("📰 Google ニュース", gn_url, use_container_width=True)

news_raw = data.get("news") or []
news_items = parse_news(news_raw)
if news_items:
    for item in news_items[:8]:
        if item.get("url") and item.get("title"):
            st.markdown(f"""
            <div class="nc">
                <a href="{item['url']}" target="_blank">📰 {item['title']}</a>
                <div style="color:#999;font-size:0.78em">{item.get('publisher','')}</div>
            </div>
            """, unsafe_allow_html=True)

st.markdown("---")
st.caption("⚠️ 投資教育目的のみ。データは yFinance より取得。")
