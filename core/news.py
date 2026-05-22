"""ニュース取得・AIダイジェスト生成エンジン"""

import os
import re
import hashlib
import pickle
from pathlib import Path
from datetime import datetime

import feedparser
import anthropic
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

CACHE_DIR = Path(__file__).parent.parent / "data" / "digest_cache"

# ============================================================
# ニュースソース定義
# ============================================================
MEDIA_SOURCES = {
    # ──── 経済・金融 ────
    "Bloomberg": {
        "url": "https://news.google.com/rss/search?q=bloomberg+market+finance&hl=en&gl=US&ceid=US:en",
        "icon": "💹", "category": "経済",
    },
    "CNBC": {
        "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "icon": "📺", "category": "経済",
    },
    "Yahoo Finance": {
        "url": "https://finance.yahoo.com/news/rssindex",
        "icon": "📈", "category": "経済",
    },
    "WSJ (GNews)": {
        "url": "https://news.google.com/rss/search?q=site:wsj.com+market&hl=en&gl=US&ceid=US:en",
        "icon": "📰", "category": "経済",
    },
    "FT (GNews)": {
        "url": "https://news.google.com/rss/search?q=site:ft.com+finance&hl=en&gl=US&ceid=US:en",
        "icon": "🏦", "category": "経済",
    },
    # ──── テクノロジー ────
    "TechCrunch": {
        "url": "https://techcrunch.com/feed/",
        "icon": "💻", "category": "テクノロジー",
    },
    "VentureBeat": {
        "url": "https://venturebeat.com/feed/",
        "icon": "🚀", "category": "テクノロジー",
    },
    "Wired": {
        "url": "https://www.wired.com/feed/rss",
        "icon": "⚡", "category": "テクノロジー",
    },
    "MIT Tech Review": {
        "url": "https://www.technologyreview.com/feed/",
        "icon": "🔬", "category": "テクノロジー",
    },
    "Hacker News": {
        "url": "https://hnrss.org/frontpage",
        "icon": "🖥️", "category": "テクノロジー",
    },
    "The Verge": {
        "url": "https://www.theverge.com/rss/index.xml",
        "icon": "📱", "category": "テクノロジー",
    },
    # ──── VC・スタートアップ ────
    "Crunchbase News": {
        "url": "https://news.crunchbase.com/feed/",
        "icon": "💰", "category": "VC",
    },
    "TechCrunch 資金調達": {
        "url": "https://techcrunch.com/tag/funding/feed/",
        "icon": "💵", "category": "VC",
    },
    "The Bridge JP": {
        "url": "https://thebridge.jp/feed",
        "icon": "🌉", "category": "VC",
    },
    "Fortune": {
        "url": "https://fortune.com/feed/",
        "icon": "🎯", "category": "VC",
    },
    # ──── 政治・国際 ────
    "NHK 政治": {
        "url": "https://www.nhk.or.jp/rss/news/cat4.xml",
        "icon": "🏛️", "category": "政治",
    },
    "NHK 国際": {
        "url": "https://www.nhk.or.jp/rss/news/cat6.xml",
        "icon": "🌍", "category": "政治",
    },
    "Google News 政治": {
        "url": "https://news.google.com/rss/search?q=日本+政治+外交&hl=ja&gl=JP&ceid=JP:ja",
        "icon": "🗳️", "category": "政治",
    },
    "AP News (GNews)": {
        "url": "https://news.google.com/rss/search?q=site:apnews.com&hl=en&gl=US&ceid=US:en",
        "icon": "📡", "category": "政治",
    },
    # ──── 日本語 ────
    "NHK 総合": {
        "url": "https://www.nhk.or.jp/rss/news/cat0.xml",
        "icon": "🇯🇵", "category": "日本",
    },
    "日経 (GNews)": {
        "url": "https://news.google.com/rss/search?q=日経+株価+経済&hl=ja&gl=JP&ceid=JP:ja",
        "icon": "📊", "category": "日本",
    },
    "Business Insider JP": {
        "url": "https://www.businessinsider.jp/feed/",
        "icon": "📑", "category": "日本",
    },
    "東洋経済": {
        "url": "https://toyokeizai.net/list/feed/rss",
        "icon": "🗾", "category": "日本",
    },
    "読売 (GNews)": {
        "url": "https://news.google.com/rss/search?q=site:yomiuri.co.jp&hl=ja&gl=JP&ceid=JP:ja",
        "icon": "📝", "category": "日本",
    },
}

CATEGORY_ORDER = ["経済", "テクノロジー", "VC", "政治", "日本"]

# ============================================================
# AIダイジェスト プロンプト
# ============================================================
DIGEST_PROMPTS = {
    "総合": """あなたは投資家・VCとして活躍するユーザーの専任ニュースアシスタントです。
以下の過去24時間のニュースヘッドラインを基に、1〜2分で読める総合ダイジェストを日本語で作成してください。

【優先事項】
- 株式市場・マクロ経済への影響
- スタートアップ・VC業界の重要な動き
- AI・テクノロジーの重要トレンド
- 投資判断に直結するニュース

【出力形式】
## 🔑 今日のキーポイント
（3〜4項目の箇条書き。最も重要な内容を端的に）

## 📊 経済・市場
（2〜3文で概況）

## 💻 テクノロジー・スタートアップ
（2〜3文で概況）

## 🗾 日本
（1〜2文で重要な日本関連ニュース）

全体で400〜500字以内。

ヘッドライン:
{headlines}
""",
    "経済": """以下のヘッドラインから経済・金融・市場のニュースを分析し、投資判断に役立つ日本語のダイジェストを作成してください（300字以内）。

ヘッドライン:
{headlines}
""",
    "テクノロジー": """以下のヘッドラインからテクノロジー・AI・スタートアップのニュースを分析し、投資家・VCとして重要な洞察を含む日本語のダイジェストを作成してください（300字以内）。

ヘッドライン:
{headlines}
""",
    "VC": """以下のヘッドラインからVC・スタートアップ・資金調達のニュースを分析し、VC投資家として重要なトレンドや案件情報を日本語でまとめてください（300字以内）。

ヘッドライン:
{headlines}
""",
    "政治": """以下のヘッドラインから政治・外交・規制のニュースを分析し、投資家・VCとして影響を受ける可能性がある内容を日本語でまとめてください（300字以内）。
規制変更、地政学リスク、政府政策の市場への影響を重点的に。

ヘッドライン:
{headlines}
""",
    "日本": """以下のヘッドラインから日本の経済・ビジネス・テクノロジーのニュースを分析し、投資家として重要な内容を日本語でまとめてください（300字以内）。

ヘッドライン:
{headlines}
""",
    "株価": """以下の市場関連ニュースを基に、今日の株式市場の動きと投資判断に役立つポイントを日本語でまとめてください。

【出力形式】
## 📈 市場概況
## 🎯 注目ポイント
## ⚠️ リスク要因

300字以内。

ヘッドライン:
{headlines}
""",
}

# AI株式分析プロンプト
STOCK_ANALYSIS_PROMPT = """あなたは優秀な投資アナリスト兼VCパートナーです。
以下の企業について、投資家・VCとして価値ある深い分析を行ってください。

企業: {company_name} ({ticker})
業界: {sector} / {industry}
国: {country}
現在株価: {price} {currency}
時価総額: {market_cap}

主要指標:
- PER: {per}
- PBR: {pbr}
- ROE: {roe}
- 営業利益率: {op_margin}
- 売上成長率: {rev_growth}
- ベータ: {beta}

最近のニュース:
{news}

以下の形式でそのままコピペできる分析レポートを日本語で作成してください：

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 {company_name}（{ticker}）投資分析レポート
生成日時: {date}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 🏭 業界・マクロ環境
（この業界の現状、主要トレンド、成長ドライバー、逆風要因を2〜3段落で）

## 🎯 企業分析
**強み（Moat）:**
（競争優位性、参入障壁、差別化要因）

**弱み・リスク:**
（構造的リスク、競合圧力、規制リスク等）

**経営陣・ガバナンス:**
（リーダーシップの質、資本配分の方針等）

## ⚔️ 競合比較
（主要競合3社との比較。ポジショニング、市場シェア、差別化）

## 🔮 将来シナリオ
**🟢 強気シナリオ（確率 30%）**
（実現条件と期待リターンの根拠）

**🟡 中立シナリオ（確率 50%）**
（ベースケース。現在の延長線）

**🔴 弱気シナリオ（確率 20%）**
（リスクが顕在化した場合）

## 💡 投資家として磨くべき視点（Learning Tips）
この企業・業界を分析することで学べる重要な投資の視点を3〜5点。
繰り返し見ることで審美眼が養われ、次の投資判断に活きる内容を記載。

## 📋 投資判断サマリー
**総合評価:** ★★★☆☆（5段階）
**短期（3ヶ月）:**
**中長期（1〜3年）:**
**注目すべき次のカタリスト:**
**適正株価レンジ（私見）:**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
※ このレポートはAIによる分析です。投資判断は自己責任でお願いします。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


# ============================================================
# ニュース取得関数
# ============================================================

@st.cache_data(ttl=900, show_spinner=False)
def fetch_feed(name: str, url: str) -> list:
    """単一RSSフィードを取得"""
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:12]:
            title = entry.get("title", "").strip()
            link  = entry.get("link", "")
            pub   = entry.get("published", "") or entry.get("updated", "")
            summ  = re.sub(r"<[^>]+>", "", entry.get("summary", "") or "")[:120]
            if title and link:
                items.append({
                    "title": title, "link": link,
                    "published": str(pub)[:16], "summary": summ,
                    "source": name,
                })
        return items
    except Exception:
        return []


def get_all_headlines(limit_per_source: int = 8) -> list:
    """全ソースのヘッドラインを集約"""
    all_items = []
    for name, cfg in MEDIA_SOURCES.items():
        items = fetch_feed(name, cfg["url"])
        all_items.extend(items[:limit_per_source])
    return all_items


def get_category_headlines(category: str, limit: int = 15) -> list:
    """カテゴリ別ヘッドライン"""
    items = []
    for name, cfg in MEDIA_SOURCES.items():
        if cfg["category"] == category:
            items.extend(fetch_feed(name, cfg["url"])[:5])
    return items[:limit]


def get_source_headlines(source_name: str) -> list:
    """ソース別ヘッドライン"""
    cfg = MEDIA_SOURCES.get(source_name)
    if not cfg:
        return []
    return fetch_feed(source_name, cfg["url"])


# ============================================================
# AIダイジェスト生成
# ============================================================

def _file_cache_get(cache_key: str) -> str | None:
    """ファイルキャッシュから取得（1時間有効）"""
    f = CACHE_DIR / f"{cache_key}.pkl"
    try:
        if f.exists() and (datetime.now().timestamp() - f.stat().st_mtime) < 3600:
            return pickle.loads(f.read_bytes())
    except Exception:
        pass
    return None


def _file_cache_set(cache_key: str, content: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        (CACHE_DIR / f"{cache_key}.pkl").write_bytes(pickle.dumps(content))
    except Exception:
        pass


def generate_ai_digest(headlines: list, digest_type: str = "総合") -> str:
    """ClaudeでAIダイジェストを生成（ファイルキャッシュ付き）"""
    if not headlines:
        return "ヘッドラインが取得できませんでした。"

    h_text = "\n".join(f"[{h.get('source','')}] {h['title']}" for h in headlines[:40] if h.get("title"))
    cache_key = hashlib.md5(f"{digest_type}:{h_text[:500]}".encode()).hexdigest()[:12]

    cached = _file_cache_get(cache_key)
    if cached:
        return cached

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return "⚠️ ANTHROPIC_API_KEY が設定されていません。"

    prompt_template = DIGEST_PROMPTS.get(digest_type, DIGEST_PROMPTS["総合"])
    prompt = prompt_template.format(headlines=h_text)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system=[{
                "type": "text",
                "text": "あなたは投資家・VCのための日本語ニュースアシスタントです。簡潔・的確・実用的な分析を提供します。",
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": prompt}],
        )
        result = resp.content[0].text
        _file_cache_set(cache_key, result)
        return result
    except Exception as e:
        return f"❌ 生成エラー: {str(e)[:100]}"


def _build_stock_prompt(data: dict, news_items: list) -> tuple[str, str]:
    """株式分析プロンプトを構築して (system, prompt) を返す"""
    def safe(val, fmt="{}", pct=False):
        if val is None:
            return "N/A"
        return f"{val*100:.1f}%" if pct else fmt.format(val)

    mc = data.get("market_cap")
    mc_str = "N/A"
    if mc:
        if data.get("currency") == "JPY":
            mc_str = f"¥{mc/1e12:.1f}兆" if mc >= 1e12 else f"¥{mc/1e8:.0f}億"
        else:
            mc_str = f"${mc/1e12:.2f}T" if mc >= 1e12 else f"${mc/1e9:.1f}B"

    news_text = "\n".join(f"- {n['title']}" for n in news_items[:8] if n.get("title")) or "ニュースなし"

    system_msg = "あなたは10年以上の経験を持つトップクラスの投資アナリスト兼VCパートナーです。投資家として価値ある深い洞察を提供します。"
    prompt = STOCK_ANALYSIS_PROMPT.format(
        company_name=data.get("company_name", data.get("ticker", "")),
        ticker=data.get("ticker", ""),
        sector=data.get("sector", "N/A"),
        industry=data.get("industry", "N/A"),
        country=data.get("country", "N/A"),
        price=f"{data.get('current_price', 0):,.2f}",
        currency=data.get("currency", "USD"),
        market_cap=mc_str,
        per=safe(data.get("per"), "{:.1f}x"),
        pbr=safe(data.get("pbr"), "{:.2f}x"),
        roe=safe(data.get("roe"), pct=True),
        op_margin=safe(data.get("operating_margin"), pct=True),
        rev_growth=safe(data.get("revenue_growth"), pct=True),
        beta=safe(data.get("beta"), "{:.2f}"),
        news=news_text,
        date=datetime.now().strftime("%Y年%m月%d日 %H:%M"),
    )
    return system_msg, prompt


def generate_stock_analysis_stream(data: dict, news_items: list):
    """銘柄のAI総合分析をストリーミングで生成（ジェネレータ）"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        yield "⚠️ ANTHROPIC_API_KEY が設定されていません。"
        return

    system_msg, prompt = _build_stock_prompt(data, news_items)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            system=[{
                "type": "text",
                "text": system_msg,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text
    except Exception as e:
        yield f"❌ 分析生成エラー: {str(e)[:200]}"


def generate_stock_analysis(data: dict, news_items: list) -> str:
    """銘柄のAI総合分析を生成（非ストリーミング版・後方互換）"""
    return "".join(generate_stock_analysis_stream(data, news_items))
