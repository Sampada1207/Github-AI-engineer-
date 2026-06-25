"use client";

import React, { useState, useEffect } from "react";
import { useParams } from "next/params";
import { fetchApi } from "@/lib/api";
import { AppLayout } from "@/components/shared/app-layout";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { 
  BookOpen, FileText, Download, Play, Loader2, Sparkles, Check, 
  ChevronRight, Calendar 
} from "lucide-react";

interface Documentation {
  id: string;
  doc_type: string;
  file_path?: string;
  content: string;
  created_at: string;
}

export default function RepositoryDocsPage() {
  const params = useParams();
  const repoId = params?.id as string || "";

  const [repo, setRepo] = useState<any>(null);
  const [docs, setDocs] = useState<Documentation[]>([]);
  const [generating, setGenerating] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    if (!repoId) return;
    try {
      const repoData = await fetchApi(`/repositories/${repoId}`);
      setRepo(repoData);
      
      const docsData = await fetchApi(`/repositories/${repoId}/docs`);
      setDocs(docsData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [repoId]);

  const handleGenerate = async (type: string) => {
    setGenerating(type);
    try {
      const newDoc = await fetchApi(`/repositories/${repoId}/docs`, {
        method: "POST",
        body: JSON.stringify({ doc_type: type }),
      });
      // Replace or insert doc
      setDocs((prev) => {
        const filtered = prev.filter((d) => d.doc_type !== type);
        return [newDoc, ...filtered];
      });
    } catch (err) {
      console.error(err);
    } finally {
      setGenerating(null);
    }
  };

  const handleDownload = (doc: Documentation) => {
    const blob = new Blob([doc.content], { type: "text/markdown;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `${repo?.name || "repository"}_${doc.doc_type.toUpperCase()}.md`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const getDocTypeName = (type: string) => {
    const mapped: Record<string, string> = {
      readme: "Repository README",
      api: "REST API Reference Guide",
      class: "Class & Schema Guide",
      function: "Functional Directory Guide"
    };
    return mapped[type.toLowerCase()] || type;
  };

  const docTypes = ["readme", "api", "class", "function"];

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
      <div className="space-y-8">
        {/* Header */}
        <div className="border-b border-slate-900 pb-6">
          <h1 className="text-3xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            Documentation Center
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Generate and export professional markdown documentation catalogs representing classes, methods, and schemas.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Action trigger columns (Left) */}
          <div className="lg:col-span-4 space-y-4">
            <h2 className="text-sm font-bold text-slate-500 uppercase tracking-widest px-1">Trigger Generators</h2>
            
            {docTypes.map((type) => {
              const existingDoc = docs.find((d) => d.doc_type.toLowerCase() === type);
              const isGenerating = generating === type;
              
              return (
                <Card key={type} className="border-slate-900 bg-slate-900/30 hover:bg-slate-900/60 transition-colors">
                  <CardHeader className="p-4 flex flex-row items-center justify-between space-y-0">
                    <div className="space-y-1">
                      <CardTitle className="text-sm font-bold text-slate-200 capitalize">{type} Guide</CardTitle>
                      <CardDescription className="text-[10px] text-slate-400">
                        {type === "readme" ? "Outline architecture and setup." : 
                         type === "api" ? "Analyze API route endpoints." :
                         type === "class" ? "Document properties & models." : "Reference core functions."}
                      </CardDescription>
                    </div>
                    
                    <Button 
                      onClick={() => handleGenerate(type)} 
                      disabled={generating !== null}
                      size="sm"
                      className={`h-8 px-3 text-xs font-semibold gap-1 ${
                        existingDoc 
                          ? "bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-800" 
                          : "bg-purple-600 hover:bg-purple-500 text-white"
                      }`}
                    >
                      {isGenerating ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : existingDoc ? (
                        <>Rebuild <Play className="h-2.5 w-2.5" /></>
                      ) : (
                        <>Build <Sparkles className="h-2.5 w-2.5" /></>
                      )}
                    </Button>
                  </CardHeader>
                </Card>
              );
            })}
          </div>

          {/* Viewer Accordion (Right) */}
          <div className="lg:col-span-8 space-y-4">
            <h2 className="text-sm font-bold text-slate-500 uppercase tracking-widest px-1">Documentation Logs</h2>
            
            {docs.length === 0 ? (
              <Card className="border-dashed border-slate-900 bg-slate-900/10 text-center p-12">
                <CardContent className="flex flex-col items-center justify-center space-y-3">
                  <div className="p-4 bg-slate-900 border border-slate-800 text-slate-500 rounded-full">
                    <BookOpen className="h-6 w-6" />
                  </div>
                  <h3 className="text-base font-bold text-slate-300">No Documents Generated</h3>
                  <p className="text-slate-400 text-xs">Trigger any doc builder panel on the left to compile manuals.</p>
                </CardContent>
              </Card>
            ) : (
              <Accordion type="single" collapsible className="space-y-4">
                {docs.map((doc) => (
                  <AccordionItem 
                    key={doc.id} 
                    value={doc.id}
                    className="border border-slate-900 bg-slate-900/20 rounded-xl px-4 overflow-hidden"
                  >
                    <AccordionTrigger className="hover:no-underline py-4 flex items-center justify-between text-slate-200 hover:text-slate-100">
                      <div className="flex items-center gap-3 text-left">
                        <div className="p-2 bg-purple-500/10 text-purple-400 border border-purple-500/10 rounded-lg">
                          <FileText className="h-4.5 w-4.5" />
                        </div>
                        <div>
                          <h4 className="text-sm font-bold text-slate-200">{getDocTypeName(doc.doc_type)}</h4>
                          <span className="text-[10px] text-slate-500 font-bold flex items-center gap-1 mt-0.5">
                            <Calendar className="h-3 w-3" /> Compiled on {new Date(doc.created_at).toLocaleString()}
                          </span>
                        </div>
                      </div>
                    </AccordionTrigger>
                    
                    <AccordionContent className="border-t border-slate-900 pt-4 pb-6 space-y-4">
                      {/* Action Header bar */}
                      <div className="flex justify-end gap-2">
                        <Button 
                          onClick={() => handleDownload(doc)} 
                          size="sm" 
                          variant="outline"
                          className="h-8 border-slate-800 hover:bg-slate-950 text-slate-300 text-xs gap-1.5 font-semibold"
                        >
                          <Download className="h-3.5 w-3.5" /> Export Markdown
                        </Button>
                      </div>
                      
                      {/* Text Markdown Box */}
                      <div className="p-5 rounded-lg border border-slate-900 bg-slate-950/60 font-mono text-xs overflow-auto max-h-[500px] text-slate-300 leading-relaxed whitespace-pre-wrap">
                        {doc.content}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            )}
          </div>

        </div>
      </div>
    </AppLayout>
  );
}
