"""
Claude API を使った分析・記事生成モジュール
claude-opus-4-7 + adaptive thinking で分析の深度を最大化
"""

import anthropic
import json
from datetime import datetime
from pathlib import Path
from fetcher import format_financials_for_prompt
from models import summarize_valuations


client = anthropic.Anthropic()
MODEL = "claude-opus-4-7"


def _call_claude(system: str, user: str, max_tokens: int = 4000) -> str:
    """Claude API を呼び出してテキストを返す"""
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    # テキストブロックを抽出
    text_parts = [b.text for b in response.content if b.type == "text"]
    return "\n".join(text_parts)


def analyze_macro_and_industry(data: dict) -> str:
    """マクロ環境・業界動向を分析"""
    system = (
        "あなたは経験豊富な株式アナリストです。"
        "投資家向けに、マクロ経済と業界動向を深く、かつ分かりやすく分析してください。"
        "過去・現在・将来の3つの時間軸で整理し、具体的な数字や事例を交えてください。"
    )
    user = f"""以下の銘柄のセクター・業種について分析してください。

銘柄情報:
- 会社名: {data['company_name']} ({data['ticker']})
- セクター: {data['sector']}
- 業種: {data['industry']}
- 国: {data['country']}
- 事業概要: {data.get('description', 'N/A')[:500]}

以下の観点で分析してください：

【マクロ環境】
- 金利・インフレ・経済成長のトレンドがこの業種に与える影響
- 地政学リスクや規制変化
- テクノロジー変革・デジタル化の波

【業界動向】
- 業界の成長ステージ（黎明期/成長期/成熟期/衰退期）
- 主要な競合プレイヤーの動向
- 業界全体の収益性トレンド（PER水準、マージン傾向）
- 構造的な追い風・向かい風

【今後5年の見通し】
- 業界の成長ドライバー
- 最大のリスク要因
- 注目すべきイノベーションや破壊的変化

分析は日本語で、投資家が判断に使える実用的な内容にしてください。"""

    return _call_claude(system, user, max_tokens=3000)


def analyze_company(data: dict) -> str:
    """企業分析（競争優位性・財務・経営）"""
    system = (
        "あなたは株式投資の専門家です。"
        "企業の競争優位性、財務の健全性、経営陣の質を多角的に分析してください。"
        "ウォーレン・バフェットやチャーリー・マンガーのような視点で深く掘り下げてください。"
    )

    financials_text = format_financials_for_prompt(data)

    user = f"""以下の企業を詳細に分析してください。

{financials_text}

以下の観点で分析してください：

【ビジネスモデル解剖】
- 収益の源泉と構造
- 顧客ロックイン・スイッチングコスト
- ネットワーク効果・スケールメリット

【競争優位性 (モート)】
- 持続的競争優位の強さと耐久性
- ブランド力・特許・規制障壁
- コスト優位性

【財務分析】
- 売上・利益のトレンドと質
- キャッシュフロー創出能力
- 財務レバレッジとリスク
- 資本効率 (ROE, ROIC)

【経営の質】
- 資本配分の実績（M&A、自社株買い、配当）
- インサイダー保有比率と経営陣のコミット

【強み・弱み・機会・脅威 (SWOT)】
簡潔に整理してください。"""

    return _call_claude(system, user, max_tokens=3500)


def generate_scenarios(data: dict, macro_analysis: str, company_analysis: str) -> tuple[str, list[dict]]:
    """
    将来シナリオを3つ生成し、構造化データも返す
    Returns: (scenario_text, scenarios_for_valuation)
    """
    system = (
        "あなたはプロの株式アナリストです。"
        "企業の将来を、強気・中立・弱気の3シナリオで描写してください。"
        "各シナリオは独立した「物語」として、投資家が感情移入できるストーリー性を持たせてください。"
        "また、各シナリオの転換トリガー（いつ・何が起きたら実現するか）も必ず明示してください。"
    )

    user = f"""以下の情報を踏まえて、{data['company_name']} ({data['ticker']}) の将来シナリオを3つ作成してください。

【マクロ・業界分析サマリー】
{macro_analysis[:1500]}

【企業分析サマリー】
{company_analysis[:1500]}

【現在の財務指標】
- 現在株価: {data.get('current_price', 'N/A')} {data.get('currency', '')}
- PER: {data.get('per', 'N/A')}
- 売上成長率: {(data.get('revenue_growth') or 0)*100:.1f}%
- 営業利益率: {(data.get('operating_margin') or 0)*100:.1f}%

各シナリオについて以下を含めてください：

## 強気シナリオ (Bull Case)
**確率: XX%**
- シナリオの概要（2〜3段落のストーリー）
- 主な仮定（売上成長率、利益率、FCF成長率）
- 転換トリガー（このシナリオが実現する鍵となるイベント）
- 想定PER水準と目標株価レンジ

## 中立シナリオ (Base Case)
**確率: XX%**
- シナリオの概要
- 主な仮定
- 転換トリガー
- 想定PER水準と目標株価レンジ

## 弱気シナリオ (Bear Case)
**確率: XX%**
- シナリオの概要
- 主な仮定
- 転換トリガー
- 想定PER水準と目標株価レンジ

最後に「シナリオ確率×株価感応度マップ」として、どのシナリオが最もリターン/リスクに影響するかをまとめてください。"""

    scenario_text = _call_claude(system, user, max_tokens=4000)

    # シナリオごとのバリュエーション用パラメータを推定
    # （Claude の出力から数値を抽出するのが理想だが、ここでは典型値を使用）
    revenue_growth = data.get("revenue_growth") or 0.05
    scenarios_for_valuation = [
        {
            "name": "強気 (Bull)",
            "fcf_growth_rates": [revenue_growth * 2, revenue_growth * 1.8,
                                   revenue_growth * 1.5, revenue_growth * 1.3, revenue_growth * 1.1],
            "terminal_growth": 0.03,
            "wacc": 0.08,
            "forward_per": (data.get("per") or 20) * 1.3,
        },
        {
            "name": "中立 (Base)",
            "fcf_growth_rates": [revenue_growth * 1.2] * 5,
            "terminal_growth": 0.02,
            "wacc": 0.09,
            "forward_per": data.get("per") or 20,
        },
        {
            "name": "弱気 (Bear)",
            "fcf_growth_rates": [max(revenue_growth * 0.3, -0.05)] * 5,
            "terminal_growth": 0.01,
            "wacc": 0.11,
            "forward_per": (data.get("per") or 20) * 0.7,
        },
    ]

    return scenario_text, scenarios_for_valuation


def generate_valuation_commentary(
    data: dict,
    scenario_results: list[dict],
    reverse_dcf_result: dict,
) -> str:
    """バリュエーション分析のコメンタリーを生成"""
    system = (
        "あなたはバリュエーションの専門家です。"
        "複数の手法による試算結果を統合し、投資家にとって意味のある解釈を提供してください。"
    )

    valuation_summary = summarize_valuations(scenario_results, data.get("current_price", 0))

    implied_growth = reverse_dcf_result.get("implied_growth_rate_pct", 0)
    interpretation = reverse_dcf_result.get("interpretation", "")

    user = f"""以下のバリュエーション試算結果について、解説・考察を書いてください。

{valuation_summary}

【逆算DCF (市場の期待値分析)】
現在株価が織り込む期待FCF成長率: {implied_growth:.1f}% (年率、5年間)
解釈: {interpretation}
WACC仮定: {reverse_dcf_result.get('wacc', 0.09)*100:.1f}%
永続成長率仮定: {reverse_dcf_result.get('terminal_growth', 0.02)*100:.1f}%

【アナリスト予想】
{json.dumps(data.get('analyst_price_targets', {}), ensure_ascii=False, indent=2)}

以下の観点で分析してください：
1. 各シナリオの目標株価と現在株価のギャップはどう解釈できるか
2. 市場が織り込んでいる期待値は高すぎるか/低すぎるか
3. どのバリュエーション指標が最も信頼性が高いか（この企業の特性に合った手法）
4. 投資判断の総括（買い/中立/売り の根拠）
5. リスクと注目すべきカタリスト

専門的かつ、投資家が判断しやすい実用的な内容にしてください。"""

    return _call_claude(system, user, max_tokens=2500)


def write_note_article(
    data: dict,
    macro_analysis: str,
    company_analysis: str,
    scenario_text: str,
    valuation_commentary: str,
    chart_paths: dict,
    output_path: Path,
) -> str:
    """
    最終的な note 向け記事を生成してファイルに書き出す
    """
    system = (
        "あなたはプロの投資ライターです。"
        "データに基づいた深い分析を、note に掲載する投資記事として書き上げてください。"
        "読者は個人投資家〜セミプロ投資家を想定しています。"
        "わかりやすさと専門性のバランスを保ち、「なぜ今この銘柄なのか」が伝わる記事にしてください。"
        "Markdown 形式で、見出し・箇条書き・強調を適切に使ってください。"
    )

    today = datetime.now().strftime("%Y年%m月%d日")
    current_price = data.get("current_price", "N/A")
    currency = data.get("currency", "USD")

    user = f"""以下の分析内容をもとに、note投稿用の記事を書いてください。

【記事の構成】
1. タイトルと導入 (読者の興味を引くリード文)
2. 企業概要（箇条書きでコンパクトに）
3. マクロ・業界環境の分析
4. 企業の強み・ビジネスモデル
5. 将来シナリオ (3シナリオ)
6. バリュエーション分析
7. 投資判断まとめ
8. リスクと注目カタリスト
9. 免責事項

【分析データ】

◆ マクロ・業界分析:
{macro_analysis[:2000]}

◆ 企業分析:
{company_analysis[:2000]}

◆ シナリオ分析:
{scenario_text[:2500]}

◆ バリュエーション解説:
{valuation_commentary[:2000]}

【基本情報】
- 会社名: {data['company_name']}
- ティッカー: {data['ticker']}
- 現在株価: {current_price} {currency}
- セクター/業種: {data['sector']} / {data['industry']}
- 執筆日: {today}

【注意事項】
- 記事のトーン: プロフェッショナルかつ親しみやすい
- 分量: 4,000〜6,000字程度
- 図表は ![チャート名](チャートファイル名.png) の形式で本文中に挿入する指示を含めてください
- 最後に「本記事は投資助言ではありません」の免責事項を入れてください
- 読者が記事を読み終わった後に「このタイミングでこの銘柄を検討する意義」を感じられる内容に

記事はMarkdown形式で書いてください。"""

    article_content = _call_claude(system, user, max_tokens=6000)

    # チャートの挿入指示を実際のMarkdown画像構文に変換
    chart_labels = {
        "01_price_history.png": "株価推移（5年）",
        "02_financial_trend.png": "財務推移（売上・利益）",
        "03_scenario_valuation.png": "シナリオ別目標株価",
        "04_kpi_radar.png": "KPIレーダー",
    }

    # ヘッダーを付加
    header = f"""---
# {data['company_name']} ({data['ticker']}) 企業分析レポート
**執筆日:** {today}
**現在株価:** {current_price} {currency}
**分析モデル:** Claude Opus 4.7 + DCF / PER / 逆算DCF

---

"""
    full_article = header + article_content

    # ファイルに書き出し
    output_path.write_text(full_article, encoding="utf-8")
    print(f"✅ 記事を保存しました: {output_path}")

    return full_article


def run_full_analysis(data: dict, scenario_results: list[dict], reverse_dcf_result: dict,
                      chart_paths: dict, output_dir: Path) -> str:
    """分析の全ステップを実行して記事を生成"""

    print("📊 Step 1/4: マクロ・業界分析中...")
    macro_analysis = analyze_macro_and_industry(data)

    print("🏢 Step 2/4: 企業分析中...")
    company_analysis = analyze_company(data)

    print("🔭 Step 3/4: シナリオ生成中...")
    scenario_text, _ = generate_scenarios(data, macro_analysis, company_analysis)

    print("💰 Step 4/4: バリュエーション解説 & 記事執筆中...")
    valuation_commentary = generate_valuation_commentary(data, scenario_results, reverse_dcf_result)

    ticker_clean = data["ticker"].replace(".", "_")
    today = datetime.now().strftime("%Y%m%d")
    output_path = output_dir / f"{ticker_clean}_{today}_analysis.md"

    article = write_note_article(
        data=data,
        macro_analysis=macro_analysis,
        company_analysis=company_analysis,
        scenario_text=scenario_text,
        valuation_commentary=valuation_commentary,
        chart_paths=chart_paths,
        output_path=output_path,
    )

    return article
