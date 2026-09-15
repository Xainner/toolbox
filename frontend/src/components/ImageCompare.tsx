import { useEffect, useState } from "react";
import { Columns2 } from "lucide-react";

export default function ImageCompare({ before, after }: { before: string; after: string }) {
  const [position, setPosition] = useState(50);
  const [ratio, setRatio] = useState("4 / 3");

  useEffect(() => {
    const image = new Image();
    image.onload = () => setRatio(`${image.naturalWidth} / ${image.naturalHeight}`);
    image.src = before;
  }, [before]);

  return (
    <div>
      <div className="checkerboard relative max-h-[620px] w-full overflow-hidden rounded-xl border" style={{ aspectRatio: ratio }}>
        <img src={before} alt="Imagen original" className="absolute inset-0 size-full object-contain" />
        <img src={after} alt="Resultado procesado" className="absolute inset-0 size-full object-contain"
          style={{ clipPath: `inset(0 ${100 - position}% 0 0)` }} />
        <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-white shadow" style={{ left: `${position}%` }} />
        <span className="absolute left-3 top-3 rounded-md bg-black/70 px-2 py-1 text-xs text-white">Resultado</span>
        <span className="absolute right-3 top-3 rounded-md bg-black/70 px-2 py-1 text-xs text-white">Original</span>
      </div>
      <label className="mt-3 flex items-center gap-3 text-sm text-muted-foreground">
        <Columns2 className="size-4" />
        <span className="sr-only">Posición del comparador</span>
        <input className="w-full accent-[var(--brand)]" type="range" min="0" max="100" value={position}
          onChange={(event) => setPosition(Number(event.target.value))} />
      </label>
    </div>
  );
}
