import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Shell } from './components/Shell';
import { OrgOverview } from './pages/OrgOverview';
import { RepoView } from './pages/RepoView';
import { StackDetail } from './pages/StackDetail';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Shell />}>
            <Route path="/" element={<OrgOverview />} />
            <Route path="/repos/:owner/:name" element={<RepoView />} />
            <Route path="/repos/:owner/:name/stacks/:stackId" element={<StackDetail />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
