/** App shell — sidebar nav + header + content area. */

import { useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { useSSE } from '../api/useSSE';
import { useCurrentUser } from '../App';
import { api } from '../api/client';
import { TeamPanel } from './TeamPanel';
import { SpaceManager } from './SpaceManager';
import { Tooltip } from './Tooltip';
import styles from './Shell.module.css';

const BASE = import.meta.env.DEV ? 'http://localhost:8000' : '';

export function Shell() {
  const location = useLocation();
  useSSE();
  const isHome = location.pathname === '/';
  const [showTeam, setShowTeam] = useState(false);
  const [showSpaces, setShowSpaces] = useState(false);
  const { user, setUser } = useCurrentUser();

  function handleConnectGitHub() {
    window.location.href = `${BASE}/api/auth/github`;
  }

  async function handleDisconnect() {
    await api.disconnectGitHub();
    setUser(null);
  }

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <Link to="/" className={styles.logo}>PR Dashboard</Link>
        <nav className={styles.nav}>
          <Tooltip text="View all tracked repositories" position="bottom">
            <Link to="/" className={isHome ? styles.active : ''}>Repos</Link>
          </Tooltip>
          <Tooltip text="Manage GitHub connections" position="bottom">
            <button className={styles.teamBtn} onClick={() => setShowSpaces(true)}>Spaces</button>
          </Tooltip>
          <Tooltip text="Manage team members and assignments" position="bottom">
            <button className={styles.teamBtn} onClick={() => setShowTeam(true)}>Team</button>
          </Tooltip>
        </nav>
        <div className={styles.spacer} />
        <div className={styles.userArea}>
          {user ? (
            <Tooltip text={`Signed in as ${user.login}. Click to disconnect.`} position="bottom">
              <button className={styles.userBtn} onClick={handleDisconnect}>
                {user.avatar_url && (
                  <img src={user.avatar_url} alt="" className={styles.avatar} />
                )}
                <span className={styles.userName}>{user.name || user.login}</span>
              </button>
            </Tooltip>
          ) : (
            <Tooltip text="Connect GitHub for identity and token sharing" position="bottom">
              <button className={styles.connectBtn} onClick={handleConnectGitHub}>
                Connect GitHub
              </button>
            </Tooltip>
          )}
        </div>
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
      {showTeam && <TeamPanel onClose={() => setShowTeam(false)} />}
      {showSpaces && <SpaceManager onClose={() => setShowSpaces(false)} />}
    </div>
  );
}
