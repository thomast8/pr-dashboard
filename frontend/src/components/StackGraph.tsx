/** Stack dependency graph with SVG arrows and auto-layout.
 *
 * Layout: PRs arranged in rows of up to COLS_PER_ROW cards.
 * Arrows connect parent → child following the stack order.
 * Same-row: cubic bezier. Cross-row: L-shaped path.
 */

import { useMemo } from 'react';
import type { StackMember } from '../api/client';
import { StatusDot } from './StatusDot';
import styles from './StackGraph.module.css';

interface Props {
  members: StackMember[];
  selectedPrId: number | null;
  onSelectPr: (id: number | null) => void;
}

const CARD_W = 210;
const CARD_H = 85;
const GAP_X = 40;
const GAP_Y = 30;
const COLS_PER_ROW = 6;
const PAD = 20;

interface CardPos {
  x: number;
  y: number;
  member: StackMember;
}

export function StackGraph({ members, selectedPrId, onSelectPr }: Props) {
  const layout = useMemo(() => {
    const positions: CardPos[] = members.map((m, i) => {
      const col = i % COLS_PER_ROW;
      const row = Math.floor(i / COLS_PER_ROW);
      return {
        x: PAD + col * (CARD_W + GAP_X),
        y: PAD + row * (CARD_H + GAP_Y),
        member: m,
      };
    });
    return positions;
  }, [members]);

  // Build id → position lookup
  const posMap = useMemo(() => {
    const map = new Map<number, CardPos>();
    layout.forEach((pos) => map.set(pos.member.pr.id, pos));
    return map;
  }, [layout]);

  // Compute SVG arrows
  const arrows = useMemo(() => {
    return layout
      .filter((pos) => pos.member.parent_pr_id != null)
      .map((pos) => {
        const parent = posMap.get(pos.member.parent_pr_id!);
        if (!parent) return null;

        const fromX = parent.x + CARD_W;
        const fromY = parent.y + CARD_H / 2;
        const toX = pos.x;
        const toY = pos.y + CARD_H / 2;

        // Same row: simple bezier
        if (Math.abs(fromY - toY) < 5) {
          const cx = (fromX + toX) / 2;
          return {
            key: `${parent.member.pr.id}-${pos.member.pr.id}`,
            d: `M ${fromX} ${fromY} C ${cx} ${fromY}, ${cx} ${toY}, ${toX} ${toY}`,
          };
        }

        // Cross row: L-shaped path (right, down, then left to target)
        const midX = fromX + GAP_X / 2;
        return {
          key: `${parent.member.pr.id}-${pos.member.pr.id}`,
          d: `M ${fromX} ${fromY} L ${midX} ${fromY} L ${midX} ${toY} L ${toX} ${toY}`,
        };
      })
      .filter(Boolean) as { key: string; d: string }[];
  }, [layout, posMap]);

  const maxRow = Math.floor((members.length - 1) / COLS_PER_ROW);
  const maxCol = Math.min(members.length - 1, COLS_PER_ROW - 1);
  const svgW = PAD * 2 + (maxCol + 1) * (CARD_W + GAP_X);
  const svgH = PAD * 2 + (maxRow + 1) * (CARD_H + GAP_Y);

  return (
    <div className={styles.graphArea}>
      <div className={styles.graphContainer} style={{ width: svgW, height: svgH }}>
        {/* SVG arrows layer */}
        <svg className={styles.svg} width={svgW} height={svgH}>
          <defs>
            <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
              <polygon points="0 0, 8 3, 0 6" fill="var(--border-hover)" />
            </marker>
          </defs>
          {arrows.map((a) => (
            <path
              key={a.key}
              d={a.d}
              className={styles.arrowPath}
              markerEnd="url(#arrowhead)"
            />
          ))}
        </svg>

        {/* PR cards layer */}
        {layout.map((pos) => {
          const pr = pos.member.pr;
          const isSelected = selectedPrId === pr.id;
          return (
            <div
              key={pr.id}
              className={`${styles.card} ${isSelected ? styles.cardSelected : ''}`}
              style={{ left: pos.x, top: pos.y, width: CARD_W, height: CARD_H }}
              onClick={() => onSelectPr(isSelected ? null : pr.id)}
            >
              <div className={styles.cardHeader}>
                <span className={styles.position}>{pos.member.position + 1}</span>
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
            </div>
          );
        })}
      </div>
    </div>
  );
}
