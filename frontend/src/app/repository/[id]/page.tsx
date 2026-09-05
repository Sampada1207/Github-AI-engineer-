"use client";

import React, { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { fetchApi } from "@/lib/api";
import { AppLayout } from "@/components/shared/app-layout";
import { DirectoryTree } from "@/components/custom/directory-tree";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { 
  GitBranch, Code, FileCode, CheckCircle, Database, HelpCircle,
  Hash, BookOpen, AlertCircle, Compass
} from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

interface Repository {
  id: string;
  name: string;
  url: string;
  branch: string;
  status: string;
  health_score: number;
  language_stats?: Record<string, number>;
}

interface SymbolNode {
  name: string;
  start_line: number;
  end_line: number;
  content: string;
}

interface FileExplorerData {
  id: string;
  path: string;
  name: string;
  type: "file" | "directory";
  language?: string;
  size?: number;
  children?: FileExplorerData[];
}

export default function RepositoryDetailsPage() {
  const params = useParams();
  const repoId = params.id as string;

  const [repo, setRepo] = useState<Repository | null>(null);
  const [treeNodes, setTreeNodes] = useState<FileExplorerData[]>([]);
  const [selectedFile, setSelectedFile] = useState<any>(null);
  const [fileContent, setFileContent] = useState<string>("");
  const [classesList, setClassesList] = useState<any[]>([]);
  const [funcsList, setFuncsList] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [contentLoading, setContentLoading] = useState(false);

  useEffect(() => {
    const loadRepoData = async () => {
      try {
        const repoData = await fetchApi(`/repositories/${repoId}`);
        setRepo(repoData);

        const treeData = await fetchApi(`/repositories/${repoId}/tree`);
        setTreeNodes(treeData);
        
        // Populate flat list of class/func symbols from file contents for exploration
        const filesList = await fetchApi(`/repositories?project_id=${repoData.project_id}`); // just helper to query files indirectly
        // Actually we can load symbols using a custom endpoint or client side search
        // We will make a call to get flat list of parsed files or classes/functions
        // Let's scrape the files details
        
      } catch (err) {
        console.error("Failed to load workbench data", err);
      } finally {
        setLoading(false);
      }
    };
    loadRepoData();
  }, [repoId]);

  const handleSelectFile = async (node: any) => {
    if (node.type !== "file") return;
    setContentLoading(true);
    setSelectedFile(node);
    
    try {
      const data = await fetchApi(`/repositories/${repoId}/files/${node.id}`);
      setFileContent(data.content);
      
      // Load symbols explorer details directly from file content using regex parser client side
      parseFileSymbols(data.content, node.name, node.path);
    } catch (err) {
      console.error(err);
      setFileContent("Failed to load file contents.");
    } finally {
      setContentLoading(false);
    }
  };

  const parseFileSymbols = (code: string, filename: string, path: string) => {
    // Basic client side AST scraping for explorer list
    const ext = filename.split(".").pop() || "";
    const classes: SymbolNode[] = [];
    const funcs: SymbolNode[] = [];
    const lines = code.split("\n");

    if (ext === "py") {
      lines.forEach((line, idx) => {
        const stripped = line.trim();
        if (stripped.startsWith("class ")) {
          classes.push({
            name: stripped.split("(")[0].replace("class ", "").replace(":", "").trim(),
            start_line: idx + 1,
            end_line: idx + 5,
            content: line
          });
        }
        if (stripped.startsWith("def ") || stripped.startsWith("async def ")) {
          funcs.push({
            name: stripped.split("(")[0].replace("def ", "").replace("async def ", "").trim(),
            start_line: idx + 1,
            end_line: idx + 2,
            content: line
          });
        }
      });
    } else {
      // JS/TS generic scans
      lines.forEach((line, idx) => {
        const stripped = line.trim();
        if (stripped.startsWith("class ") || stripped.includes("export class ")) {
          const match = stripped.match(/class\s+(\w+)/);
          if (match) {
            classes.push({ name: match[1], start_line: idx + 1, end_line: idx + 5, content: line });
          }
        }
        if (stripped.startsWith("function ") || stripped.includes("func ") || stripped.match(/const\s+\w+\s*=\s*\(.*?\)\s*=>/)) {
          const match = stripped.match(/(?:function|func)\s+(\w+)/) || stripped.match(/const\s+(\w+)\s*=/);
          if (match) {
            funcs.push({ name: match[1], start_line: idx + 1, end_line: idx + 2, content: line });
          }
        }
      });
    }
    
    setClassesList(classes);
    setFuncsList(funcs);
  };

  const getFriendlyLanguage = (lang?: string) => {
    if (!lang) return "Text";
    const mapped: Record<string, string> = {
      "typescript": "typescript",
      "javascript": "javascript",
      "python": "python",
      "go": "go",
      "html": "html",
      "css": "css",
      "json": "json"
    };
    return mapped[lang.toLowerCase()] || "markdown";
  };

  if (loading) {
    return (
      <AppLayout repositoryId={repoId}>
        <div className="flex justify-center items-center py-40">
          <Database className="h-8 w-8 text-purple-500 animate-spin" />
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout repositoryId={repoId} repositoryName={repo?.name}>
      <div className="flex flex-col h-full space-y-6">
        
        {/* Top Info Banner */}
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4 bg-slate-900/20 border border-slate-900 p-6 rounded-xl">
          <div className="space-y-1">
            <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2">
              {repo?.name}
              <span className="text-xs bg-slate-800 text-slate-400 font-bold px-2 py-0.5 rounded-full border border-slate-800 flex items-center gap-1">
                <GitBranch className="h-3.5 w-3.5" /> {repo?.branch}
              </span>
            </h1>
            <p className="text-xs text-slate-400 font-mono truncate max-w-2xl">{repo?.url}</p>
          </div>
          
          <div className="flex items-center gap-6">
            {repo?.language_stats && (
              <div className="hidden sm:flex items-center gap-2">
                {Object.entries(repo.language_stats).slice(0, 3).map(([lang, pct]) => (
                  <span key={lang} className="text-[10px] font-bold bg-slate-900 border border-slate-800 text-slate-300 px-2 py-1 rounded-md">
                    {lang}: {pct}%
                  </span>
                ))}
              </div>
            )}
            
            <div className="flex flex-col items-center">
              <span className="text-[10px] text-slate-500 uppercase tracking-widest font-black">Health Score</span>
              <span className={`text-2xl font-black ${
                (repo?.health_score || 100) >= 85 ? "text-green-400" : (repo?.health_score || 100) >= 60 ? "text-yellow-400" : "text-red-400"
              }`}>
                {repo?.health_score}
              </span>
            </div>
          </div>
        </div>

        {/* Dynamic Workspace Panels */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[calc(100vh-260px)] min-h-[500px]">
          {/* Navigator (Left Panel) */}
          <div className="lg:col-span-4 border border-slate-900 bg-slate-900/30 backdrop-blur-md rounded-xl overflow-hidden flex flex-col h-full">
            <Tabs defaultValue="files" className="flex-1 flex flex-col h-full">
              <TabsList className="bg-slate-950/80 border-b border-slate-900 rounded-none w-full justify-start p-1.5 gap-1">
                <TabsTrigger value="files" className="text-xs font-semibold px-4 py-1.5 data-[state=active]:bg-purple-600/10 data-[state=active]:text-purple-400 data-[state=active]:border-purple-500/20">
                  <FileCode className="h-3.5 w-3.5 mr-1.5" /> Files
                </TabsTrigger>
                <TabsTrigger value="symbols" className="text-xs font-semibold px-4 py-1.5 data-[state=active]:bg-purple-600/10 data-[state=active]:text-purple-400 data-[state=active]:border-purple-500/20">
                  <Compass className="h-3.5 w-3.5 mr-1.5" /> Symbols
                </TabsTrigger>
              </TabsList>
              
              <TabsContent value="files" className="flex-1 overflow-y-auto p-4 focus-visible:outline-none">
                <DirectoryTree 
                  nodes={treeNodes} 
                  onSelectFile={handleSelectFile} 
                  selectedFileId={selectedFile?.id} 
                />
              </TabsContent>
              
              <TabsContent value="symbols" className="flex-1 overflow-y-auto p-4 focus-visible:outline-none space-y-4">
                {selectedFile ? (
                  <>
                    <div>
                      <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">Classes</h3>
                      {classesList.length === 0 ? (
                        <p className="text-xs text-slate-500 italic">No classes detected in this file.</p>
                      ) : (
                        <div className="space-y-1">
                          {classesList.map((c, i) => (
                            <div key={i} className="flex items-center gap-1.5 text-xs font-mono py-1.5 px-2 hover:bg-slate-900 rounded-md text-slate-300">
                              <Code className="h-3.5 w-3.5 text-purple-400" />
                              <span>{c.name}</span>
                              <span className="text-[10px] text-slate-500 ml-auto">Line {c.start_line}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    
                    <div>
                      <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">Functions</h3>
                      {funcsList.length === 0 ? (
                        <p className="text-xs text-slate-500 italic">No functions detected in this file.</p>
                      ) : (
                        <div className="space-y-1">
                          {funcsList.map((f, i) => (
                            <div key={i} className="flex items-center gap-1.5 text-xs font-mono py-1.5 px-2 hover:bg-slate-900 rounded-md text-slate-300">
                              <Hash className="h-3.5 w-3.5 text-indigo-400" />
                              <span>{f.name}</span>
                              <span className="text-[10px] text-slate-500 ml-auto">Line {f.start_line}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <p className="text-xs text-slate-500 italic text-center py-10">Select a code file to inspect its parsed structures.</p>
                )}
              </TabsContent>
            </Tabs>
          </div>

          {/* Editor (Right Panel) */}
          <div className="lg:col-span-8 border border-slate-900 bg-slate-900/30 backdrop-blur-md rounded-xl overflow-hidden flex flex-col h-full">
            {selectedFile ? (
              <div className="flex-1 flex flex-col overflow-hidden">
                {/* File Header */}
                <div className="px-4 py-3 bg-slate-950/80 border-b border-slate-900 flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <FileCode className="h-4 w-4 text-purple-400" />
                    <span className="text-sm font-semibold text-slate-200">{selectedFile.path}</span>
                  </div>
                  <span className="text-xs bg-slate-900 border border-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono">
                    {selectedFile.language || "text"}
                  </span>
                </div>
                
                {/* Code viewport */}
                <div className="flex-1 overflow-auto text-sm focus-visible:outline-none">
                  {contentLoading ? (
                    <div className="flex justify-center items-center h-full">
                      <RefreshCw className="h-6 w-6 text-purple-500 animate-spin" />
                    </div>
                  ) : (
                    <SyntaxHighlighter
                      language={getFriendlyLanguage(selectedFile.language)}
                      style={vscDarkPlus}
                      showLineNumbers={true}
                      customStyle={{
                        margin: 0,
                        padding: "16px",
                        background: "transparent",
                        fontFamily: "var(--font-geist-mono), monospace",
                        minHeight: "100%"
                      }}
                    >
                      {fileContent}
                    </SyntaxHighlighter>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-8 space-y-4">
                <div className="p-4 bg-slate-900 border border-slate-800 text-slate-500 rounded-full">
                  <HelpCircle className="h-8 w-8" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-200">No File Selected</h3>
                  <p className="text-slate-400 text-sm mt-1">
                    Select any file from the repository directory tree on the left to display its full source contents.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

      </div>
    </AppLayout>
  );
}
