"""
Orquestador del pipeline completo: universo histórico -> descarga de ambas
fuentes -> caché -> reconciliación -> dataset final + reporte agregado.

Por qué ambas fuentes y no cascada de corto-circuito: reconcile_sources
necesita las dos fuentes crudas simultáneamente para poder compararlas y
producir las estadísticas de acuerdo entre fuentes que van directo a la
sección de datos del paper (ej. "97.8% coincidió dentro de 0.5%").
"""

import json
import time

import pandas as pd

from src import config
from src.data.cache import load_from_cache, save_to_cache
from src.data.fetch_constituents import get_historical_universe, to_tiingo_ticker, to_yfinance_ticker
from src.data.fetch_tiingo import fetch_tiingo
from src.data.fetch_yfinance import fetch_yfinance
from src.data.reconcile import reconcile_sources


def _fetch_and_cache_raw(ticker: str, source: str, fetch_fn, formatted_ticker: str, start: str, end: str) -> pd.DataFrame:
    """
    Descarga cruda de UNA fuente para un ticker, con caché por (ticker, fuente).

    Se cachea también el resultado vacío: el universo incluye a propósito
    muchos tickers deslistados que van a fallar en fuentes modernas (para
    evitar sesgo de supervivencia) — no cachear el vacío significaría
    reintentar la descarga de cientos de tickers en cada corrida, sin
    beneficio real (no es un fallo transitorio, es estructural). Si
    sospechas que un fallo puntual sí fue transitorio, borra manualmente
    el .parquet vacío correspondiente para forzar un reintento.
    """
    cached = load_from_cache(ticker, source=source)
    if cached is not None:
        return cached

    df = fetch_fn(formatted_ticker, start, end)

    # Normalizar la columna 'ticker' al ticker CANÓNICO (el del universo
    # histórico, ej. 'BRK.B'), no al formato específico de la fuente (ej.
    # 'BRK-B' de yfinance) — si no, reconcile_sources agrupa mal por
    # (ticker, fecha) porque cada fuente traería un string distinto para
    # el mismo activo.
    if not df.empty:
        df = df.copy()
        df["ticker"] = ticker

    save_to_cache(ticker, df, source=source)
    return df


def _build_aggregate_report(per_ticker_stats: list[dict], universe: set[str], covered: list[str], failed: list[str]) -> dict:
    # Los porcentajes de reconcile_sources ya están normalizados sobre el
    # total de CADA ticker — promediarlos directo pesaría igual a un
    # ticker con 4000 filas que a uno con 5. Se reponderan por
    # total_ticker_fechas antes de sumar.
    df_stats = pd.DataFrame(per_ticker_stats)
    total = int(df_stats["total_ticker_fechas"].sum()) if not df_stats.empty else 0

    def weighted_pct(col: str) -> float:
        if total == 0:
            return 0.0
        return round(100 * (df_stats[col] / 100 * df_stats["total_ticker_fechas"]).sum() / total, 2)

    return {
        "tickers_en_universo_historico": len(universe),
        "tickers_con_datos": len(covered),
        "tickers_sin_datos_en_ninguna_fuente": len(failed),
        "cobertura_pct": round(100 * len(covered) / len(universe), 2) if universe else 0.0,
        "total_ticker_fechas": total,
        "acuerdo_cercano_pct": weighted_pct("acuerdo_cercano_pct"),
        "acuerdo_flexible_pct": weighted_pct("acuerdo_flexible_pct"),
        "descartados_pct": weighted_pct("descartados_pct"),
        "solo_una_fuente": int(df_stats["solo_una_fuente"].sum()) if not df_stats.empty else 0,
        "tickers_fallidos": sorted(failed),
    }


def build_dataset(
    start: str = config.START_DATE,
    end: str = config.END_DATE,
    tickers: set[str] | None = None,
    force_refresh_universe: bool = False,
) -> dict:
    """
    tickers: override opcional del universo — útil para pruebas rápidas con
    un puñado de tickers antes de correr el universo histórico completo
    (puede tardar horas por el volumen de llamadas de red).
    """
    universe = tickers or get_historical_universe(start, end, force_refresh=force_refresh_universe)
    print(f"[build_dataset] Universo histórico: {len(universe)} tickers ({start} a {end})")

    reconciled_frames: list[pd.DataFrame] = []
    per_ticker_stats: list[dict] = []
    covered: list[str] = []
    failed: list[str] = []

    for i, ticker in enumerate(sorted(universe), start=1):
        print(f"[build_dataset] ({i}/{len(universe)}) {ticker}")
        try:
            df_yf = _fetch_and_cache_raw(ticker, "yfinance", fetch_yfinance, to_yfinance_ticker(ticker), start, end)
            df_tiingo = _fetch_and_cache_raw(ticker, "tiingo", fetch_tiingo, to_tiingo_ticker(ticker), start, end)
        except Exception as e:
            # Nunca debe tumbar el proceso completo por un ticker individual.
            print(f"[build_dataset] Error inesperado con {ticker}, se omite: {e}")
            failed.append(ticker)
            continue

        if df_yf.empty and df_tiingo.empty:
            failed.append(ticker)
            continue

        reconciled, stats = reconcile_sources({"yfinance": df_yf, "tiingo": df_tiingo})
        if reconciled.empty:
            failed.append(ticker)
            continue

        covered.append(ticker)
        reconciled_frames.append(reconciled)
        stats["ticker"] = ticker
        per_ticker_stats.append(stats)

        time.sleep(config.BUILD_DATASET_DELAY_SECONDS)

    dataset = pd.concat(reconciled_frames, ignore_index=True) if reconciled_frames else pd.DataFrame(columns=config.UNIFIED_COLUMNS)
    dataset.to_parquet(config.CACHE_DIR / "sp500_dataset.parquet", index=False)

    report = _build_aggregate_report(per_ticker_stats, universe, covered, failed)
    (config.CACHE_DIR / "sp500_dataset_report.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    # python -m src.data.build_dataset
    report = build_dataset()
    print("\n=== Reporte agregado ===")
    for k, v in report.items():
        if k != "tickers_fallidos":
            print(f"{k}: {v}")
