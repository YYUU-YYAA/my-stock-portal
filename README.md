# 株式分析ワンストップツール

Claude AI (Opus 4.7) + yfinance を使った個別株分析 → note記事自動生成システム

## セットアップ

```bash
cd stock-analyst
pip install -r requirements.txt
cp .env.example .env
# .env を編集して ANTHROPIC_API_KEY を設定
```

## 使い方

```bash
# 基本的な使い方 (フル分析 + 記事生成)
python main.py AAPL         # Apple
python main.py 7203.T       # トヨタ (東証)
python main.py NVDA         # NVIDIA
python main.py 6758.T       # ソニー

# オプション
python main.py AAPL --skip-charts     # チャート生成をスキップ
python main.py AAPL --skip-article    # AI分析をスキップ (数値計算のみ)
```

## 出力

`output/<ティッカー>_<日付>/` フォルダに生成されます:

```
output/AAPL_20240519/
├── 01_price_history.png       # 株価推移チャート
├── 02_financial_trend.png     # 財務推移チャート
├── 03_scenario_valuation.png  # シナリオ別目標株価
├── 04_kpi_radar.png           # KPIレーダー
└── AAPL_20240519_analysis.md  # note向け分析記事 (Markdown)
```

## 分析内容

### 定量分析
- **株価分析**: 5年推移、移動平均、52週高値・安値
- **DCF**: シナリオ別キャッシュフロー割引モデル
- **PER比較**: 予想EPS × 想定PER
- **逆算DCF**: 現在株価が織り込む期待成長率を算出

### AI分析 (Claude Opus 4.7)
1. マクロ環境・業界動向 (過去/現在/未来)
2. 企業分析 (ビジネスモデル、競争優位性、財務分析)
3. 将来シナリオ3本 (Bull/Base/Bear) + 転換トリガー
4. バリュエーション解説 + 投資判断
5. note向け記事執筆 (4,000〜6,000字)

## カスタマイズ

`main.py` の `scenarios` 変数でシナリオのパラメータを調整できます:

```python
scenarios = [
    {
        "name": "強気 (Bull)",
        "fcf_growth_rates": [0.25, 0.22, 0.18, 0.14, 0.10],
        "terminal_growth": 0.03,
        "wacc": 0.08,
        "forward_per": 35,
    },
    ...
]
```

## ティッカーの形式

| 市場 | 形式 | 例 |
|------|------|----|
| 米国株 | そのまま | `AAPL`, `NVDA`, `MSFT` |
| 東証一部 | `.T` を付加 | `7203.T` (トヨタ), `6758.T` (ソニー) |
| 名証 | `.N` を付加 | |
| 香港 | `.HK` を付加 | `0700.HK` (テンセント) |
