"""
Índice de Precios al Consumidor (CPI) de EE.UU. — insumo para medir
Return, Max Drawdown y Calmar en términos REALES en vez de nominales
(Sharpe, Sortino y Turnover se quedan como están, ver Paper1_Repaso_Conceptos.md).

Por qué importa: si el capital nominal sube solo porque hay inflación (no
porque la estrategia genere valor real), Max Drawdown medido en dólares
nominales se ve más "sano" de lo que realmente es — se pierde poder
adquisitivo sin que se refleje como caída. Deflactar por CPI corrige esto.

Fuente: FRED (Reserva Federal de EE.UU.), serie CPIAUCSL — descarga
directa por CSV, sin API key, mismo patrón que fetch_constituents.py: se
descarga una vez y se versiona localmente (el CPI histórico a veces se
revisa retroactivamente, así que fijar una copia local es lo correcto
para que el dataset del paper no cambie solo porque FRED actualiza una
cifra vieja).

⚠️ Igual que fetch_constituents.py: SÍ puede lanzar excepción si falla la
   descarga y no hay copia local — sin esto no se puede medir ningún
   objetivo en términos reales, así que fallar en silencio sería peor
   que un error ruidoso.
"""

import hashlib
import json
from datetime import datetime, timezone
from urllib.request import urlopen

import pandas as pd

from src.config import CPI_URL, EXTERNAL_DIR

CSV_PATH = EXTERNAL_DIR / "cpi_cpiaucsl.csv"
META_PATH = EXTERNAL_DIR / "cpi_cpiaucsl.meta.json"


def _ensure_local_csv(force_refresh: bool = False) -> None:
    if CSV_PATH.exists() and not force_refresh:
        return

    try:
        with urlopen(CPI_URL, timeout=30) as response:
            raw_bytes = response.read()
    except Exception as e:
        if CSV_PATH.exists():
            print(f"[cpi] Falló refrescar el CSV ({e}); se usa la copia local existente (ver {META_PATH.name}).")
            return
        raise RuntimeError(
            f"No se pudo descargar el CPI desde {CPI_URL} y no hay copia local en "
            f"{CSV_PATH}. Sin este archivo no se puede medir ningún objetivo en "
            f"términos reales — revisa tu conexión e intenta de nuevo."
        ) from e

    CSV_PATH.write_bytes(raw_bytes)
    META_PATH.write_text(json.dumps({
        "source_url": CPI_URL,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "n_bytes": len(raw_bytes),
    }, indent=2))
    print(f"[cpi] Descargado y versionado en {CSV_PATH}")


def get_cpi_series(force_refresh: bool = False) -> pd.Series:
    """
    Serie mensual de CPI, indexada por fecha (primer día de cada mes).
    Uso previsto en Fase 2: para deflactar una curva de capital a
    términos reales, cada fecha se empareja con el CPI del mes vigente
    más reciente (ej. pd.merge_asof con direction="backward") y se aplica
    real = nominal * CPI[fecha_base] / CPI[fecha]. No se implementa esa
    función aquí todavía porque depende de cómo el motor de backtest
    (aún sin construir) represente la curva de capital.
    """
    _ensure_local_csv(force_refresh=force_refresh)
    df = pd.read_csv(CSV_PATH)
    df = df.rename(columns={"observation_date": "date", "CPIAUCSL": "cpi"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["cpi"]).sort_values("date").reset_index(drop=True)
    return df.set_index("date")["cpi"]


if __name__ == "__main__":
    # Prueba manual — córrela tú en tu máquina:
    #   python -m src.data.fetch_cpi
    cpi = get_cpi_series()
    print(f"CPI: {len(cpi)} observaciones mensuales, {cpi.index.min().date()} a {cpi.index.max().date()}")
    print(cpi.tail())
