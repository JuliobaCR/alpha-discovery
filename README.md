# alpha-discovery — Pipeline de datos (Fase 1)

Pipeline de adquisición de datos para el Paper 1 (GECCO 2027):
*"LLM-Guided Variation Operators for Multi-Objective Evolutionary Alpha Discovery"*.

## Qué hace este código, en una frase

Descarga precios diarios (OHLCV) del S&P 500 de varias fuentes gratuitas,
las reconcilia automáticamente entre sí, y guarda un dataset unificado
y cacheado en disco — listo para que el motor evolutivo (Fase 2) lo consuma.

## Por qué existe cada pieza

| Archivo | Responsabilidad |
|---|---|
| `src/config.py` | Todas las decisiones de diseño en un solo lugar (mercado, fechas, umbrales) |
| `src/data/fetch_yfinance.py` | Habla con yfinance, traduce a nuestro esquema unificado |
| `src/data/cache.py` | Guarda/recupera datos ya descargados en formato parquet |
| `src/data/fetch_stooq.py` | *(siguiente paso)* fuente de respaldo |
| `src/data/reconcile.py` | *(siguiente paso)* compara fuentes y resuelve discrepancias automáticamente |

## Cómo correrlo

```bash
pip install -r requirements.txt
python -m src.data.fetch_yfinance   # prueba rápida con AAPL, un mes
```

## ⚠️ Nota importante

Este código se escribió y se probó parcialmente en un entorno sin acceso
a APIs financieras externas (solo a repositorios de paquetes). La lógica
de caché y reconciliación ya está probada con datos sintéticos — la
descarga real de yfinance necesita correrse en tu máquina para confirmar
que trae datos de verdad.

## Estado

- [x] Estructura del repo
- [x] Fetcher de yfinance + esquema unificado
- [x] Capa de caché (parquet)
- [x] Fetcher de Stooq (respaldo)
- [x] Reconciliación automática entre fuentes (probada con datos sintéticos — ver `src/data/reconcile.py`)
- [ ] Constituyentes históricos del S&P 500 (evitar sesgo de supervivencia)
- [ ] Orquestador del pipeline completo (`build_dataset.py`)
