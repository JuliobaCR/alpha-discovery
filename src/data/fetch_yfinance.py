"""
Adaptador de yfinance.

Responsabilidad única: hablar con yfinance y devolver los datos en
NUESTRO esquema unificado (ver config.UNIFIED_COLUMNS). Nada más se
entera de cómo yfinance nombra sus columnas por dentro.

⚠️ Nota de entorno: esta función necesita salida de red a Yahoo Finance,
   que no está disponible en el sandbox donde se escribió este código.
   Pruébala en tu propia máquina antes de confiar en que funciona.
"""

import pandas as pd
import yfinance as yf

from src.config import UNIFIED_COLUMNS


def fetch_yfinance(ticker: str, start: str, end: str) -> pd.DataFrame:
    """
    Descarga OHLCV diario de un ticker desde yfinance y lo devuelve
    en el esquema unificado del proyecto.

    Si yfinance no tiene datos para ese ticker/rango, devuelve un
    DataFrame vacío (no lanza excepción) — así el pipeline puede
    seguir con la siguiente fuente sin caerse.
    """
    try:
        raw = yf.download(
            ticker,
            start=start,
            end=end,
            auto_adjust=False,  # queremos close Y close ajustado por separado, no que yfinance los mezcle
            progress=False,
        )
    except Exception as e:
        print(f"[yfinance] Falló la descarga de {ticker}: {e}")
        return pd.DataFrame(columns=UNIFIED_COLUMNS)

    if raw.empty:
        return pd.DataFrame(columns=UNIFIED_COLUMNS)

    # yfinance puede devolver columnas con MultiIndex si pides varios tickers a la vez;
    # aquí asumimos un ticker a la vez para mantenerlo simple y predecible.
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    out = pd.DataFrame({
        "ticker": ticker,
        "fecha": raw.index,
        "open": raw["Open"].values,
        "high": raw["High"].values,
        "low": raw["Low"].values,
        "close": raw["Close"].values,
        "volumen": raw["Volume"].values,
        "close_ajustado": raw["Adj Close"].values,
        "fuente": "yfinance",
    })
    out["fecha"] = pd.to_datetime(out["fecha"]).dt.date
    return out[UNIFIED_COLUMNS]


if __name__ == "__main__":
    # Prueba manual rápida — córrela tú en tu máquina:
    #   python -m src.data.fetch_yfinance
    df = fetch_yfinance("AAPL", "2024-01-01", "2024-01-31")
    print(df.head())
    print(f"\nFilas obtenidas: {len(df)}")
