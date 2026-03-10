/** Prioritize view — cross-repo ranked list of open PRs by priority score. */

import { useQuery } from '@tanstack/react-query';
import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import { api, type PrioritizedPR, type PriorityBreakdown, type RepoSummary, type User } from '../api/client';
import { useCurrentUser } from '../App';
import { PRDetailPanel } from '../components/PRDetailPanel';
import { Tooltip } from '../components/Tooltip';
import { useStore } from '../store/useStore';
import styles from './PrioritizeView.module.css';

function scoreColor(score: number): string {
  if (score >= 70) return 'var(--accent-green)';
  if (score >= 40) return 'var(--accent-amber)';
  return 'var(--accent-red)';
}


function BreakdownTooltip({ breakdown, score }: { breakdown: PriorityBreakdown; score: number }) {
  return (
    <div className={styles.breakdownTooltip}>
      <div className={styles.breakdownTitle}>Score breakdown ({score}/100)</div>
      <div className={styles.breakdownRow}><span>Review readiness</span><span>{breakdown.review}/35</span></div>
      <div className={styles.breakdownRow}><span>CI status</span><span>{breakdown.ci}/25</span></div>
      <div className={styles.breakdownRow}><span>Mergeable</span><span>{breakdown.mergeable}/15</span></div>
      <div className={styles.breakdownRow}><span>Size (inverse)</span><span>{breakdown.size}/10</span></div>
      <div className={styles.breakdownRow}><span>Age</span><span>{breakdown.age}/10</span></div>
      <div className={styles.breakdownRow}><span>Rebase check</span><span>{breakdown.rebase}/5</span></div>
      {breakdown.draft_penalty < 0 && (
        <div className={`${styles.breakdownRow} ${styles.breakdownPenalty}`}>
          <span>Draft penalty</span><span>{breakdown.draft_penalty}</span>
        </div>
      )}
    </div>
  );
}

type ScoreImpact = 'positive' | 'negative' | 'neutral';
type ScoredPhrase = { text: string; tip: string; impact: ScoreImpact; priority: number };

function scoreSummary(b: PriorityBreakdown, reviewState: string): ScoredPhrase[] {
  const phrases: ScoredPhrase[] = [];

  // Review (max 35)
  if (b.review === 35) phrases.push({ text: 'Approved', tip: 'Review approved, ready to merge', impact: 'positive', priority: 6 });
  else if (reviewState === 'reviewed') phrases.push({ text: 'Reviewed', tip: 'Has review comments but not yet approved', impact: 'neutral', priority: 4 });
  else if (reviewState === 'none') phrases.push({ text: 'Awaiting review', tip: 'No reviews yet, needs someone to look at it', impact: 'negative', priority: 6 });
  else if (b.review === 0) phrases.push({ text: 'Changes requested', tip: 'Reviewer requested changes, must be addressed before merge', impact: 'negative', priority: 9 });

  // CI (max 25)
  if (b.ci === 25) phrases.push({ text: 'CI passing', tip: 'All checks passing, safe to merge', impact: 'positive', priority: 3 });
  else if (b.ci === 10) phrases.push({ text: 'CI pending', tip: 'Checks still running, wait for results', impact: 'neutral', priority: 5 });
  else if (b.ci === 0) phrases.push({ text: 'CI failing', tip: 'Checks are failing, must be fixed before merge', impact: 'negative', priority: 8 });

  // Size (max 10)
  if (b.size === 10) phrases.push({ text: 'Small diff', tip: 'Small change, easy to review', impact: 'positive', priority: 1 });
  else if (b.size === 0) phrases.push({ text: 'Very large diff', tip: 'Over 1000 lines changed, hard to review, consider splitting', impact: 'negative', priority: 5 });
  else if (b.size === 2) phrases.push({ text: 'Large diff', tip: '500-1000 lines changed, may be hard to review', impact: 'negative', priority: 4 });

  // Mergeable (max 15)
  if (b.mergeable === 15) phrases.push({ text: 'Clean merge', tip: 'No conflicts, can merge cleanly', impact: 'positive', priority: 2 });
  else if (b.mergeable === 0) phrases.push({ text: 'Has conflicts', tip: 'Merge conflicts detected, needs rebase', impact: 'negative', priority: 7 });

  // Age (max 10)
  if (b.age >= 8) phrases.push({ text: 'Getting stale', tip: 'Open for over a week, aging PRs risk merge conflicts', impact: 'neutral', priority: 3 });

  // Rebase (max 5)
  if (b.rebase === 5) phrases.push({ text: 'Freshly rebased', tip: 'Rebased since last approval, up to date with base branch', impact: 'positive', priority: 1 });

  // Draft penalty
  if (b.draft_penalty < 0) phrases.push({ text: 'Draft', tip: 'Draft PR, not ready for review, large score penalty', impact: 'negative', priority: 10 });

  const order: Record<ScoreImpact, number> = { positive: 0, neutral: 1, negative: 2 };
  phrases.sort((a, b) => order[a.impact] - order[b.impact] || b.priority - a.priority);
  return phrases.slice(0, 4);
}

function ScoringGuide({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <div className={styles.guide}>
      <button className={styles.guideToggle} onClick={onToggle}>
        How scoring works {open ? '\u25B4' : '\u25BE'}
      </button>
      {open && (
        <div className={styles.guideBody}>
          <p>Each PR is scored 0–100 based on how ready it is to review and merge:</p>
          <table className={styles.guideTable}>
            <thead><tr><th>Signal</th><th>Max</th><th>Logic</th></tr></thead>
            <tbody>
              <tr><td>Review readiness</td><td>35</td><td>Approved (35), reviewed (15), no review (15), changes requested (0)</td></tr>
              <tr><td>CI status</td><td>25</td><td>Passing (25), pending (10), unknown (5), failing (0)</td></tr>
              <tr><td>Mergeable</td><td>15</td><td>Clean (15), unstable (8), conflicts/blocked (0)</td></tr>
              <tr><td>Diff size</td><td>10</td><td>Smaller PRs score higher — easier to review, less rebase risk</td></tr>
              <tr><td>Age</td><td>10</td><td>Older PRs rise in priority (linear over 7 days)</td></tr>
              <tr><td>Rebase check</td><td>5</td><td>+5 if rebased since last approval (needs re-review)</td></tr>
              <tr><td>Draft</td><td>-30</td><td>Penalty for draft PRs (not ready for review)</td></tr>
            </tbody>
          </table>
          <p><strong>Manual priority</strong> overrides score-based ordering. High-priority PRs always appear at the top, low-priority at the bottom. Within each tier, PRs are sorted by automated score.</p>
          <p><strong>Stacked PRs</strong> are ordered parent-before-child — you review the base of the stack first. The stack&apos;s position in the queue is determined by the root PR&apos;s score.</p>
          <p>Hover over any score bar to see the full breakdown. Set priority from the PR detail panel.</p>
        </div>
      )}
    </div>
  );
}

export function PrioritizeView() {
  const { selectedPrNumber, selectPr, selectedRepoId, setSelectedRepoId } = useStore();
  const { user: currentUser } = useCurrentUser();
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  const [filterRepoId, setFilterRepoId] = useState<number | undefined>(undefined);
  const [guideOpen, setGuideOpen] = useState(false);

  // Filter state
  const [reviewerFilter, setReviewerFilter] = useState('');

  // Dropdown open/close state
  const [repoDropdownOpen, setRepoDropdownOpen] = useState(false);
  const [reviewerDropdownOpen, setReviewerDropdownOpen] = useState(false);

  // Dropdown refs
  const repoDropdownRef = useRef<HTMLDivElement>(null);
  const reviewerDropdownRef = useRef<HTMLDivElement>(null);

  // Default reviewer to "Me" once currentUser loads
  const defaultedReviewer = useRef(false);
  useEffect(() => {
    if (currentUser && !defaultedReviewer.current) {
      defaultedReviewer.current = true;
      setReviewerFilter('__me__');
    }
  }, [currentUser]);

  const hasActiveFilters = reviewerFilter !== (currentUser ? '__me__' : '');

  const clearAllFilters = () => {
    setReviewerFilter(currentUser ? '__me__' : '');
  };

  // Click-outside handler for all dropdowns
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (repoDropdownRef.current && !repoDropdownRef.current.contains(e.target as Node)) setRepoDropdownOpen(false);
      if (reviewerDropdownRef.current && !reviewerDropdownRef.current.contains(e.target as Node)) setReviewerDropdownOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const { data: repos } = useQuery({
    queryKey: ['repos'],
    queryFn: () => api.listRepos(),
  });

  const { data: items, isLoading } = useQuery({
    queryKey: ['prioritized', filterRepoId],
    queryFn: () => api.listPrioritized(filterRepoId),
    refetchInterval: 30_000,
  });

  const { data: team } = useQuery({
    queryKey: ['team'],
    queryFn: api.listTeam,
  });
  const activeTeam = team?.filter((m: User) => m.is_active) || [];

  // Collect all GitHub logins belonging to the current user
  const myLogins = useMemo(() => {
    if (!currentUser) return new Set<string>();
    const me = activeTeam.find((m: User) => m.id === currentUser.id);
    const logins = new Set<string>();
    if (me) {
      logins.add(me.login);
      for (const acct of me.linked_accounts || []) {
        logins.add(acct.login);
      }
    } else {
      logins.add(currentUser.login);
    }
    return logins;
  }, [currentUser, activeTeam]);

  // Build GitHub login → { avatar, displayName } from team members + linked accounts
  const authorInfoMap = useMemo(() => {
    const map = new Map<string, { avatar: string | null; displayName: string }>();
    for (const m of activeTeam) {
      const displayName = m.name || m.login;
      for (const acct of m.linked_accounts || []) {
        map.set(acct.login, { avatar: acct.avatar_url, displayName });
      }
      if (!map.has(m.login)) {
        map.set(m.login, { avatar: m.avatar_url, displayName });
      }
    }
    return map;
  }, [activeTeam]);

  const allPrs = items || [];

  // Derive reviewer options from unfiltered data
  const reviewerPeopleMap = useMemo(() => {
    const map = new Map<string, { login: string; avatar: string | null }>();
    for (const item of allPrs) {
      for (const r of item.pr.github_requested_reviewers || []) {
        if (!map.has(r.login)) {
          map.set(r.login, { login: r.login, avatar: r.avatar_url });
        }
      }
    }
    return map;
  }, [allPrs]);
  const reviewers = [...reviewerPeopleMap.values()].sort((a, b) => a.login.localeCompare(b.login));

  // Client-side filtering: reviewer only
  let prs = allPrs;
  if (reviewerFilter === '__me__') {
    prs = prs.filter((item) =>
      (item.pr.github_requested_reviewers || []).some((r) => myLogins.has(r.login)),
    );
  } else if (reviewerFilter) {
    prs = prs.filter((item) =>
      (item.pr.github_requested_reviewers || []).some((r) => r.login === reviewerFilter),
    );
  }

  if (isLoading) return <div className={styles.loading}>Loading prioritized PRs...</div>;

  const readyCount = prs.filter((p) => p.priority_score >= 70 && !p.blocked_by_pr_id).length;
  const needsAttentionCount = prs.filter((p) => p.priority_score < 40).length;

  function handleSelectPr(item: PrioritizedPR) {
    setSelectedRepoId(item.repo_id);
    selectPr(item.pr.number);
  }

  // Reviewer filter icon
  const reviewerIcon = <svg className={styles.filterIcon} viewBox="0 0 16 16" fill="currentColor"><path d="M8 3C4.5 3 1.7 5.1.5 8c1.2 2.9 4 5 7.5 5s6.3-2.1 7.5-5c-1.2-2.9-4-5-7.5-5zm0 8a3 3 0 110-6 3 3 0 010 6zm0-5a2 2 0 100 4 2 2 0 000-4z"/></svg>;

  return (
    <div className={styles.container}>
      <div className={styles.content}>
        <div className={styles.header}>
          <h2 className={styles.title}>Priority Queue</h2>
          <div className={styles.summaryBar}>
            <span className={styles.summaryItem}>
              <span className={styles.summaryCount}>{prs.length}</span> open
            </span>
            <span className={`${styles.summaryItem} ${styles.summaryGreen}`}>
              <span className={styles.summaryCount}>{readyCount}</span> ready to merge
            </span>
            <span className={`${styles.summaryItem} ${styles.summaryRed}`}>
              <span className={styles.summaryCount}>{needsAttentionCount}</span> needs attention
            </span>
          </div>
        </div>

        <div className={styles.filters}>
          {/* 1. Repo */}
          <Tooltip text="Filter by repository" position="bottom" disabled={repoDropdownOpen}>
            <div className={styles.filterDropdown} ref={repoDropdownRef}>
              <button
                className={`${styles.filterTrigger} ${styles.repoTrigger}`}
                onClick={() => setRepoDropdownOpen(!repoDropdownOpen)}
              >
                <span>{filterRepoId ? (repos || []).find((r: RepoSummary) => r.id === filterRepoId)?.full_name ?? 'All repos' : 'All repos'}</span>
                <span className={styles.filterChevron}>{repoDropdownOpen ? '\u25B4' : '\u25BE'}</span>
              </button>
              {repoDropdownOpen && (
                <div className={styles.filterMenu}>
                  <div
                    className={`${styles.filterMenuItem} ${filterRepoId === undefined ? styles.filterMenuItemActive : ''}`}
                    onClick={() => { setFilterRepoId(undefined); setRepoDropdownOpen(false); }}
                  >
                    <span>All repos</span>
                  </div>
                  {Object.entries(
                    (repos || []).reduce<Record<string, RepoSummary[]>>((groups, r) => {
                      (groups[r.owner] ??= []).push(r);
                      return groups;
                    }, {})
                  ).map(([ownerGroup, groupRepos]) => (
                    <div key={ownerGroup}>
                      <div className={styles.filterMenuGroupHeader}>{ownerGroup}</div>
                      {groupRepos.map((r) => (
                        <div
                          key={r.id}
                          className={`${styles.filterMenuItem} ${styles.filterMenuItemIndented} ${filterRepoId === r.id ? styles.filterMenuItemActive : ''}`}
                          onClick={() => { setFilterRepoId(r.id); setRepoDropdownOpen(false); }}
                        >
                          <span>{r.name}</span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Tooltip>

          {/* 2. Reviewer */}
          <Tooltip text="Filter PRs by requested reviewer" position="bottom" disabled={reviewerDropdownOpen}>
            <div className={styles.filterDropdown} ref={reviewerDropdownRef}>
              <button
                className={styles.filterTrigger}
                onClick={() => setReviewerDropdownOpen(!reviewerDropdownOpen)}
              >
                {reviewerIcon}
                {(() => {
                  if (reviewerFilter === '__me__') {
                    return (
                      <span className={styles.filterOption}>
                        {currentUser?.avatar_url && <img src={currentUser.avatar_url} alt="Me" className={styles.filterAvatar} />}
                        <span>Me</span>
                      </span>
                    );
                  }
                  if (reviewerFilter) {
                    const info = authorInfoMap.get(reviewerFilter);
                    const prData = reviewerPeopleMap.get(reviewerFilter);
                    const avatar = info?.avatar ?? prData?.avatar ?? null;
                    const displayName = info?.displayName ?? reviewerFilter;
                    return (
                      <span className={styles.filterOption}>
                        {avatar && <img src={avatar} alt={reviewerFilter} className={styles.filterAvatar} />}
                        <span>{displayName}</span>
                      </span>
                    );
                  }
                  return <span>All reviewers</span>;
                })()}
                <span className={styles.filterChevron}>{reviewerDropdownOpen ? '\u25B4' : '\u25BE'}</span>
              </button>
              {reviewerDropdownOpen && (
                <div className={styles.filterMenu}>
                  <div
                    className={`${styles.filterMenuItem} ${!reviewerFilter ? styles.filterMenuItemActive : ''}`}
                    onClick={() => { setReviewerFilter(''); setReviewerDropdownOpen(false); }}
                  >
                    <span>All reviewers</span>
                  </div>
                  {currentUser && (
                    <div
                      className={`${styles.filterMenuItem} ${reviewerFilter === '__me__' ? styles.filterMenuItemActive : ''}`}
                      onClick={() => { setReviewerFilter('__me__'); setReviewerDropdownOpen(false); }}
                    >
                      {currentUser.avatar_url && <img src={currentUser.avatar_url} alt="Me" className={styles.filterAvatar} />}
                      <span>Me</span>
                    </div>
                  )}
                  {reviewers.map((r) => {
                    const info = authorInfoMap.get(r.login);
                    const avatar = info?.avatar ?? r.avatar ?? null;
                    const displayName = info?.displayName ?? r.login;
                    return (
                      <div
                        key={r.login}
                        className={`${styles.filterMenuItem} ${reviewerFilter === r.login ? styles.filterMenuItemActive : ''}`}
                        onClick={() => { setReviewerFilter(r.login); setReviewerDropdownOpen(false); }}
                      >
                        {avatar && <img src={avatar} alt={r.login} className={styles.filterAvatar} />}
                        <span>{displayName}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </Tooltip>

          {/* Clear filters */}
          {hasActiveFilters && (
            <button className={styles.clearFilters} onClick={clearAllFilters} title="Reset all filters">
              <svg className={styles.filterIcon} viewBox="0 0 16 16" fill="currentColor"><path d="M4.646 4.646a.5.5 0 01.708 0L8 7.293l2.646-2.647a.5.5 0 01.708.708L8.707 8l2.647 2.646a.5.5 0 01-.708.708L8 8.707l-2.646 2.647a.5.5 0 01-.708-.708L7.293 8 4.646 5.354a.5.5 0 010-.708z"/></svg>
              Reset
            </button>
          )}
        </div>

        <ScoringGuide open={guideOpen} onToggle={() => setGuideOpen(!guideOpen)} />

        {prs.length === 0 ? (
          <div className={styles.empty}>No open PRs found across your tracked repos.</div>
        ) : (
          <div className={styles.list}>
            {prs.map((item, idx) => {
              // Show tier separator when the tier changes
              const prevTier = idx > 0 ? prs[idx - 1].priority_tier : null;
              const showSeparator = item.priority_tier !== prevTier;
              const tierLabel = item.priority_tier === 'high' ? 'High Priority' : item.priority_tier === 'low' ? 'Low Priority' : 'Normal Priority';
              return (<Fragment key={item.pr.id}>
              {showSeparator && (
                <div className={`${styles.tierSeparator} ${styles[`tierSeparator${item.priority_tier.charAt(0).toUpperCase() + item.priority_tier.slice(1)}`]}`}>
                  {tierLabel}
                </div>
              )}

              <div
                className={`${styles.row} ${selectedPrNumber === item.pr.number ? styles.rowSelected : ''}`}
                onClick={() => handleSelectPr(item)}
              >
                <div className={styles.position}>#{item.merge_position}</div>

                <div className={styles.main}>
                  <div className={styles.prTitleRow}>
                    <span className={styles.repoName}>{item.repo_full_name}</span>
                    <a
                      href={item.pr.html_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={styles.prLink}
                      onClick={(e) => e.stopPropagation()}
                    >
                      #{item.pr.number}
                    </a>
                    <span className={styles.prTitle}>{item.pr.title}</span>
                  </div>
                  <div className={styles.prMeta}>
                    <span className={styles.author}>{item.pr.author}</span>
                    <span className={styles.lines}>
                      <span className={styles.additions}>+{item.pr.additions}</span>
                      <span className={styles.deletions}>-{item.pr.deletions}</span>
                    </span>
                    {item.pr.manual_priority === 'high' && <span className={`${styles.badge} ${styles.badgeRed}`}>{'\u2191'} High</span>}
                    {item.pr.manual_priority === 'low' && <span className={`${styles.badge} ${styles.badgeDim}`}>{'\u2193'} Low</span>}
                    {item.stack_name && (
                      <span className={`${styles.badge} ${styles.badgeStack}`}>{item.stack_name}</span>
                    )}
                    {item.blocked_by_pr_id && (
                      <span className={`${styles.badge} ${styles.badgeAmber}`}>Blocked</span>
                    )}
                    {scoreSummary(item.priority_breakdown, item.pr.review_state).map((p, i) => {
                      const cls = p.impact === 'positive' ? styles.badgeGreen
                        : p.impact === 'negative' ? styles.badgeRed
                        : styles.badgeDim;
                      return (
                        <Tooltip key={i} text={p.tip} position="bottom">
                          <span className={`${styles.badge} ${cls}`}>{p.text}</span>
                        </Tooltip>
                      );
                    })}
                  </div>
                </div>

                <div
                  className={styles.scoreArea}
                  onMouseEnter={() => setHoveredId(item.pr.id)}
                  onMouseLeave={() => setHoveredId(null)}
                >
                  <div className={styles.scoreBar}>
                    <div
                      className={styles.scoreFill}
                      style={{
                        width: `${item.priority_score}%`,
                        backgroundColor: scoreColor(item.priority_score),
                      }}
                    />
                  </div>
                  <span className={styles.scoreLabel} style={{ color: scoreColor(item.priority_score) }}>
                    {item.priority_score}
                  </span>
                  {hoveredId === item.pr.id && (
                    <BreakdownTooltip breakdown={item.priority_breakdown} score={item.priority_score} />
                  )}
                </div>
              </div>
              </Fragment>);
            })}
          </div>
        )}
      </div>

      {selectedPrNumber && selectedRepoId && (
        <PRDetailPanel
          repoId={selectedRepoId}
          prNumber={selectedPrNumber}
          onClose={() => { selectPr(null); setSelectedRepoId(null); }}
        />
      )}
    </div>
  );
}
