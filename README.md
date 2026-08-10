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
| `src/data/fetch_stooq.py` | Fuente de respaldo, mismo esquema unificado |
| `src/data/reconcile.py` | Compara fuentes y resuelve discrepancias automáticamente (umbrales 0.5% / 5%) |

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

## Bitácora de avance

Registro paso a paso del progreso — sirve como historial legible ya que
la subida a GitHub se hizo por upload web, sin conservar los commits
individuales originales.

1. **Diseño del dataset (Fase 1) cerrado** — mercado (S&P 500), fuentes en cascada (yfinance → Stooq → Tiingo → Alpha Vantage), umbrales de reconciliación (0.5% / 5%), esquema unificado. Documentado en `Paper1_Repaso_Conceptos.md`.
2. **Estructura del repo creada** — `src/`, `src/data/`, `data_cache/`, git inicializado.
3. **`config.py`** — configuración centralizada (fechas, umbrales, rutas).
4. **`fetch_yfinance.py`** — adaptador de yfinance al esquema unificado. Manejo de errores probado en vivo (el sandbox no tiene salida a Yahoo Finance — confirmó que el fallo se atrapa bien y devuelve tabla vacía en vez de romper el programa). **Pendiente: confirmar que trae datos reales, correr en tu máquina.**
5. **`cache.py`** — guardar/recuperar en formato parquet. Probado con datos sintéticos, funcionó correcto.
6. **`fetch_stooq.py`** — adaptador de Stooq como respaldo. **Pendiente: confirmar en tu máquina, mismo motivo que yfinance.**
7. **`reconcile.py`** — reconciliación automática entre fuentes (sin revisión manual). Probado con 3 casos sintéticos a propósito (acuerdo cercano, acuerdo flexible, descarte por diferencia >5%) — los tres salieron correctos.
8. **Repo subido a GitHub** — `github.com/JuliobaCR/alpha-discovery`, verificado por clonación directa que el contenido subido coincide exactamente con lo construido.

### Lo que sigue
9. Constituyentes históricos del S&P 500 (evitar sesgo de supervivencia).
10. Orquestador del pipeline completo (`build_dataset.py`) — junta todo en un solo comando.

## Estado (checklist rápido)

- [x] Estructura del repo
- [x] Fetcher de yfinance + esquema unificado
- [x] Capa de caché (parquet)
- [x] Fetcher de Stooq (respaldo)
- [x] Reconciliación automática entre fuentes (probada con datos sintéticos — ver `src/data/reconcile.py`)
- [ ] Constituyentes históricos del S&P 500 (evitar sesgo de supervivencia)
- [ ] Orquestador del pipeline completo (`build_dataset.py`)
