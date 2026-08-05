"""
======================================================================
 SCREENER — VERSIÓN AUTOMATIZADA (genera data.json para el dashboard)
======================================================================
Este script es una adaptación de screener_oportunidades.py pensada
para correr sola, todos los días, dentro de GitHub Actions.

En vez de imprimir una tabla en consola, guarda TODOS los resultados
en data.json, que es el archivo que lee index.html (el dashboard).

No necesitas correr esto manualmente en tu compu salvo para probar
que funciona. GitHub Actions lo ejecuta solo según el horario definido
en .github/workflows/update.yml
======================================================================
"""

import json
import time
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

# ======================================================================
# 1. CONFIGURACIÓN — MODIFICA AQUÍ
# ======================================================================

# Respaldo fijo por si falla la descarga dinámica del S&P 500
SP500_BACKUP = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JPM", "V", "MA",
    "UNH", "HD", "PG", "KO", "PEP", "XOM", "CVX", "ABBV", "MRK", "PFE",
    "COST", "WMT", "DIS", "NFLX", "ADBE", "CRM", "INTC", "AMD", "QCOM", "TXN",
]

# ADRs mexicanos / latam + emisoras BMV directas (se mantienen a mano,
# no existe una fuente pública tan confiable para automatizar esta lista)
ADRS_LATAM = [
    "AMX", "CX", "KOF", "FMX", "VIST",
    "GFNORTEO.MX", "WALMEX.MX", "BIMBOA.MX", "GRUMAB.MX", "GAPB.MX",
    "ASURB.MX", "ORBIA.MX", "ALFAA.MX", "PE&OLES.MX",
]


def get_sp500_tickers() -> list:
    """Obtiene la lista ACTUAL y COMPLETA del S&P 500 desde Wikipedia.
    Si falla (sin internet, cambio de formato de la página, etc.),
    usa el respaldo fijo de arriba para que el script no truene."""
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)
        tickers = tables[0]["Symbol"].tolist()
        # yfinance usa "-" en vez de "." para tickers como BRK.B
        tickers = [t.replace(".", "-") for t in tickers]
        print(f"✅ S&P 500 obtenido dinámicamente: {len(tickers)} tickers")
        return tickers
    except Exception as e:
        print(f"⚠️ No se pudo obtener el S&P 500 dinámicamente ({e}). Usando respaldo fijo.")
        return SP500_BACKUP


TICKERS_UNIVERSE = get_sp500_tickers() + ADRS_LATAM

THRESHOLDS = {
    "peg_max": 1.5,
    "pe_forward_max": 30,
    "ev_ebitda_max": 15,
    "roe_min": 0.12,
    "roe_ideal": 0.15,
    "debt_ebitda_max": 3.0,
    "fcf_yield_min": 0.03,
    "drawdown_min": -0.45,
    "drawdown_max": -0.15,
    "rev_growth_min": 0.03,
}

REQUEST_PAUSE = 0.4
OUTPUT_JSON = "data.json"
OUTPUT_CSV = "screener_resultados_completos.csv"


# ======================================================================
# 2. OBTENCIÓN DE DATOS
# ======================================================================

def get_stock_data(ticker: str) -> dict | None:
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not info or price is None:
            return None
        hist = tk.history(period="5y", interval="1mo")
        return {"ticker": ticker, "info": info, "hist": hist, "tk": tk}
    except Exception as e:
        print(f"  ⚠️  Error obteniendo datos de {ticker}: {e}")
        return None


def calculate_eps_cagr_5y(tk: yf.Ticker) -> float:
    try:
        fin = tk.income_stmt
        if fin is None or fin.empty:
            return np.nan
        row = None
        for name in ("Diluted EPS", "Basic EPS"):
            if name in fin.index:
                row = fin.loc[name].dropna()
                break
        if row is None or len(row) < 2:
            return np.nan
        row = row.sort_index()
        eps_start, eps_end = row.iloc[0], row.iloc[-1]
        years = len(row) - 1
        if eps_start is None or eps_start <= 0 or years == 0:
            return np.nan
        return (eps_end / eps_start) ** (1 / years) - 1
    except Exception:
        return np.nan


# ======================================================================
# 3. MÉTRICAS
# ======================================================================

def calculate_metrics(data: dict) -> dict:
    info = data["info"]
    hist = data["hist"]
    ticker = data["ticker"]

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    high_52w = info.get("fiftyTwoWeekHigh")
    low_52w = info.get("fiftyTwoWeekLow")
    drawdown = (price - high_52w) / high_52w if price and high_52w else np.nan

    mom_1m, mom_3m = np.nan, np.nan
    if hist is not None and not hist.empty:
        closes = hist["Close"].dropna()
        if len(closes) >= 2:
            mom_1m = closes.iloc[-1] / closes.iloc[-2] - 1
        if len(closes) >= 4:
            mom_3m = closes.iloc[-1] / closes.iloc[-4] - 1

    total_debt = info.get("totalDebt")
    ebitda = info.get("ebitda")
    debt_ebitda = (
        total_debt / ebitda if total_debt and ebitda and ebitda > 0 else np.nan
    )

    fcf = info.get("freeCashflow")
    mcap = info.get("marketCap")
    fcf_yield = (fcf / mcap) if fcf and mcap else np.nan

    return {
        "ticker": ticker,
        "nombre": info.get("shortName", ticker),
        "sector": info.get("sector", "N/D"),
        "precio": price,
        "max_52w": high_52w,
        "min_52w": low_52w,
        "drawdown_52w": drawdown,
        "pe_forward": info.get("forwardPE"),
        "peg": info.get("pegRatio") or info.get("trailingPegRatio"),
        "ev_ebitda": info.get("enterpriseToEbitda"),
        "pb": info.get("priceToBook"),
        "roe": info.get("returnOnEquity"),
        "rev_growth_yoy": info.get("revenueGrowth"),
        "eps_cagr_5y": calculate_eps_cagr_5y(data["tk"]),
        "debt_ebitda": debt_ebitda,
        "fcf_yield": fcf_yield,
        "mom_1m": mom_1m,
        "mom_3m": mom_3m,
        "profit_margin": info.get("profitMargins"),
    }


# ======================================================================
# 4. SCORING
# ======================================================================

def score_value(m, th):
    score = 0.0
    pe = m["pe_forward"]
    if pd.notna(pe) and pe > 0:
        if pe <= 15:
            score += 7
        elif pe <= th["pe_forward_max"]:
            score += 7 * (1 - (pe - 15) / (th["pe_forward_max"] - 15))
    peg = m["peg"]
    if pd.notna(peg) and peg > 0:
        if peg <= 1.0:
            score += 7
        elif peg <= th["peg_max"]:
            score += 7 * (1 - (peg - 1.0) / (th["peg_max"] - 1.0))
    ev = m["ev_ebitda"]
    if pd.notna(ev) and ev > 0:
        if ev <= 8:
            score += 6
        elif ev <= th["ev_ebitda_max"]:
            score += 6 * (1 - (ev - 8) / (th["ev_ebitda_max"] - 8))
    fcf_y = m["fcf_yield"]
    if pd.notna(fcf_y):
        if fcf_y >= 0.08:
            score += 5
        elif fcf_y >= th["fcf_yield_min"]:
            score += 5 * ((fcf_y - th["fcf_yield_min"]) / (0.08 - th["fcf_yield_min"]))
    return min(score, 25.0)


def score_growth(m, th):
    score = 0.0
    rg = m["rev_growth_yoy"]
    if pd.notna(rg):
        if rg >= 0.15:
            score += 12
        elif rg >= th["rev_growth_min"]:
            score += 12 * ((rg - th["rev_growth_min"]) / (0.15 - th["rev_growth_min"]))
    eps_cagr = m["eps_cagr_5y"]
    if pd.notna(eps_cagr):
        if eps_cagr >= 0.15:
            score += 13
        elif eps_cagr > 0:
            score += 13 * (eps_cagr / 0.15)
    return min(score, 25.0)


def score_quality(m, th):
    score = 0.0
    roe = m["roe"]
    if pd.notna(roe):
        if roe >= th["roe_ideal"]:
            score += 10
        elif roe >= th["roe_min"]:
            score += 10 * ((roe - th["roe_min"]) / (th["roe_ideal"] - th["roe_min"]))
    de = m["debt_ebitda"]
    if pd.notna(de):
        if de <= 1.0:
            score += 8
        elif de <= th["debt_ebitda_max"]:
            score += 8 * (1 - (de - 1.0) / (th["debt_ebitda_max"] - 1.0))
    else:
        score += 4
    fcf_y = m["fcf_yield"]
    if pd.notna(fcf_y) and fcf_y > 0:
        score += 7
    return min(score, 25.0)


def score_momentum(m, th):
    score = 0.0
    in_zone = False
    dd = m["drawdown_52w"]
    if pd.notna(dd):
        if th["drawdown_min"] <= dd <= th["drawdown_max"]:
            in_zone = True
            score += 15
        elif dd > th["drawdown_max"]:
            score += 5
        else:
            score += 3
    if pd.notna(m["mom_1m"]) and m["mom_1m"] > 0:
        score += 5
    if pd.notna(m["mom_3m"]) and m["mom_3m"] > -0.05:
        score += 5
    return min(score, 25.0), in_zone


def calculate_composite_score(m, th):
    v = score_value(m, th)
    g = score_growth(m, th)
    q = score_quality(m, th)
    mo, in_zone = score_momentum(m, th)
    base = v + g + q + mo
    bonus = 10 if (in_zone and q >= 18 and v >= 15) else 0
    total = min(base + bonus, 100)
    return {
        "value_score": round(v, 1),
        "growth_score": round(g, 1),
        "quality_score": round(q, 1),
        "momentum_score": round(mo, 1),
        "bonus": bonus,
        "composite_score": round(total, 1),
    }


def generate_reason(m, scores):
    reasons = []
    dd = m["drawdown_52w"]
    if pd.notna(dd) and -0.45 <= dd <= -0.15:
        reasons.append(f"Cae {abs(dd) * 100:.0f}% desde máx. 52s")
    if pd.notna(m["roe"]) and m["roe"] >= 0.15:
        reasons.append(f"ROE sólido ({m['roe'] * 100:.1f}%)")
    if pd.notna(m["peg"]) and 0 < m["peg"] < 1.5:
        reasons.append(f"PEG atractivo ({m['peg']:.2f})")
    if pd.notna(m["rev_growth_yoy"]) and m["rev_growth_yoy"] > 0.08:
        reasons.append(f"crece {m['rev_growth_yoy'] * 100:.1f}% YoY")
    if scores["bonus"] > 0:
        reasons.append("caída + fundamentales de calidad (bono)")
    if not reasons:
        reasons.append("cumple criterios base del screener")
    return "; ".join(reasons[:3]).capitalize()


# ======================================================================
# 5. PIPELINE PRINCIPAL
# ======================================================================

def run_screener():
    rows = []
    for i, ticker in enumerate(TICKERS_UNIVERSE, 1):
        print(f"[{i}/{len(TICKERS_UNIVERSE)}] Procesando {ticker}...")
        data = get_stock_data(ticker)
        if data is None:
            print(f"  ⚠️  Sin datos suficientes para {ticker}, se omite.")
            continue
        try:
            m = calculate_metrics(data)
            s = calculate_composite_score(m, THRESHOLDS)
            m.update(s)
            m["razon"] = generate_reason(m, s)
            rows.append(m)
        except Exception as e:
            print(f"  ⚠️  Error calculando métricas de {ticker}: {e}")
        time.sleep(REQUEST_PAUSE)
    return pd.DataFrame(rows)


def clean_for_json(df: pd.DataFrame) -> list:
    """Convierte NaN/NaT a None para que sea JSON válido."""
    import math
    records = df.to_dict(orient="records")
    for row in records:
        for k, v in row.items():
            if isinstance(v, float) and math.isnan(v):
                row[k] = None
    return records


if __name__ == "__main__":
    print("=" * 70)
    print(" SCREENER AUTOMATIZADO — generando data.json")
    print("=" * 70)

    df = run_screener()

    if df.empty:
        print("No se obtuvieron datos. No se actualiza data.json.")
    else:
        df = df.sort_values("composite_score", ascending=False)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data": clean_for_json(df),
        }
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=None)
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"\n✅ {OUTPUT_JSON} y {OUTPUT_CSV} generados con {len(df)} tickers.")
