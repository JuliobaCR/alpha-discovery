"""
Prepara el panel OHLCV ancho que consumen los árboles de expresión, con
`high`/`low` ajustados por splits/dividendos para que sean consistentes
con `close_ajustado` (y por tanto con ATR, que necesita high/low/close en
la MISMA base — mezclar crudo con ajustado distorsionaría el True Range
alrededor de cualquier split).

El dataset de Fase 1 (UNIFIED_COLUMNS) trae `high`/`low` crudos de
yfinance y `close_ajustado` ya ajustado — se ajustan `high`/`low` por el
mismo factor que ya ajusta `close` -> `close_ajustado`. `open` se omite:
ningún indicador de la tabla de diseño lo necesita.
"""

import pandas as pd

from src.engine.backtest import prices_to_wide_multi
from src.engine.gp.indicators import atr_wilder

ATR_WINDOW = 14  # Wilder 1978 — ver Paper1_Repaso_Conceptos.md sección "Representación"


def build_adjusted_ohlcv_wide(prices_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    prices_df: dataset largo de Fase 1 (UNIFIED_COLUMNS).

    Devuelve {"close", "high", "low", "volume", "atr_14"} — paneles
    anchos (fecha × ticker), high/low ya ajustados, atr_14 precalculado
    UNA sola vez (no dentro de cada evaluación de árbol — ver primitives.py
    para por qué ATR es un terminal y no un primitivo de aridad 3).
    """
    df = prices_df.copy()
    factor = df["close_ajustado"] / df["close"]
    df["high"] = df["high"] * factor
    df["low"] = df["low"] * factor

    wide = prices_to_wide_multi(df, ["close_ajustado", "high", "low", "volumen"])

    close = wide["close_ajustado"]
    high = wide["high"]
    low = wide["low"]
    volume = wide["volumen"]

    atr_14 = atr_wilder(high, low, close, window=ATR_WINDOW)

    return {"close": close, "high": high, "low": low, "volume": volume, "atr_14": atr_14}


if __name__ == "__main__":
    # Prueba manual — un ticker con un "split" simulado: el precio crudo
    # salta de 200 a 100 en el día 3, pero close_ajustado sigue una línea
    # continua (100,101,102,...) como si el split ya estuviera reflejado
    # desde el principio. high/low crudos deben "encogerse" igual que
    # close al pasar por el ajuste, para quedar consistentes.
    from src.config import UNIFIED_COLUMNS

    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    close_crudo = [200.0, 202.0, 204.0, 102.0, 103.0]       # salta a la mitad en el día 4 (split 2:1)
    close_ajustado = [100.0, 101.0, 102.0, 102.0, 103.0]     # ya refleja el split desde el inicio
    high_crudo = [c + 4 for c in close_crudo]
    low_crudo = [c - 4 for c in close_crudo]

    df = pd.DataFrame({
        "ticker": "AAA",
        "fecha": dates,
        "open": close_crudo,
        "high": high_crudo,
        "low": low_crudo,
        "close": close_crudo,
        "volumen": 1_000_000,
        "close_ajustado": close_ajustado,
        "fuente": "sintetico",
    })[UNIFIED_COLUMNS]

    panels = build_adjusted_ohlcv_wide(df)
    print("close (=close_ajustado):")
    print(panels["close"]["AAA"].tolist())
    print("\nhigh ajustado (esperado: high_crudo * factor, factor=0.5 antes del split, 1.0 despues):")
    print(panels["high"]["AAA"].tolist())
    print("Esperado a mano:", [(c + 4) * (a / c) for c, a in zip(close_crudo, close_ajustado)])
    print("\natr_14 (últimos valores, debe ser finito una vez pasado el warm-up):")
    print(panels["atr_14"]["AAA"].tail(2).tolist())
