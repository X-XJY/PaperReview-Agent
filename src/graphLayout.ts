/** Original deterministic layout; positions never imply missing proof edges. */
export function dependencyPositions(
  ids: string[],
  edges: { source: string; target: string }[],
) {
  const incoming = new Map(ids.map((id) => [id, 0]));
  const children = new Map(ids.map((id) => [id, new Set<string>()]));
  const levels = new Map(ids.map((id) => [id, 0]));
  for (const edge of edges) {
    if (
      !incoming.has(edge.source) ||
      !incoming.has(edge.target) ||
      children.get(edge.source)!.has(edge.target)
    )
      continue;
    children.get(edge.source)!.add(edge.target);
    incoming.set(edge.target, incoming.get(edge.target)! + 1);
  }
  const queue = ids.filter((id) => incoming.get(id) === 0);
  for (let i = 0; i < queue.length; i++) {
    const source = queue[i];
    for (const target of children.get(source)!) {
      levels.set(
        target,
        Math.max(levels.get(target)!, levels.get(source)! + 1),
      );
      incoming.set(target, incoming.get(target)! - 1);
      if (incoming.get(target) === 0) queue.push(target);
    }
  }
  if (queue.length !== ids.length) return null;
  const rows = new Map<number, string[]>();
  for (const id of ids) {
    const level = levels.get(id)!;
    rows.set(level, [...(rows.get(level) || []), id]);
  }
  const width = Math.max(1, ...Array.from(rows.values(), (row) => row.length));
  const positions: Record<string, { x: number; y: number }> = {};
  for (const [level, row] of rows) {
    row.forEach((id, index) => {
      positions[id] = {
        x: (index + (width - row.length) / 2) * 220,
        y: level * 160,
      };
    });
  }
  return positions;
}
