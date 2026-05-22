"""共有サイドバー・ナビゲーションコンポーネント"""

import streamlit as st
from utils import (
    load_watchlist, save_watchlist,
    load_prices_batch, fmt_compact,
    get_stock_display_name, is_cloud,
)


def _move_category(wl: dict, idx: int, direction: int) -> None:
    """カテゴリを上下に移動"""
    cats = list(wl["categories"].items())
    target = idx + direction
    if 0 <= target < len(cats):
        cats[idx], cats[target] = cats[target], cats[idx]
        wl["categories"] = dict(cats)
        save_watchlist(wl)


def _move_stock(wl: dict, cat_name: str, idx: int, direction: int) -> None:
    """銘柄を上下に移動"""
    tickers = wl["categories"][cat_name]
    target = idx + direction
    if 0 <= target < len(tickers):
        tickers[idx], tickers[target] = tickers[target], tickers[idx]
        wl["categories"][cat_name] = tickers
        save_watchlist(wl)


def render_sidebar() -> None:
    """全ページ共通サイドバー（ウォッチリスト + 並び替え + 銘柄管理）"""
    with st.sidebar:
        st.markdown("## ⭐ ウォッチリスト")

        # 編集モード切り替え
        edit_mode = st.toggle("✏️ 並び替え・編集モード", key="sidebar_edit_mode", value=False)

        wl = load_watchlist()
        cats = list(wl["categories"].items())

        # ---- 全銘柄の価格を一括取得 ----
        all_tickers = list({t for _, ts in cats for t in ts})
        prices = {}
        if all_tickers:
            try:
                prices = load_prices_batch(tuple(all_tickers))
            except Exception:
                pass

        # ---- カテゴリ別表示 ----
        for i, (cat_name, tickers) in enumerate(cats):
            if edit_mode:
                # 編集モード: カテゴリ行に ↑↓ ボタン
                hc1, hc2, hc3 = st.columns([1, 1, 5])
                if hc1.button("↑", key=f"cup_{i}", disabled=(i == 0),
                              use_container_width=True):
                    _move_category(wl, i, -1)
                    st.rerun()
                if hc2.button("↓", key=f"cdn_{i}", disabled=(i == len(cats) - 1),
                              use_container_width=True):
                    _move_category(wl, i, +1)
                    st.rerun()
                with hc3:
                    st.markdown(f"**{cat_name}** ({len(tickers)})")
            else:
                st.markdown(f"**{cat_name}** ({len(tickers)})")

            for j, ticker in enumerate(tickers):
                p      = prices.get(ticker, {})
                price  = p.get("price", 0)
                chg    = p.get("change_pct", 0)
                sign   = "+" if chg >= 0 else ""
                color  = "green" if chg >= 0 else "red"

                # 日本株は企業名を取得
                if ticker.upper().endswith(".T"):
                    disp_name = get_stock_display_name(ticker)
                    label_text = f"{ticker.replace('.T','')} {disp_name}"
                else:
                    label_text = ticker

                chg_tag = f" :{color}[{sign}{chg:.1f}%]"

                if edit_mode:
                    # 編集モード: 銘柄行に ↑↓ × ボタン
                    sc1, sc2, sc3, sc4 = st.columns([1, 1, 4, 1])
                    if sc1.button("↑", key=f"sup_{cat_name}_{j}",
                                  disabled=(j == 0), use_container_width=True):
                        _move_stock(wl, cat_name, j, -1)
                        st.rerun()
                    if sc2.button("↓", key=f"sdn_{cat_name}_{j}",
                                  disabled=(j == len(tickers) - 1), use_container_width=True):
                        _move_stock(wl, cat_name, j, +1)
                        st.rerun()
                    with sc3:
                        if st.button(f"{label_text}{chg_tag}",
                                     key=f"wl_e_{cat_name}_{ticker}",
                                     use_container_width=True):
                            st.session_state.active_ticker = ticker
                            st.switch_page("analysis.py")
                    if sc4.button("×", key=f"del_{cat_name}_{ticker}",
                                  use_container_width=True):
                        wl["categories"][cat_name].remove(ticker)
                        ns = wl.get("news_search", {})
                        still_exists = any(
                            ticker in ts for cn, ts in wl["categories"].items()
                            if cn != cat_name
                        )
                        if not still_exists:
                            ns.pop(ticker, None)
                        save_watchlist(wl)
                        st.rerun()
                else:
                    # 通常モード: クリックで分析ページへ
                    if st.button(
                        f"{label_text}{chg_tag}",
                        key=f"wl_{cat_name}_{ticker}",
                        use_container_width=True,
                    ):
                        st.session_state.active_ticker = ticker
                        st.switch_page("analysis.py")

            # ---- カテゴリ内クイック追加 ----
            add_key = f"cat_quick_add_{cat_name}"
            toggle_key = f"cat_add_open_{cat_name}"
            if st.button(f"＋ {cat_name} に追加", key=add_key, use_container_width=True):
                st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)

            if st.session_state.get(toggle_key, False):
                new_t = st.text_input(
                    "", placeholder="AAPL / 7203.T",
                    key=f"cat_inp_{cat_name}", label_visibility="collapsed",
                ).strip().upper()
                c_ok, c_no = st.columns(2)
                if c_ok.button("追加", key=f"cat_ok_{cat_name}", use_container_width=True) and new_t:
                    if new_t not in wl["categories"][cat_name]:
                        wl["categories"][cat_name].append(new_t)
                        wl.setdefault("news_search", {})[new_t] = True
                        save_watchlist(wl)
                    st.session_state[toggle_key] = False
                    st.rerun()
                if c_no.button("キャンセル", key=f"cat_cancel_{cat_name}", use_container_width=True):
                    st.session_state[toggle_key] = False
                    st.rerun()

            st.markdown("")  # スペーサー

        st.divider()

        # ---- 銘柄・カテゴリ管理 ----
        with st.expander("➕ 銘柄・カテゴリを追加"):
            add_ticker = st.text_input(
                "ティッカーを追加", placeholder="AAPL / 7203.T", key="sb_add_t",
            ).strip().upper()
            cat_options = list(wl["categories"].keys())
            add_cat = st.selectbox("カテゴリ", cat_options, key="sb_add_c") if cat_options else None
            news_on = st.toggle("ニュース検索を有効", value=True, key="sb_ns")

            if st.button("追加", type="primary", use_container_width=True,
                         key="sb_add_btn") and add_ticker and add_cat:
                if add_ticker not in wl["categories"][add_cat]:
                    wl["categories"][add_cat].append(add_ticker)
                    wl.setdefault("news_search", {})[add_ticker] = news_on
                    save_watchlist(wl)
                    st.success(f"✅ {add_ticker} を追加")
                    st.rerun()
                else:
                    st.info("既に登録済み")

            st.markdown("─")
            new_cat = st.text_input("新しいカテゴリ名", placeholder="グロース株 🚀",
                                     key="sb_new_cat")
            if st.button("カテゴリ作成", use_container_width=True,
                         key="sb_cat_btn") and new_cat.strip():
                if new_cat.strip() not in wl["categories"]:
                    wl["categories"][new_cat.strip()] = []
                    save_watchlist(wl)
                    st.rerun()

        # カテゴリ削除（編集モード時のみ）
        if edit_mode:
            cat_options = list(wl["categories"].keys())
            if cat_options:
                with st.expander("🗑 カテゴリを削除"):
                    del_cat = st.selectbox("", ["—"] + cat_options, key="sb_del_cat",
                                           label_visibility="collapsed")
                    if st.button("削除", use_container_width=True,
                                 key="sb_del_btn") and del_cat != "—":
                        del wl["categories"][del_cat]
                        save_watchlist(wl)
                        st.rerun()

        # ---- アクセス情報 ----
        with st.expander("📱 アクセス情報"):
            if is_cloud():
                st.success("✅ Streamlit Cloud で公開中")
                st.markdown("このURLをスマホにブックマークしてください。")
            else:
                import socket
                try:
                    local_ip = socket.gethostbyname(socket.gethostname())
                except Exception:
                    local_ip = "192.168.x.x"
                st.markdown(f"**同じWi-Fiのスマホ**から:\n```\nhttp://{local_ip}:8501\n```")
                st.caption("外出先からアクセスするには Streamlit Cloud へのデプロイが必要です。")


def render_topnav() -> None:
    """全ページ上部ナビゲーションバー"""
    c1, c2, c3 = st.columns([1, 1, 6])
    with c1:
        st.page_link("home.py", label="📰 ニュース", use_container_width=True)
    with c2:
        st.page_link("analysis.py", label="📊 分析", use_container_width=True)
    st.markdown(
        "<hr style='margin:4px 0 12px 0;border:none;border-top:2px solid #e8e8e8'>",
        unsafe_allow_html=True,
    )
