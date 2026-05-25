"""ニュースダイジェスト メインページ"""

import streamlit as st
import streamlit.components.v1 as components
import json

from core.sidebar import render_topnav
from core.news import (
    MEDIA_SOURCES, CATEGORY_ORDER,
    get_all_headlines, get_category_headlines, get_source_headlines,
    get_niche_headlines, generate_ai_digest, generate_today_digest,
    is_summary_article,
)
from utils import (
    TRENDING_US, TRENDING_JP,
    load_prices_batch, load_watchlist, fmt_compact,
    render_mini_chart_html,
)

# ============================================================
# CSS
# ============================================================
st.markdown("""
<style>
.nc{background:#fff;border:1px solid #eee;border-radius:8px;padding:12px 14px;
    margin-bottom:7px;transition:box-shadow .15s}
.nc:hover{box-shadow:0 2px 8px rgba(0,0,0,.09)}
.nc a{text-decoration:none;color:#111;font-weight:600;font-size:0.9em;line-height:1.4}
.nc a:hover{color:#1a73e8}
.nc-meta{color:#aaa;font-size:0.74em;margin-top:4px}
.digest-box{background:linear-gradient(135deg,#f0f4ff,#f9f9ff);
            border-left:4px solid #1a73e8;border-radius:0 8px 8px 0;
            padding:16px 20px;margin-bottom:16px;font-size:0.95em;line-height:1.7}
.section-h{font-size:1.2em;font-weight:700;border-left:4px solid #1a73e8;
           padding-left:10px;margin:14px 0 8px}
.mkt-box{text-align:center;padding:10px;background:#f8f9fa;border-radius:8px}
.nc-summary{background:linear-gradient(135deg,#fffbf0,#fff8e1);
            border:1px solid #f9c84a;border-left:4px solid #f9a825 !important;border-radius:8px}
</style>
""", unsafe_allow_html=True)

# ---- トップナビ ----
render_topnav()

st.markdown("# 📰 ニュース & マーケット")

# ============================================================
# 今日のネタ（最上部・常設）
# ============================================================
with st.container():
    st.markdown('<div class="section-h">🌅 今日のネタ</div>', unsafe_allow_html=True)

    c_inp, c_btn = st.columns([4, 1])
    with c_inp:
        today_custom = st.text_input(
            "", placeholder="🔍 追加でリサーチしてほしいことを入力（例: 半導体の最新動向、円安の影響、AIエージェントの事例）",
            key="today_custom", label_visibility="collapsed",
        )
    with c_btn:
        gen_today = st.button("🤖 生成", type="primary", use_container_width=True, key="gen_today")

    if gen_today:
        st.session_state.pop("digest_今日のネタ", None)

    if gen_today or st.session_state.get("digest_今日のネタ"):
        if not st.session_state.get("digest_今日のネタ"):
            with st.spinner("ニュース＋サイエンス情報を分析中..."):
                news_items  = get_all_headlines(limit_per_source=4)
                niche_items = get_niche_headlines(limit=3)
                result = generate_today_digest(news_items, niche_items, today_custom)
            st.session_state["digest_今日のネタ"] = result

        digest_today = st.session_state["digest_今日のネタ"]
        st.markdown(
            f'<div class="digest-box">{digest_today.replace(chr(10), "<br>")}</div>',
            unsafe_allow_html=True,
        )
        if st.button("🔄 再生成", key="regen_today"):
            st.session_state.pop("digest_今日のネタ", None)
            st.rerun()

st.markdown("---")

# ============================================================
# タブ構成: 総合 | 分野別 | メディア別 | 株価
# ============================================================
tab_all, tab_cat, tab_media, tab_mkt = st.tabs([
    "📋 総合ダイジェスト",
    "🌐 分野別",
    "📰 メディア別",
    "📈 株価",
])

# ============================================================
# TAB 1: 総合ダイジェスト
# ============================================================
with tab_all:
    st.markdown('<div class="section-h">🤖 AIニュースダイジェスト（全ソース統合）</div>', unsafe_allow_html=True)

    all_custom = st.text_input(
        "", placeholder="🔍 追加でリサーチしてほしいことを入力（任意）",
        key="all_custom", label_visibility="collapsed",
    )
    col_gen, col_info = st.columns([2, 5])
    with col_gen:
        gen_all = st.button("🔄 AIダイジェスト生成", type="primary",
                            use_container_width=True, key="gen_all")
    with col_info:
        st.caption("全ニュースソースを統合してClaudeが1〜2分で読めるダイジェストを生成します")

    if gen_all:
        st.session_state.pop("digest_総合", None)

    if gen_all or st.session_state.get("digest_総合"):
        if not st.session_state.get("digest_総合"):
            with st.spinner("AIがニュースを分析中..."):
                headlines = get_all_headlines(limit_per_source=6)
                digest = generate_ai_digest(headlines, "総合", all_custom)
            st.session_state["digest_総合"] = digest
        st.markdown(
            f'<div class="digest-box">{st.session_state["digest_総合"].replace(chr(10), "<br>")}</div>',
            unsafe_allow_html=True,
        )

    # ---- 最新ヘッドライン（CNBC・日経新聞・NHK総合） ----
    st.markdown('<div class="section-h">📡 最新ヘッドライン</div>', unsafe_allow_html=True)

    HEADLINE_SOURCES = ["CNBC", "日経新聞", "NHK総合"]
    headline_items = []
    for src in HEADLINE_SOURCES:
        headline_items.extend(get_source_headlines(src)[:8])

    if headline_items:
        summary_items = [item for item in headline_items if is_summary_article(item["title"])]
        regular_items = [item for item in headline_items if not is_summary_article(item["title"])]

        # まとめ記事を上部に表示
        if summary_items:
            st.markdown('<div class="section-h" style="font-size:1em;color:#b8860b">📋 今日のまとめ記事</div>', unsafe_allow_html=True)
            for item in summary_items[:6]:
                st.markdown(f"""
                <div class="nc nc-summary">
                    <a href="{item['link']}" target="_blank">{item['title']}</a>
                    <div class="nc-meta">📌 {item['source']} &nbsp;·&nbsp; {item['published']}</div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("<div style='margin-bottom:8px'></div>", unsafe_allow_html=True)

        # 通常記事を2列表示
        col_a, col_b = st.columns(2)
        for i, item in enumerate(regular_items[:24]):
            col = col_a if i % 2 == 0 else col_b
            with col:
                summ = f"<div style='color:#666;font-size:0.78em;margin-top:3px'>{item['summary']}</div>" if item.get("summary") else ""
                st.markdown(f"""
                <div class="nc">
                    <a href="{item['link']}" target="_blank">{item['title']}</a>
                    {summ}
                    <div class="nc-meta">📌 {item['source']} &nbsp;·&nbsp; {item['published']}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("ニュースを取得中です...")

# ============================================================
# TAB 2: 分野別
# ============================================================
with tab_cat:
    CAT_ICONS = {"経済": "💹", "テクノロジー": "💻", "VC": "🚀", "政治": "🏛️", "日本": "🇯🇵"}
    cat_tabs = st.tabs([f"{CAT_ICONS.get(c, '📌')} {c}" for c in CATEGORY_ORDER])

    for cat_tab, category in zip(cat_tabs, CATEGORY_ORDER):
        with cat_tab:
            cat_custom = st.text_input(
                "", placeholder="🔍 追加でリサーチしてほしいことを入力（任意）",
                key=f"cat_custom_{category}", label_visibility="collapsed",
            )
            col_g, col_inf = st.columns([2, 5])
            with col_g:
                gen_cat = st.button(f"🤖 AIダイジェスト生成",
                                    key=f"gen_cat_{category}", type="primary",
                                    use_container_width=True)
            with col_inf:
                cat_desc = {
                    "経済": "市場・金融ニュースを総合",
                    "テクノロジー": "AI・スタートアップトレンド",
                    "VC": "資金調達・スタートアップ動向",
                    "政治": "国内外の政治・外交ニュース",
                    "日本": "日本語ニュースを総合",
                }
                st.caption(cat_desc.get(category, ""))

            if gen_cat:
                st.session_state.pop(f"digest_{category}", None)

            if gen_cat or st.session_state.get(f"digest_{category}"):
                if not st.session_state.get(f"digest_{category}"):
                    with st.spinner("生成中..."):
                        cat_headlines = get_category_headlines(category, limit=30)
                        digest = generate_ai_digest(cat_headlines, category, cat_custom)
                    st.session_state[f"digest_{category}"] = digest
                st.markdown(
                    f'<div class="digest-box">{st.session_state[f"digest_{category}"].replace(chr(10), "<br>")}</div>',
                    unsafe_allow_html=True,
                )

            # ヘッドライン
            st.markdown(f"**ヘッドライン — {category}**")

            sources_in_cat = {n: c for n, c in MEDIA_SOURCES.items() if c["category"] == category}
            if sources_in_cat:
                src_tabs = st.tabs([f"{cfg['icon']} {name}" for name, cfg in sources_in_cat.items()])
                for src_tab, (src_name, src_cfg) in zip(src_tabs, sources_in_cat.items()):
                    with src_tab:
                        items = get_source_headlines(src_name)
                        if not items:
                            st.caption("取得できませんでした")
                            continue
                        for item in items[:10]:
                            st.markdown(f"""
                            <div class="nc">
                                <a href="{item['link']}" target="_blank">{item['title']}</a>
                                <div class="nc-meta">{item['published']}</div>
                            </div>
                            """, unsafe_allow_html=True)

# ============================================================
# TAB 3: メディア別
# ============================================================
with tab_media:
    media_names = list(MEDIA_SOURCES.keys())

    # ---- メディア表示順の管理（session_state） ----
    if "media_order" not in st.session_state:
        st.session_state.media_order = media_names.copy()
    else:
        # 新しく追加されたソースを末尾に追加
        for n in media_names:
            if n not in st.session_state.media_order:
                st.session_state.media_order.append(n)
        # 削除されたソースを除去
        st.session_state.media_order = [n for n in st.session_state.media_order if n in media_names]

    ordered_media = st.session_state.media_order

    # ---- 並び替えUI ----
    with st.expander("🔀 メディアの表示順を変更"):
        st.caption("↑↓ で並び替えできます")
        for idx, mname in enumerate(ordered_media):
            icon = MEDIA_SOURCES[mname]["icon"]
            col_u, col_d, col_lbl = st.columns([1, 1, 8])
            with col_u:
                if st.button("↑", key=f"mo_up_{idx}", disabled=(idx == 0),
                             use_container_width=True):
                    ordered_media[idx], ordered_media[idx - 1] = ordered_media[idx - 1], ordered_media[idx]
                    st.session_state.media_order = ordered_media
                    st.rerun()
            with col_d:
                if st.button("↓", key=f"mo_dn_{idx}", disabled=(idx == len(ordered_media) - 1),
                             use_container_width=True):
                    ordered_media[idx], ordered_media[idx + 1] = ordered_media[idx + 1], ordered_media[idx]
                    st.session_state.media_order = ordered_media
                    st.rerun()
            with col_lbl:
                st.markdown(f"{icon} **{mname}**")

    # ---- メディア別タブ ----
    media_tab_labels = [f"{MEDIA_SOURCES[n]['icon']} {n}" for n in ordered_media]
    media_tabs = st.tabs(media_tab_labels)

    for m_tab, media_name in zip(media_tabs, ordered_media):
        with m_tab:
            cfg = MEDIA_SOURCES[media_name]

            media_custom = st.text_input(
                "", placeholder="🔍 追加でリサーチしてほしいことを入力（任意）",
                key=f"media_custom_{media_name}", label_visibility="collapsed",
            )
            col_g2, col_inf2 = st.columns([2, 5])
            with col_g2:
                gen_media = st.button("🤖 このメディアのダイジェスト",
                                      key=f"gen_media_{media_name}", use_container_width=True)
            with col_inf2:
                st.caption(f"カテゴリ: {cfg['category']}")

            if gen_media:
                st.session_state.pop(f"digest_media_{media_name}", None)

            if gen_media or st.session_state.get(f"digest_media_{media_name}"):
                if not st.session_state.get(f"digest_media_{media_name}"):
                    items_for_ai = get_source_headlines(media_name)
                    if items_for_ai:
                        with st.spinner("生成中..."):
                            digest = generate_ai_digest(items_for_ai, "総合", media_custom)
                        st.session_state[f"digest_media_{media_name}"] = digest
                if st.session_state.get(f"digest_media_{media_name}"):
                    st.markdown(
                        f'<div class="digest-box">{st.session_state[f"digest_media_{media_name}"].replace(chr(10), "<br>")}</div>',
                        unsafe_allow_html=True,
                    )

            # ヘッドライン
            items = get_source_headlines(media_name)
            if not items:
                st.info("ニュースを取得できませんでした（一時的なエラーの可能性があります）")
            else:
                for item in items:
                    summ_part = f"<div style='color:#666;font-size:0.78em;margin-top:3px'>{item['summary']}</div>" if item.get("summary") else ""
                    st.markdown(f"""
                    <div class="nc">
                        <a href="{item['link']}" target="_blank">{item['title']}</a>
                        {summ_part}
                        <div class="nc-meta">{item['published']}</div>
                    </div>
                    """, unsafe_allow_html=True)

# ============================================================
# TAB 4: 株価
# ============================================================
with tab_mkt:
    # ---- AI市場ダイジェスト ----
    st.markdown('<div class="section-h">🤖 AI 市場ダイジェスト（24h）</div>', unsafe_allow_html=True)

    mkt_custom = st.text_input(
        "", placeholder="🔍 追加でリサーチしてほしいことを入力（例: Fed政策、半導体セクター）",
        key="mkt_custom", label_visibility="collapsed",
    )
    col_mg, col_mi = st.columns([2, 5])
    with col_mg:
        gen_mkt = st.button("🤖 市場ダイジェスト生成", key="gen_mkt",
                            type="primary", use_container_width=True)
    with col_mi:
        st.caption("経済・株価ニュースからClaudeが24時間の市場サマリーを生成します")

    if gen_mkt:
        st.session_state.pop("digest_株価", None)

    if gen_mkt or st.session_state.get("digest_株価"):
        if not st.session_state.get("digest_株価"):
            with st.spinner("市場を分析中..."):
                mkt_headlines = get_category_headlines("経済", limit=30)
                mkt_digest = generate_ai_digest(mkt_headlines, "株価", mkt_custom)
            st.session_state["digest_株価"] = mkt_digest
        st.markdown(
            f'<div class="digest-box">{st.session_state["digest_株価"].replace(chr(10), "<br>")}</div>',
            unsafe_allow_html=True,
        )

    # ---- 主要指数ミニチャート ----
    st.markdown('<div class="section-h">📊 主要指数チャート（6ヶ月）</div>', unsafe_allow_html=True)
    INDEX_CHARTS = [
        ("S&P 500",  "FOREXCOM:SPXUSD"),
        ("NASDAQ",   "FOREXCOM:NSXUSD"),
        ("Dow Jones","FOREXCOM:DJI"),
        ("USD/JPY",  "FX:USDJPY"),
        ("VIX",      "CBOE:VIX"),
        ("Bitcoin",  "BITSTAMP:BTCUSD"),
    ]
    chart_cols = st.columns(3)
    for i, (name, sym) in enumerate(INDEX_CHARTS):
        with chart_cols[i % 3]:
            st.markdown(f"**{name}**")
            components.html(render_mini_chart_html(sym, 200), height=200, scrolling=False)

    # ---- ウォッチリスト銘柄 ----
    st.markdown('<div class="section-h">⭐ ウォッチリスト 株価</div>', unsafe_allow_html=True)

    wl = load_watchlist()
    all_wl_tickers = list({t for cats in wl["categories"].values() for t in cats})

    if all_wl_tickers:
        with st.spinner("価格取得中..."):
            prices = load_prices_batch(tuple(all_wl_tickers))

        for cat_idx, (cat_name, tickers) in enumerate(wl["categories"].items()):
            if not tickers:
                continue
            st.markdown(f"**{cat_name}**")
            cols = st.columns(min(len(tickers), 6))
            for i, sym in enumerate(tickers):
                p = prices.get(sym, {})
                price = p.get("price", 0)
                chg   = p.get("change_pct", 0)
                color = "#28a745" if chg >= 0 else "#dc3545"
                sign  = "+" if chg >= 0 else ""
                with cols[i % 6]:
                    st.markdown(f"""
                    <div class="mkt-box">
                        <div style="font-weight:bold;font-size:0.85em">{sym.replace('.T','')}</div>
                        <div style="font-size:1.1em;font-weight:bold">{fmt_compact(price)}</div>
                        <div style="color:{color};font-size:0.85em">{sign}{chg:.2f}%</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("分析", key=f"mkt_an_{cat_idx}_{i}_{sym}",
                                 use_container_width=True):
                        st.session_state.active_ticker = sym
                        st.switch_page("analysis.py")

        # ニュース検索が有効なウォッチリスト銘柄のニュース
        news_enabled = [t for t in all_wl_tickers
                        if wl.get("news_search", {}).get(t, True)]
        if news_enabled:
            st.markdown('<div class="section-h">📰 ウォッチリスト関連ニュース</div>', unsafe_allow_html=True)
            import yfinance as yf
            for sym in news_enabled[:5]:
                try:
                    ticker_obj = yf.Ticker(sym)
                    news = ticker_obj.news[:3] if ticker_obj.news else []
                    if news:
                        st.markdown(f"**{sym}**")
                        for n in news:
                            if "content" in n:
                                title = n["content"].get("title", "")
                                url   = n["content"].get("clickThroughUrl", {}).get("url", "")
                            else:
                                title = n.get("title", "")
                                url   = n.get("link", "")
                            if title and url:
                                st.markdown(f"- [{title}]({url})")
                except Exception:
                    pass
    else:
        st.info("ウォッチリストに銘柄を追加すると、ここに株価が表示されます。")

st.markdown("---")
st.caption("データ: yFinance / TradingView / RSS各社フィード ／ AIダイジェスト: Claude (Anthropic) ／ 投資教育目的のみ")
