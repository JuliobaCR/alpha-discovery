"""
Adaptador de Tiingo.

Reemplaza a Stooq como fuente de respaldo: Stooq empezó a bloquear la
descarga programática con un challenge de JavaScript anti-bot (confirmado
en vivo — antes servía el CSV directo, dejó de funcionar sin previo aviso
del lado de nuestro código). Tiingo cubre bien EE.UU., que es lo que
necesitamos, y ya estaba anotado como respaldo en el diseño original.

Misma responsabilidad que los demás adaptadores: hablar con la fuente
externa y devolver datos en NUESTRO esquema unificado.

⚠️ A diferencia de yfinance y Stooq, Tiingo requiere una API key gratuita
   en la variable de entorno TIINGO_API_KEY. Sin ella, esta función no
   rompe el pipeline — solo devuelve DataFrame vacío con un warning claro,
   igual que si la fuente no tuviera el dato.

⚠️ Nota de entorno: necesita salida de red a api.tiingo.com. El paso de
   token vía query string (?token=...) está documentado por Tiingo como
   alternativa al header Authorization — pendiente de confirmar en tu
   máquina con una key real, mismo patrón que el resto del repo.
"""

import os

import pandas as pd

from src.config import UNIFIED_COLUMNS

TIINGO_URL = "https://api.tiingo.com/tiingo/daily/{ticker}/prices"


def fetch_tiingo(ticker: str, start: str, end: str) -> pd.DataFrame:
    """
    Descarga OHLCV diario de un ticker desde Tiingo y lo devuelve en el
    esquema unificado del proyecto.

    Igual que fetch_yfinance/fetch_stooq: nunca lanza excepción, devuelve
    DataFrame vacío si algo falla (sin key, sin red, ticker inexistente).
    """
    api_key = os.environ.get("TIINGO_API_KEY")
    if not api_key:
        print("[tiingo] Falta la variable de entorno TIINGO_API_KEY — se omite esta fuente.")
        return pd.DataFrame(columns=UNIFIED_COLUMNS)

    url = (
        f"{TIINGO_URL.format(ticker=ticker.lower())}"
        f"?startDate={start}&endDate={end}&format=csv&token={api_key}"
    )

    try:
        raw = pd.read_csv(url)
    except Exception as e:
        print(f"[tiingo] Falló la descarga de {ticker}: {e}")
        return pd.DataFrame(columns=UNIFIED_COLUMNS)

    if raw.empty or "close" not in raw.columns:
        return pd.DataFrame(columns=UNIFIED_COLUMNS)

    out = pd.DataFrame({
        "ticker": ticker,
        "fecha": pd.to_datetime(raw["date"]).dt.date,
        "open": raw["open"],
        "high": raw["high"],
        "low": raw["low"],
        "close": raw["close"],
        "volumen": raw["volume"],
        "close_ajustado": raw["adjClose"],
        "fuente": "tiingo",
    })
    return out[UNIFIED_COLUMNS]


if __name__ == "__main__":
    # Prueba manual — necesita TIINGO_API_KEY en el entorno:
    #   python -m src.data.fetch_tiingo
    df = fetch_tiingo("AAPL", "2024-01-01", "2024-01-31")
    print(df.head())
    print(f"\nFilas obtenidas: {len(df)}")
