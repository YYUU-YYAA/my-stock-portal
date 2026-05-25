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
    "CNBC": {
        "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "icon": "📡", "category": "経済",
    },
    "Bloomberg": {
        "url": "https://news.google.com/rss/search?q=bloomberg+market+finance&hl=en&gl=US&ceid=US:en",
        "icon": "💹", "category": "経済",
    },
    "Yahoo Finance": {
        "url": "https://finance.yahoo.com/news/rssindex",
        "icon": "📈", "category": "経済",
    },
    # ──── テクノロジー・VC ────
    "TechCrunch": {
        "url": "https://techcrunch.com/feed/",
        "icon": "💻", "category": "テクノロジー",
    },
    "Hacker News": {
        "url": "https://hnrss.org/frontpage",
        "icon": "🖥️", "category": "テクノロジー",
    },
    "Crunchbase News": {
        "url": "https://news.crunchbase.com/feed/",
        "icon": "💰", "category": "VC",
    },
    "The Bridge JP": {
        "url": "https://thebridge.jp/feed",
        "icon": "🌉", "category": "VC",
    },
    # ──── 日本語 ────
    "NHK総合": {
        "url": "https://www.nhk.or.jp/rss/news/cat0.xml",
        "icon": "🇯🇵", "category": "日本",
    },
    "日経新聞": {
        "url": "https://news.google.com/rss/search?q=site:nikkei.com&hl=ja&gl=JP&ceid=JP:ja",
        "icon": "📰", "category": "日本",
    },
}

CATEGORY_ORDER = ["経済", "テクノロジー", "VC", "日本"]

# ニッチ・サイエンス情報ソース
NICHE_SOURCES = {
    "ScienceDaily": "https://www.sciencedaily.com/rss/top/science.xml",
    "Quanta Magazine": "https://www.quantamagazine.org/feed/",
    "Space.com": "https://www.space.com/home/feed/site.xml",
    "Interesting Engineering": "https://interestingengineering.com/feed",
}

# ============================================================
# AIダイジェスト プロンプト
# ============================================================
DIGEST_PROMPTS = {
    "今日のネタ": """あなたは多忙な投資家・VCのための情報キュレーターです。
以下のニュースと科学情報を基に、1分で全体把握できる日本語ダイジェストを作成してください。

## 📌 今日のキーニュース
（箇条書き4〜5個。各1文。数字・固有名詞で具体的に。最重要から順に）

## 🔬 今日の話のネタ
（一般ニュースでは取り上げない面白い・驚くべき話題を2個。各3文。会話のきっかけになる内容）

{custom}

ニュース:
{headlines}

サイエンス・ニッチ:
{niche}
""",
    "総合": """投資家・VC向けニュースを日本語で簡潔にまとめてください。

## 🔑 キーポイント（3項目・箇条書き）
## 📊 市場・経済（2文）
## 💻 テクノロジー・スタートアップ（2文）

{custom}

200字以内。

ヘッドライン:
{headlines}
""",
    "経済": """経済・金融・市場ニュースを投資判断に役立つ形で日本語200字以内にまとめてください。箇条書き優先。{custom}\nヘッドライン:\n{headlines}
""",
    "テクノロジー": """テクノロジー・AI・スタートアップのニュースをVC投資家向けに日本語200字以内にまとめてください。{custom}\nヘッドライン:\n{headlines}
""",
    "VC": """VC・スタートアップ・資金調達のニュースをVC投資家向けに日本語200字以内にまとめてください。{custom}\nヘッドライン:\n{headlines}
""",
    "政治": """政治・外交・規制ニュースの市場への影響を投資家向けに日本語200字以内にまとめてください。{custom}\nヘッドライン:\n{headlines}
""",
    "日本": """日本の経済・ビジネス・テクノロジーニュースを投資家向けに日本語200字以内にまとめてください。{custom}\nヘッドライン:\n{headlines}
""",
    "株価": """株式市場の動きを以下の形式で日本語200字以内にまとめてください。\n## 📈 市場概況\n## 🎯 注目ポイント\n## ⚠️ リスク要因\n{custom}\nヘッドライン:\n{headlines}
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


def get_all_headlines(limit_per_source: int = 5) -> list:
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


def generate_ai_digest(headlines: list, digest_type: str = "総合", custom: str = "") -> str:
    """ClaudeでAIダイジェストを生成（ファイルキャッシュ付き）"""
    if not headlines:
        return "ヘッドラインが取得できませんでした。"

    h_text = "\n".join(f"[{h.get('source','')}] {h['title']}" for h in headlines[:20] if h.get("title"))
    cache_key = hashlib.md5(f"{digest_type}:{h_text[:500]}".encode()).hexdigest()[:12]

    cached = _file_cache_get(cache_key)
    if cached:
        return cached

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return "⚠️ ANTHROPIC_API_KEY が設定されていません。"

    prompt_template = DIGEST_PROMPTS.get(digest_type, DIGEST_PROMPTS["総合"])
    custom_section = f"\n【追加リサーチ指示】{custom}\n" if custom else ""
    prompt = prompt_template.format(headlines=h_text, custom=custom_section, niche="")

    import time
    client = anthropic.Anthropic(api_key=api_key)
    for attempt in range(3):
        try:
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
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 2:
                time.sleep(10 * (attempt + 1))
            else:
                return f"❌ 生成エラー: {str(e)[:100]}"
        except Exception as e:
            return f"❌ 生成エラー: {str(e)[:100]}"
    return "❌ サーバー混雑のため生成できませんでした。しばらくしてから再試行してください。"


@st.cache_data(ttl=900, show_spinner=False)
def get_niche_headlines(limit: int = 3) -> list:
    """サイエンス・ニッチ情報を取得"""
    items = []
    for name, url in NICHE_SOURCES.items():
        items.extend(fetch_feed(name, url)[:limit])
    return items


def generate_today_digest(
    news_headlines: list,
    niche_headlines: list,
    custom: str = "",
) -> str:
    """今日のネタ: 主要ニュース + サイエンス・ニッチ話題を生成"""
    api_key = _get_secret("ANTHROPIC_API_KEY") if False else os.getenv("ANTHROPIC_API_KEY", "")
    # シークレットも試みる
    if not api_key:
        try:
            import streamlit as _st
            api_key = _st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass
    if not api_key:
        return "⚠️ ANTHROPIC_API_KEY が設定されていません。"

    news_text  = "\n".join(f"・{h['title']}" for h in news_headlines[:15] if h.get("title"))
    niche_text = "\n".join(f"・[{h['source']}] {h['title']}" for h in niche_headlines[:8] if h.get("title"))
    custom_section = f"\n【追加リサーチ指示】\n{custom}\n" if custom else ""

    prompt = DIGEST_PROMPTS["今日のネタ"].format(
        headlines=news_text,
        niche=niche_text,
        custom=custom_section,
    )

    import time
    client = anthropic.Anthropic(api_key=api_key)
    for attempt in range(3):
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
                system=[{
                    "type": "text",
                    "text": "あなたは多忙な投資家・VCのための情報キュレーターです。簡潔・具体的・読みやすい日本語で書いてください。",
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 2:
                time.sleep(10 * (attempt + 1))
            else:
                return f"❌ 生成エラー: {str(e)[:100]}"
        except Exception as e:
            return f"❌ 生成エラー: {str(e)[:100]}"
    return "❌ サーバー混雑のため生成できませんでした。しばらくしてから再試行してください。"


# まとめ記事判定キーワード
_SUMMARY_KEYWORDS = [
    # 日本語
    "まとめ", "ダイジェスト", "朝刊", "夕刊", "ニュース速報まとめ", "今日の主な",
    "週間まとめ", "本日の", "きょうの",
    # 英語
    "wrap", "roundup", "recap", "morning brief", "evening brief",
    "5 things", "this morning", "today in", "what to watch",
    "the day ahead", "market minute", "daily digest", "headlines",
]


def is_summary_article(title: str) -> bool:
    """タイトルがまとめ・ダイジェスト系記事かどうか判定"""
    t = title.lower()
    return any(kw in t for kw in _SUMMARY_KEYWORDS)


def _get_secret(key: str) -> str:
    """ローカル環境変数またはStreamlit secretsから取得"""
    val = os.getenv(key, "")
    if val:
        return val
    try:
        import streamlit as _st
        return _st.secrets.get(key, "")
    except Exception:
        return ""


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

    import time
    client = anthropic.Anthropic(api_key=api_key)
    for attempt in range(3):
        try:
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
            return
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 2:
                yield f"\n⏳ サーバー混雑中... {10*(attempt+1)}秒後に再試行します ({attempt+1}/3)\n"
                time.sleep(10 * (attempt + 1))
            else:
                yield f"❌ 分析生成エラー: {str(e)[:200]}"
                return
        except Exception as e:
            yield f"❌ 分析生成エラー: {str(e)[:200]}"
            return


def generate_stock_analysis(data: dict, news_items: list) -> str:
    """銘柄のAI総合分析を生成（非ストリーミング版・後方互換）"""
    return "".join(generate_stock_analysis_stream(data, news_items))
