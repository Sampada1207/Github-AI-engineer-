"use client";

import React, { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";

interface MermaidViewerProps {
  chart: string;
}

export function MermaidViewer({ chart }: MermaidViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!chart) return;
    
    setLoading(true);
    setError(null);
    setSvg(null);

    // Dynamic import to prevent nextjs ssr window errors
    import("mermaid").then(async (mermaid) => {
      try {
        mermaid.default.initialize({
          startOnLoad: false,
          theme: "dark",
          securityLevel: "loose",
          fontFamily: "var(--font-geist-sans), sans-serif",
          themeVariables: {
            background: "#0b0f19",
            primaryColor: "#7c3aed",
            primaryTextColor: "#ffffff",
            primaryBorderColor: "#7c3aed",
            lineColor: "#64748b",
            secondaryColor: "#312e81"
          }
        });
        
        const id = `mermaid-svg-${Date.now()}`;
        const { svg: renderedSvg } = await mermaid.default.render(id, chart);
        setSvg(renderedSvg);
      } catch (err: any) {
        console.error("Mermaid parsing failed", err);
        setError("Unable to render diagram syntax. Mermaid code returned syntax warnings.");
      } finally {
        setLoading(false);
      }
    });
  }, [chart]);

  return (
    <div className="w-full flex items-center justify-center p-4 border border-slate-900 bg-slate-950/80 rounded-lg min-h-[400px] overflow-auto">
      {loading && (
        <div className="flex flex-col items-center gap-2">
          <Loader2 className="h-6 w-6 text-purple-500 animate-spin" />
          <span className="text-xs text-slate-500 font-semibold">Compiling canvas vectors...</span>
        </div>
      )}
      
      {error && (
        <div className="text-center p-6 space-y-2">
          <p className="text-sm font-semibold text-red-400">{error}</p>
          <pre className="text-[10px] text-slate-600 bg-slate-900 p-3 rounded text-left font-mono max-w-xl max-h-40 overflow-y-auto whitespace-pre-wrap">{chart}</pre>
        </div>
      )}
      
      {svg && (
        <div 
          ref={containerRef}
          className="w-full max-w-full overflow-x-auto flex justify-center py-4"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      )}
    </div>
  );
}
