"""バリュエーション計算モジュール - 複数の手法で株価の理論値を計算する"""

import numpy as np
from dataclasses import dataclass, field


@dataclass
class ValuationResult:
    method: str
    fair_value: float
    current_price: float
    upside_pct: float
    assumptions: dict = field(default_factory=dict)
    is_valid: bool = True
    error_msg: str = ""


def calc_dcf(
    current_price: float,
    fcf_per_share: float,
    growth_rate: float,
    terminal_growth: float,
    discount_rate: float,
    years: int = 10,
) -> ValuationResult:
    """DCF法: 将来FCFを割り引いて現在価値を計算"""
    if fcf_per_share <= 0:
        return ValuationResult("DCF", 0.0, current_price, 0.0, is_valid=False,
                               error_msg="FCFが負またはゼロのため計算不可")
    if discount_rate <= terminal_growth:
        return ValuationResult("DCF", 0.0, current_price, 0.0, is_valid=False,
                               error_msg="割引率 > 永続成長率 が必要")

    pv = sum(
        fcf_per_share * (1 + growth_rate) ** t / (1 + discount_rate) ** t
        for t in range(1, years + 1)
    )
    fcf_n = fcf_per_share * (1 + growth_rate) ** years
    terminal_value = fcf_n * (1 + terminal_growth) / (discount_rate - terminal_growth)
    pv_tv = terminal_value / (1 + discount_rate) ** years
    fair_value = pv + pv_tv

    return ValuationResult(
        method="DCF",
        fair_value=fair_value,
        current_price=current_price,
        upside_pct=(fair_value - current_price) / current_price * 100 if current_price > 0 else 0.0,
        assumptions={
            "成長率": f"{growth_rate*100:.1f}%",
            "永続成長率": f"{terminal_growth*100:.1f}%",
            "割引率": f"{discount_rate*100:.1f}%",
            "計算期間": f"{years}年",
        },
    )


def calc_per_val(
    current_price: float,
    eps: float,
    target_per: float,
) -> ValuationResult:
    """PER倍率法: 目標PERにEPSをかけて適正株価を算出"""
    if eps <= 0 or target_per <= 0:
        return ValuationResult("PER", 0.0, current_price, 0.0, is_valid=False,
                               error_msg="EPS または目標PERが無効")
    fair_value = eps * target_per
    return ValuationResult(
        method="PER",
        fair_value=fair_value,
        current_price=current_price,
        upside_pct=(fair_value - current_price) / current_price * 100 if current_price > 0 else 0.0,
        assumptions={"EPS": f"{eps:.2f}", "目標PER": f"{target_per:.1f}倍"},
    )


def calc_pbr_val(
    current_price: float,
    bvps: float,
    target_pbr: float,
) -> ValuationResult:
    """PBR倍率法: 目標PBRに1株純資産をかけて適正株価を算出"""
    if bvps <= 0 or target_pbr <= 0:
        return ValuationResult("PBR", 0.0, current_price, 0.0, is_valid=False,
                               error_msg="1株純資産 または目標PBRが無効")
    fair_value = bvps * target_pbr
    return ValuationResult(
        method="PBR",
        fair_value=fair_value,
        current_price=current_price,
        upside_pct=(fair_value - current_price) / current_price * 100 if current_price > 0 else 0.0,
        assumptions={"1株純資産": f"{bvps:.2f}", "目標PBR": f"{target_pbr:.2f}倍"},
    )


def calc_graham_val(
    current_price: float,
    eps: float,
    growth_rate_pct: float,
    bond_yield_pct: float = 4.4,
) -> ValuationResult:
    """グレアム式: V = EPS × (8.5 + 2g) × 4.4 / Y"""
    if eps <= 0:
        return ValuationResult("グレアム", 0.0, current_price, 0.0, is_valid=False,
                               error_msg="EPSが負のため計算不可")
    if bond_yield_pct <= 0:
        return ValuationResult("グレアム", 0.0, current_price, 0.0, is_valid=False,
                               error_msg="社債利回りが無効")
    fair_value = eps * (8.5 + 2 * growth_rate_pct) * 4.4 / bond_yield_pct
    return ValuationResult(
        method="グレアム",
        fair_value=fair_value,
        current_price=current_price,
        upside_pct=(fair_value - current_price) / current_price * 100 if current_price > 0 else 0.0,
        assumptions={
            "EPS": f"{eps:.2f}",
            "期待成長率": f"{growth_rate_pct:.1f}%",
            "社債利回り": f"{bond_yield_pct:.1f}%",
        },
    )


def calc_ddm_val(
    current_price: float,
    dps: float,
    div_growth: float,
    required_return: float,
) -> ValuationResult:
    """DDM（Gordon Growth Model）: P = D1 / (r - g)"""
    if dps <= 0:
        return ValuationResult("DDM", 0.0, current_price, 0.0, is_valid=False,
                               error_msg="配当なし（無配銘柄）")
    if required_return <= div_growth:
        return ValuationResult("DDM", 0.0, current_price, 0.0, is_valid=False,
                               error_msg="要求収益率 > 配当成長率 が必要")
    d1 = dps * (1 + div_growth)
    fair_value = d1 / (required_return - div_growth)
    return ValuationResult(
        method="DDM",
        fair_value=fair_value,
        current_price=current_price,
        upside_pct=(fair_value - current_price) / current_price * 100 if current_price > 0 else 0.0,
        assumptions={
            "1株配当": f"{dps:.2f}",
            "配当成長率": f"{div_growth*100:.1f}%",
            "要求収益率": f"{required_return*100:.1f}%",
        },
    )


def calc_ev_ebitda_val(
    current_price: float,
    ebitda: float,
    net_debt: float,
    shares_outstanding: float,
    target_multiple: float,
) -> ValuationResult:
    """EV/EBITDA法: EV = EBITDA × Multiple → 株価 = (EV - 純負債) / 株式数"""
    if ebitda <= 0 or shares_outstanding <= 0:
        return ValuationResult("EV/EBITDA", 0.0, current_price, 0.0, is_valid=False,
                               error_msg="EBITDAが負または株式数が不明")
    ev = ebitda * target_multiple
    equity_value = ev - net_debt
    fair_value = equity_value / shares_outstanding
    return ValuationResult(
        method="EV/EBITDA",
        fair_value=fair_value,
        current_price=current_price,
        upside_pct=(fair_value - current_price) / current_price * 100 if current_price > 0 else 0.0,
        assumptions={
            "EBITDA": f"{ebitda/1e9:.2f}B",
            "目標倍率": f"{target_multiple:.1f}倍",
            "純負債": f"{net_debt/1e9:.2f}B",
        },
    )


def dcf_sensitivity_matrix(
    fcf_per_share: float,
    growth_rates: list,
    discount_rates: list,
    terminal_growth: float = 0.025,
    years: int = 10,
) -> np.ndarray:
    """感度分析マトリクス: shape = (len(discount_rates), len(growth_rates))"""
    matrix = np.zeros((len(discount_rates), len(growth_rates)))
    for i, dr in enumerate(discount_rates):
        for j, gr in enumerate(growth_rates):
            res = calc_dcf(0.0, fcf_per_share, gr, terminal_growth, dr, years)
            matrix[i, j] = res.fair_value if res.is_valid else np.nan
    return matrix
