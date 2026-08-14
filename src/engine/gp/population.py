"""
Generación de la población inicial — Ramped Half-and-Half (Paper1_Repaso_
Conceptos.md, sección "Representación"): profundidad máxima repartida
entre 2 y 6 por individuo, con la mitad de cada grupo generado por "Full"
y la otra mitad por "Grow" — esto último ya lo hace gp.genHalfAndHalf de
DEAP internamente para un rango de profundidad fijo; el "ramped" (variar
la profundidad a través de la población) se implementa aquí muestreando
max_depth por individuo, porque DEAP no lo hace automáticamente.

La raíz de cada árbol puede ser cualquiera de las 4 categorías (Price,
Bounded, Volatility, Volume son todas señales de alpha válidas para el
motor de backtest, que no distingue categorías) — se muestrea también
por individuo.
"""

import random

from deap import gp

from src.engine.gp.types import Bounded, Price, Volatility, Volume

ROOT_TYPES = [Price, Bounded, Volatility, Volume]


def generate_initial_population(
    n: int,
    pset: gp.PrimitiveSetTyped,
    min_depth: int = 2,
    max_depth: int = 6,
    seed: int | None = None,
) -> list[gp.PrimitiveTree]:
    """
    Devuelve n árboles (gp.PrimitiveTree puros, sin envolver en
    creator.Individual — eso es responsabilidad del futuro motor NSGA-II,
    que decide los pesos/signos de fitness por objetivo).

    seed: si se pasa, dos llamadas con la misma semilla producen
    poblaciones IDÉNTICAS — necesario para que el ablation (fuera de
    alcance de este módulo) pueda generar la misma generación 0 en ambos
    brazos del experimento. DEAP genera con el módulo global `random`, no
    con una instancia inyectable, así que se guarda y restaura el estado
    previo para no dejar efectos colaterales en el resto del proceso.
    """
    prev_state = random.getstate()
    try:
        if seed is not None:
            random.seed(seed)

        population = []
        for _ in range(n):
            depth = random.randint(min_depth, max_depth)
            root_type = random.choice(ROOT_TYPES)
            nodes = gp.genHalfAndHalf(pset, min_=min_depth, max_=depth, type_=root_type)
            population.append(gp.PrimitiveTree(nodes))

        return population
    finally:
        random.setstate(prev_state)


if __name__ == "__main__":
    # Prueba manual: confirma reproducibilidad por semilla, profundidades
    # dentro de [2,6], y mezcla de categorías raíz.
    from src.engine.gp.primitives import build_pset

    pset = build_pset()

    pop_a = generate_initial_population(30, pset, seed=123)
    pop_b = generate_initial_population(30, pset, seed=123)
    pop_c = generate_initial_population(30, pset, seed=999)

    iguales_ab = [str(a) == str(b) for a, b in zip(pop_a, pop_b)]
    print(f"Misma semilla (123 vs 123) -> poblaciones idénticas: {all(iguales_ab)} ({sum(iguales_ab)}/30)")

    iguales_ac = [str(a) == str(c) for a, c in zip(pop_a, pop_c)]
    print(f"Semilla distinta (123 vs 999) -> deberían diferir: {not all(iguales_ac)} (idénticos: {sum(iguales_ac)}/30)")

    depths = [ind.height for ind in pop_a]
    print(f"\nProfundidades (esperado todas en [2,6]): min={min(depths)}, max={max(depths)}")
    print("Distribución:", {d: depths.count(d) for d in sorted(set(depths))})

    # Confirma que el estado global de random NO quedó "contaminado" tras
    # generar con semilla: dos llamadas random.random() después de esto
    # deben seguir siendo impredecibles (no atadas a la semilla 999).
    random.seed()  # solo para no depender de qué corrió antes en este script
    import time
    random.seed(int(time.time() * 1000) % 100000)
    x1 = random.random()
    print(f"\nEstado global de random restaurado correctamente (valor post-generación): {x1:.4f}")
