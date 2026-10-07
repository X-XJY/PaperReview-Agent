/** Conservative matching in PDF text order; ambiguous snippets aren't highlighted. */
export function normalizePdfText(text: string) {
  return text
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]/gu, "");
}
export function matchingItems(texts: string[], quote: string): number[] {
  const normalized = texts.map(normalizePdfText),
    whole = normalized.join(""),
    needle = normalizePdfText(quote);
  if (needle.length < 24) return [];
  const anchors =
    needle.length <= 100
      ? [needle]
      : [
          needle.slice(0, 100),
          needle.slice(
            Math.floor((needle.length - 100) / 2),
            Math.floor((needle.length - 100) / 2) + 100,
          ),
          needle.slice(-100),
        ];
  const found = new Set<number>();
  for (const anchor of anchors) {
    const start = whole.indexOf(anchor);
    if (start < 0 || whole.indexOf(anchor, start + 1) !== -1) continue;
    let offset = 0;
    normalized.forEach((part, i) => {
      if (
        part.length &&
        offset < start + anchor.length &&
        offset + part.length > start
      )
        found.add(i);
      offset += part.length;
    });
  }
  return [...found];
}
