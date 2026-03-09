import { useState, useEffect, useCallback, createContext, useContext } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider, MutationCache } from '@tanstack/react-query';
import { Shell } from './components/Shell';
import { OrgOverview } from './pages/OrgOverview';
import { PrioritizeView } from './pages/PrioritizeView';
import { RepoView } from './pages/RepoView';
import { Login } from './pages/Login';
import type { GitHubUser } from './api/client';

// Global toast state — shared via context
let _showToast: (msg: string) => void = () => {};

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
  mutationCache: new MutationCache({
    onError: (error) => {
      const message = error instanceof Error ? error.message : 'Something went wrong';
      _showToast(message);
    },
  }),
});

interface UserContextValue {
  user: GitHubUser | null;
  setUser: (u: GitHubUser | null) => void;
  oauthConfigured: boolean;
}

export const UserContext = createContext<UserContextValue>({
  user: null,
  setUser: () => {},
  oauthConfigured: false,
});

export function useCurrentUser() {
  return useContext(UserContext);
}

export default function App() {
  const [authChecked, setAuthChecked] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [authEnabled, setAuthEnabled] = useState(true);
  const [user, setUser] = useState<GitHubUser | null>(null);
  const [oauthConfigured, setOauthConfigured] = useState(false);

  useEffect(() => {
    fetch('/api/auth/me', { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => {
        setAuthenticated(data.authenticated);
        setAuthEnabled(data.auth_enabled);
        setOauthConfigured(data.oauth_configured ?? false);
        if (data.user) setUser(data.user);
        setAuthChecked(true);
      })
      .catch(() => setAuthChecked(true));
  }, []);

  if (!authChecked) return null;

  async function handleLogin() {
    const resp = await fetch('/api/auth/me', { credentials: 'include' });
    const data = await resp.json();
    setAuthenticated(data.authenticated);
    setOauthConfigured(data.oauth_configured ?? false);
    if (data.user) setUser(data.user);
  }

  if (authEnabled && !authenticated) {
    return <Login onLogin={handleLogin} />;
  }

  const [toast, setToast] = useState<string | null>(null);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 5000);
  }, []);

  // Wire up global toast function
  useEffect(() => { _showToast = showToast; }, [showToast]);

  return (
    <UserContext.Provider value={{ user, setUser, oauthConfigured }}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route element={<Shell />}>
              <Route path="/" element={<OrgOverview />} />
              <Route path="/prioritize" element={<PrioritizeView />} />
              <Route path="/repos/:owner/:name" element={<RepoView />} />
              <Route path="/repos/:owner/:name/stacks/:stackId" element={<StackRedirect />} />
            </Route>
          </Routes>
        </BrowserRouter>
        {toast && (
          <div
            style={{
              position: 'fixed', bottom: 20, right: 20, zIndex: 9999,
              background: 'var(--ci-fail, #d73a4a)', color: '#fff',
              padding: '10px 16px', borderRadius: 8, fontSize: '0.9rem',
              boxShadow: '0 4px 12px rgba(0,0,0,0.3)', cursor: 'pointer',
              maxWidth: 400,
            }}
            onClick={() => setToast(null)}
          >
            {toast}
          </div>
        )}
      </QueryClientProvider>
    </UserContext.Provider>
  );
}

function StackRedirect() {
  const params = window.location.pathname.match(/\/repos\/([^/]+)\/([^/]+)/);
  if (params) {
    return <Navigate to={`/repos/${params[1]}/${params[2]}`} replace />;
  }
  return <Navigate to="/" replace />;
}
