"""
Fórmulas de indicadores técnicos, sobre paneles anchos (fecha × ticker) —
funciones puras, sin DEAP, sin fechas de calendario más allá del rolling
que cada indicador necesita. Verificables a mano, igual que metrics.py.

Todas preservan la forma (fecha × ticker) de sus entradas — elementwise o
rolling/ewm por columna — para que cualquier composición de estos
indicadores dentro de un árbol siga siendo un panel válido para
evaluate_tree.py / compute_objectives.
"""

import numpy as np
import pandas as pd

PROTECTED_DIV_EPS = 1e-9


def ema(x: pd.DataFrame, span: int) -> pd.DataFrame:
    """Media móvil exponencial — span en días de trading."""
    return x.ewm(span=span, adjust=False).mean()


def sma(x: pd.DataFrame, window: int) -> pd.DataFrame:
    """Media móvil simple (ts_mean del documento de diseño)."""
    return x.rolling(window).mean()


def ts_std(x: pd.DataFrame, window: int) -> pd.DataFrame:
    """Desviación estándar rodante — mide volatilidad de NIVELES de una
    serie tipo-precio (distinto del cálculo de volatilidad de RETORNOS
    que hace weights.py para dimensionar posiciones)."""
    return x.rolling(window).std()


def rsi_wilder(close: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """
    RSI de Wilder (1978), normalizado a [0,1] (RSI/100) para que combine
    en la misma escala que rank_cross_sectional dentro de la categoría
    Bounded. Suavizado de Wilder = EMA con alpha=1/window (no una SMA
    simple de ganancias/pérdidas, esa es la definición original exacta).
    """
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()

    rs = avg_gain / avg_loss  # avg_loss=0 -> rs=inf -> rsi=100, manejado por aritmética de floats sin excepción
    rsi = 100 - 100 / (1 + rs)
    return rsi / 100


def atr_wilder(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """
    Average True Range de Wilder (1978). True Range = el mayor entre
    (high-low), |high-close_previo|, |low-close_previo| — captura gaps
    entre sesiones, no solo el rango intradía. Suavizado de Wilder (EMA
    con alpha=1/window), igual que RSI.
    """
    prev_close = close.shift(1)
    tr = np.maximum(high - low, np.maximum((high - prev_close).abs(), (low - prev_close).abs()))
    return tr.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()


def rank_cross_sectional(x: pd.DataFrame) -> pd.DataFrame:
    """
    Rank percentil transversal por fecha (0,1] — el puente hacia Bounded.
    NaN se propaga como NaN (pandas excluye NaN del ranking por defecto),
    consistente con "sin dato -> sin señal" en el resto del motor.
    """
    return x.rank(axis=1, pct=True)


def protected_div(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """
    a / b, con NaN (no un valor centinela) donde |b| < eps — consistente
    con cómo weights.py ya trata NaN como "sin señal", en vez de inyectar
    un valor ficticio que un árbol evolutivo podría aprender a explotar.
    """
    result = a / b
    return result.mask(b.abs() < PROTECTED_DIV_EPS)


if __name__ == "__main__":
    # Casos hand-verificables.
    dates = pd.date_range("2024-01-01", periods=6, freq="D")

    # EMA span=2: alpha=2/3. Serie [10,12,14,...] -> ema0=10 (primer valor
    # = el dato, adjust=False), ema1 = 12*(2/3)+10*(1/3) = 11.333...
    x = pd.DataFrame({"A": [10.0, 12.0, 14.0, 16.0, 18.0, 20.0]}, index=dates)
    e = ema(x, span=2)
    print("EMA span=2, primeros 2 valores (esperado 10.0, 11.3333):")
    print(e["A"].iloc[:2].tolist())

    # SMA ventana 2 sobre la misma serie: sma[1] = (10+12)/2 = 11.0
    s = sma(x, window=2)
    print("SMA ventana=2, segundo valor (esperado 11.0):", s["A"].iloc[1])

    # RSI: precios siempre subiendo -> pérdida siempre 0 -> RSI debe
    # converger a 1.0 (100/100) tras el warm-up.
    up = pd.DataFrame({"A": [10.0 + i for i in range(30)]}, index=pd.date_range("2024-01-01", periods=30))
    r_up = rsi_wilder(up, window=14)
    print("RSI (serie siempre subiendo, esperado ~1.0):", r_up["A"].iloc[-1])

    # RSI: precios siempre bajando -> ganancia siempre 0 -> RSI debe
    # converger a 0.0.
    down = pd.DataFrame({"A": [50.0 - i for i in range(30)]}, index=pd.date_range("2024-01-01", periods=30))
    r_down = rsi_wilder(down, window=14)
    print("RSI (serie siempre bajando, esperado ~0.0):", r_down["A"].iloc[-1])

    # ATR: high=low+2 constante, close=low+1 constante -> TR = high-low = 2
    # todos los días (sin gaps) -> ATR converge a 2.0.
    low_s = pd.DataFrame({"A": [100.0 + i for i in range(30)]}, index=pd.date_range("2024-01-01", periods=30))
    high_s = low_s + 2.0
    close_s = low_s + 1.0
    a = atr_wilder(high_s, low_s, close_s, window=14)
    print("ATR (rango constante=2, esperado ~2.0):", a["A"].iloc[-1])

    # rank_cross_sectional: día con A=1,B=3,C=2 -> percentiles 1/3,3/3,2/3
    cs = pd.DataFrame({"A": [1.0], "B": [3.0], "C": [2.0]})
    print("Rank percentil (esperado A=0.333, B=1.0, C=0.667):", rank_cross_sectional(cs).iloc[0].to_dict())

    # protected_div: b=0 exacto -> NaN, no inf ni error
    a_df = pd.DataFrame({"A": [10.0]})
    b_df = pd.DataFrame({"A": [0.0]})
    print("protected_div con b=0 (esperado NaN):", protected_div(a_df, b_df)["A"].iloc[0])
