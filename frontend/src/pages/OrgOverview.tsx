/** Level 1 — Org overview showing all tracked repos as cards. */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useState } from 'react';
import { api, type RepoSummary } from '../api/client';
import styles from './OrgOverview.module.css';

function healthColor(repo: RepoSummary): string {
  if (repo.failing_ci_count > 0) return 'var(--ci-fail)';
  if (repo.stale_pr_count > 0) return 'var(--ci-pending)';
  return 'var(--ci-pass)';
}

export function OrgOverview() {
  const qc = useQueryClient();
  const { data: repos, isLoading } = useQuery({
    queryKey: ['repos'],
    queryFn: api.listRepos,
    refetchInterval: 30_000,
  });

  const [owner, setOwner] = useState('');
  const [name, setName] = useState('');

  const addMutation = useMutation({
    mutationFn: () => api.addRepo(owner, name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['repos'] });
      setOwner('');
      setName('');
    },
  });

  if (isLoading) return <div className={styles.loading}>Loading repos...</div>;

  return (
    <div>
      <div className={styles.titleRow}>
        <h1 className={styles.title}>Tracked Repositories</h1>
      </div>

      <div className={styles.grid}>
        {repos?.map((repo) => (
          <Link
            key={repo.id}
            to={`/repos/${repo.owner}/${repo.name}`}
            className={styles.card}
          >
            <div className={styles.cardHeader}>
              <span
                className={styles.healthDot}
                style={{ background: healthColor(repo) }}
              />
              <span className={styles.repoName}>{repo.full_name}</span>
            </div>
            <div className={styles.stats}>
              <div className={styles.stat}>
                <span className={styles.statValue}>{repo.open_pr_count}</span>
                <span className={styles.statLabel}>Open PRs</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statValue} style={{ color: repo.failing_ci_count > 0 ? 'var(--ci-fail)' : undefined }}>
                  {repo.failing_ci_count}
                </span>
                <span className={styles.statLabel}>Failing CI</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statValue}>{repo.stack_count}</span>
                <span className={styles.statLabel}>Stacks</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statValue} style={{ color: repo.stale_pr_count > 0 ? 'var(--ci-pending)' : undefined }}>
                  {repo.stale_pr_count}
                </span>
                <span className={styles.statLabel}>Stale</span>
              </div>
            </div>
            {repo.last_synced_at && (
              <div className={styles.synced}>
                Synced {new Date(repo.last_synced_at).toLocaleTimeString()}
              </div>
            )}
          </Link>
        ))}

        {/* Add repo card */}
        <div className={styles.addCard}>
          <div className={styles.addTitle}>Track a repo</div>
          <div className={styles.addForm}>
            <input
              placeholder="owner"
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
              className={styles.input}
            />
            <input
              placeholder="repo"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={styles.input}
            />
            <button
              onClick={() => addMutation.mutate()}
              disabled={!owner || !name || addMutation.isPending}
              className={styles.addBtn}
            >
              {addMutation.isPending ? 'Adding...' : 'Add'}
            </button>
          </div>
          {addMutation.isError && (
            <div className={styles.error}>{(addMutation.error as Error).message}</div>
          )}
        </div>
      </div>
    </div>
  );
}
