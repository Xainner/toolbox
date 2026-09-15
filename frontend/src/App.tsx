import { lazy, Suspense, useEffect, useMemo, useState, createContext, useContext } from "react";
import { Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import Header from "@/components/Header";
import Home from "@/pages/Home";
import ToolPage from "@/pages/ToolPage";
import { ThemeProvider } from "@/lib/theme";
import { fetchTools } from "@/lib/api";
import type { ToolMeta } from "@/lib/types";

const StatsPage = lazy(() => import("@/pages/StatsPage"));

interface ToolsCtx {
  tools: ToolMeta[];
  loading: boolean;
  error: string | null;
}

const Ctx = createContext<ToolsCtx>({ tools: [], loading: true, error: null });
export const useTools = () => useContext(Ctx);

export default function App() {
  const [tools, setTools] = useState<ToolMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTools()
      .then((t) => setTools(t))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo(() => ({ tools, loading, error }), [tools, loading, error]);

  return (
    <ThemeProvider>
      <Ctx.Provider value={value}>
      <div className="min-h-dvh bg-background text-foreground">
        <Header />
        <main>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/tool/:toolId" element={<ToolPage />} />
            <Route path="/stats" element={<Suspense fallback={<div className="p-10 text-center text-muted-foreground">Cargando actividad…</div>}><StatsPage /></Suspense>} />
          </Routes>
        </main>
        <footer className="border-t py-6 text-center text-xs text-muted-foreground">
          Toolbox · self-hosted · casa3090
        </footer>
      </div>
      <Toaster position="bottom-right" richColors closeButton />
      </Ctx.Provider>
    </ThemeProvider>
  );
}
