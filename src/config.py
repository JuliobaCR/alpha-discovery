"""
Configuración central del pipeline de datos.

Todo lo que sea un "número mágico" o una decisión de diseño vive aquí,
no enterrado dentro de las funciones — así, cuando cambies el mercado
o el rango de fechas, solo tocas este archivo.
"""

from pathlib import Path

# --- Mercado y rango histórico ---
MARKET = "S&P 500"
START_DATE = "2010-01-01"   # ~15 años hacia atrás desde hoy, cubre 2020 (COVID) y 2022
END_DATE = "2025-12-31"

# --- Fuentes, en orden de prioridad (cascada) ---
# El pipeline intenta la primera; si falta un dato, cae a la siguiente.
SOURCE_PRIORITY = ["yfinance", "stooq"]  # tiingo y alpha_vantage se agregan después (necesitan API key)

# --- Umbrales de reconciliación automática (sin revisión manual) ---
DIFF_THRESHOLD_ACCEPT = 0.005   # 0.5% — diferencia aceptable entre fuentes, se promedia o prioriza
DIFF_THRESHOLD_DISCARD = 0.05   # 5%   — diferencia inaceptable, el dato se descarta (no se adivina)

# --- Rutas ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "data_cache"
CACHE_DIR.mkdir(exist_ok=True)

# --- Esquema unificado que toda fuente debe producir ---
UNIFIED_COLUMNS = ["ticker", "fecha", "open", "high", "low", "close", "volumen", "close_ajustado", "fuente"]
