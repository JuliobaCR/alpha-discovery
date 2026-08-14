"""
Fórmulas de los 6 objetivos de Paper1_Repaso_Conceptos.md (secciones 2 y
7.1), sobre series de retornos ya calculadas. Funciones puras — no tocan
pivots, precios ni CPI — se prueban con series sintéticas donde el
resultado se puede verificar a mano.
"""

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """(media(R) - Rf) / std(R) × √252 — Rf anual, se pasa a diario internamente."""
    if len(returns) < 2:
        return float("nan")
    rf_daily = risk_free_rate / TRADING_DAYS_PER_YEAR
    std = returns.std()
    if std == 0:
        return float("nan")
    return float((returns.mean() - rf_daily) / std * np.sqrt(TRADING_DAYS_PER_YEAR))


def sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """
    Igual que Sharpe, pero el denominador es la desviación estándar
    calculada SOLO sobre los días de retorno negativo (lectura literal del
    documento de diseño — no semi-desviación de longitud completa con
    ceros en los días positivos).
    """
    negative = returns[returns < 0]
    if len(returns) < 2 or len(negative) < 2:
        return float("nan")
    rf_daily = risk_free_rate / TRADING_DAYS_PER_YEAR
    downside_std = negative.std()
    if downside_std == 0:
        return float("nan")
    return float((returns.mean() - rf_daily) / downside_std * np.sqrt(TRADING_DAYS_PER_YEAR))


def annualized_return(returns: pd.Series) -> float:
    """(1 + retorno_total)^(252/N) - 1"""
    if len(returns) == 0:
        return float("nan")
    total = float((1 + returns).prod())
    if total <= 0:
        # Capital llegó a cero (posible con retornos de -100% por
        # deslistamiento concentrados) — el retorno anualizado real es
        # -100%, no una raíz de un número negativo.
        return -1.0
    return float(total ** (TRADING_DAYS_PER_YEAR / len(returns)) - 1)


def max_drawdown(returns: pd.Series) -> float:
    """
    Caída porcentual máxima desde un pico de capital acumulado. Número
    negativo (ej. -0.32 = -32%). Sobre TODA la serie de un tirón — nunca
    se parte por año (partir un crash real por año lo diluiría, ver
    Paper1_Repaso_Conceptos.md sección 7.1).
    """
    if len(returns) == 0:
        return float("nan")
    capital = (1 + returns).cumprod()
    drawdown = capital / capital.cummax() - 1
    return float(drawdown.min())


def turnover(weights_decision: pd.DataFrame) -> float:
    """
    Σ|peso_i(t) - peso_i(t-1)| / 2, promediado por periodo. Sobre los
    pesos DE DECISIÓN (sin el shift de lookahead de backtest.py): el costo
    de operar ocurre en el momento del rebalanceo, no cuando el retorno se
    realiza al día siguiente.
    """
    if len(weights_decision) == 0:
        return float("nan")
    diffs = weights_decision.diff().abs().sum(axis=1) / 2
    diffs.iloc[0] = weights_decision.iloc[0].abs().sum() / 2  # primer día: armar el libro desde cero
    return float(diffs.mean())


def annual_median(returns: pd.Series, metric_fn, start: str, end: str, min_trading_days: int) -> float:
    """
    Calcula metric_fn año por año (calendario) dentro de [start, end], y
    devuelve la MEDIANA entre años — no el promedio, para que un solo año
    atípico no tape la inconsistencia del resto (mitigación de alpha
    decay, Paper1_Repaso_Conceptos.md sección 7.1).

    Años con menos de min_trading_days observaciones se excluyen (evita
    que un año parcial en el borde de la ventana meta ruido). Si NINGÚN
    año cumple el mínimo (ventanas de prueba cortas), calcula metric_fn
    sobre todo el rango de un tirón, para no reventar.
    """
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    windowed = returns[(returns.index >= start_ts) & (returns.index <= end_ts)]

    valores = []
    for year in range(start_ts.year, end_ts.year + 1):
        r_year = windowed[windowed.index.year == year]
        if len(r_year) < min_trading_days:
            continue
        v = metric_fn(r_year)
        if not np.isnan(v):
            valores.append(v)

    if not valores:
        return metric_fn(windowed)

    return float(np.median(valores))


if __name__ == "__main__":
    # Casos hand-verificables.

    # Sharpe: mean(R)=0 -> numerador 0 -> Sharpe debe dar exactamente 0.0
    r = pd.Series([0.10, -0.10])
    print("Sharpe (mean=0, esperado 0.0):", sharpe_ratio(r))

    # Sortino: solo 1 día negativo -> NaN por guarda (no se puede estimar std con 1 dato)
    print("Sortino (1 día negativo, esperado NaN):", sortino_ratio(r))

    # Max Drawdown: +10%, -20%, +5% -> capital 1.10, 0.88, 0.924; pico=1.10;
    # peor drawdown en el día 2: 0.88/1.10 - 1 = -0.20 exacto
    r2 = pd.Series([0.10, -0.20, 0.05])
    print("Max Drawdown (esperado -0.20):", max_drawdown(r2))

    # Return anualizado: con exactamente 252 observaciones, el exponente
    # 252/252=1, así que debe dar exactamente el retorno total compuesto.
    r3 = pd.Series([0.001] * 252)
    esperado = float((1.001) ** 252 - 1)
    print(f"Return anualizado (N=252, esperado == retorno total = {esperado:.6f}):", annualized_return(r3))

    # Turnover: día0 {A:0.5,B:-0.5} (armar desde cero, |0.5|+|0.5| /2 = 0.5),
    # día1 {A:0.3,B:-0.3} (cambio |0.2|+|0.2| /2 = 0.2) -> promedio (0.5+0.2)/2 = 0.35
    w = pd.DataFrame({"A": [0.5, 0.3], "B": [-0.5, -0.3]})
    print("Turnover (esperado 0.35):", turnover(w))

    # annual_median: 3 años sintéticos con Sharpe muy distinto cada uno ->
    # la mediana debe ser el del año de en medio (2021), no el promedio de los 3.
    dates = pd.date_range("2020-01-01", "2022-12-31", freq="B")
    rng = np.random.default_rng(42)
    returns_by_year = pd.Series(0.0, index=dates)
    for year, mean_r in zip([2020, 2021, 2022], [0.01, 0.0005, -0.01]):
        mask = returns_by_year.index.year == year
        returns_by_year[mask] = rng.normal(mean_r, 0.01, mask.sum())
    med = annual_median(returns_by_year, sharpe_ratio, "2020-01-01", "2022-12-31", min_trading_days=20)
    print("Sharpe mediana anual (3 años, esperado cercano al Sharpe de 2021, el de en medio):", med)
