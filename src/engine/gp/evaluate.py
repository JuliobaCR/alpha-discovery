"""
Compila un árbol (individuo) y lo evalúa sobre el panel de precios,
produciendo el DataFrame ancho `signal` que compute_objectives() ya sabe
consumir — cierra el lazo entre la representación (este paquete) y el
motor de backtest (src/engine/backtest.py).
"""

import pandas as pd
from deap import gp


def evaluate_tree(individual: gp.PrimitiveTree, pset: gp.PrimitiveSetTyped, prices_wide_by_field: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    prices_wide_by_field: {"close","high","low","volume","atr_14"} — ver
    preprocessing.build_adjusted_ohlcv_wide(). Se llama por kwargs (no
    posicional) para no depender del orden exacto de pset.in_types,
    siempre que las claves coincidan con los nombres puestos por
    renameArguments en primitives.build_pset().

    Cada primitivo opera elementwise/rolling/rank(axis=1) — preserva la
    forma (fecha × ticker) de sus entradas — así que el resultado es
    siempre un DataFrame ancho válido como `signal`, sin importar qué
    categoría (Price/Bounded/Volatility/Volume) haya terminado siendo la
    raíz del árbol.
    """
    func = gp.compile(individual, pset)
    return func(**prices_wide_by_field)


if __name__ == "__main__":
    # Prueba manual: compila y evalúa un árbol generado de verdad sobre un
    # panel sintético, confirmando forma y tipo del resultado.
    from src.engine.gp.population import generate_initial_population
    from src.engine.gp.primitives import build_pset
    from src.engine.gp.preprocessing import build_adjusted_ohlcv_wide
    from src.config import UNIFIED_COLUMNS
    import numpy as np

    rng = np.random.default_rng(0)
    dates = pd.bdate_range("2023-01-01", "2023-12-31")
    tickers = [f"T{i}" for i in range(5)]

    log_returns = rng.normal(0.0002, 0.015, size=(len(dates), len(tickers)))
    close = 100 * np.exp(np.cumsum(log_returns, axis=0))
    rows = []
    for j, tk in enumerate(tickers):
        for i, d in enumerate(dates):
            c = close[i, j]
            rows.append({
                "ticker": tk, "fecha": d, "open": c, "high": c * 1.01, "low": c * 0.99,
                "close": c, "volumen": 1_000_000, "close_ajustado": c, "fuente": "sintetico",
            })
    prices_df = pd.DataFrame(rows)[UNIFIED_COLUMNS]

    pset = build_pset()
    panels = build_adjusted_ohlcv_wide(prices_df)
    population = generate_initial_population(5, pset, seed=1)

    for i, individual in enumerate(population):
        signal = evaluate_tree(individual, pset, panels)
        n_validas = signal.notna().sum().sum()
        print(f"Árbol {i} (tamaño={len(individual)}, profundidad={individual.height}): "
              f"signal shape={signal.shape}, valores no-NaN={n_validas}")
