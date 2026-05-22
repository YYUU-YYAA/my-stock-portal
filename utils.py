"""共有ユーティリティ - 全ページから利用"""

import json
import os
from pathlib import Path

import pandas as pd
import requests as _requests
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf

from fetcher import fetch_stock_data

# ============================================================
# パス
# ============================================================
ROOT = Path(__file__).parent
WATCHLIST_FILE = ROOT / "data" / "watchlist.json"

# ============================================================
# 定数
# ============================================================

EXAMPLES = {
    "🍎 Apple": "AAPL", "🪟 Microsoft": "MSFT", "🟢 NVIDIA": "NVDA", "⚡ Tesla": "TSLA",
    "🚗 トヨタ": "7203.T", "🎵 ソニー": "6758.T", "🎮 任天堂": "7974.T", "📱 SoftBank": "9984.T",
}

TRENDING_US = ["AAPL", "MSFT", "NVDA", "TSLA", "META", "AMZN", "GOOGL", "AMD", "PLTR", "NFLX"]
TRENDING_JP = ["7203.T", "6758.T", "7974.T", "9984.T", "6501.T", "4063.T", "8306.T", "9433.T", "6367.T", "7751.T"]

SECTOR_BENCHMARKS = {
    "Technology":             {"wacc": "8-12%", "growth": "10-20%", "per": 25, "pbr": 5.0},
    "Financial Services":    {"wacc": "7-10%", "growth": "5-10%",  "per": 12, "pbr": 1.5},
    "Consumer Defensive":    {"wacc": "6-9%",  "growth": "3-7%",   "per": 20, "pbr": 3.0},
    "Healthcare":            {"wacc": "7-11%", "growth": "7-15%",  "per": 22, "pbr": 4.0},
    "Consumer Cyclical":     {"wacc": "8-12%", "growth": "5-12%",  "per": 18, "pbr": 2.5},
    "Industrials":           {"wacc": "7-10%", "growth": "5-10%",  "per": 18, "pbr": 2.5},
    "Energy":                {"wacc": "7-10%", "growth": "3-8%",   "per": 14, "pbr": 1.5},
    "Communication Services":{"wacc": "8-11%", "growth": "7-15%",  "per": 20, "pbr": 3.5},
    "Real Estate":           {"wacc": "6-9%",  "growth": "3-6%",   "per": 25, "pbr": 2.0},
    "Utilities":             {"wacc": "5-8%",  "growth": "2-5%",   "per": 18, "pbr": 1.5},
}

METHOD_DESCRIPTIONS = {
    "DCF": """
**DCF（Discounted Cash Flow / 割引キャッシュフロー）法**

企業が将来生み出すフリーキャッシュフロー（FCF）を、リスクを加味した割引率（WACC）で
現在価値に割り引いて理論株価を算出する最も本格的な手法。

- **成長率**: 今後N年間のFCF年成長率
- **永続成長率**: N年後以降の永続成長率（インフレ率程度、2-3%が一般的）
- **割引率（WACC）**: 資本コスト。リスクが高い企業ほど高くなる
""",
    "PER": """
**PER（Price-to-Earnings Ratio / 株価収益率）倍率法**

EPS（1株当たり利益）×目標PER = 理論株価

- 成長企業（IT等）: 20-40倍
- 成熟企業: 10-15倍
- 市場平均（S&P500）: 18-25倍
""",
    "PBR": """
**PBR（Price-to-Book Ratio）倍率法**

1株純資産（BPS）×目標PBR = 理論株価

- PBR 1.0倍 = 解散価値（清算時の理論価格）
- 銀行・保険・製造業の評価に特に有効
""",
    "グレアム": """
**グレアム式（Benjamin Graham の内在価値公式）**

V = EPS × (8.5 + 2g) × 4.4 / Y

- g = 期待成長率（%表示）
- Y = 現在のAAA社債利回り
- バフェットの師匠が考案した保守的な評価手法
""",
    "DDM": """
**DDM（Dividend Discount Model / 配当割引モデル）**

P = D₁ / (r − g)　　（Gordon Growth Model）

配当を安定的に出す成熟企業・高配当株に最適。
無配銘柄には使えない。
""",
    "EV/EBITDA": """
**EV/EBITDA法**

EV = EBITDA × 目標倍率 → 株価 = (EV − 純負債) / 株式数

国際比較・M&A分析の標準的な指標。
一般企業8-12倍、成長企業15-25倍が目安。
""",
}

# ============================================================
# フォーマット関数
# ============================================================

def fmt_price(price: float, currency: str) -> str:
    if currency == "JPY":
        return f"¥{price:,.0f}"
    return f"${price:,.2f}"


def fmt_compact(price: float) -> str:
    if price >= 10000:
        return f"{price:,.0f}"
    elif price >= 10:
        return f"{price:,.2f}"
    return f"{price:.4f}"


def fmt_pct(val) -> str:
    return "N/A" if val is None else f"{val * 100:.1f}%"


@st.cache_data(ttl=86400, show_spinner=False)
def get_stock_display_name(ticker: str) -> str:
    """ティッカーの表示名を取得（日本株は企業名を短縮表示）"""
    try:
        info = yf.Ticker(ticker).info
        name = info.get("shortName") or info.get("longName") or ""
        if not name:
            return ticker.replace(".T", "")
        for suffix in [" Co., Ltd.", ", Ltd.", " Corporation", " Corp.", " Inc.", " Ltd.", " Group"]:
            name = name.replace(suffix, "")
        return name[:16].strip()
    except Exception:
        return ticker.replace(".T", "")


def to_tv_symbol(ticker: str, exchange: str = "") -> str:
    if ticker.upper().endswith(".T"):
        return f"TSE:{ticker[:-2]}"
    m = {"NMS": "NASDAQ", "NGM": "NASDAQ", "NCM": "NASDAQ",
         "NYQ": "NYSE", "NYA": "NYSE", "ASE": "AMEX"}
    ex = m.get(exchange, "")
    return f"{ex}:{ticker}" if ex else ticker


def estimate_wacc(data: dict) -> float:
    beta = data.get("beta") or 1.0
    cost_equity = 0.04 + beta * 0.05
    mc = data.get("market_cap") or 1
    nd = max(data.get("net_debt") or 0, 0)
    total = mc + nd
    if total > 0 and nd > 0:
        wacc = (mc / total) * cost_equity + (nd / total) * 0.04 * 0.79
    else:
        wacc = cost_equity
    return round(max(min(wacc, 0.20), 0.04), 4)


def result_html(res, currency: str) -> str:
    if not res.is_valid:
        return f'<div class="result-box" style="color:#999;padding:30px">{res.error_msg}</div>'
    price_str = fmt_price(res.fair_value, currency)
    sign = "+" if res.upside_pct >= 0 else ""
    if res.upside_pct > 10:
        cls, arrow = "upside-up", "▲"
    elif res.upside_pct >= -10:
        cls, arrow = "upside-mid", ("▲" if res.upside_pct >= 0 else "▼")
    else:
        cls, arrow = "upside-down", "▼"
    assumptions = " &nbsp;|&nbsp; ".join(f"{k}: <b>{v}</b>" for k, v in res.assumptions.items())
    return f"""
    <div class="result-box">
        <div class="fair-value">{price_str}</div>
        <div class="{cls}">{arrow} {sign}{res.upside_pct:.1f}%（現在値との乖離）</div>
        <div style="color:#555;font-size:0.85em;margin-top:10px">{assumptions}</div>
    </div>
    """


def parse_news(raw_news: list) -> list:
    items = []
    for item in raw_news[:12]:
        if "content" in item:
            c = item["content"]
            url = (c.get("clickThroughUrl") or {}).get("url", "")
            publisher = (c.get("provider") or {}).get("displayName", "")
            items.append({"title": c.get("title", ""), "url": url, "publisher": publisher})
        else:
            items.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "publisher": item.get("publisher", ""),
            })
    return [i for i in items if i["title"]]


# ============================================================
# データ取得（キャッシュ）
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def load_data(ticker: str) -> dict:
    try:
        return fetch_stock_data(ticker)
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def search_tickers(query: str) -> list:
    if len(query) < 2:
        return []
    try:
        results = yf.Search(query, max_results=10).quotes
        out = []
        for r in results:
            sym = r.get("symbol", "")
            name = r.get("shortname") or r.get("longname") or sym
            exch = r.get("exchDisp") or r.get("exchange", "")
            if sym and r.get("quoteType") in ("EQUITY", "ETF"):
                out.append({"symbol": sym, "name": name, "exchange": exch})
        return out
    except Exception:
        return []


@st.cache_data(ttl=180, show_spinner=False)
def load_prices_batch(symbols: tuple) -> dict:
    result = {}
    sym_list = list(symbols)
    if not sym_list:
        return result
    try:
        raw = yf.download(sym_list, period="2d", auto_adjust=True,
                          progress=False, group_by="ticker")
        for sym in sym_list:
            try:
                hist = raw if len(sym_list) == 1 else (
                    raw[sym] if isinstance(raw.columns, pd.MultiIndex) else pd.DataFrame()
                )
                if not hist.empty:
                    close = hist["Close"].dropna()
                    if len(close) >= 1:
                        last = float(close.iloc[-1])
                        prev = float(close.iloc[-2]) if len(close) >= 2 else last
                        chg = (last - prev) / prev * 100 if prev > 0 else 0
                        result[sym] = {"price": last, "change_pct": chg}
            except Exception:
                pass
    except Exception:
        pass
    return result


# ============================================================
# TradingView
# ============================================================

def render_tradingview_chart(tv_symbol: str, height: int = 650) -> None:
    """メインチャート（高さ固定版）"""
    cfg = json.dumps({
        "width": "100%",
        "height": height,
        "symbol": tv_symbol,
        "interval": "D",
        "timezone": "Asia/Tokyo",
        "theme": "light",
        "style": "1",
        "locale": "ja",
        "allow_symbol_change": False,
        "calendar": False,
        "support_host": "https://www.tradingview.com",
        "autosize": False,
    })
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:100%;height:{height}px;overflow:hidden}}
.tradingview-widget-container{{width:100%;height:{height}px}}
.tradingview-widget-container__widget{{width:100%;height:{height-32}px}}
</style></head><body>
<div class="tradingview-widget-container">
  <div class="tradingview-widget-container__widget"></div>
  <div class="tradingview-widget-copyright">
    <a href="https://www.tradingview.com/" rel="noopener nofollow" target="_blank">
      <span style="color:#3BB3E4">TradingView</span>
    </a>
  </div>
  <script type="text/javascript"
    src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js"
    async>{cfg}</script>
</div></body></html>"""
    components.html(html, height=height, scrolling=False)


def render_mini_chart_html(symbol: str, height: int = 200) -> str:
    """ミニチャートのHTML文字列を返す"""
    cfg = json.dumps({
        "symbol": symbol, "width": "100%", "height": height,
        "locale": "ja", "dateRange": "6M", "colorTheme": "light",
        "trendLineColor": "rgba(41,98,255,1)",
        "underLineColor": "rgba(41,98,255,0.15)",
        "underLineBottomColor": "rgba(41,98,255,0)",
        "isTransparent": False, "autosize": False,
    })
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>*{{margin:0;padding:0}}html,body{{height:{height}px;overflow:hidden}}</style>
</head><body>
<div class="tradingview-widget-container" style="height:{height}px">
  <div class="tradingview-widget-container__widget"></div>
  <script type="text/javascript"
    src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js"
    async>{cfg}</script>
</div></body></html>"""


# ============================================================
# ウォッチリスト（ローカル + GitHub Gist クラウド対応）
# ============================================================

DEFAULT_WATCHLIST = {
    "categories": {
        "テック株 🤖": ["AAPL", "MSFT", "NVDA", "GOOGL", "META"],
        "日本株 🇯🇵": ["7203.T", "6758.T", "7974.T", "9984.T"],
        "ETF 📊": ["SPY", "QQQ"],
        "高配当 💰": ["JNJ", "KO"],
    }
}


def _get_secret(key: str) -> str:
    """環境変数 → Streamlit secrets の順で取得"""
    val = os.getenv(key, "")
    if val:
        return val
    try:
        return st.secrets.get(key, "")
    except Exception:
        return ""


def _gist_headers() -> dict:
    token = _get_secret("GITHUB_TOKEN")
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }


def _load_from_gist() -> dict | None:
    """GitHub Gistからウォッチリストを取得"""
    gist_id = _get_secret("GIST_ID")
    token   = _get_secret("GITHUB_TOKEN")
    if not gist_id or not token:
        return None
    try:
        resp = _requests.get(
            f"https://api.github.com/gists/{gist_id}",
            headers=_gist_headers(), timeout=8,
        )
        if resp.status_code == 200:
            files = resp.json().get("files", {})
            content = next(iter(files.values()), {}).get("content", "")
            return json.loads(content)
    except Exception:
        pass
    return None


def _save_to_gist(wl: dict) -> None:
    """GitHub Gistにウォッチリストを保存"""
    gist_id = _get_secret("GIST_ID")
    token   = _get_secret("GITHUB_TOKEN")
    if not gist_id or not token:
        return
    try:
        content = json.dumps(wl, ensure_ascii=False, indent=2)
        _requests.patch(
            f"https://api.github.com/gists/{gist_id}",
            headers=_gist_headers(),
            json={"files": {"watchlist.json": {"content": content}}},
            timeout=8,
        )
    except Exception:
        pass


def _load_from_local() -> dict:
    if WATCHLIST_FILE.exists():
        try:
            return json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return DEFAULT_WATCHLIST.copy()


def _save_to_local(wl: dict) -> None:
    try:
        WATCHLIST_FILE.parent.mkdir(exist_ok=True)
        WATCHLIST_FILE.write_text(json.dumps(wl, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_watchlist() -> dict:
    """ウォッチリストを読み込む（Gist優先・session_stateキャッシュ）"""
    if "watchlist_data" in st.session_state:
        return st.session_state.watchlist_data
    wl = _load_from_gist() or _load_from_local()
    st.session_state.watchlist_data = wl
    return wl


def save_watchlist(wl: dict) -> None:
    """ウォッチリストを保存（session_state + Gist + ローカル）"""
    st.session_state.watchlist_data = wl
    _save_to_gist(wl)
    _save_to_local(wl)


def is_cloud() -> bool:
    """Streamlit Cloud上で実行中かを判定"""
    return bool(_get_secret("GIST_ID"))
