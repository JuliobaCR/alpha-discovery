"""
Categorías de tipo para los árboles de expresión (Paper1_Repaso_Conceptos.md,
sección 1): clases marcador vacías, usadas solo para que DEAP (gp.Primitive
SetTyped) sepa qué nodos pueden combinarse directamente entre sí.

Combinaciones directas solo dentro de la misma categoría; para cruzar
categorías, pasar por rank() (ver primitives.py) — Bounded es el puente
universal hacia el que apuntan todas las funciones rank_*.
"""


class Price:
    pass


class Bounded:
    pass


class Volatility:
    pass


class Volume:
    pass
