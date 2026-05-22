"""ニュースダイジェスト メインページ"""

import streamlit as st
import streamlit.components.v1 as components
import json

from core.sidebar import render_topnav
from core.news import (
    MEDIA_SOURCES, CATEGORY_ORDER,
    get_all_headlines, get_category_headlines, get_source_headlines,
    generate_ai_digest,
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
</style>
""", unsafe_allow_html=True)

# ---- トップナビ ----
render_topnav()

st.markdown("# 📰 ニュース & マーケット")
st.caption(f"最終更新: ニュース15分キャッシュ ／ AIダイジェスト1時間キャッシュ")

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

    col_gen, col_info = st.columns([2, 5])
    with col_gen:
        gen_all = st.button("🔄 AIダイジェスト生成", type="primary",
                            use_container_width=True, key="gen_all")
    with col_info:
        st.caption("全ニュースソースを統合してClaudeが1〜2分で読めるダイジェストを生成します（初回のみ数秒かかります）")

    if gen_all or st.session_state.get("digest_総合"):
        with st.spinner("AIがニュースを分析中..."):
            headlines = get_all_headlines(limit_per_source=6)
            digest = generate_ai_digest(headlines, "総合")
        st.session_state["digest_総合"] = digest
        st.markdown(f'<div class="digest-box">{digest.replace(chr(10), "<br>")}</div>',
                    unsafe_allow_html=True)

    st.markdown('<div class="section-h">📡 最新ヘッドライン（全ソース）</div>', unsafe_allow_html=True)

    all_items = get_all_headlines(limit_per_source=5)
    if all_items:
        col_a, col_b = st.columns(2)
        for i, item in enumerate(all_items[:24]):
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
            # AI ダイジェスト
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

            if gen_cat or st.session_state.get(f"digest_{category}"):
                with st.spinner("生成中..."):
                    cat_headlines = get_category_headlines(category, limit=30)
                    digest = generate_ai_digest(cat_headlines, category)
                st.session_state[f"digest_{category}"] = digest
                st.markdown(f'<div class="digest-box">{digest.replace(chr(10), "<br>")}</div>',
                            unsafe_allow_html=True)

            # ヘッドライン
            st.markdown(f"**ヘッドライン — {category}**")
            cat_items = get_category_headlines(category, limit=20)

            # ソース別にグループ化して表示
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
    media_tab_labels = [f"{MEDIA_SOURCES[n]['icon']} {n}" for n in media_names]
    media_tabs = st.tabs(media_tab_labels)

    for m_tab, media_name in zip(media_tabs, media_names):
        with m_tab:
            cfg = MEDIA_SOURCES[media_name]

            col_g2, col_inf2 = st.columns([2, 5])
            with col_g2:
                gen_media = st.button("🤖 このメディアのダイジェスト",
                                      key=f"gen_media_{media_name}", use_container_width=True)
            with col_inf2:
                st.caption(f"カテゴリ: {cfg['category']}")

            if gen_media or st.session_state.get(f"digest_media_{media_name}"):
                items_for_ai = get_source_headlines(media_name)
                if items_for_ai:
                    with st.spinner("生成中..."):
                        digest = generate_ai_digest(items_for_ai, "総合")
                    st.session_state[f"digest_media_{media_name}"] = digest
                    st.markdown(f'<div class="digest-box">{digest.replace(chr(10), "<br>")}</div>',
                                unsafe_allow_html=True)

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

    col_mg, col_mi = st.columns([2, 5])
    with col_mg:
        gen_mkt = st.button("🤖 市場ダイジェスト生成", key="gen_mkt",
                            type="primary", use_container_width=True)
    with col_mi:
        st.caption("経済・株価ニュースからClaudeが24時間の市場サマリーを生成します")

    if gen_mkt or st.session_state.get("digest_株価"):
        with st.spinner("市場を分析中..."):
            mkt_headlines = get_category_headlines("経済", limit=30)
            mkt_digest = generate_ai_digest(mkt_headlines, "株価")
        st.session_state["digest_株価"] = mkt_digest
        st.markdown(f'<div class="digest-box">{mkt_digest.replace(chr(10), "<br>")}</div>',
                    unsafe_allow_html=True)

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
                    # cat_idx を key に含めて重複を防ぐ
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
