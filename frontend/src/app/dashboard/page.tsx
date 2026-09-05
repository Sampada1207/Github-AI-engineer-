"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { fetchApi } from "@/lib/api";
import { AppLayout } from "@/components/shared/app-layout";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { 
  GitBranch, GitPullRequest, Search, RefreshCw, AlertCircle, 
  CheckCircle, Hourglass, Database, ExternalLink, ShieldCheck, FileCode,
  FolderKanban
} from "lucide-react";
import Link from "next/link";

interface Repository {
  id: string;
  project_id: string;
  url: string;
  name: string;
  branch: string;
  status: string;
  error_message?: string;
  language_stats?: Record<string, number>;
  health_score: number;
  last_analyzed_at?: string;
  created_at: string;
}

interface Project {
  id: string;
  name: string;
  description: string;
}

export default function DashboardPage() {
  const searchParams = useSearchParams();
  const projectId = searchParams.get("project");
  
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    if (!projectId) {
      setLoading(false);
      return;
    }

    try {
      // Load project details
      const projData = await fetchApi(`/projects/${projectId}`);
      setProject(projData);

      // Load repos
      const reposData = await fetchApi(`/repositories?project_id=${projectId}`);
      // The API filters by project internally when we query repositories
      const projectRepos = reposData.filter((r: Repository) => r.project_id === projectId);
      setRepositories(projectRepos);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Failed to load project details");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Set up polling for items that are currently processing (cloning, parsing, indexing)
  useEffect(() => {
    const processingRepos = repositories.some(r => 
      ["cloning", "parsing", "indexing"].includes(r.status)
    );

    if (!processingRepos) return;

    const interval = setInterval(async () => {
      try {
        const reposData = await fetchApi(`/repositories?project_id=${projectId}`);
        const projectRepos = reposData.filter((r: Repository) => r.project_id === projectId);
        setRepositories(projectRepos);
      } catch (err) {
        console.error("Polling failed", err);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [repositories, projectId]);

  const handleSubmitRepo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoUrl) return;
    setSubmitting(true);
    setError(null);

    try {
      const newRepo = await fetchApi("/repositories", {
        method: "POST",
        body: JSON.stringify({
          url: repoUrl,
          name: repoUrl.split("/").pop() || "repository",
          branch,
          project_id: projectId
        }),
      });

      setRepositories((prev) => [newRepo, ...prev]);
      setRepoUrl("");
      setBranch("main");
    } catch (err: any) {
      setError(err.message || "Failed to submit repository");
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const styles = {
      cloning: "bg-blue-500/10 text-blue-400 border-blue-500/20",
      parsing: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
      indexing: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20",
      completed: "bg-green-500/10 text-green-400 border-green-500/20",
      failed: "bg-red-500/10 text-red-400 border-red-500/20",
    };
    
    const icons = {
      cloning: <RefreshCw className="h-3 w-3 animate-spin" />,
      parsing: <Hourglass className="h-3 w-3 animate-pulse" />,
      indexing: <Database className="h-3 w-3 animate-pulse" />,
      completed: <CheckCircle className="h-3 w-3" />,
      failed: <AlertCircle className="h-3 w-3" />,
    };

    const val = status.toLowerCase();
    const style = styles[val as keyof typeof styles] || "bg-slate-500/10 text-slate-400 border-slate-500/20";
    const icon = icons[val as keyof typeof icons] || null;

    return (
      <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${style}`}>
        {icon}
        {status}
      </span>
    );
  };

  if (!projectId) {
    return (
      <AppLayout>
        <div className="flex flex-col items-center justify-center py-24 space-y-6 max-w-lg mx-auto text-center">
          <div className="p-4 bg-purple-500/10 text-purple-400 border border-purple-500/20 rounded-full">
            <FolderKanban className="h-10 w-10" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-100">Select a Project</h1>
            <p className="text-slate-400 mt-2">
              Select or create a workspace under the projects panel to begin repository engineering and analysis.
            </p>
          </div>
          <Link href="/projects">
            <Button className="bg-purple-600 hover:bg-purple-500 text-white font-semibold">
              Go to Projects
            </Button>
          </Link>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-slate-900 pb-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-100">
              {project?.name || "Workspace"}
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              {project?.description || "Select a repository below to analyze structure or chat with code."}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={loadData} className="border-slate-800 hover:bg-slate-950 text-slate-300 gap-1.5">
            <RefreshCw className="h-3.5 w-3.5" /> Refresh List
          </Button>
        </div>

        {/* Submit Git Repository URL */}
        <Card className="border-slate-900 bg-slate-900/30 backdrop-blur-md">
          <CardHeader>
            <CardTitle className="text-base font-bold text-slate-200">Ingest GitHub Repository</CardTitle>
            <CardDescription className="text-slate-400 text-xs">
              Clone files directly to begin building semantic indices and code smell audits.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmitRepo} className="flex flex-col md:flex-row gap-4">
              <div className="flex-1 space-y-1.5">
                <Input
                  placeholder="https://github.com/owner/repository"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  className="bg-slate-950/80 border-slate-800 focus:border-purple-500 text-slate-100 placeholder:text-slate-600"
                  required
                />
              </div>
              <div className="w-full md:w-48 space-y-1.5">
                <div className="relative">
                  <GitBranch className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-500" />
                  <Input
                    placeholder="branch (main)"
                    value={branch}
                    onChange={(e) => setBranch(e.target.value)}
                    className="bg-slate-950/80 border-slate-800 focus:border-purple-500 text-slate-100 pl-9"
                  />
                </div>
              </div>
              <Button type="submit" disabled={submitting} className="bg-purple-600 hover:bg-purple-500 text-white font-semibold gap-1.5">
                {submitting ? <RefreshCw className="h-4 w-4 animate-spin" /> : <GitPullRequest className="h-4.5 w-4.5" />}
                Analyze Repository
              </Button>
            </form>
            {error && (
              <Alert variant="destructive" className="mt-4 bg-red-500/10 border-red-500/20 text-red-400 text-xs">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>

        {/* Repository Grid */}
        {loading ? (
          <div className="flex justify-center items-center py-20">
            <RefreshCw className="h-8 w-8 text-purple-500 animate-spin" />
          </div>
        ) : repositories.length === 0 ? (
          <Card className="border-dashed border-slate-900 bg-slate-900/10 text-center p-12">
            <CardContent className="flex flex-col items-center justify-center space-y-3">
              <div className="p-4 bg-slate-900/50 text-slate-400 rounded-full border border-slate-800">
                <Search className="h-6 w-6" />
              </div>
              <h3 className="text-base font-semibold text-slate-300">No Repositories Ingested</h3>
              <p className="text-slate-400 text-xs">Enter a git URL above to start code intelligence indexing.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-6">
            {repositories.map((repo) => {
              const isFinished = repo.status === "completed";
              return (
                <Card key={repo.id} className="border-slate-900 bg-slate-900/40 hover:bg-slate-900/80 transition-all duration-300 p-6 flex flex-col md:flex-row justify-between gap-6 items-start md:items-center">
                  <div className="space-y-3 flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2.5">
                      <h2 className="text-xl font-bold text-slate-100 truncate">{repo.name}</h2>
                      {getStatusBadge(repo.status)}
                      <span className="text-[10px] bg-slate-800/80 border border-slate-800 text-slate-400 px-2 py-0.5 rounded-full font-bold flex items-center gap-1">
                        <GitBranch className="h-3 w-3" /> {repo.branch}
                      </span>
                    </div>

                    <div className="text-slate-400 text-xs truncate max-w-2xl">
                      <span className="font-semibold text-slate-300">Git Origin:</span> {repo.url}
                    </div>

                    {/* Language Statistics Tags */}
                    {isFinished && repo.language_stats && (
                      <div className="flex flex-wrap items-center gap-1.5">
                        {Object.entries(repo.language_stats).slice(0, 3).map(([lang, percentage]) => (
                          <span key={lang} className="text-[10px] font-semibold bg-purple-500/5 border border-purple-500/10 text-purple-400 px-2 py-0.5 rounded-md flex items-center gap-1">
                            <FileCode className="h-3 w-3" /> {lang} ({percentage}%)
                          </span>
                        ))}
                      </div>
                    )}

                    {repo.error_message && (
                      <div className="p-3 text-xs bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg max-w-xl">
                        <span className="font-bold block mb-0.5 uppercase tracking-wide text-[9px]">Ingestion Error:</span>
                        {repo.error_message}
                      </div>
                    )}
                  </div>

                  {/* Quality indicators & links */}
                  <div className="flex items-center gap-6 w-full md:w-auto justify-between border-t border-slate-900/50 md:border-0 pt-4 md:pt-0">
                    {isFinished && (
                      <div className="flex items-center gap-2">
                        <div className="flex flex-col items-center">
                          <span className="text-[9px] uppercase tracking-wider text-slate-500 font-bold">Health Score</span>
                          <span className={`text-2xl font-black mt-0.5 ${
                            repo.health_score >= 85 ? "text-green-400" : repo.health_score >= 60 ? "text-yellow-400" : "text-red-400"
                          }`}>
                            {repo.health_score}
                          </span>
                        </div>
                      </div>
                    )}

                    <div className="flex items-center gap-3">
                      {isFinished ? (
                        <Link href={`/repository/${repo.id}`} className="w-full">
                          <Button className="w-full bg-purple-600 hover:bg-purple-500 text-white font-semibold gap-1.5 shadow-lg shadow-purple-600/15">
                            Enter Workbench <ExternalLink className="h-3.5 w-3.5" />
                          </Button>
                        </Link>
                      ) : (
                        <Button disabled className="border-slate-800 text-slate-500 bg-slate-900/50 cursor-not-allowed">
                          Indexing Codebase
                        </Button>
                      )}
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
