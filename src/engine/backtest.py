"""
Orquestador: convierte una señal de alpha + el dataset de precios de
Fase 1 en los 6 objetivos definidos en Paper1_Repaso_Conceptos.md
(secciones 2 y 7.1). Es el único módulo del motor que toca pivots, fechas
de calendario reales y el CPI — weights.py y metrics.py son piezas puras
que este archivo combina.
"""

import numpy as np
import pandas as pd

from src import config
from src.data.fetch_cpi import get_cpi_series
from src.engine.metrics import annual_median, annualized_return, max_drawdown, sharpe_ratio, sortino_ratio, turnover
from src.engine.weights import signal_to_weights


class ObjectivesComputationError(Exception):
    """
    Se lanza cuando, incluso con el fallback de annual_median, algún
    objetivo queda en NaN (ej. candidato degenerado que nunca opera, o
    ventana sin suficientes datos). La política de qué hacer con esto
    (descartar el candidato, penalizarlo con un valor fijo) es decisión
    del futuro envoltorio de NSGA-II — este motor solo reporta el fallo.
    """


def prices_to_wide(prices_df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivotea el dataset largo de Fase 1 (UNIFIED_COLUMNS) a un panel ancho
    (índice=fecha, columnas=ticker) sobre `close_ajustado` — nunca `close`,
    para que splits/dividendos no contaminen el retorno.
    """
    df = prices_df.copy()
    df["fecha"] = pd.to_datetime(df["fecha"])

    if df.duplicated(["ticker", "fecha"]).any():
        raise ValueError(
            "prices_df tiene filas duplicadas (ticker, fecha) — no se puede "
            "pivotear de forma segura. Revisa reconcile_sources/build_dataset."
        )

    return df.pivot(index="fecha", columns="ticker", values="close_ajustado")


def _deflate_returns(returns_nominal: pd.Series, trading_dates: pd.DatetimeIndex) -> pd.Series:
    """
    r_real(t) = (1 + r_nominal(t)) * CPI(t_prev) / CPI(t) - 1

    CPI(t) es el CPI del mes vigente en la fecha de trading t (merge_asof
    hacia atrás contra get_cpi_series()); CPI(t_prev) es el CPI de la fecha
    de trading INMEDIATAMENTE ANTERIOR — shift posicional sobre el
    calendario de trading COMPLETO (`trading_dates`, no solo las fechas de
    `returns_nominal`), para que el primer retorno válido de la serie
    también tenga un "día anterior" correcto contra el cual comparar.

    Por telescopía del producto de retornos consecutivos, esto equivale
    exactamente a deflactar contra una fecha base fija en el primer día de
    la ventana, sin tener que declararla aparte (ver Paper1_Repaso_
    Conceptos.md, sección 7.1). Dentro de un mismo mes calendario (el caso
    más común, CPI mensual vs. trading diario) el ajuste es un no-op exacto.
    """
    cpi = get_cpi_series()
    cpi_df = cpi.reset_index()  # columnas: date, cpi

    dates_df = pd.DataFrame({"date": pd.DatetimeIndex(trading_dates).unique()}).sort_values("date")
    merged = pd.merge_asof(dates_df, cpi_df.sort_values("date"), on="date", direction="backward")
    cpi_mapped = pd.Series(merged["cpi"].values, index=merged["date"].values).sort_index()
    cpi_prev = cpi_mapped.shift(1)

    cpi_now = cpi_mapped.reindex(returns_nominal.index)
    cpi_before = cpi_prev.reindex(returns_nominal.index)

    return (1 + returns_nominal) * cpi_before / cpi_now - 1


def compute_objectives_from_wide(
    signal: pd.DataFrame,
    prices_wide: pd.DataFrame,
    start: str,
    end: str,
    risk_free_rate: float = config.RISK_FREE_RATE,
    min_trading_days_per_year: int = config.MIN_TRADING_DAYS_PER_YEAR,
) -> dict:
    """
    Núcleo real del motor — separado de compute_objectives() para que un
    futuro harness de walk-forward pueda pivotear el parquet completo UNA
    sola vez fuera del loop y llamar esta función repetidamente por
    ventana, en vez de re-pivotear millones de filas en cada llamada.
    """
    signal_aligned, prices_aligned = signal.align(prices_wide, join="outer")

    weights_decision = signal_to_weights(signal_aligned, prices_aligned)

    # --- Lookahead bias: la señal observada al cierre de t determina la
    # posición que captura el retorno de t a t+1 — nunca el retorno de t
    # mismo. Sin este shift, el motor "conocería" el cierre de hoy y
    # operaría con él en ese mismo día, algo imposible de ejecutar en la
    # realidad. Es la línea más importante de todo el módulo.
    weights_applied = weights_decision.shift(1)

    ticker_returns = prices_aligned.pct_change()

    # Retorno de deslistamiento: el día que un ticker pasa de tener precio
    # a no tenerlo se trata como -100% en esa posición, no como "sin
    # dato" — de lo contrario una quiebra desaparecería sin consecuencia,
    # reintroduciendo por la puerta de atrás el sesgo de supervivencia que
    # ya evitamos al incluir tickers deslistados en el universo (Fase 1).
    present = prices_aligned.notna()
    first_missing = (~present) & present.shift(1).fillna(False)
    ticker_returns = ticker_returns.mask(first_missing, -1.0)

    portfolio_returns_nominal = weights_applied.mul(ticker_returns).sum(axis=1, min_count=1)
    # Corrige un comportamiento de pandas: sum(skipna=True) sobre una fila
    # enteramente NaN da 0.0, no NaN — sin esto, el primer día de la serie
    # (sin peso previo, weights_applied todo NaN) se colaría como un falso
    # "retorno de 0%" en vez de quedar excluido.
    portfolio_returns_nominal[weights_applied.isna().all(axis=1)] = np.nan
    portfolio_returns_nominal = portfolio_returns_nominal.dropna()

    portfolio_returns_real = _deflate_returns(portfolio_returns_nominal, prices_aligned.index)

    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    returns_real_window = portfolio_returns_real[(portfolio_returns_real.index >= start_ts) & (portfolio_returns_real.index <= end_ts)]
    weights_decision_window = weights_decision[(weights_decision.index >= start_ts) & (weights_decision.index <= end_ts)]

    # Return/Sharpe/Sortino: mediana anual (annual_median recorta a
    # [start, end] internamente y aplica su propio fallback de rango corto).
    return_real = annual_median(portfolio_returns_real, annualized_return, start, end, min_trading_days_per_year)
    sharpe = annual_median(portfolio_returns_nominal, lambda r: sharpe_ratio(r, risk_free_rate), start, end, min_trading_days_per_year)
    sortino = annual_median(portfolio_returns_nominal, lambda r: sortino_ratio(r, risk_free_rate), start, end, min_trading_days_per_year)

    # Max Drawdown y Turnover: toda la ventana de un tirón, nunca por año.
    max_dd_real = max_drawdown(returns_real_window)
    turnover_val = turnover(weights_decision_window)

    # Calmar se DERIVA de los otros dos ya calculados — no se computa año
    # por año. Es la única lectura consistente con que Max Drawdown nunca
    # se parte por año (documento, sección 7.1): "mediana de Calmar anual"
    # solo tendría sentido si cada año usara SU PROPIO MaxDD, pero esa
    # regla está explícitamente prohibida — así que Calmar usa el MaxDD
    # global, y "mediana de Return / MaxDD global constante" colapsa
    # algebraicamente a "mediana de Return / MaxDD global".
    if np.isnan(max_dd_real) or max_dd_real == 0 or np.isnan(return_real):
        calmar_real = float("nan")
    else:
        calmar_real = return_real / abs(max_dd_real)

    objectives = {
        "return_real": return_real,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar_real": calmar_real,
        "max_drawdown_real": max_dd_real,
        "turnover": turnover_val,
    }

    invalidos = [k for k, v in objectives.items() if v is None or (isinstance(v, float) and np.isnan(v))]
    if invalidos:
        raise ObjectivesComputationError(
            f"No se pudieron calcular estos objetivos (candidato degenerado o "
            f"ventana sin suficientes datos): {invalidos}"
        )

    return objectives


def compute_objectives(
    signal: pd.DataFrame,
    prices_df: pd.DataFrame,
    start: str,
    end: str,
    risk_free_rate: float = config.RISK_FREE_RATE,
    min_trading_days_per_year: int = config.MIN_TRADING_DAYS_PER_YEAR,
) -> dict:
    """
    signal: DataFrame ancho (índice=fecha, columnas=ticker canónico,
    valores=señal de alpha, NaN donde no aplica). Cualquier generador de
    alpha puede producir esta forma — el motor no asume nada sobre cómo se
    construyó.
    prices_df: dataset de Fase 1 en formato largo (UNIFIED_COLUMNS), ej.
    el resultado de build_dataset() cargado desde sp500_dataset.parquet.
    """
    prices_wide = prices_to_wide(prices_df)
    return compute_objectives_from_wide(signal, prices_wide, start, end, risk_free_rate, min_trading_days_per_year)


if __name__ == "__main__":
    # Prueba manual con datos SINTÉTICOS (no se necesita sp500_dataset.parquet
    # ni red — usa el CPI ya cacheado localmente de fetch_cpi.py) — córrela
    # tú en tu máquina:
    #   python -m src.engine.backtest
    #
    # Señal placeholder: momentum de 20 días. No es un módulo permanente —
    # es el mismo lugar donde, cuando existan los árboles de GP, se probará
    # una fórmula real en su lugar.
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2018-01-01", "2021-12-31")
    tickers = [f"T{i}" for i in range(10)]

    log_returns = rng.normal(0.0003, 0.015, size=(len(dates), len(tickers)))
    prices_wide_synth = pd.DataFrame(100 * np.exp(np.cumsum(log_returns, axis=0)), index=dates, columns=tickers)

    prices_long = (
        prices_wide_synth.reset_index(names="fecha")
        .melt(id_vars="fecha", var_name="ticker", value_name="close_ajustado")
    )
    for col in ["open", "high", "low", "close"]:
        prices_long[col] = prices_long["close_ajustado"]
    prices_long["volumen"] = 1_000_000
    prices_long["fuente"] = "sintetico"
    prices_long = prices_long[config.UNIFIED_COLUMNS]

    signal_synth = prices_wide_synth.pct_change(20)

    objectives = compute_objectives(signal_synth, prices_long, start="2019-01-01", end="2021-12-31")
    print("Objetivos (datos sintéticos, señal = momentum 20 días):")
    for k, v in objectives.items():
        print(f"  {k}: {v:.4f}")
