/** Dependency graph showing PRs as cards with SVG arrows.
 *
 * Layout: builds parent-child edges from head_ref/base_ref relationships,
 * then BFS from roots to assign columns. Standalone PRs shown in a grid below.
 */

import { useMemo } from 'react';
import type { PRSummary, Stack } from '../api/client';
import { StatusDot } from './StatusDot';
import styles from './DependencyGraph.module.css';

interface Props {
  prs: PRSummary[];
  stacks: Stack[];
  highlightStackId: number | null;
  selectedPrId: number | null;
  onSelectPr: (id: number | null) => void;
}

const CARD_W = 210;
const CARD_H = 85;
const GAP_X = 50;
const GAP_Y = 30;
const PAD = 20;

interface CardPos {
  x: number;
  y: number;
  pr: PRSummary;
}

interface Arrow {
  key: string;
  d: string;
  dimmed: boolean;
}

export function DependencyGraph({ prs, stacks, highlightStackId, selectedPrId, onSelectPr }: Props) {
  // Build highlighted PR set
  const highlightedPrIds = useMemo(() => {
    if (highlightStackId == null) return null;
    const stack = stacks.find((s) => s.id === highlightStackId);
    if (!stack) return null;
    return new Set(stack.members.map((m) => m.pr.id));
  }, [stacks, highlightStackId]);

  // Build graph edges from head_ref/base_ref
  const { layout, standalones, arrows, svgW, svgH } = useMemo(() => {
    // Map head_ref -> PR (a PR's head_ref is its branch name)
    const headRefToPr = new Map<string, PRSummary>();
    for (const pr of prs) {
      headRefToPr.set(pr.head_ref, pr);
    }

    // Build parent -> children map
    // If PR's base_ref matches another PR's head_ref, that other PR is the parent
    const children = new Map<number, PRSummary[]>();
    const parentOf = new Map<number, PRSummary>();

    for (const pr of prs) {
      const parent = headRefToPr.get(pr.base_ref);
      if (parent && parent.id !== pr.id) {
        parentOf.set(pr.id, parent);
        const siblings = children.get(parent.id) || [];
        siblings.push(pr);
        children.set(parent.id, siblings);
      }
    }

    // Find roots: PRs that have children but no parent in the map
    const roots: PRSummary[] = [];
    const standalone: PRSummary[] = [];

    for (const pr of prs) {
      const hasChildren = children.has(pr.id);
      const hasParent = parentOf.has(pr.id);
      if (!hasParent && hasChildren) {
        roots.push(pr);
      } else if (!hasParent && !hasChildren) {
        standalone.push(pr);
      }
      // PRs with parents are placed via BFS
    }

    // BFS layout: column = depth from root, rows tracked per column
    const positions: CardPos[] = [];
    const rowsPerCol = new Map<number, number>();

    function getNextRow(col: number): number {
      const row = rowsPerCol.get(col) || 0;
      rowsPerCol.set(col, row + 1);
      return row;
    }

    const queue: { pr: PRSummary; col: number }[] = [];
    for (const root of roots) {
      queue.push({ pr: root, col: 0 });
    }

    const visited = new Set<number>();
    while (queue.length > 0) {
      const { pr, col } = queue.shift()!;
      if (visited.has(pr.id)) continue;
      visited.add(pr.id);

      const row = getNextRow(col);
      positions.push({
        x: PAD + col * (CARD_W + GAP_X),
        y: PAD + row * (CARD_H + GAP_Y),
        pr,
      });

      const kids = children.get(pr.id) || [];
      for (const child of kids) {
        if (!visited.has(child.id)) {
          queue.push({ pr: child, col: col + 1 });
        }
      }
    }

    // Position map for arrow computation
    const posMap = new Map<number, CardPos>();
    positions.forEach((pos) => posMap.set(pos.pr.id, pos));

    // Compute arrows
    const arrowList: Arrow[] = [];
    for (const pos of positions) {
      const parent = parentOf.get(pos.pr.id);
      if (!parent) continue;
      const parentPos = posMap.get(parent.id);
      if (!parentPos) continue;

      const fromX = parentPos.x + CARD_W;
      const fromY = parentPos.y + CARD_H / 2;
      const toX = pos.x;
      const toY = pos.y + CARD_H / 2;

      let d: string;
      if (Math.abs(fromY - toY) < 5) {
        const cx = (fromX + toX) / 2;
        d = `M ${fromX} ${fromY} C ${cx} ${fromY}, ${cx} ${toY}, ${toX} ${toY}`;
      } else {
        const midX = fromX + GAP_X / 2;
        d = `M ${fromX} ${fromY} L ${midX} ${fromY} L ${midX} ${toY} L ${toX} ${toY}`;
      }

      const dimmed = highlightedPrIds != null &&
        (!highlightedPrIds.has(pos.pr.id) || !highlightedPrIds.has(parent.id));

      arrowList.push({ key: `${parent.id}-${pos.pr.id}`, d, dimmed });
    }

    // SVG dimensions
    let maxX = 0;
    let maxY = 0;
    for (const pos of positions) {
      maxX = Math.max(maxX, pos.x + CARD_W);
      maxY = Math.max(maxY, pos.y + CARD_H);
    }

    return {
      layout: positions,
      standalones: standalone,
      arrows: arrowList,
      svgW: maxX + PAD,
      svgH: maxY + PAD,
    };
  }, [prs, highlightedPrIds]);

  const isDimmed = (prId: number) =>
    highlightedPrIds != null && !highlightedPrIds.has(prId);

  function renderCard(pr: PRSummary) {
    return (
      <>
        <div className={styles.cardHeader}>
          <a
            href={pr.html_url}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.prNumber}
            onClick={(e) => e.stopPropagation()}
          >
            #{pr.number}
          </a>
          {pr.draft && <span className={styles.draftBadge}>Draft</span>}
        </div>
        <div className={styles.cardTitle}>{pr.title}</div>
        <div className={styles.cardFooter}>
          <StatusDot status={pr.ci_status} title={`CI: ${pr.ci_status}`} size={7} />
          <StatusDot status={pr.review_state} title={`Review: ${pr.review_state}`} size={7} />
          <span className={styles.cardDiff}>
            <span className={styles.add}>+{pr.additions}</span>
            <span className={styles.del}>-{pr.deletions}</span>
          </span>
        </div>
      </>
    );
  }

  return (
    <div className={styles.graphArea}>
      {layout.length > 0 && (
        <div className={styles.graphContainer} style={{ width: svgW, height: svgH }}>
          <svg className={styles.svg} width={svgW} height={svgH}>
            <defs>
              <marker id="dep-arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                <polygon points="0 0, 8 3, 0 6" fill="var(--border-hover)" />
              </marker>
            </defs>
            {arrows.map((a) => (
              <path
                key={a.key}
                d={a.d}
                className={`${styles.arrowPath} ${a.dimmed ? styles.arrowDimmed : ''}`}
                markerEnd="url(#dep-arrowhead)"
              />
            ))}
          </svg>

          {layout.map((pos) => {
            const isSelected = selectedPrId === pos.pr.id;
            const dimmed = isDimmed(pos.pr.id);
            return (
              <div
                key={pos.pr.id}
                className={`${styles.card} ${isSelected ? styles.cardSelected : ''} ${dimmed ? styles.cardDimmed : ''}`}
                style={{ left: pos.x, top: pos.y, width: CARD_W, height: CARD_H }}
                onClick={() => onSelectPr(isSelected ? null : pos.pr.id)}
              >
                {renderCard(pos.pr)}
              </div>
            );
          })}
        </div>
      )}

      {standalones.length > 0 && (
        <div className={styles.standaloneSection}>
          <div className={styles.standaloneLabel}>Standalone PRs</div>
          <div className={styles.standaloneGrid}>
            {standalones.map((pr) => {
              const isSelected = selectedPrId === pr.id;
              const dimmed = isDimmed(pr.id);
              return (
                <div
                  key={pr.id}
                  className={`${styles.standaloneCard} ${isSelected ? styles.cardSelected : ''} ${dimmed ? styles.cardDimmed : ''}`}
                  onClick={() => onSelectPr(isSelected ? null : pr.id)}
                >
                  {renderCard(pr)}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
