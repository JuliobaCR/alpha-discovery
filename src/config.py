"""
Configuración central del pipeline de datos.

Todo lo que sea un "número mágico" o una decisión de diseño vive aquí,
no enterrado dentro de las funciones — así, cuando cambies el mercado
o el rango de fechas, solo tocas este archivo.
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # carga .env (ej. TIINGO_API_KEY) si existe — no falla si no existe

# --- Mercado y rango histórico ---
MARKET = "S&P 500"
START_DATE = "2010-01-01"   # ~15 años hacia atrás desde hoy, cubre 2020 (COVID) y 2022
END_DATE = "2025-12-31"

# --- Fuentes, en orden de prioridad (cascada) ---
# El pipeline intenta la primera; si falta un dato, cae a la siguiente.
# Stooq quedó fuera: empezó a bloquear descargas programáticas con un
# challenge anti-bot (confirmado en vivo, no es un problema de nuestro
# código) — fetch_stooq.py se deja en el repo por si se puede resolver
# más adelante, pero build_dataset.py ya no lo usa.
SOURCE_PRIORITY = ["yfinance", "tiingo"]  # alpha_vantage se agrega después si hace falta otro respaldo

# --- Umbrales de reconciliación automática (sin revisión manual) ---
DIFF_THRESHOLD_ACCEPT = 0.005   # 0.5% — diferencia aceptable entre fuentes, se promedia o prioriza
DIFF_THRESHOLD_DISCARD = 0.05   # 5%   — diferencia inaceptable, el dato se descarta (no se adivina)

# --- Rutas ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "data_cache"
CACHE_DIR.mkdir(exist_ok=True)

EXTERNAL_DIR = CACHE_DIR / "external"  # insumos crudos de terceros (ej. lista de constituyentes) — se versionan en git, a diferencia de los .parquet regenerables
EXTERNAL_DIR.mkdir(exist_ok=True)

# --- Esquema unificado que toda fuente debe producir ---
UNIFIED_COLUMNS = ["ticker", "fecha", "open", "high", "low", "close", "volumen", "close_ajustado", "fuente"]

# --- Universo histórico de tickers (constituyentes del S&P 500) ---
# Fuente documentada y citable: historial de cambios del índice derivado de
# Wikipedia, mantenido activamente. Ver src/data/fetch_constituents.py.
CONSTITUENTS_URL = "https://raw.githubusercontent.com/fja05680/sp500/master/S%26P%20500%20Historical%20Components%20%26%20Changes.csv"

# --- CPI (para medir Return/Max Drawdown/Calmar en términos reales) ---
# CPIAUCSL = CPI-U, todos los artículos, EE.UU., mensual, ajustada
# estacionalmente. Fuente: FRED (Reserva Federal), descarga directa sin
# API key. Ver src/data/fetch_cpi.py.
CPI_SERIES_ID = "CPIAUCSL"
CPI_URL = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={CPI_SERIES_ID}"

# --- Orquestador (build_dataset.py) ---
# Pausa entre tickers para no disparar rate-limiting al recorrer el universo
# completo (cientos de tickers). Valor conservador de partida — calibrar en
# tu máquina si corre demasiado lento o si igual te limitan la tasa.
BUILD_DATASET_DELAY_SECONDS = 0.5
