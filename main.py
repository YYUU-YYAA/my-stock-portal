"""
株式分析ワンストップツール
使い方: python main.py <ティッカー> [--skip-charts] [--skip-article]

例:
  python main.py AAPL            # Apple
  python main.py 7203.T          # トヨタ (東証)
  python main.py NVDA
  python main.py 6758.T          # ソニー
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

# Windows での UTF-8 出力を有効化
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# --- 環境変数ロード (.env があれば) ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fetcher import fetch_stock_data, format_financials_for_prompt
from models import build_scenario_valuations, reverse_dcf, summarize_valuations
from visualizer import generate_all_charts
from article_generator import run_full_analysis


def run(ticker: str, skip_charts: bool = False, skip_article: bool = False) -> None:
    print(f"\n{'='*60}")
    print(f"  株式分析: {ticker}")
    print(f"  実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    # --- 出力ディレクトリ ---
    ticker_clean = ticker.replace(".", "_")
    today = datetime.now().strftime("%Y%m%d")
    output_dir = Path("output") / f"{ticker_clean}_{today}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # ─────────────────────────────────────────
    # 1. データ取得
    # ─────────────────────────────────────────
    print("📡 財務データを取得中...")
    data = fetch_stock_data(ticker)

    if not data.get("company_name"):
        print(f"❌ 銘柄 '{ticker}' のデータが見つかりません。ティッカーを確認してください。")
        sys.exit(1)

    print(f"✅ 取得完了: {data['company_name']} ({data['ticker']})")
    print(f"   現在株価: {data.get('current_price', 'N/A')} {data.get('currency', '')}")
    print(f"   セクター: {data.get('sector', 'N/A')}")
    print()

    # ─────────────────────────────────────────
    # 2. バリュエーション計算
    # ─────────────────────────────────────────
    print("🔢 バリュエーションモデルを計算中...")

    # シナリオ定義（デフォルト）
    revenue_growth = data.get("revenue_growth") or 0.05
    scenarios = [
        {
            "name": "強気 (Bull)",
            "fcf_growth_rates": [
                max(revenue_growth * 2, 0.05),
                max(revenue_growth * 1.8, 0.05),
                max(revenue_growth * 1.5, 0.04),
                max(revenue_growth * 1.3, 0.03),
                max(revenue_growth * 1.1, 0.03),
            ],
            "terminal_growth": 0.03,
            "wacc": 0.08,
            "forward_per": (data.get("per") or 20) * 1.35,
        },
        {
            "name": "中立 (Base)",
            "fcf_growth_rates": [max(revenue_growth * 1.2, 0.03)] * 5,
            "terminal_growth": 0.02,
            "wacc": 0.09,
            "forward_per": data.get("per") or 20,
        },
        {
            "name": "弱気 (Bear)",
            "fcf_growth_rates": [max(revenue_growth * 0.3, -0.05)] * 5,
            "terminal_growth": 0.01,
            "wacc": 0.11,
            "forward_per": (data.get("per") or 20) * 0.65,
        },
    ]

    scenario_results = build_scenario_valuations(data, scenarios)

    # 逆算DCF
    current_price = data.get("current_price")
    fcf_base = data.get("free_cash_flow")
    if not fcf_base and data.get("annual_financials"):
        for row in data["annual_financials"]:
            if row.get("fcf") and row["fcf"] > 0:
                fcf_base = row["fcf"]
                break

    shares = (data.get("market_cap", 0) / current_price) if (current_price and data.get("market_cap")) else 1e9

    reverse_dcf_result = {}
    if current_price and fcf_base and fcf_base > 0 and shares > 0:
        reverse_dcf_result = reverse_dcf(
            current_price=current_price,
            fcf_base=fcf_base,
            terminal_growth=0.02,
            wacc=0.09,
            shares_outstanding=shares,
        )

    # バリュエーションサマリーを表示
    if scenario_results:
        print("\n" + summarize_valuations(scenario_results, current_price or 0))

    if reverse_dcf_result and "implied_growth_rate_pct" in reverse_dcf_result:
        print(f"逆算DCF 示唆成長率: {reverse_dcf_result['implied_growth_rate_pct']:.1f}%/年 "
              f"({reverse_dcf_result.get('interpretation','')})")
        print()

    # ─────────────────────────────────────────
    # 3. チャート生成
    # ─────────────────────────────────────────
    chart_paths = {}
    if not skip_charts:
        print("📈 チャートを生成中...")
        chart_paths = generate_all_charts(data, scenario_results, output_dir)
        for name, path in chart_paths.items():
            if path:
                print(f"  ✅ {name}: {path}")
        print()

    # ─────────────────────────────────────────
    # 4. AI分析 & 記事生成
    # ─────────────────────────────────────────
    if not skip_article:
        print("🤖 Claude AI による分析・記事生成を開始します...\n")
        article = run_full_analysis(
            data=data,
            scenario_results=scenario_results,
            reverse_dcf_result=reverse_dcf_result,
            chart_paths=chart_paths,
            output_dir=output_dir,
        )

    print(f"\n{'='*60}")
    print(f"  ✅ 分析完了!")
    print(f"  出力フォルダ: {output_dir.resolve()}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="株式分析ワンストップツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使い方:
  python main.py AAPL          # Apple
  python main.py 7203.T        # トヨタ (東証)
  python main.py NVDA
  python main.py 6758.T        # ソニー
  python main.py AAPL --skip-charts    # チャートなし
  python main.py AAPL --skip-article   # AI記事なし (数値計算のみ)
        """
    )
    parser.add_argument("ticker", help="銘柄コード (例: AAPL, 7203.T)")
    parser.add_argument("--skip-charts", action="store_true", help="チャート生成をスキップ")
    parser.add_argument("--skip-article", action="store_true", help="AI記事生成をスキップ")

    args = parser.parse_args()
    run(args.ticker, skip_charts=args.skip_charts, skip_article=args.skip_article)


if __name__ == "__main__":
    main()
