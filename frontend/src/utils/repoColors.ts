/** Deterministic color assignment for repos based on sorted index. */

const REPO_COLORS = [
  '#61dafb', // cyan
  '#a78bfa', // purple
  '#fb923c', // orange
  '#4ade80', // green
  '#f472b6', // pink
  '#facc15', // yellow
  '#38bdf8', // sky
  '#c084fc', // violet
  '#34d399', // emerald
  '#fb7185', // rose
];

/**
 * Build a map from repo full_name to color, assigning colors by sorted index.
 * Guarantees unique colors for up to 10 repos.
 */
export function buildRepoColorMap(fullNames: string[]): Map<string, string> {
  const sorted = [...fullNames].sort();
  const map = new Map<string, string>();
  for (let i = 0; i < sorted.length; i++) {
    map.set(sorted[i], REPO_COLORS[i % REPO_COLORS.length]);
  }
  return map;
}

/** Fallback: hash-based color for contexts without the full repo list. */
export function repoColor(fullName: string): string {
  let hash = 0;
  for (const c of fullName) hash = ((hash << 5) - hash + c.charCodeAt(0)) | 0;
  return REPO_COLORS[Math.abs(hash) % REPO_COLORS.length];
}
