import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Wrench, BarChart3, Search, Menu } from "lucide-react";
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from "@/components/ui/command";
import { useTools } from "@/App";
import { toolIcon } from "@/lib/types";
import { Button } from "@/components/ui/button";

export function CommandPalette({ open, setOpen }: { open: boolean; setOpen: (v: boolean) => void }) {
  const { tools } = useTools();
  const navigate = useNavigate();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen(!open);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, [open, setOpen]);

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Buscar herramienta..." />
      <CommandList>
        <CommandEmpty>Sin resultados.</CommandEmpty>
        <CommandGroup heading="Herramientas">
          {tools.map((t) => {
            const Icon = toolIcon(t.icon);
            return (
              <CommandItem
                key={t.id}
                value={`${t.name} ${t.description} ${t.category}`}
                onSelect={() => {
                  navigate(`/tool/${t.id}`);
                  setOpen(false);
                }}
              >
                <Icon className="mr-2 size-4 text-brand" />
                <span>{t.name}</span>
                <span className="ml-auto text-xs text-muted-foreground">{t.category}</span>
              </CommandItem>
            );
          })}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}

export default function Header() {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const { tools, loading, error } = useTools();

  return (
    <>
      <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4">
          <Link to="/" className="flex items-center gap-2 font-bold tracking-tight">
            <span className="grid size-8 place-items-center rounded-lg bg-brand text-brand-foreground shadow-sm">
              <Wrench className="size-4" />
            </span>
            <span className="text-lg">
              App<span className="text-brand">3</span> Toolbox
            </span>
          </Link>

          <nav className="ml-6 hidden items-center gap-1 text-sm md:flex">
            <Button variant="ghost" size="sm" onClick={() => setPaletteOpen(true)}>
              <Search className="size-4" />
              Buscar
              <kbd className="pointer-events-none ml-2 rounded border bg-muted px-1.5 font-mono text-[10px] text-muted-foreground">
                Ctrl K
              </kbd>
            </Button>
            <Button variant="ghost" size="sm" asChild>
              <Link to="/stats">
                <BarChart3 className="size-4" /> Actividad
              </Link>
            </Button>
          </nav>

          <div className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
            <Menu className="hidden size-5 md:hidden" />
            <span className="hidden sm:inline">
              {loading ? "cargando…" : error ? "API sin conexión" : `${tools.length} herramientas`}
            </span>
          </div>
        </div>
      </header>
      <CommandPalette open={paletteOpen} setOpen={setPaletteOpen} />
    </>
  );
}
