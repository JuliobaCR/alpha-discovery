"""
Adaptador de Stooq.

Misma responsabilidad que fetch_yfinance.py: hablar con la fuente externa
y devolver datos en nuestro esquema unificado. Stooq permite descarga
directa por CSV sin necesidad de API key, lo cual lo hace un buen
respaldo simple cuando yfinance falla o no tiene un dato puntual.

⚠️ Misma nota que el de yfinance: necesita salida de red a stooq.com,
   no disponible en este sandbox — pruébalo en tu máquina.
"""

import pandas as pd

from src.config import UNIFIED_COLUMNS

STOOQ_URL = "https://stooq.com/q/d/l/?s={ticker}.us&d1={start}&d2={end}&i=d"


def fetch_stooq(ticker: str, start: str, end: str) -> pd.DataFrame:
    """
    Descarga OHLCV diario de un ticker desde Stooq (formato CSV directo)
    y lo devuelve en el esquema unificado del proyecto.

    Stooq usa fechas en formato YYYYMMDD en la URL, así que convertimos
    desde el formato YYYY-MM-DD que usamos internamente.
    """
    start_fmt = start.replace("-", "")
    end_fmt = end.replace("-", "")
    url = STOOQ_URL.format(ticker=ticker.lower(), start=start_fmt, end=end_fmt)

    try:
        raw = pd.read_csv(url)
    except Exception as e:
        print(f"[stooq] Falló la descarga de {ticker}: {e}")
        return pd.DataFrame(columns=UNIFIED_COLUMNS)

    # Stooq devuelve una sola línea con "No data" en vez de un CSV real
    # cuando el ticker no existe o no hay datos en ese rango.
    if raw.empty or "Date" not in raw.columns:
        return pd.DataFrame(columns=UNIFIED_COLUMNS)

    out = pd.DataFrame({
        "ticker": ticker,
        "fecha": pd.to_datetime(raw["Date"]).dt.date,
        "open": raw["Open"],
        "high": raw["High"],
        "low": raw["Low"],
        "close": raw["Close"],
        "volumen": raw["Volume"],
        # Stooq no separa close ajustado del close normal en el CSV gratuito;
        # lo dejamos igual al close por ahora — se puede refinar más adelante
        # si se necesita el ajuste por dividendos exacto de esta fuente.
        "close_ajustado": raw["Close"],
        "fuente": "stooq",
    })
    return out[UNIFIED_COLUMNS]


if __name__ == "__main__":
    # Prueba manual — córrela tú en tu máquina:
    #   python -m src.data.fetch_stooq
    df = fetch_stooq("AAPL", "2024-01-01", "2024-01-31")
    print(df.head())
    print(f"\nFilas obtenidas: {len(df)}")
