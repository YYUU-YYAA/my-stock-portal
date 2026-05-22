"""
チャート生成モジュール
matplotlib で株価・財務・バリュエーション図を出力する
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional


# --- フォント設定 (日本語対応) ---
import matplotlib.font_manager as fm
import sys

def _setup_font():
    """日本語フォントを設定する"""
    if sys.platform == "win32":
        candidates = ["MS Gothic", "Yu Gothic", "Meiryo", "IPAGothic"]
    else:
        candidates = ["Hiragino Sans", "Noto Sans CJK JP", "IPAGothic"]

    for font in candidates:
        if any(font.lower() in f.name.lower() for f in fm.fontManager.ttflist):
            plt.rcParams["font.family"] = font
            return
    # フォールバック: matplotlibデフォルト
    plt.rcParams["axes.unicode_minus"] = False

_setup_font()

COLORS = {
    "bull": "#2ecc71",
    "base": "#3498db",
    "bear": "#e74c3c",
    "price": "#2c3e50",
    "ma50": "#e67e22",
    "ma200": "#9b59b6",
    "positive": "#27ae60",
    "negative": "#c0392b",
    "neutral": "#7f8c8d",
}


def plot_price_history(data: dict, output_dir: Path) -> str:
    """株価推移チャートを生成"""
    price_history = data.get("price_history")
    if price_history is None or price_history.empty:
        return ""

    fig, ax = plt.subplots(figsize=(12, 5))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#f8f9fa")

    close = price_history["Close"]
    ax.plot(close.index, close, color=COLORS["price"], linewidth=1.5, label="株価")

    # 移動平均
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    ax.plot(close.index, ma50, color=COLORS["ma50"], linewidth=1.0, linestyle="--",
            alpha=0.8, label="50日MA")
    ax.plot(close.index, ma200, color=COLORS["ma200"], linewidth=1.0, linestyle="--",
            alpha=0.8, label="200日MA")

    # 陰影 (52週高値・安値)
    if data.get("week52_high") and data.get("week52_low"):
        ax.axhline(data["week52_high"], color="#e74c3c", linewidth=0.8,
                   linestyle=":", alpha=0.6, label=f"52週高値 {data['week52_high']:,.0f}")
        ax.axhline(data["week52_low"], color="#2ecc71", linewidth=0.8,
                   linestyle=":", alpha=0.6, label=f"52週安値 {data['week52_low']:,.0f}")

    ax.set_title(
        f"{data['company_name']} ({data['ticker']}) — 株価推移 (5年)",
        fontsize=13, fontweight="bold", pad=10
    )
    ax.set_ylabel(f"株価 ({data.get('currency','USD')})", fontsize=10)
    ax.legend(fontsize=8, loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y/%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    plt.xticks(rotation=30, ha="right", fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    path = output_dir / "01_price_history.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    return str(path)


def plot_financial_trend(data: dict, output_dir: Path) -> str:
    """売上・利益推移の棒グラフ"""
    annual = data.get("annual_financials")
    if not annual:
        return ""

    years = [r.get("year", "") for r in annual][::-1]
    revenues = [r.get("revenue", 0) or 0 for r in annual][::-1]
    operating_incomes = [r.get("operating_income", 0) or 0 for r in annual][::-1]
    net_incomes = [r.get("net_income", 0) or 0 for r in annual][::-1]

    # 単位スケール
    scale = 1e9
    unit = "十億"
    if max(revenues, default=0) > 1e12:
        scale = 1e12
        unit = "兆"

    revenues_s = [v / scale for v in revenues]
    oi_s = [v / scale for v in operating_incomes]
    ni_s = [v / scale for v in net_incomes]

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#f8f9fa")

    x = np.arange(len(years))
    width = 0.28

    ax.bar(x - width, revenues_s, width, label="売上高", color=COLORS["base"], alpha=0.85)
    ax.bar(x, oi_s, width, label="営業利益", color=COLORS["bull"], alpha=0.85)
    ax.bar(x + width, ni_s, width, label="純利益", color=COLORS["neutral"], alpha=0.85)

    ax.set_title(
        f"{data['company_name']} — 財務推移",
        fontsize=13, fontweight="bold", pad=10
    )
    ax.set_ylabel(f"金額 ({unit}{data.get('currency','USD')})", fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(years, fontsize=10)
    ax.legend(fontsize=9)
    ax.grid(True, axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    path = output_dir / "02_financial_trend.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    return str(path)


def plot_valuation_scenarios(
    data: dict,
    scenario_results: list[dict],
    output_dir: Path,
) -> str:
    """シナリオ別目標株価チャート"""
    current_price = data.get("current_price", 0)
    if not current_price or not scenario_results:
        return ""

    scenario_names = []
    dcf_prices = []
    per_prices = []

    for sc in scenario_results:
        scenario_names.append(sc["scenario"])
        vals = sc.get("valuations", {})
        dcf_prices.append(vals.get("dcf") or 0)
        per_prices.append(vals.get("per") or 0)

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#f8f9fa")

    x = np.arange(len(scenario_names))
    width = 0.35

    bars_dcf = ax.bar(x - width/2, dcf_prices, width, label="DCF法", color=COLORS["base"], alpha=0.85)
    bars_per = ax.bar(x + width/2, per_prices, width, label="PER法", color=COLORS["bull"], alpha=0.85)

    # 現在株価の水平線
    ax.axhline(current_price, color=COLORS["bear"], linewidth=2,
               linestyle="--", label=f"現在株価 {current_price:,.0f}", alpha=0.9)

    # 値ラベル
    for bar in bars_dcf:
        h = bar.get_height()
        if h > 0:
            ax.annotate(f"{h:,.0f}", xy=(bar.get_x() + bar.get_width() / 2, h),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", fontsize=8)
    for bar in bars_per:
        h = bar.get_height()
        if h > 0:
            ax.annotate(f"{h:,.0f}", xy=(bar.get_x() + bar.get_width() / 2, h),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", fontsize=8)

    ax.set_title(
        f"{data['company_name']} — シナリオ別目標株価",
        fontsize=13, fontweight="bold", pad=10
    )
    ax.set_ylabel(f"株価 ({data.get('currency','USD')})", fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(scenario_names, fontsize=10)
    ax.legend(fontsize=9)
    ax.grid(True, axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    path = output_dir / "03_scenario_valuation.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    return str(path)


def plot_kpi_radar(data: dict, output_dir: Path) -> str:
    """KPIレーダーチャート (収益性・成長性・財務健全性)"""
    metrics = {
        "ROE": data.get("roe") or 0,
        "営業\n利益率": data.get("operating_margin") or 0,
        "売上\n成長率": data.get("revenue_growth") or 0,
        "粗利\n益率": data.get("gross_margin") or 0,
        "FCF\n利益率": 0,
    }

    # FCF利益率を計算
    rev = None
    if data.get("annual_financials"):
        for row in data["annual_financials"]:
            if row.get("revenue") and row.get("fcf"):
                metrics["FCF\n利益率"] = row["fcf"] / row["revenue"]
                break

    categories = list(metrics.keys())
    values_raw = list(metrics.values())

    # 0〜1 にスケーリング (各指標の合理的な上限)
    upper_bounds = [0.40, 0.35, 0.40, 0.70, 0.25]
    values_norm = [
        max(0, min(1, v / ub)) if ub > 0 else 0
        for v, ub in zip(values_raw, upper_bounds)
    ]

    N = len(categories)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    values_norm += values_norm[:1]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#f8f9fa")

    ax.plot(angles, values_norm, color=COLORS["base"], linewidth=2)
    ax.fill(angles, values_norm, color=COLORS["base"], alpha=0.2)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=9)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["25%", "50%", "75%", "100%"], fontsize=7)
    ax.grid(True, alpha=0.4)
    ax.set_title(
        f"{data['company_name']} — KPIレーダー",
        fontsize=11, fontweight="bold", pad=15
    )

    plt.tight_layout()
    path = output_dir / "04_kpi_radar.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    return str(path)


def generate_all_charts(data: dict, scenario_results: list[dict], output_dir: Path) -> dict[str, str]:
    """全チャートを生成してパスの辞書を返す"""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}

    paths["price_history"] = plot_price_history(data, output_dir)
    paths["financial_trend"] = plot_financial_trend(data, output_dir)
    paths["valuation_scenarios"] = plot_valuation_scenarios(data, scenario_results, output_dir)
    paths["kpi_radar"] = plot_kpi_radar(data, output_dir)

    return {k: v for k, v in paths.items() if v}
