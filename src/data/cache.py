"""
Caché local en disco (parquet).

Por qué parquet y no CSV: guarda los tipos de dato correctamente
(fechas, floats), pesa menos, y se lee mucho más rápido — importante
cuando vas a re-correr el experimento muchas veces sobre el mismo dataset.
"""

import pandas as pd

from src.config import CACHE_DIR


def cache_path(ticker: str) -> "Path":
    return CACHE_DIR / f"{ticker}.parquet"


def save_to_cache(ticker: str, df: pd.DataFrame) -> None:
    df.to_parquet(cache_path(ticker), index=False)


def load_from_cache(ticker: str) -> pd.DataFrame | None:
    path = cache_path(ticker)
    if path.exists():
        return pd.read_parquet(path)
    return None
