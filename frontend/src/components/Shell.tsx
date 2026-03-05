/** App shell — sidebar nav + header + content area. */

import { Link, Outlet, useLocation } from 'react-router-dom';
import styles from './Shell.module.css';

export function Shell() {
  const location = useLocation();
  const isHome = location.pathname === '/';

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <Link to="/" className={styles.logo}>PR Dashboard</Link>
        <nav className={styles.nav}>
          <Link to="/" className={isHome ? styles.active : ''}>Repos</Link>
        </nav>
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
