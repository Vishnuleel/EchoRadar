import React, { Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@fontsource-variable/inter";
import "@fontsource-variable/space-grotesk";
import "./index.css";
import { SessionProvider } from "./store";
import Shell from "./components/Shell";
import { PageSkeleton } from "./components/ui";
import Home from "./pages/Home";
import Radar from "./pages/Radar";
import Overview from "./pages/Overview";
import CompanyDNA from "./pages/CompanyDNA";
import Blueprint from "./pages/Blueprint";
import Evaluation from "./pages/Evaluation";
import Staff from "./pages/Staff";

const Graph = lazy(() => import("./pages/Graph")); // the force-graph library is only loaded when needed

// Data changes only on feedback or refinement, and those invalidate explicitly: revisits are instant.
const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5 * 60 * 1000, gcTime: 30 * 60 * 1000, refetchOnWindowFocus: false, retry: 1 } },
});

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <SessionProvider>
          <Routes>
            <Route element={<Shell />}>
              <Route index element={<Home />} />
              <Route path="radar" element={<Radar />} />
              <Route path="dna" element={<CompanyDNA />} />
              <Route path="blueprint" element={<Blueprint />} />
              <Route path="overview" element={<Overview />} />
              <Route path="graph" element={<Suspense fallback={<PageSkeleton />}><Graph /></Suspense>} />
              <Route path="staff" element={<Staff />} />
              <Route path="evaluation" element={<Evaluation />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </SessionProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
