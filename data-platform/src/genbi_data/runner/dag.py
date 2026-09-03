"""DAG de modelos: orden topológico y detección de ciclos (PRD E2-H1-T2.1)."""

from __future__ import annotations

from collections import defaultdict, deque


def topological_order(names: list[str], depends_on: dict[str, list[str]]) -> list[str]:
    """Orden topológico de ``names`` dado ``depends_on`` (nombre -> dependencias).

    Lanza ``ValueError`` si existe un ciclo.
    """
    graph: dict[str, list[str]] = defaultdict(list)
    indegree: dict[str, int] = {name: 0 for name in names}
    for name in names:
        for dep in depends_on.get(name, []):
            if dep not in names:
                raise ValueError(f"'{name}' depende de '{dep}' que no está declarado")
            graph[dep].append(name)
            indegree[name] += 1

    queue: deque[str] = deque(name for name, deg in indegree.items() if deg == 0)
    order: list[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for nxt in graph[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    if len(order) != len(names):
        cyclic = [n for n in names if indegree[n] > 0]
        raise ValueError(f"ciclo detectado entre: {', '.join(sorted(cyclic))}")
    return order