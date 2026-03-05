import { useState, useEffect, createContext, useContext } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Shell } from './components/Shell';
import { OrgOverview } from './pages/OrgOverview';
import { RepoView } from './pages/RepoView';
import { Login } from './pages/Login';
import type { GitHubUser } from './api/client';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

interface UserContextValue {
  user: GitHubUser | null;
  setUser: (u: GitHubUser | null) => void;
}

export const UserContext = createContext<UserContextValue>({
  user: null,
  setUser: () => {},
});

export function useCurrentUser() {
  return useContext(UserContext);
}

export default function App() {
  const [authChecked, setAuthChecked] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [authEnabled, setAuthEnabled] = useState(true);
  const [user, setUser] = useState<GitHubUser | null>(null);

  useEffect(() => {
    fetch('/api/auth/me', { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => {
        setAuthenticated(data.authenticated);
        setAuthEnabled(data.auth_enabled);
        if (data.user) setUser(data.user);
        setAuthChecked(true);
      })
      .catch(() => setAuthChecked(true));
  }, []);

  if (!authChecked) return null;

  if (authEnabled && !authenticated) {
    return <Login onLogin={() => setAuthenticated(true)} />;
  }

  return (
    <UserContext.Provider value={{ user, setUser }}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route element={<Shell />}>
              <Route path="/" element={<OrgOverview />} />
              <Route path="/repos/:owner/:name" element={<RepoView />} />
              <Route path="/repos/:owner/:name/stacks/:stackId" element={<StackRedirect />} />
            </Route>
          </Routes>
        </BrowserRouter>
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
