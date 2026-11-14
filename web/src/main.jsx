import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@fontsource-variable/newsreader/opsz.css"; // optical sizes: display cuts for headlines, text cuts for body
import "@fontsource-variable/newsreader/opsz-italic.css";
import "@fontsource-variable/source-sans-3";
import "./index.css";
import { SessionProvider } from "./store";
import Shell from "./components/Shell";
import Paper from "./components/Paper";

// Data changes only on feedback or refinement, and those invalidate explicitly: revisits are instant.
const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5 * 60 * 1000, gcTime: 30 * 60 * 1000, refetchOnWindowFocus: false, retry: 1 } },
});

// Every address is the paper: "/" and "/p/:n" show a spread on the desk; a section's path opens that page to read.
createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <SessionProvider>
          <Routes>
            <Route element={<Shell />}>
              <Route path="*" element={<Paper />} />
            </Route>
          </Routes>
        </SessionProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
