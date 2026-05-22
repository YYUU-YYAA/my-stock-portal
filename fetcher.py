"""
財務データ取得モジュール
yfinance を使って日米株の財務データ・ニュースを取得する
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional


def fetch_stock_data(ticker: str) -> dict:
    """
    銘柄コードから必要な情報をすべて取得する。
    日本株は '7203.T' のようにサフィックス付きで渡す。
    """
    stock = yf.Ticker(ticker)
    info = stock.info

    # --- 基本情報 ---
    company_name = info.get("longName") or info.get("shortName", ticker)
    currency = info.get("currency", "USD")
    country = info.get("country", "")
    industry = info.get("industry", "")
    sector = info.get("sector", "")
    description = info.get("longBusinessSummary", "")
    website = info.get("website", "")
    employees = info.get("fullTimeEmployees")

    # --- 株価履歴 (5年) ---
    price_history = stock.history(period="5y")
    price_history.index = pd.to_datetime(price_history.index)

    # 現在株価
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    if current_price is None and not price_history.empty:
        current_price = float(price_history["Close"].iloc[-1])

    # --- バリュエーション指標 ---
    per = info.get("trailingPE") or info.get("forwardPE")
    pbr = info.get("priceToBook")
    psr = info.get("priceToSalesTrailing12Months")
    ev_ebitda = info.get("enterpriseToEbitda")
    ev = info.get("enterpriseValue")
    market_cap = info.get("marketCap")
    beta = info.get("beta")

    # --- バリュエーション計算用追加フィールド ---
    shares_outstanding = info.get("sharesOutstanding") or 0
    book_value_per_share = info.get("bookValue") or 0
    dividend_per_share = info.get("dividendRate") or 0
    ebitda = info.get("ebitda") or 0
    total_debt = info.get("totalDebt") or 0
    total_cash = info.get("totalCash") or 0
    net_debt = total_debt - total_cash
    exchange = info.get("exchange", "")

    # --- 収益性指標 ---
    roe = info.get("returnOnEquity")
    roa = info.get("returnOnAssets")
    gross_margin = info.get("grossMargins")
    operating_margin = info.get("operatingMargins")
    profit_margin = info.get("profitMargins")

    # --- 成長性指標 ---
    revenue_growth = info.get("revenueGrowth")
    earnings_growth = info.get("earningsGrowth")
    earnings_quarterly_growth = info.get("earningsQuarterlyGrowth")

    # --- 財務健全性 ---
    debt_to_equity = info.get("debtToEquity")
    current_ratio = info.get("currentRatio")
    quick_ratio = info.get("quickRatio")
    free_cash_flow = info.get("freeCashflow")
    dividend_yield = info.get("dividendYield")
    payout_ratio = info.get("payoutRatio")

    # --- 財務諸表 (年次) ---
    try:
        income_stmt = stock.financials  # 年次損益計算書
        balance_sheet = stock.balance_sheet
        cash_flow = stock.cashflow
    except Exception:
        income_stmt = pd.DataFrame()
        balance_sheet = pd.DataFrame()
        cash_flow = pd.DataFrame()

    # --- 四半期財務諸表 ---
    try:
        quarterly_income = stock.quarterly_financials
    except Exception:
        quarterly_income = pd.DataFrame()

    # --- アナリスト予想 ---
    try:
        recommendations = stock.recommendations
        analyst_price_targets = {
            "current": info.get("currentPrice"),
            "low": info.get("targetLowPrice"),
            "mean": info.get("targetMeanPrice"),
            "high": info.get("targetHighPrice"),
            "num_analysts": info.get("numberOfAnalystOpinions"),
            "recommendation": info.get("recommendationKey"),
        }
    except Exception:
        recommendations = pd.DataFrame()
        analyst_price_targets = {}

    # --- ニュース ---
    try:
        news = stock.news[:10] if stock.news else []
    except Exception:
        news = []

    # --- 52週高値・安値 ---
    week52_high = info.get("fiftyTwoWeekHigh")
    week52_low = info.get("fiftyTwoWeekLow")
    day50_ma = info.get("fiftyDayAverage")
    day200_ma = info.get("twoHundredDayAverage")

    # --- EPS情報 ---
    eps_ttm = info.get("trailingEps")
    eps_forward = info.get("forwardEps")

    # --- 収益の時系列を整理 ---
    annual_financials = _extract_annual_financials(income_stmt, cash_flow, balance_sheet)

    return {
        # 基本
        "ticker": ticker,
        "company_name": company_name,
        "currency": currency,
        "country": country,
        "industry": industry,
        "sector": sector,
        "description": description,
        "website": website,
        "employees": employees,
        # 株価
        "current_price": current_price,
        "price_history": price_history,
        "week52_high": week52_high,
        "week52_low": week52_low,
        "day50_ma": day50_ma,
        "day200_ma": day200_ma,
        # バリュエーション
        "per": per,
        "pbr": pbr,
        "psr": psr,
        "ev_ebitda": ev_ebitda,
        "ev": ev,
        "market_cap": market_cap,
        "beta": beta,
        # 収益性
        "roe": roe,
        "roa": roa,
        "gross_margin": gross_margin,
        "operating_margin": operating_margin,
        "profit_margin": profit_margin,
        # 成長性
        "revenue_growth": revenue_growth,
        "earnings_growth": earnings_growth,
        # 財務健全性
        "debt_to_equity": debt_to_equity,
        "current_ratio": current_ratio,
        "free_cash_flow": free_cash_flow,
        "dividend_yield": dividend_yield,
        "payout_ratio": payout_ratio,
        # EPS
        "eps_ttm": eps_ttm,
        "eps_forward": eps_forward,
        # 財務諸表
        "income_stmt": income_stmt,
        "balance_sheet": balance_sheet,
        "cash_flow": cash_flow,
        "quarterly_income": quarterly_income,
        # アナリスト
        "analyst_price_targets": analyst_price_targets,
        "recommendations": recommendations,
        # ニュース
        "news": news,
        # 整理済み年次データ
        "annual_financials": annual_financials,
        # バリュエーション計算用
        "shares_outstanding": shares_outstanding,
        "book_value_per_share": book_value_per_share,
        "dividend_per_share": dividend_per_share,
        "ebitda": ebitda,
        "net_debt": net_debt,
        "exchange": exchange,
    }


def _extract_annual_financials(
    income_stmt: pd.DataFrame,
    cash_flow: pd.DataFrame,
    balance_sheet: pd.DataFrame,
) -> list[dict]:
    """財務諸表から年次サマリーを抽出する"""
    result = []

    if income_stmt.empty:
        return result

    for col in income_stmt.columns[:4]:  # 直近4年
        year = str(col)[:4] if hasattr(col, '__str__') else str(col)
        row = {"year": year}

        # 損益計算書
        for key, label in [
            ("Total Revenue", "revenue"),
            ("Gross Profit", "gross_profit"),
            ("Operating Income", "operating_income"),
            ("Net Income", "net_income"),
            ("EBITDA", "ebitda"),
        ]:
            try:
                val = income_stmt.loc[key, col] if key in income_stmt.index else None
                row[label] = float(val) if val is not None and not pd.isna(val) else None
            except Exception:
                row[label] = None

        # キャッシュフロー計算書
        if not cash_flow.empty and col in cash_flow.columns:
            for key, label in [
                ("Free Cash Flow", "fcf"),
                ("Operating Cash Flow", "operating_cf"),
                ("Capital Expenditure", "capex"),
            ]:
                try:
                    val = cash_flow.loc[key, col] if key in cash_flow.index else None
                    row[label] = float(val) if val is not None and not pd.isna(val) else None
                except Exception:
                    row[label] = None

        # 貸借対照表
        if not balance_sheet.empty and col in balance_sheet.columns:
            for key, label in [
                ("Total Assets", "total_assets"),
                ("Total Debt", "total_debt"),
                ("Stockholders Equity", "equity"),
            ]:
                try:
                    val = balance_sheet.loc[key, col] if key in balance_sheet.index else None
                    row[label] = float(val) if val is not None and not pd.isna(val) else None
                except Exception:
                    row[label] = None

        result.append(row)

    return result


def format_financials_for_prompt(data: dict) -> str:
    """Claude への入力用に財務データをテキスト化する"""
    lines = []

    # 基本情報
    lines.append(f"=== {data['company_name']} ({data['ticker']}) ===")
    lines.append(f"セクター: {data['sector']} / 業種: {data['industry']}")
    lines.append(f"国: {data['country']} / 通貨: {data['currency']}")
    if data.get("employees"):
        lines.append(f"従業員数: {data['employees']:,}人")
    lines.append("")

    # 株価情報
    lines.append("【株価情報】")
    if data.get("current_price"):
        lines.append(f"現在株価: {data['current_price']:,.2f} {data['currency']}")
    if data.get("week52_high") and data.get("week52_low"):
        lines.append(f"52週高値: {data['week52_high']:,.2f} / 低値: {data['week52_low']:,.2f}")
    if data.get("market_cap"):
        mc = data["market_cap"]
        if mc >= 1e12:
            lines.append(f"時価総額: {mc/1e12:.2f}兆{data['currency']}")
        elif mc >= 1e9:
            lines.append(f"時価総額: {mc/1e9:.2f}十億{data['currency']}")
        else:
            lines.append(f"時価総額: {mc:,.0f} {data['currency']}")
    lines.append("")

    # バリュエーション
    lines.append("【バリュエーション】")
    for label, val in [
        ("PER (実績)", data.get("per")),
        ("PBR", data.get("pbr")),
        ("PSR", data.get("psr")),
        ("EV/EBITDA", data.get("ev_ebitda")),
        ("ベータ", data.get("beta")),
    ]:
        if val is not None:
            lines.append(f"{label}: {val:.2f}")
    lines.append("")

    # 収益性
    lines.append("【収益性指標】")
    for label, val in [
        ("ROE", data.get("roe")),
        ("ROA", data.get("roa")),
        ("粗利益率", data.get("gross_margin")),
        ("営業利益率", data.get("operating_margin")),
        ("純利益率", data.get("profit_margin")),
    ]:
        if val is not None:
            lines.append(f"{label}: {val*100:.1f}%")
    lines.append("")

    # 成長性
    lines.append("【成長性】")
    for label, val in [
        ("売上成長率 (YoY)", data.get("revenue_growth")),
        ("利益成長率 (YoY)", data.get("earnings_growth")),
    ]:
        if val is not None:
            lines.append(f"{label}: {val*100:.1f}%")
    lines.append("")

    # 財務健全性
    lines.append("【財務健全性】")
    for label, val in [
        ("有利子負債/自己資本", data.get("debt_to_equity")),
        ("流動比率", data.get("current_ratio")),
        ("配当利回り", data.get("dividend_yield")),
    ]:
        if val is not None:
            if label == "配当利回り":
                lines.append(f"{label}: {val*100:.2f}%")
            else:
                lines.append(f"{label}: {val:.2f}")
    if data.get("free_cash_flow"):
        fcf = data["free_cash_flow"]
        lines.append(f"フリーキャッシュフロー: {fcf/1e9:.2f}十億{data['currency']}")
    lines.append("")

    # 年次財務推移
    if data.get("annual_financials"):
        lines.append("【年次財務推移】")
        for row in data["annual_financials"]:
            yr = row.get("year", "")
            rev = row.get("revenue")
            oi = row.get("operating_income")
            ni = row.get("net_income")
            fcf = row.get("fcf")
            parts = []
            if rev:
                parts.append(f"売上={rev/1e9:.1f}B")
            if oi:
                parts.append(f"営業利益={oi/1e9:.1f}B")
            if ni:
                parts.append(f"純利益={ni/1e9:.1f}B")
            if fcf:
                parts.append(f"FCF={fcf/1e9:.1f}B")
            if parts:
                lines.append(f"  {yr}: {', '.join(parts)}")
        lines.append("")

    # アナリスト予想
    apt = data.get("analyst_price_targets", {})
    if apt.get("mean"):
        lines.append("【アナリスト目標株価】")
        lines.append(f"平均目標株価: {apt['mean']:,.2f} (Low: {apt.get('low','N/A')} / High: {apt.get('high','N/A')})")
        if apt.get("num_analysts"):
            lines.append(f"アナリスト数: {apt['num_analysts']}人 / レーティング: {apt.get('recommendation','N/A')}")
        lines.append("")

    # ニュース
    if data.get("news"):
        lines.append("【最近のニュース (最大10件)】")
        for n in data["news"][:10]:
            title = n.get("title", "")
            if title:
                lines.append(f"- {title}")
        lines.append("")

    return "\n".join(lines)
