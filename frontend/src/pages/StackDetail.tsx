/** Level 3 — Stack detail view with dependency graph and SVG arrows. */

import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { api, type StackMember, type RepoSummary } from '../api/client';
import { StatusDot } from '../components/StatusDot';
import { StackGraph } from '../components/StackGraph';
import { PRDetailPanel } from '../components/PRDetailPanel';
import { useStore } from '../store/useStore';
import styles from './StackDetail.module.css';

export function StackDetail() {
  const { owner, name, stackId } = useParams<{ owner: string; name: string; stackId: string }>();
  const { selectedPrId, selectPr } = useStore();

  const { data: repos } = useQuery({ queryKey: ['repos'], queryFn: api.listRepos });
  const repo = repos?.find((r: RepoSummary) => r.owner === owner && r.name === name);

  const { data: stack, isLoading } = useQuery({
    queryKey: ['stack', repo?.id, stackId],
    queryFn: () => api.getStack(repo!.id, parseInt(stackId!, 10)),
    enabled: !!repo && !!stackId,
  });

  if (isLoading || !stack) return <div className={styles.loading}>Loading stack...</div>;

  return (
    <div className={styles.container}>
      <div className={styles.content}>
        <div className={styles.titleRow}>
          <div>
            <Link to={`/repos/${owner}/${name}`} className={styles.breadcrumb}>
              {owner}/{name}
            </Link>
            <h1 className={styles.title}>{stack.name || `Stack #${stack.id}`}</h1>
            <div className={styles.subtitle}>
              {stack.members.length} PRs in chain
            </div>
          </div>
        </div>

        <StackGraph
          members={stack.members}
          selectedPrId={selectedPrId}
          onSelectPr={selectPr}
        />

        {/* Summary table below the graph */}
        <div className={styles.summarySection}>
          <h2 className={styles.sectionTitle}>PRs in Stack</h2>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>#</th>
                <th>PR</th>
                <th>Title</th>
                <th>CI</th>
                <th>Review</th>
                <th>Diff</th>
              </tr>
            </thead>
            <tbody>
              {stack.members.map((m: StackMember) => (
                <tr
                  key={m.pr.id}
                  className={`${styles.row} ${selectedPrId === m.pr.id ? styles.selected : ''}`}
                  onClick={() => selectPr(m.pr.id)}
                >
                  <td className={styles.position}>{m.position + 1}</td>
                  <td className={styles.prNum}>
                    <a href={m.pr.html_url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>
                      #{m.pr.number}
                    </a>
                  </td>
                  <td className={styles.prTitle}>{m.pr.title}</td>
                  <td><StatusDot status={m.pr.ci_status} /></td>
                  <td><StatusDot status={m.pr.review_state} /></td>
                  <td className={styles.diff}>
                    <span className={styles.add}>+{m.pr.additions}</span>
                    <span className={styles.del}>-{m.pr.deletions}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selectedPrId && repo && (
        <PRDetailPanel repoId={repo.id} prId={selectedPrId} onClose={() => selectPr(null)} />
      )}
    </div>
  );
}
