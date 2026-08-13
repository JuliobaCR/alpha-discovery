# alpha-discovery — Pipeline de datos (Fase 1 completa)

Pipeline de adquisición de datos para el Paper 1 (GECCO 2027):
*"LLM-Guided Variation Operators for Multi-Objective Evolutionary Alpha Discovery"*.

## Qué hace este código, en una frase

Descarga precios diarios (OHLCV) del universo histórico completo del S&P 500
(activos + deslistados, para evitar sesgo de supervivencia), las reconcilia
automáticamente entre fuentes, y guarda un dataset unificado y cacheado en
disco — listo para que el motor evolutivo (Fase 2) lo consuma.

## Por qué existe cada pieza

| Archivo | Responsabilidad |
|---|---|
| `src/config.py` | Todas las decisiones de diseño en un solo lugar (mercado, fechas, umbrales, rutas) |
| `src/data/fetch_yfinance.py` | Habla con yfinance, traduce a nuestro esquema unificado — fuente principal |
| `src/data/fetch_tiingo.py` | Fuente de respaldo activa, mismo esquema unificado (necesita `TIINGO_API_KEY`) |
| `src/data/fetch_stooq.py` | Fuera de uso — Stooq bloquea descargas programáticas con un challenge anti-bot. Se deja el código por si se resuelve más adelante. |
| `src/data/fetch_constituents.py` | Universo histórico de tickers del S&P 500 (activos + deslistados), evita sesgo de supervivencia |
| `src/data/fetch_cpi.py` | CPI de EE.UU. (FRED) — para medir Return/Max Drawdown/Calmar en términos reales en Fase 2 |
| `src/data/cache.py` | Guarda/recupera datos ya descargados en formato parquet, por ticker y por fuente |
| `src/data/reconcile.py` | Compara fuentes y resuelve discrepancias automáticamente (umbrales 0.5% / 5%) |
| `src/data/build_dataset.py` | Orquestador: junta universo + fetch + caché + reconciliación en un solo comando |

## Cómo correrlo

```bash
pip install -r requirements.txt

# Tiingo necesita una API key gratuita — ponla en un .env local (ya está
# en .gitignore, nunca se sube):
echo "TIINGO_API_KEY=tu_key_aqui" > .env

python -m src.data.build_dataset   # corre el pipeline completo
```

Para pruebas rápidas sin correr el universo completo (puede tardar horas):

```python
from src.data.build_dataset import build_dataset
build_dataset(start="2024-01-01", end="2024-01-31", tickers={"AAPL", "MSFT"})
```

## Bitácora de avance

Registro paso a paso del progreso — sirve como historial legible ya que
la subida original a GitHub se hizo por upload web, sin conservar los
commits individuales de esa primera versión.

1. **Diseño del dataset (Fase 1) cerrado** — mercado (S&P 500), umbrales de reconciliación (0.5% / 5%), esquema unificado. Documentado en `Paper1_Repaso_Conceptos.md`.
2. **Estructura del repo creada** — `src/`, `src/data/`, `data_cache/`, git inicializado.
3. **`config.py`** — configuración centralizada (fechas, umbrales, rutas).
4. **`fetch_yfinance.py`** — adaptador de yfinance. **Confirmado con datos reales.**
5. **`cache.py`** — guardar/recuperar en formato parquet. Probado con datos sintéticos y reales.
6. **`fetch_stooq.py`** — adaptador de Stooq. **Descartado como fuente activa**: Stooq empezó a bloquear descargas programáticas con un challenge JavaScript anti-bot (confirmado en vivo, no es un problema de nuestro código). Se reemplazó por Tiingo.
7. **`reconcile.py`** — reconciliación automática entre fuentes. Probado con datos sintéticos y con datos reales (yfinance + Tiingo, ~65% de acuerdo cercano en una muestra).
8. **Repo subido a GitHub** — `github.com/JuliobaCR/alpha-discovery`, con historial de commits real desde entonces.
9. **`fetch_constituents.py`** — universo histórico de tickers (fuente: `fja05680/sp500`, CSV versionado localmente para reproducibilidad). **Confirmado: 694 tickers históricos (2010-2025) vs. 504 vigentes hoy.**
10. **`fetch_tiingo.py`** — reemplaza a Stooq como fuente de respaldo. **Confirmado con datos reales y API key propia.**
11. **`build_dataset.py`** — orquestador completo: universo → fetch ambas fuentes → caché por (ticker, fuente) → reconciliación → dataset final + reporte agregado (`sp500_dataset_report.json`, con cobertura del universo y % de acuerdo entre fuentes, listo para citar en el paper). **Probado de punta a punta con datos reales.**
12. **`fetch_cpi.py`** — CPI de EE.UU. (FRED, serie CPIAUCSL, sin API key). **Confirmado: 954 observaciones mensuales, 1947 a la fecha.**
13. **Diseño de los 6 objetivos cerrado para Fase 2** (documentado en `Paper1_Repaso_Conceptos.md`, sección 7.1): Return/Sharpe/Sortino/Calmar se calculan como mediana de valores anuales (no promedio del periodo completo) para seleccionar por consistencia y mitigar alpha decay; Return/Max Drawdown/Calmar se calculan en términos reales (deflactados por CPI); split in-sample 2010-2021 / out-of-sample 2022-2025, con walk-forward de alpha decay sobre el frente final.

### Lo que sigue — Fase 2 (motor evolutivo)

14. Motor de backtest: a partir de una fórmula de alpha y el dataset de Fase 1, calcular la serie de retornos del portafolio y los 6 objetivos (con mediana anual + deflactación CPI ya definidas).
15. Representación de alphas como árboles de expresión (GP) + generación de población inicial (Ramped Half-and-Half).
16. Motor de búsqueda NSGA-II + operadores clásicos (brazo control del ablation).
17. Operador de mutación/cruce guiado por LLM (brazo experimental) + validación de salida estructurada.
18. Baselines: MO-CMA-ES, GDE3, Random Search sobre representación de vector de pesos.
19. Protocolo experimental completo: ~30 semillas × 5 configuraciones, métricas EMO (hypervolume, IGD, spread), análisis estadístico (Wilcoxon + Bonferroni).

## Estado (checklist rápido)

**Fase 1 — completa:**
- [x] Estructura del repo
- [x] Fetcher de yfinance (confirmado con datos reales)
- [x] Fetcher de Tiingo (confirmado con datos reales, reemplaza a Stooq)
- [x] Capa de caché (parquet, por ticker y por fuente)
- [x] Reconciliación automática entre fuentes (confirmada con datos reales)
- [x] Universo histórico de tickers del S&P 500 (evita sesgo de supervivencia)
- [x] CPI/FRED (para términos reales en Fase 2)
- [x] Orquestador del pipeline completo (`build_dataset.py`)
- [x] Metodología de los 6 objetivos cerrada (mediana anual, términos reales, split in/out-of-sample)

**Fase 2 — pendiente:**
- [ ] Motor de backtest (calcula los 6 objetivos a partir de una fórmula)
- [ ] Representación de alphas (árboles GP) + población inicial
- [ ] NSGA-II + operadores clásicos
- [ ] Operador guiado por LLM
- [ ] Baselines (MO-CMA-ES, GDE3, Random Search)
- [ ] Protocolo experimental completo + análisis estadístico
