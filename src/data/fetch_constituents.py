"""
Universo histórico de constituyentes del S&P 500 (activos + deslistados).

Por qué esto importa: si solo usáramos los tickers que están en el índice
HOY, el pipeline tendría sesgo de supervivencia — solo verían "supervivientes"
las fórmulas de alpha, nunca las empresas que quebraron o fueron adquiridas.
Para evitarlo, se reconstruye qué tickers estuvieron vigentes en cualquier
momento dentro del rango de fechas del experimento.

Fuente: fja05680/sp500 (GitHub) — historial de cambios del índice derivado
de Wikipedia, mantenido activamente. Cada fila del CSV es una fecha de
cambio con la lista completa de tickers vigentes en esa fecha; los que ya
salieron del índice llevan sufijo "-AAAAMM" (fecha de salida) y desaparecen
de la lista en las filas posteriores a su salida real.

⚠️ A diferencia de fetch_yfinance.py y fetch_stooq.py, las funciones de
   descarga aquí SÍ pueden lanzar excepción: sin este archivo no hay
   universo de tickers en absoluto, así que fallar en silencio produciría
   una corrida "exitosa" con dataset vacío — peor que un error ruidoso.
"""

import hashlib
import json
from datetime import datetime, timezone
from urllib.request import urlopen

import pandas as pd

from src.config import CONSTITUENTS_URL, EXTERNAL_DIR

CSV_PATH = EXTERNAL_DIR / "sp500_constituents.csv"
META_PATH = EXTERNAL_DIR / "sp500_constituents.meta.json"


def _ensure_local_csv(force_refresh: bool = False) -> None:
    """
    Descarga el CSV de constituyentes UNA sola vez y lo deja versionado en
    disco. No se vuelve a descargar automáticamente en corridas futuras —
    eso es intencional: el dataset del paper no debe cambiar solo porque
    el repo externo en GitHub se actualizó. Para refrescar, pasar
    force_refresh=True explícitamente.
    """
    if CSV_PATH.exists() and not force_refresh:
        return

    try:
        with urlopen(CONSTITUENTS_URL, timeout=30) as response:
            raw_bytes = response.read()
    except Exception as e:
        if CSV_PATH.exists():
            print(f"[constituents] Falló refrescar el CSV ({e}); se usa la copia local existente (ver {META_PATH.name} para su fecha de descarga).")
            return
        raise RuntimeError(
            f"No se pudo descargar la lista de constituyentes desde {CONSTITUENTS_URL} "
            f"y no hay copia local en {CSV_PATH}. Sin este archivo no hay universo de "
            f"tickers para el pipeline — revisa tu conexión e intenta de nuevo."
        ) from e

    CSV_PATH.write_bytes(raw_bytes)
    META_PATH.write_text(json.dumps({
        "source_url": CONSTITUENTS_URL,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "n_bytes": len(raw_bytes),
    }, indent=2))
    print(f"[constituents] Descargado y versionado en {CSV_PATH}")


def _load_raw_constituents_df(force_refresh: bool = False) -> pd.DataFrame:
    _ensure_local_csv(force_refresh=force_refresh)
    df = pd.read_csv(CSV_PATH, parse_dates=["date"])
    return df.sort_values("date").reset_index(drop=True)


def _parse_ticker_token(token: str) -> tuple[str, str | None]:
    """
    'AAMRQ-201312' -> ('AAMRQ', '201312')  (salió del índice en dic-2013)
    'AAPL'         -> ('AAPL', None)       (vigente, sin sufijo)
    """
    if len(token) > 7 and token[-7] == "-" and token[-6:].isdigit():
        return token[:-7], token[-6:]
    return token, None


def _row_tickers(tickers_cell: str) -> set[str]:
    # Cada celda trae una coma final (confirmado en el CSV real) que deja
    # un token vacío al hacer split — se descarta.
    tokens = [t.strip() for t in tickers_cell.split(",") if t.strip()]
    return {_parse_ticker_token(t)[0] for t in tokens}


def get_constituents_at(date: str, force_refresh: bool = False) -> set[str]:
    """
    Composición del índice vigente en una fecha puntual (la fila cuya
    fecha es la más reciente <= date). Útil para reportar el tamaño del
    índice en fechas de interés del paper, y para debugging.
    """
    df = _load_raw_constituents_df(force_refresh=force_refresh)
    target = pd.Timestamp(date)
    subset = df[df["date"] <= target]
    if subset.empty:
        raise ValueError(
            f"No hay datos de constituyentes en o antes de {date} "
            f"(el histórico empieza en {df['date'].min().date()})."
        )
    row = subset.iloc[-1]
    return _row_tickers(row["tickers"])


def get_historical_universe(start: str, end: str, force_refresh: bool = False) -> set[str]:
    """
    Unión de todos los tickers base que estuvieron vigentes en algún
    momento dentro de [start, end] — activos y deslistados.

    No se infiere un intervalo (entrada, salida) por ticker a partir del
    sufijo: eso es frágil por reutilización de símbolos entre empresas
    distintas en épocas distintas. En vez de eso, se toma la unión de la
    composición vigente justo antes de `start` más cada cambio dentro de
    la ventana — cada fila del CSV ya es un snapshot completo de quién
    está vigente, así que no hace falta razonar sobre el significado del
    sufijo para decidir inclusión.
    """
    df = _load_raw_constituents_df(force_refresh=force_refresh)
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)

    universe: set[str] = set()

    boundary = df[df["date"] <= start_ts]
    if not boundary.empty:
        universe |= _row_tickers(boundary.iloc[-1]["tickers"])

    inside_window = df[(df["date"] > start_ts) & (df["date"] <= end_ts)]
    for tickers_cell in inside_window["tickers"]:
        universe |= _row_tickers(tickers_cell)

    return universe


def to_yfinance_ticker(ticker: str) -> str:
    # yfinance/Yahoo Finance usa guión para acciones de clase (BF.B -> BF-B).
    return ticker.replace(".", "-")


def to_stooq_ticker(ticker: str) -> str:
    # Ya no se usa en build_dataset.py (Stooq bloquea descargas
    # programáticas, ver fetch_stooq.py) — se deja por si se retoma.
    # Pendiente: confirmar en tu máquina si Stooq espera guión, punto, o
    # sin separador para acciones de clase.
    return ticker


def to_tiingo_ticker(ticker: str) -> str:
    # Pendiente: confirmar en tu máquina el formato exacto que espera
    # Tiingo para acciones de clase (BF.B) — se deja tal cual por ahora.
    return ticker


if __name__ == "__main__":
    # Prueba manual — córrela tú en tu máquina:
    #   python -m src.data.fetch_constituents
    from src.config import END_DATE, START_DATE

    universe = get_historical_universe(START_DATE, END_DATE)
    print(f"Universo histórico ({START_DATE} a {END_DATE}): {len(universe)} tickers")

    hoy = datetime.now(timezone.utc).date().isoformat()
    actuales = get_constituents_at(hoy)
    print(f"Constituyentes vigentes hoy ({hoy}): {len(actuales)} tickers")
