"""
バリュエーションモデル
DCF / PER比較 / 逆算DCF / EV-EBITDA を実装
"""

import numpy as np
from typing import Optional


def dcf_valuation(
    fcf_base: float,
    growth_rates: list[float],
    terminal_growth: float,
    wacc: float,
    shares_outstanding: float,
    net_debt: float = 0.0,
) -> dict:
    """
    DCF (割引キャッシュフロー) による株価算定

    Args:
        fcf_base: 基準年FCF (直近実績)
        growth_rates: 予測期間の年次成長率リスト (例: [0.15, 0.12, 0.10, 0.08, 0.06])
        terminal_growth: 永続成長率
        wacc: 加重平均資本コスト
        shares_outstanding: 発行済み株式数
        net_debt: 純有利子負債 (負の値 = ネットキャッシュ)

    Returns:
        dict: 試算結果
    """
    if shares_outstanding <= 0 or wacc <= terminal_growth:
        return {"error": "Invalid parameters"}

    # 予測期間のFCF
    projected_fcfs = []
    current_fcf = fcf_base
    for g in growth_rates:
        current_fcf *= (1 + g)
        projected_fcfs.append(current_fcf)

    # 各年のPV
    pv_fcfs = []
    for i, fcf in enumerate(projected_fcfs):
        pv = fcf / (1 + wacc) ** (i + 1)
        pv_fcfs.append(pv)

    # ターミナルバリュー (Gordon Growth Model)
    terminal_fcf = projected_fcfs[-1] * (1 + terminal_growth)
    terminal_value = terminal_fcf / (wacc - terminal_growth)
    pv_terminal = terminal_value / (1 + wacc) ** len(growth_rates)

    # エンタープライズバリュー
    enterprise_value = sum(pv_fcfs) + pv_terminal

    # エクイティバリュー
    equity_value = enterprise_value - net_debt
    intrinsic_value_per_share = equity_value / shares_outstanding

    return {
        "projected_fcfs": projected_fcfs,
        "pv_fcfs": pv_fcfs,
        "terminal_value": terminal_value,
        "pv_terminal": pv_terminal,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "intrinsic_value_per_share": intrinsic_value_per_share,
        "wacc": wacc,
        "terminal_growth": terminal_growth,
    }


def per_valuation(
    eps_forward: float,
    peer_per_list: list[float],
    historical_per_avg: Optional[float] = None,
) -> dict:
    """
    PER比較法による株価算定

    Args:
        eps_forward: 予想EPS
        peer_per_list: 同業他社のPERリスト
        historical_per_avg: 過去平均PER

    Returns:
        dict: PER別の推定株価
    """
    if not peer_per_list or eps_forward <= 0:
        return {"error": "Invalid parameters"}

    peer_per_avg = np.mean(peer_per_list)
    peer_per_median = np.median(peer_per_list)
    peer_per_low = np.percentile(peer_per_list, 25)
    peer_per_high = np.percentile(peer_per_list, 75)

    result = {
        "eps_forward": eps_forward,
        "peer_per_avg": peer_per_avg,
        "peer_per_median": peer_per_median,
        "price_at_peer_avg": eps_forward * peer_per_avg,
        "price_at_peer_median": eps_forward * peer_per_median,
        "price_at_peer_low": eps_forward * peer_per_low,
        "price_at_peer_high": eps_forward * peer_per_high,
    }

    if historical_per_avg:
        result["historical_per_avg"] = historical_per_avg
        result["price_at_historical_avg"] = eps_forward * historical_per_avg

    return result


def reverse_dcf(
    current_price: float,
    fcf_base: float,
    terminal_growth: float,
    wacc: float,
    shares_outstanding: float,
    net_debt: float = 0.0,
    forecast_years: int = 5,
) -> dict:
    """
    逆算DCF: 現在株価が織り込んでいる成長率を算出

    二分法で "implied growth rate" を求める
    """
    if shares_outstanding <= 0 or current_price <= 0:
        return {"error": "Invalid parameters"}

    target_equity = current_price * shares_outstanding

    def equity_from_growth(g: float) -> float:
        growth_rates = [g] * forecast_years
        res = dcf_valuation(
            fcf_base=fcf_base,
            growth_rates=growth_rates,
            terminal_growth=terminal_growth,
            wacc=wacc,
            shares_outstanding=shares_outstanding,
            net_debt=net_debt,
        )
        if "error" in res:
            return 0
        return res["equity_value"]

    # 二分法で implied growth rate を求める
    low_g, high_g = -0.5, 3.0
    implied_g = None
    for _ in range(100):
        mid_g = (low_g + high_g) / 2
        val = equity_from_growth(mid_g)
        if abs(val - target_equity) / target_equity < 1e-6:
            implied_g = mid_g
            break
        if val < target_equity:
            low_g = mid_g
        else:
            high_g = mid_g
    implied_g = implied_g or (low_g + high_g) / 2

    return {
        "current_price": current_price,
        "implied_growth_rate": implied_g,
        "implied_growth_rate_pct": implied_g * 100,
        "wacc": wacc,
        "terminal_growth": terminal_growth,
        "interpretation": _interpret_implied_growth(implied_g),
    }


def _interpret_implied_growth(g: float) -> str:
    if g > 0.30:
        return "市場は極めて高い成長を織り込んでいる（ハイリスク）"
    elif g > 0.20:
        return "市場は高い成長を織り込んでいる"
    elif g > 0.10:
        return "市場は中程度の成長を織り込んでいる"
    elif g > 0.05:
        return "市場は緩やかな成長を織り込んでいる"
    elif g > 0.00:
        return "市場は低成長を織り込んでいる"
    else:
        return "市場はマイナス成長（収縮）を織り込んでいる"


def ev_ebitda_valuation(
    ebitda: float,
    peer_ev_ebitda_list: list[float],
    net_debt: float,
    shares_outstanding: float,
) -> dict:
    """EV/EBITDA 比較法による株価算定"""
    if not peer_ev_ebitda_list or ebitda <= 0 or shares_outstanding <= 0:
        return {"error": "Invalid parameters"}

    avg_multiple = np.mean(peer_ev_ebitda_list)
    median_multiple = np.median(peer_ev_ebitda_list)

    implied_ev_avg = ebitda * avg_multiple
    implied_ev_median = ebitda * median_multiple

    price_avg = (implied_ev_avg - net_debt) / shares_outstanding
    price_median = (implied_ev_median - net_debt) / shares_outstanding

    return {
        "ebitda": ebitda,
        "avg_multiple": avg_multiple,
        "median_multiple": median_multiple,
        "price_at_avg": price_avg,
        "price_at_median": price_median,
    }


def build_scenario_valuations(
    data: dict,
    scenarios: list[dict],
) -> list[dict]:
    """
    シナリオ別バリュエーションを計算する

    scenarios: [
        {
            "name": "強気 (Bull)",
            "fcf_growth_rates": [0.20, 0.18, 0.15, 0.12, 0.10],
            "terminal_growth": 0.03,
            "wacc": 0.08,
            "forward_per": 30,
        },
        ...
    ]
    """
    fcf_base = None
    if data.get("free_cash_flow"):
        fcf_base = data["free_cash_flow"]
    elif data.get("annual_financials"):
        for row in data["annual_financials"]:
            if row.get("fcf"):
                fcf_base = row["fcf"]
                break

    shares = data.get("market_cap", 0) / data.get("current_price", 1) if data.get("current_price") else 1e9
    net_debt = 0  # 簡略化

    results = []
    for sc in scenarios:
        sc_result = {"scenario": sc["name"], "valuations": {}}

        # DCF
        if fcf_base and fcf_base > 0:
            dcf_res = dcf_valuation(
                fcf_base=fcf_base,
                growth_rates=sc.get("fcf_growth_rates", [0.05] * 5),
                terminal_growth=sc.get("terminal_growth", 0.02),
                wacc=sc.get("wacc", 0.09),
                shares_outstanding=shares,
                net_debt=net_debt,
            )
            if "error" not in dcf_res:
                sc_result["valuations"]["dcf"] = dcf_res["intrinsic_value_per_share"]

        # PER法
        eps = data.get("eps_forward") or data.get("eps_ttm")
        if eps and eps > 0:
            per_target = sc.get("forward_per")
            if per_target:
                sc_result["valuations"]["per"] = eps * per_target

        results.append(sc_result)

    return results


def summarize_valuations(scenario_results: list[dict], current_price: float) -> str:
    """バリュエーション結果をテキストサマリーに変換"""
    lines = ["【シナリオ別バリュエーション一覧】"]
    lines.append(f"現在株価: {current_price:,.2f}\n")

    for sc in scenario_results:
        lines.append(f"■ {sc['scenario']}")
        vals = sc.get("valuations", {})
        for method, price in vals.items():
            if price and price > 0:
                upside = (price / current_price - 1) * 100
                method_label = {"dcf": "DCF法", "per": "PER法", "ev_ebitda": "EV/EBITDA法"}.get(method, method)
                lines.append(f"  {method_label}: {price:,.0f}  (現在比 {upside:+.1f}%)")
        lines.append("")

    return "\n".join(lines)
