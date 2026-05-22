"""ナビゲーション統合 + 共有サイドバー"""

import streamlit as st
from core.sidebar import render_sidebar

st.set_page_config(
    page_title="My Stock Portal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# モバイル対応 CSS
st.markdown("""
<style>
/* スマートフォン向けレスポンシブ */
@media (max-width: 768px) {
    .main .block-container {
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        padding-top: 0.5rem !important;
    }
    /* ボタンを小さく */
    .stButton > button {
        font-size: 0.78em !important;
        padding: 0.25rem 0.4rem !important;
    }
    /* フォントサイズ調整 */
    h1 { font-size: 1.4em !important; }
    h2 { font-size: 1.2em !important; }
    h3 { font-size: 1.1em !important; }
}
/* サイドバーの幅を固定 */
[data-testid="stSidebar"] {
    min-width: 260px !important;
    max-width: 320px !important;
}
/* ニュースカードのリンクを青くしない（読みやすく） */
a { color: inherit; }
</style>
""", unsafe_allow_html=True)

# ウォッチリストサイドバーは全ページで共有
render_sidebar()

# ページナビゲーション
pg = st.navigation([
    st.Page("home.py",     title="📰 ニュース",  icon="📰"),
    st.Page("analysis.py", title="📊 分析",      icon="📊"),
])
pg.run()
