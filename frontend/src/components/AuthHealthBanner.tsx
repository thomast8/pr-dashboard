/** Banner that shows auth health issues below the nav bar. */

import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import styles from './AuthHealthBanner.module.css';

const CRITICAL_STATUSES = new Set(['expired', 'revoked', 'decrypt_failed']);

interface Props {
  onViewDetails: () => void;
}

export function AuthHealthBanner({ onViewDetails }: Props) {
  const { data } = useQuery({
    queryKey: ['auth-health'],
    queryFn: api.authHealth,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

  if (!data?.has_issues) return null;

  const accountCount = data.accounts.length;
  const repoCount = data.stale_repos.length +
    data.accounts.reduce((sum, a) => sum + a.affected_repos.length, 0);
  const isCritical = data.accounts.some(a => CRITICAL_STATUSES.has(a.token_status));

  return (
    <div className={`${styles.banner} ${isCritical ? styles.critical : styles.warning}`}>
      <span className={styles.icon}>{isCritical ? '\u26A0' : '\u24D8'}</span>
      <span>
        {accountCount} account{accountCount !== 1 ? 's have' : ' has'} authentication issues
        {repoCount > 0 && <> &mdash; {repoCount} repo{repoCount !== 1 ? 's' : ''} not syncing</>}
      </span>
      <button className={styles.link} onClick={onViewDetails}>
        View details
      </button>
    </div>
  );
}
