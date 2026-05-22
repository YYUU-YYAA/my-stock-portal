"""ウォッチリスト - お気に入り銘柄管理"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go

from utils import (
    fmt_price, fmt_pct, fmt_compact,
    load_data, load_prices_batch,
    load_watchlist, save_watchlist,
)

st.set_page_config(
    page_title="ウォッチリスト | Stock Portal",
    page_icon="⭐",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.wl-card{background:#f8f9fa;border-radius:10px;padding:16px;margin-bottom:12px}
.wl-title{font-size:1.1em;font-weight:700;margin-bottom:10px}
.up{color:#28a745;font-weight:bold}
.dn{color:#dc3545;font-weight:bold}
</style>
""", unsafe_allow_html=True)

# ============================================================
# サイドバー
# ============================================================
with st.sidebar:
    st.markdown("## ⭐ ウォッチリスト")
    st.page_link("app.py", label="← ニュース & マーケット")
    st.page_link("pages/1_銘柄分析.py", label="📊 銘柄分析")
    st.markdown("---")

    st.markdown("**📁 カテゴリ管理**")
    wl = load_watchlist()

    # 新規カテゴリ作成
    new_cat = st.text_input("新しいカテゴリ名を入力", placeholder="例: グロース株 🚀",
                             key="new_cat")
    if st.button("＋ カテゴリ追加", use_container_width=True) and new_cat.strip():
        if new_cat.strip() not in wl["categories"]:
            wl["categories"][new_cat.strip()] = []
            save_watchlist(wl)
            st.success(f"「{new_cat}」を追加しました")
            st.rerun()

    st.markdown("---")

    # カテゴリに銘柄を追加
    st.markdown("**＋ 銘柄を追加**")
    add_ticker = st.text_input("ティッカーシンボル", placeholder="AAPL / 7203.T", key="add_t").strip().upper()
    add_cat = st.selectbox("カテゴリを選択", list(wl["categories"].keys()),
                           key="add_c") if wl["categories"] else None
    if st.button("ウォッチリストに追加", type="primary", use_container_width=True):
        if add_ticker and add_cat:
            if add_ticker not in wl["categories"][add_cat]:
                wl["categories"][add_cat].append(add_ticker)
                save_watchlist(wl)
                st.success(f"{add_ticker} を「{add_cat}」に追加しました")
                st.rerun()
            else:
                st.info("既に登録済みです")

# ============================================================
# メインエリア
# ============================================================
st.markdown("# ⭐ ウォッチリスト")
st.caption("お気に入り銘柄を分類して管理できます。価格はリアルタイム取得です。")

wl = load_watchlist()

if not wl["categories"]:
    st.info("ウォッチリストが空です。左サイドバーからカテゴリと銘柄を追加してください。")
    st.stop()

# ---- カテゴリ削除ボタン（右上） ----
del_cat_options = ["（カテゴリを削除...）"] + list(wl["categories"].keys())
col_del1, col_del2 = st.columns([3, 1])
with col_del2:
    del_sel = st.selectbox("", del_cat_options, key="del_cat",
                           label_visibility="collapsed")
    if st.button("🗑 カテゴリ削除", use_container_width=True) and del_sel != del_cat_options[0]:
        del wl["categories"][del_sel]
        save_watchlist(wl)
        st.success(f"「{del_sel}」を削除しました")
        st.rerun()

st.markdown("---")

# ---- 全銘柄一括価格取得 ----
all_tickers = list({t for cat in wl["categories"].values() for t in cat})

with st.spinner("価格取得中..."):
    prices = load_prices_batch(tuple(all_tickers)) if all_tickers else {}

# ---- カテゴリ別表示 ----
for cat_name, tickers in wl["categories"].items():
    if not tickers:
        st.markdown(f"**{cat_name}** — 銘柄なし")
        col_empty = st.columns(1)[0]
        col_empty.caption("左サイドバーから銘柄を追加してください")
        st.markdown("---")
        continue

    # ヘッダー
    h1, h2 = st.columns([4, 1])
    with h1:
        st.markdown(f"### {cat_name}")
    with h2:
        # 銘柄削除セレクタ
        rem_options = ["（銘柄を削除...）"] + tickers
        rem_sel = st.selectbox("", rem_options, key=f"rem_{cat_name}",
                               label_visibility="collapsed")
        if st.button("🗑", key=f"rmbtn_{cat_name}") and rem_sel != rem_options[0]:
            wl["categories"][cat_name].remove(rem_sel)
            save_watchlist(wl)
            st.rerun()

    # 銘柄テーブル
    rows = []
    for sym in tickers:
        d = prices.get(sym, {})
        price = d.get("price", 0)
        chg   = d.get("change_pct", 0)
        rows.append({
            "ティッカー": sym,
            "価格": fmt_compact(price) if price else "---",
            "前日比 %": f"{'+'if chg>=0 else ''}{chg:.2f}%",
            "▲▼": "▲" if chg >= 0 else "▼",
        })

    # カード形式で表示
    n_cols = min(len(tickers), 5)
    cols = st.columns(n_cols)
    for i, (sym, row) in enumerate(zip(tickers, rows)):
        with cols[i % n_cols]:
            chg = prices.get(sym, {}).get("change_pct", 0)
            color = "#28a745" if chg >= 0 else "#dc3545"
            sign = "+" if chg >= 0 else ""
            disp = sym.replace(".T", "")
            st.markdown(f"""
            <div style="background:#fff;border:1px solid #e8e8e8;border-radius:8px;
                        padding:12px;text-align:center;margin:3px">
                <div style="font-weight:bold;font-size:0.95em">{disp}</div>
                <div style="font-size:1.2em;font-weight:bold;margin:4px 0">{row['価格']}</div>
                <div style="color:{color};font-weight:bold">{sign}{chg:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("分析", key=f"an_{cat_name}_{sym}", use_container_width=True):
                st.session_state.active_ticker = sym
                st.switch_page("pages/1_銘柄分析.py")

    # ミニバーチャート（価格比較）
    if len(tickers) >= 2:
        price_vals = [prices.get(t, {}).get("price", 0) for t in tickers]
        chg_vals   = [prices.get(t, {}).get("change_pct", 0) for t in tickers]
        if any(v > 0 for v in chg_vals):
            with st.expander(f"前日比チャート — {cat_name}"):
                fig = go.Figure(go.Bar(
                    x=[t.replace(".T", "") for t in tickers],
                    y=chg_vals,
                    marker_color=["#28a745" if v >= 0 else "#dc3545" for v in chg_vals],
                    text=[f"{'+' if v>=0 else ''}{v:.2f}%" for v in chg_vals],
                    textposition="outside",
                ))
                fig.add_hline(y=0, line_color="#333", line_width=1)
                fig.update_layout(
                    title=f"{cat_name} — 前日比 (%)",
                    yaxis_title="前日比 (%)",
                    height=280,
                    showlegend=False,
                    plot_bgcolor="white",
                    margin=dict(t=40, b=10),
                )
                st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

# ---- 全銘柄サマリーテーブル ----
if all_tickers:
    with st.expander("📋 全銘柄サマリーテーブル（詳細データ）"):
        with st.spinner("詳細データ取得中...（初回のみ時間がかかります）"):
            detail_rows = []
            for sym in all_tickers:
                cat = next((c for c, ts in wl["categories"].items() if sym in ts), "")
                d_detail = load_data(sym)
                p = prices.get(sym, {})
                if d_detail:
                    detail_rows.append({
                        "カテゴリ": cat,
                        "ティッカー": sym,
                        "会社名": (d_detail.get("company_name") or sym)[:20],
                        "株価": fmt_compact(p.get("price", 0)),
                        "前日比": f"{'+'if p.get('change_pct',0)>=0 else ''}{p.get('change_pct',0):.2f}%",
                        "PER": f"{d_detail.get('per',0):.1f}x" if d_detail.get("per") else "N/A",
                        "PBR": f"{d_detail.get('pbr',0):.2f}x" if d_detail.get("pbr") else "N/A",
                        "ROE": fmt_pct(d_detail.get("roe")),
                        "配当利回り": fmt_pct(d_detail.get("dividend_yield")),
                    })
            if detail_rows:
                import pandas as pd
                df = pd.DataFrame(detail_rows)
                st.dataframe(df, use_container_width=True, hide_index=True)

st.caption("データ: yFinance　|　投資教育目的のみ")
