"""
Construye el PrimitiveSetTyped de DEAP: cablea las 4 categorías de tipo
(types.py) con las fórmulas de indicators.py, siguiendo la tabla de
diseño de Paper1_Repaso_Conceptos.md sección "Representación". Este
archivo NO calcula nada — solo tipa y nombra lo que ya existe en
indicators.py.

Ventanas fijas (no parametrizables por el árbol) — cada combinación
función+ventana es un primitivo concreto, con una convención de la
industria citable detrás (decisión explícita: nada de números sin
fundamento):
  RSI 14 / ATR 14        -> periodo original de Wilder (1978).
  EMA 12 / 26             -> componentes del MACD.
  EMA 50 / 200, SMA 50/200 -> cruce dorado / cruce de la muerte.
  SMA 20, ts_std 20        -> base de Bandas de Bollinger.
  vol_sma_20               -> misma ventana que config.VOLATILITY_WINDOW
                               (ya usada en weights.py para dimensionar riesgo).
"""

import operator
from functools import partial

from deap import gp

from src.engine.gp import indicators as ind
from src.engine.gp.types import Bounded, Price, Volatility, Volume


def build_pset() -> gp.PrimitiveSetTyped:
    """
    Terminales (argumentos de entrada, ver preprocessing.py para cómo se
    producen): close, high, low (Price); volume (Volume); atr_14
    (Volatility, precalculado — no es un primitivo de aridad 3, ver
    docstring de por qué en el plan de diseño: mezclar ramas evolutivas
    independientes en high/low/close rompería la semántica de Wilder).

    El tipo de retorno por defecto del pset (Price) es solo el default de
    gp.genHalfAndHalf/genFull/genGrow — population.py lo sobreescribe por
    llamada con type_=<categoría> para poder generar raíces de las 4
    categorías (todas son señales de alpha válidas).
    """
    pset = gp.PrimitiveSetTyped("alpha", [Price, Price, Price, Volume, Volatility], Price, "IN")
    pset.renameArguments(IN0="close", IN1="high", IN2="low", IN3="volume", IN4="atr_14")

    # --- Price -> Price ---
    pset.addPrimitive(partial(ind.ema, span=12), [Price], Price, name="ema_12")
    pset.addPrimitive(partial(ind.ema, span=26), [Price], Price, name="ema_26")
    pset.addPrimitive(partial(ind.ema, span=50), [Price], Price, name="ema_50")
    pset.addPrimitive(partial(ind.ema, span=200), [Price], Price, name="ema_200")
    pset.addPrimitive(partial(ind.sma, window=20), [Price], Price, name="sma_20")
    pset.addPrimitive(partial(ind.sma, window=50), [Price], Price, name="sma_50")
    pset.addPrimitive(partial(ind.sma, window=200), [Price], Price, name="sma_200")
    pset.addPrimitive(operator.add, [Price, Price], Price, name="price_add")
    pset.addPrimitive(operator.sub, [Price, Price], Price, name="price_sub")
    pset.addPrimitive(ind.protected_div, [Price, Price], Price, name="price_protected_div")

    # --- Bounded (puente universal) ---
    pset.addPrimitive(partial(ind.rsi_wilder, window=14), [Price], Bounded, name="rsi_14")
    pset.addPrimitive(ind.rank_cross_sectional, [Price], Bounded, name="rank_price")
    pset.addPrimitive(ind.rank_cross_sectional, [Volatility], Bounded, name="rank_volatility")
    pset.addPrimitive(ind.rank_cross_sectional, [Volume], Bounded, name="rank_volume")
    pset.addPrimitive(operator.add, [Bounded, Bounded], Bounded, name="bounded_add")
    pset.addPrimitive(operator.sub, [Bounded, Bounded], Bounded, name="bounded_sub")
    pset.addPrimitive(operator.mul, [Bounded, Bounded], Bounded, name="bounded_mul")
    pset.addPrimitive(ind.protected_div, [Bounded, Bounded], Bounded, name="bounded_protected_div")
    pset.addTerminal(0.5, Bounded, name="neutral_bounded")

    # --- Volatility ---
    pset.addPrimitive(partial(ind.ts_std, window=20), [Price], Volatility, name="ts_std_20")
    pset.addPrimitive(partial(ind.ts_std, window=50), [Price], Volatility, name="ts_std_50")
    pset.addPrimitive(partial(ind.ts_std, window=200), [Price], Volatility, name="ts_std_200")
    pset.addPrimitive(operator.add, [Volatility, Volatility], Volatility, name="volatility_add")
    pset.addPrimitive(operator.sub, [Volatility, Volatility], Volatility, name="volatility_sub")
    pset.addPrimitive(ind.protected_div, [Volatility, Volatility], Volatility, name="volatility_protected_div")

    # --- Volume ---
    pset.addPrimitive(partial(ind.sma, window=20), [Volume], Volume, name="vol_sma_20")
    pset.addPrimitive(operator.add, [Volume, Volume], Volume, name="volume_add")
    pset.addPrimitive(operator.sub, [Volume, Volume], Volume, name="volume_sub")
    pset.addPrimitive(ind.protected_div, [Volume, Volume], Volume, name="volume_protected_div")

    return pset


if __name__ == "__main__":
    # Prueba manual: confirma que las 4 categorías tienen al menos un
    # terminal (si no, la generación de árboles revienta con IndexError
    # al intentar cerrar una rama en profundidad máxima — verificado
    # empíricamente en la fase de planeación) y que se pueden generar
    # árboles con cada una como raíz.
    import random

    pset = build_pset()

    print("Terminales por categoría:")
    for t, terms in pset.terminals.items():
        print(f"  {t.__name__}: {len(terms)}")

    print("\nPrimitivos por categoría:")
    for t, prims in pset.primitives.items():
        print(f"  {t.__name__}: {len(prims)} -> {[p.name for p in prims]}")

    print("\nGeneración de árboles por categoría raíz (10 intentos c/u, profundidad 2-6):")
    for categoria in [Price, Bounded, Volatility, Volume]:
        random.seed(0)
        ok = 0
        for _ in range(10):
            depth = random.choice([2, 3, 4, 5, 6])
            try:
                gp.genHalfAndHalf(pset, min_=2, max_=depth, type_=categoria)
                ok += 1
            except IndexError:
                pass
        print(f"  {categoria.__name__}: {ok}/10 sin error")
