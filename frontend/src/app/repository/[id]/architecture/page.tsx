"use client";

import React, { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { fetchApi } from "@/lib/api";
import { AppLayout } from "@/components/shared/app-layout";
import { MermaidViewer } from "@/components/custom/mermaid-viewer";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { 
  Network, Play, Loader2, Sparkles, Copy, Check, FileCode,
  LayoutGrid, GitMerge, Settings 
} from "lucide-react";

interface Diagram {
  id: string;
  diagram_type: string;
  mermaid_code: string;
  created_at: string;
}

export default function RepositoryArchitecturePage() {
  const params = useParams();
  const repoId = params.id as string;

  const [repo, setRepo] = useState<any>(null);
  const [diagrams, setDiagrams] = useState<Diagram[]>([]);
  const [activeType, setActiveType] = useState<string>("architecture");
  const [generating, setGenerating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  const loadData = async () => {
    try {
      const repoData = await fetchApi(`/repositories/${repoId}`);
      setRepo(repoData);

      const diagramsList = await fetchApi(`/repositories/${repoId}/diagrams`);
      setDiagrams(diagramsList);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [repoId]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const newDiag = await fetchApi(`/repositories/${repoId}/diagrams`, {
        method: "POST",
        body: JSON.stringify({ diagram_type: activeType }),
      });
      setDiagrams((prev) => {
        const filtered = prev.filter((d) => d.diagram_type !== activeType);
        return [newDiag, ...filtered];
      });
    } catch (err) {
      console.error(err);
    } finally {
      setGenerating(false);
    }
  };

  const getActiveDiagram = () => {
    return diagrams.find((d) => d.diagram_type.toLowerCase() === activeType.toLowerCase());
  };

  const handleCopyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const currentDiagram = getActiveDiagram();

  if (loading) {
    return (
      <AppLayout repositoryId={repoId}>
        <div className="flex justify-center items-center py-40">
          <Loader2 className="h-8 w-8 text-purple-500 animate-spin" />
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout repositoryId={repoId} repositoryName={repo?.name}>
      <div className="space-y-6">
        
        {/* Header */}
        <div className="border-b border-slate-900 pb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
              Architecture & Flows
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              Visualize code structures, dependencies, and execution pathways using automated Mermaid canvas engines.
            </p>
          </div>
        </div>

        {/* Tab Buttons */}
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-900 pb-4">
          <Button 
            onClick={() => setActiveType("architecture")}
            variant={activeType === "architecture" ? "default" : "outline"}
            className={`h-9 text-xs font-semibold gap-1.5 ${
              activeType === "architecture" ? "bg-purple-600 hover:bg-purple-500 text-white" : "border-slate-900 text-slate-400 hover:text-slate-200"
            }`}
          >
            <LayoutGrid className="h-4 w-4" /> System Layout
          </Button>
          <Button 
            onClick={() => setActiveType("dependency")}
            variant={activeType === "dependency" ? "default" : "outline"}
            className={`h-9 text-xs font-semibold gap-1.5 ${
              activeType === "dependency" ? "bg-purple-600 hover:bg-purple-500 text-white" : "border-slate-900 text-slate-400 hover:text-slate-200"
            }`}
          >
            <GitMerge className="h-4 w-4" /> File Dependencies
          </Button>
          <Button 
            onClick={() => setActiveType("module")}
            variant={activeType === "module" ? "default" : "outline"}
            className={`h-9 text-xs font-semibold gap-1.5 ${
              activeType === "module" ? "bg-purple-600 hover:bg-purple-500 text-white" : "border-slate-900 text-slate-400 hover:text-slate-200"
            }`}
          >
            <FileCode className="h-4 w-4" /> Folder Modules
          </Button>
        </div>

        {/* Main Diagram Area */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-8 items-start">
          {/* Visual canvas */}
          <div className="xl:col-span-8 space-y-4">
            {currentDiagram ? (
              <div className="space-y-4">
                <div className="flex justify-between items-center bg-slate-950/40 p-3 rounded-lg border border-slate-900">
                  <span className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">
                    Rendering: {activeType} diagram
                  </span>
                  <Button 
                    onClick={handleGenerate} 
                    disabled={generating} 
                    size="sm"
                    variant="ghost"
                    className="h-8 text-xs font-semibold text-purple-400 hover:text-purple-300 hover:bg-purple-500/5 p-2 gap-1.5"
                  >
                    {generating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
                    Regenerate Diagram
                  </Button>
                </div>
                
                <MermaidViewer chart={currentDiagram.mermaid_code} />
              </div>
            ) : (
              <Card className="border-dashed border-slate-900 bg-slate-900/10 text-center py-24">
                <CardContent className="flex flex-col items-center justify-center space-y-4">
                  <div className="p-4 bg-slate-900 border border-slate-800 text-slate-500 rounded-full">
                    <Network className="h-8 w-8" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-slate-300">No Diagram Rendered</h3>
                    <p className="text-slate-400 text-xs mt-1">Compile codebase relationships into Mermaid graphics.</p>
                  </div>
                  <Button 
                    onClick={handleGenerate} 
                    disabled={generating} 
                    className="bg-purple-600 hover:bg-purple-500 text-white font-semibold gap-1.5"
                  >
                    {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                    Generate {activeType} Diagram
                  </Button>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Raw Syntax Panel (Right side) */}
          {currentDiagram && (
            <div className="xl:col-span-4 space-y-4">
              <div className="flex justify-between items-center px-1">
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest">Mermaid Syntax</h3>
                <Button 
                  onClick={() => handleCopyCode(currentDiagram.mermaid_code)} 
                  size="sm" 
                  variant="ghost" 
                  className="h-7 text-xs text-slate-400 hover:text-slate-200 gap-1 p-2"
                >
                  {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
                  Copy Code
                </Button>
              </div>
              
              <div className="p-4 border border-slate-900 bg-slate-900/20 rounded-xl max-h-[500px] overflow-y-auto font-mono text-[11px] leading-relaxed text-slate-400 whitespace-pre">
                {currentDiagram.mermaid_code}
              </div>
            </div>
          )}
        </div>

      </div>
    </AppLayout>
  );
}
