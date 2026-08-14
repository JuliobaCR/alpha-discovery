"""
Convierte una señal de alpha (un número por ticker por día) en pesos de
portafolio long-short, neutrales a mercado, ajustados por riesgo.

Por qué long-short y no long-only: "alpha" en finanzas significa retorno
independiente del mercado, no exposición a que el mercado en general suba
(eso es "beta"). Un portafolio solo-largo se parecería demasiado al S&P 500
en general, diluyendo la diferencia entre lo que descubre el LLM vs. lo
clásico — que es justo lo que este proyecto quiere medir.

Por qué rank continuo y no deciles/top-K: usa toda la información de la
señal (no solo los extremos), y evita tener que fijar y justificar un
hiperparámetro K adicional.

Por qué ponderación por volatilidad inversa: el rank por sí solo decide
QUÉ tan largo/corto ir según el orden de la señal, pero no cuánto pesa eso
en dólares según qué tan riesgosa es cada acción — sin este ajuste, una
acción muy volátil (ej. penny stock) recibe el mismo tamaño de posición
que una tranquila (ej. blue chip) si quedan en posiciones similares del
ranking. Escalar por 1/volatilidad reciente hace que cada posición aporte
un riesgo más parejo al portafolio, en vez de dejar que unas pocas
acciones volátiles dominen el riesgo total.
"""

import pandas as pd

from src.config import VOLATILITY_WINDOW


def signal_to_weights(signal: pd.DataFrame, prices: pd.DataFrame, vol_window: int = VOLATILITY_WINDOW) -> pd.DataFrame:
    """
    signal, prices: DataFrames anchos (índice=fecha, columnas=ticker), ya
    alineados en ambos ejes (mismo índice y mismas columnas).

    Pesos long-short ajustados por riesgo, en dos pasos:
    1. Rank transversal de la señal por fecha, centrado (resta la media
       del día) para decidir DIRECCIÓN (largo/corto) — por construcción
       suma 0 antes de escalar por volatilidad.
    2. Cada posición se divide entre la volatilidad reciente de esa acción
       (desviación estándar de retornos diarios sobre `vol_window` días) —
       esto rompe la simetría del paso 1 (dividir por volatilidades
       distintas ya no suma 0), así que se vuelve a centrar DESPUÉS de
       escalar, y solo entonces se normaliza para que la exposición bruta
       (suma de valores absolutos) sea exactamente 1 cada día.

    Un ticker sin señal, sin precio, sin volatilidad calculable todavía
    (necesita `vol_window` días de historia previa), o con volatilidad
    exactamente 0 (precio constante — evita división entre cero), no
    entra al rank ese día — los demás se renormalizan solos. Un día con
    menos de 2 tickers disponibles no puede formar un libro long-short:
    sus pesos quedan en 0 (no operar ese día).
    """
    returns = prices.pct_change()
    volatility = returns.rolling(vol_window, min_periods=vol_window).std()

    avail = signal.notna() & prices.notna() & volatility.notna() & (volatility > 0)
    ranks = signal.where(avail).rank(axis=1, method="average")
    centered = ranks.sub(ranks.mean(axis=1), axis=0)

    vol_scaled = centered.div(volatility)
    vol_scaled_centered = vol_scaled.sub(vol_scaled.mean(axis=1), axis=0)

    gross = vol_scaled_centered.abs().sum(axis=1)
    weights = vol_scaled_centered.div(gross, axis=0)

    return weights.fillna(0.0)


if __name__ == "__main__":
    # Prueba manual con datos sintéticos — verifica gross=1 y net=0 exactos,
    # el caso de un ticker sin dato un día, y que el ajuste por volatilidad
    # sí cambia el tamaño relativo de las posiciones (no solo la dirección).
    dates = pd.date_range("2024-01-01", periods=30, freq="D")

    # A: señal siempre alta, poco volátil. B: señal siempre baja, muy volátil.
    # C: señal intermedia, sin dato el último día.
    signal = pd.DataFrame({"A": 3.0, "B": 1.0, "C": 2.0}, index=dates)
    signal.loc[dates[-1], "C"] = None

    rng_a = [100 + 0.1 * i for i in range(30)]         # A: casi sin ruido -> vol baja
    rng_b = [100, 105, 98, 108, 95, 110, 92, 112, 90, 115] * 3  # B: ruidoso -> vol alta
    prices = pd.DataFrame({"A": rng_a, "B": rng_b[:30], "C": [50 + 0.2 * i for i in range(30)]}, index=dates)

    w = signal_to_weights(signal, prices)
    print(w.tail())
    print("\nGross (suma |peso|) por día, últimos 5:")
    print(w.abs().sum(axis=1).tail())
    print("\nNet (suma peso) por día, últimos 5:")
    print(w.sum(axis=1).tail())
    print("\n|peso A| (poco volátil) vs |peso B| (muy volátil), último día — A debería pesar más:")
    print(w[["A", "B"]].tail(1))
