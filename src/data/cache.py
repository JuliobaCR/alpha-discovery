"""
Caché local en disco (parquet).

Por qué parquet y no CSV: guarda los tipos de dato correctamente
(fechas, floats), pesa menos, y se lee mucho más rápido — importante
cuando vas a re-correr el experimento muchas veces sobre el mismo dataset.
"""

from pathlib import Path

import pandas as pd

from src.config import CACHE_DIR


def cache_path(ticker: str, source: str | None = None) -> Path:
    # source=None preserva el nombre de archivo original (TICKER.parquet).
    # Con source, cachea el crudo por fuente (TICKER__fuente.parquet) —
    # necesario para poder re-reconciliar sin re-descargar si se ajustan
    # los umbrales de reconciliación en config.py.
    if source is None:
        return CACHE_DIR / f"{ticker}.parquet"
    return CACHE_DIR / f"{ticker}__{source}.parquet"


def save_to_cache(ticker: str, df: pd.DataFrame, source: str | None = None) -> None:
    df.to_parquet(cache_path(ticker, source=source), index=False)


def load_from_cache(ticker: str, source: str | None = None) -> pd.DataFrame | None:
    path = cache_path(ticker, source=source)
    if path.exists():
        return pd.read_parquet(path)
    return None
