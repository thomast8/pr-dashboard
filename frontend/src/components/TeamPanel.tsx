/** Modal panel for viewing users (created via GitHub OAuth or discovered from PRs). */

import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import styles from './TeamPanel.module.css';

interface Props {
  onClose: () => void;
}

export function TeamPanel({ onClose }: Props) {
  const { data: users } = useQuery({
    queryKey: ['team'],
    queryFn: api.listTeam,
  });

  const allUsers = users || [];

  // Split into logged-in (have linked GitHub accounts) vs shadow (discovered from PR activity)
  const loggedInUsers = allUsers.filter((u) => u.linked_accounts.length > 0);
  const shadowUsers = allUsers.filter((u) => u.linked_accounts.length === 0);

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2>Team Members</h2>
          <button onClick={onClose} className={styles.closeBtn}>x</button>
        </div>
        <div className={styles.body}>
          <p className={styles.hint}>
            Users appear here after logging in or being discovered from PR activity.
          </p>

          <h3 className={styles.sectionTitle}>Signed in</h3>
          {loggedInUsers.length === 0 ? (
            <div className={styles.empty}>No signed-in users yet</div>
          ) : (
            <div className={styles.memberList}>
              {loggedInUsers.map((u) => (
                <div key={u.id} className={styles.memberRow}>
                  {u.avatar_url && (
                    <img src={u.avatar_url} alt="" className={styles.memberAvatar} />
                  )}
                  <span className={styles.memberName}>{u.name || u.login}</span>
                  <span className={styles.memberLogin}>@{u.login}</span>
                  {u.linked_accounts.some((a) => a.login !== u.login) && (
                    <span className={styles.linkedAccounts}>
                      {u.linked_accounts
                        .filter((a) => a.login !== u.login)
                        .map((a) => a.login)
                        .join(' · ')}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}

          <h3 className={styles.sectionTitle}>Discovered from PRs</h3>
          {shadowUsers.length === 0 ? (
            <div className={styles.empty}>No shadow users discovered yet</div>
          ) : (
            <div className={styles.memberList}>
              {shadowUsers.map((u) => (
                <div key={u.id} className={`${styles.memberRow} ${styles.shadow}`}>
                  {u.avatar_url && (
                    <img src={u.avatar_url} alt="" className={styles.memberAvatar} />
                  )}
                  <span className={styles.memberName}>{u.name || u.login}</span>
                  <span className={styles.memberLogin}>@{u.login}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
