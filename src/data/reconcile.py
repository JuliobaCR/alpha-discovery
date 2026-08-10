"""
Reconciliación automática entre múltiples fuentes de datos.

Nada de revisión manual — todo se resuelve con reglas fijas, definidas
una sola vez en config.py:
  - Diferencia <= DIFF_THRESHOLD_DISCARD (5%)  -> se usa la fuente de
    mayor prioridad disponible (ya sea que coincidan de cerca o no tanto).
  - Diferencia >  DIFF_THRESHOLD_DISCARD (5%)  -> se descarta ese
    ticker-fecha (mejor un dato faltante que uno incorrecto).

Además devuelve estadísticas agregadas, pensadas para reportar
directamente en la sección de datos del paper.
"""

import pandas as pd

from src.config import DIFF_THRESHOLD_ACCEPT, DIFF_THRESHOLD_DISCARD, SOURCE_PRIORITY, UNIFIED_COLUMNS


def reconcile_sources(dfs_by_source: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, dict]:
    """
    dfs_by_source: ej. {"yfinance": df1, "stooq": df2}
    Devuelve (dataframe_reconciliado, estadisticas)
    """
    all_data = []
    for fuente, df in dfs_by_source.items():
        if not df.empty:
            all_data.append(df)

    if not all_data:
        return pd.DataFrame(columns=UNIFIED_COLUMNS), {"total_comparaciones": 0}

    combined = pd.concat(all_data, ignore_index=True)

    rows_out = []
    n_una_fuente = 0
    n_acuerdo_cercano = 0    # diferencia <= 0.5%
    n_acuerdo_flexible = 0   # entre 0.5% y 5%
    n_descartados = 0

    for (ticker, fecha), grupo in combined.groupby(["ticker", "fecha"]):
        if len(grupo) == 1:
            # Solo una fuente tenía este dato — se usa directo, no hay nada que reconciliar.
            rows_out.append(grupo.iloc[0])
            n_una_fuente += 1
            continue

        precios = grupo.set_index("fuente")["close_ajustado"]
        diff_relativa = (precios.max() - precios.min()) / precios.min()

        if diff_relativa > DIFF_THRESHOLD_DISCARD:
            n_descartados += 1
            continue  # se descarta, no se agrega nada para este ticker-fecha

        # Diferencia aceptable (en cualquiera de los dos rangos) -> prioridad fija
        if diff_relativa <= DIFF_THRESHOLD_ACCEPT:
            n_acuerdo_cercano += 1
        else:
            n_acuerdo_flexible += 1

        for fuente_prioritaria in SOURCE_PRIORITY:
            if fuente_prioritaria in grupo["fuente"].values:
                fila_elegida = grupo[grupo["fuente"] == fuente_prioritaria].iloc[0]
                rows_out.append(fila_elegida)
                break

    resultado = pd.DataFrame(rows_out, columns=UNIFIED_COLUMNS) if rows_out else pd.DataFrame(columns=UNIFIED_COLUMNS)

    total = n_una_fuente + n_acuerdo_cercano + n_acuerdo_flexible + n_descartados
    stats = {
        "total_ticker_fechas": total,
        "solo_una_fuente": n_una_fuente,
        "acuerdo_cercano_pct": round(100 * n_acuerdo_cercano / total, 2) if total else 0,
        "acuerdo_flexible_pct": round(100 * n_acuerdo_flexible / total, 2) if total else 0,
        "descartados_pct": round(100 * n_descartados / total, 2) if total else 0,
    }
    return resultado, stats


if __name__ == "__main__":
    # Prueba con datos sintéticos — no necesita red, corre igual aquí que en tu máquina.
    df_yf = pd.DataFrame({
        "ticker": ["AAPL", "AAPL", "AAPL"],
        "fecha": ["2024-01-02", "2024-01-03", "2024-01-04"],
        "open": [185.0, 186.0, 187.0], "high": [186.5, 187.0, 188.0],
        "low": [184.5, 185.5, 186.5], "close": [186.0, 186.5, 187.5],
        "volumen": [1000000, 1100000, 1050000],
        "close_ajustado": [186.00, 186.50, 187.50],  # caso 1: coincide de cerca con stooq
        "fuente": "yfinance",
    })
    df_stooq = pd.DataFrame({
        "ticker": ["AAPL", "AAPL", "AAPL"],
        "fecha": ["2024-01-02", "2024-01-03", "2024-01-04"],
        "open": [185.1, 186.1, 187.1], "high": [186.6, 187.1, 188.1],
        "low": [184.6, 185.6, 186.6], "close": [186.1, 186.6, 200.0],
        "volumen": [999000, 1101000, 1049000],
        "close_ajustado": [186.10, 250.00, 191.25],  # 02-ene: diff ~0.05% -> acuerdo cercano
        "fuente": "stooq",                            # 03-ene: diff ~34%  -> se descarta
    })                                                 # 04-ene: diff ~2%   -> acuerdo flexible

    resultado, stats = reconcile_sources({"yfinance": df_yf, "stooq": df_stooq})
    print(resultado[["ticker", "fecha", "close_ajustado", "fuente"]])
    print("\nEstadísticas:", stats)
