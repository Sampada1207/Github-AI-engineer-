"use client";

import React, { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { fetchApi } from "@/lib/api";
import { AppLayout } from "@/components/shared/app-layout";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { 
  GitPullRequest, Sparkles, Loader2, Play, AlertTriangle, 
  Bug, ShieldAlert, FileText, Check, ArrowRight, Activity, Zap, Code, ExternalLink, Copy
} from "lucide-react";

interface PRInfo {
  id?: number;
  number: number;
  title: string;
  state: string;
  body?: string;
  author: string;
  html_url: string;
  base_ref: string;
  head_ref: string;
  draft?: boolean;
  merged?: boolean;
  created_at?: string;
  updated_at?: string;
  additions: number;
  deletions: number;
  changed_files: number;
}

interface PRFinding {
  severity: string;
  category: string;
  file: string;
  line?: any;
  explanation: string;
  suggested_fix?: string;
}

interface PRReviewResponse {
  repository_id: string;
  github_repo: string;
  pr_info: PRInfo;
  total_files_changed: number;
  total_additions: number;
  total_deletions: number;
  changed_symbols: string[];
  files: any[];
  severity_summary: Record<string, number>;
  findings: PRFinding[];
  impact_analysis: {
    impact_risk: string;
    blast_radius_score: number;
    affected_symbols_count: number;
    affected_files_count: number;
    affected_symbols: string[];
    affected_files: string[];
  };
  github_review_summary: string;
}

export default function RepositoryPRReviewPage() {
  const params = useParams();
  const repoId = params.id as string;

  const [repo, setRepo] = useState<any>(null);
  const [githubRepoInput, setGithubRepoInput] = useState("");
  const [prNumberInput, setPrNumberInput] = useState("");

  const [loadingRepo, setLoadingRepo] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [reviewResult, setReviewResult] = useState<PRReviewResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    async function loadRepo() {
      try {
        const repoData = await fetchApi(`/repositories/${repoId}`);
        setRepo(repoData);
        if (repoData?.url) {
          setGithubRepoInput(repoData.url);
        }
      } catch (err: any) {
        console.error("Failed to load repo:", err);
      } finally {
        setLoadingRepo(false);
      }
    }
    loadRepo();
  }, [repoId]);

  const handleRunPRReview = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!prNumberInput.trim()) {
      setErrorMsg("Please enter a valid Pull Request number.");
      return;
    }

    const prNum = parseInt(prNumberInput.trim(), 10);
    if (isNaN(prNum) || prNum <= 0) {
      setErrorMsg("PR number must be a positive integer.");
      return;
    }

    setAnalyzing(true);
    setErrorMsg(null);
    setReviewResult(null);

    try {
      const payload: any = {
        pr_number: prNum
      };
      if (githubRepoInput.trim()) {
        payload.github_repo = githubRepoInput.trim();
      }

      const data: PRReviewResponse = await fetchApi(`/repositories/${repoId}/pull-requests/${prNum}/review`, {
        method: "POST",
        body: JSON.stringify(payload)
      });
      setReviewResult(data);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to execute GitHub PR Review.");
    } finally {
      setAnalyzing(false);
    }
  };

  const copyMarkdownSummary = () => {
    if (!reviewResult?.github_review_summary) return;
    navigator.clipboard.writeText(reviewResult.github_review_summary);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity.toLowerCase()) {
      case "critical":
        return "bg-red-500/10 text-red-400 border-red-500/30";
      case "high":
        return "bg-orange-500/10 text-orange-400 border-orange-500/30";
      case "medium":
        return "bg-yellow-500/10 text-yellow-400 border-yellow-500/30";
      case "low":
        return "bg-blue-500/10 text-blue-400 border-blue-500/30";
      default:
        return "bg-slate-500/10 text-slate-400 border-slate-500/30";
    }
  };

  const getRiskBadge = (risk: string) => {
    switch (risk.toLowerCase()) {
      case "high":
      case "critical":
        return "bg-red-500/20 text-red-400 border-red-500/40";
      case "medium":
        return "bg-amber-500/20 text-amber-400 border-amber-500/40";
      default:
        return "bg-emerald-500/20 text-emerald-400 border-emerald-500/40";
    }
  };

  return (
    <AppLayout repositoryId={repoId} repositoryName={repo?.name}>
      <div className="flex flex-col gap-8 max-w-7xl mx-auto pb-12">
        {/* Header */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-400">
              <GitPullRequest className="h-6 w-6" />
            </span>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-slate-100">
                GitHub Pull Request Review
              </h1>
              <p className="text-sm text-slate-400">
                Analyze GitHub PRs using Knowledge Graph blast-radius analysis & AI Code Review.
              </p>
            </div>
          </div>
        </div>

        {/* PR Selection & Configuration */}
        <Card className="border-slate-800 bg-slate-900/60 backdrop-blur-sm">
          <CardHeader className="pb-4">
            <CardTitle className="text-base font-semibold text-slate-200 flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-purple-400" />
              Target Pull Request
            </CardTitle>
            <CardDescription className="text-slate-400 text-xs">
              Specify the GitHub repository URL or owner/repo identifier and PR number.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleRunPRReview} className="flex flex-col md:flex-row gap-4 items-end">
              <div className="flex-1 space-y-1.5 min-w-[240px]">
                <label className="text-xs font-semibold text-slate-300">
                  GitHub Repository (owner/repo or URL)
                </label>
                <Input
                  value={githubRepoInput}
                  onChange={(e) => setGithubRepoInput(e.target.value)}
                  placeholder="e.g. octocat/Spoon-Knife or https://github.com/owner/repo"
                  className="bg-slate-950 border-slate-800 text-slate-200 placeholder:text-slate-600 focus:border-purple-500 text-sm font-mono"
                />
              </div>

              <div className="w-full md:w-48 space-y-1.5">
                <label className="text-xs font-semibold text-slate-300">
                  PR Number
                </label>
                <Input
                  value={prNumberInput}
                  onChange={(e) => setPrNumberInput(e.target.value)}
                  placeholder="e.g. 42"
                  type="number"
                  min="1"
                  className="bg-slate-950 border-slate-800 text-slate-200 placeholder:text-slate-600 focus:border-purple-500 text-sm font-mono"
                />
              </div>

              <Button
                type="submit"
                disabled={analyzing || loadingRepo}
                className="bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white shadow-lg shadow-purple-600/20 font-medium px-6 py-2 h-10 min-w-[140px]"
              >
                {analyzing ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Analyzing PR...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2 fill-current" />
                    Review PR
                  </>
                )}
              </Button>
            </form>

            {errorMsg && (
              <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Results Section */}
        {reviewResult && (
          <div className="flex flex-col gap-6 animate-in fade-in duration-300">
            {/* PR Metadata Banner */}
            <div className="p-6 rounded-xl bg-gradient-to-r from-slate-900 to-slate-950 border border-slate-800 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <span className="px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-purple-500/20 text-purple-300 border border-purple-500/30">
                    PR #{reviewResult.pr_info.number}
                  </span>
                  <span className={`px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider border ${
                    reviewResult.pr_info.state === "open" ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" : "bg-slate-500/20 text-slate-400 border-slate-500/30"
                  }`}>
                    {reviewResult.pr_info.state}
                  </span>
                  <a 
                    href={reviewResult.pr_info.html_url} 
                    target="_blank" 
                    rel="noreferrer"
                    className="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1 underline font-medium"
                  >
                    View on GitHub <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
                <h2 className="text-xl font-bold text-slate-100">
                  {reviewResult.pr_info.title}
                </h2>
                <div className="text-xs text-slate-400 flex items-center gap-4">
                  <span>Author: <strong className="text-slate-200">@{reviewResult.pr_info.author}</strong></span>
                  <span>Branch: <code className="bg-slate-950 px-1.5 py-0.5 rounded text-purple-300">{reviewResult.pr_info.base_ref}</code> ← <code className="bg-slate-950 px-1.5 py-0.5 rounded text-purple-300">{reviewResult.pr_info.head_ref}</code></span>
                </div>
              </div>

              <Button
                variant="outline"
                size="sm"
                onClick={copyMarkdownSummary}
                className="border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800 text-xs shrink-0 flex items-center gap-2"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? "Copied Markdown!" : "Copy PR Review Markdown"}
              </Button>
            </div>

            {/* Overview Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card className="border-slate-800 bg-slate-900/40">
                <CardContent className="p-4 flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-slate-400">Total Changes</p>
                    <p className="text-2xl font-bold text-slate-100 mt-1">
                      {reviewResult.total_files_changed} <span className="text-xs font-normal text-slate-500">files</span>
                    </p>
                    <p className="text-xs font-mono mt-1">
                      <span className="text-emerald-400">+{reviewResult.total_additions}</span>{" "}
                      <span className="text-red-400">-{reviewResult.total_deletions}</span>
                    </p>
                  </div>
                  <FileText className="h-8 w-8 text-purple-400/40" />
                </CardContent>
              </Card>

              <Card className="border-slate-800 bg-slate-900/40">
                <CardContent className="p-4 flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-slate-400">Blast Radius</p>
                    <div className="flex items-center gap-2 mt-1">
                      <p className="text-2xl font-bold text-slate-100">
                        {reviewResult.impact_analysis.blast_radius_score}
                      </p>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase ${getRiskBadge(reviewResult.impact_analysis.impact_risk)}`}>
                        {reviewResult.impact_analysis.impact_risk} Risk
                      </span>
                    </div>
                  </div>
                  <Activity className="h-8 w-8 text-indigo-400/40" />
                </CardContent>
              </Card>

              <Card className="border-slate-800 bg-slate-900/40">
                <CardContent className="p-4 flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-slate-400">Impacted Symbols</p>
                    <p className="text-2xl font-bold text-slate-100 mt-1">
                      {reviewResult.impact_analysis.affected_symbols_count}
                    </p>
                    <p className="text-[11px] text-slate-400 mt-1">
                      {reviewResult.changed_symbols.length} direct diff symbols
                    </p>
                  </div>
                  <Code className="h-8 w-8 text-purple-400/40" />
                </CardContent>
              </Card>

              <Card className="border-slate-800 bg-slate-900/40">
                <CardContent className="p-4 flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-slate-400">Downstream Files</p>
                    <p className="text-2xl font-bold text-slate-100 mt-1">
                      {reviewResult.impact_analysis.affected_files_count}
                    </p>
                    <p className="text-[11px] text-slate-400 mt-1">
                      dependency impact
                    </p>
                  </div>
                  <Zap className="h-8 w-8 text-amber-400/40" />
                </CardContent>
              </Card>
            </div>

            {/* Findings Section */}
            <Card className="border-slate-800 bg-slate-900/60 backdrop-blur-sm">
              <CardHeader className="flex flex-row items-center justify-between pb-3 border-b border-slate-800">
                <div>
                  <CardTitle className="text-base font-semibold text-slate-200 flex items-center gap-2">
                    <ShieldAlert className="h-4 w-4 text-purple-400" />
                    AI Review Findings ({reviewResult.findings.length})
                  </CardTitle>
                </div>
                {/* Severity Pills */}
                <div className="flex items-center gap-2 text-xs">
                  {Object.entries(reviewResult.severity_summary).map(([sev, count]) => (
                    <span 
                      key={sev} 
                      className={`px-2 py-0.5 rounded border text-[11px] font-semibold ${getSeverityBadge(sev)}`}
                    >
                      {sev}: {count}
                    </span>
                  ))}
                </div>
              </CardHeader>

              <CardContent className="pt-6 space-y-4">
                {reviewResult.findings.length === 0 ? (
                  <div className="p-6 text-center text-slate-400 bg-slate-950/40 rounded-lg border border-slate-800">
                    <Check className="h-8 w-8 mx-auto text-emerald-400 mb-2" />
                    <p className="text-sm font-medium text-slate-200">No Critical Code Smells or Vulnerabilities Found!</p>
                    <p className="text-xs text-slate-500 mt-1">This Pull Request looks clean according to static analysis and RAG review.</p>
                  </div>
                ) : (
                  reviewResult.findings.map((item, idx) => (
                    <div 
                      key={idx} 
                      className="p-4 rounded-lg bg-slate-950/60 border border-slate-800 hover:border-slate-700 transition-colors space-y-3"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className={`px-2.5 py-0.5 rounded border text-[10px] font-bold uppercase tracking-wider ${getSeverityBadge(item.severity)}`}>
                            {item.severity}
                          </span>
                          <span className="text-xs font-semibold text-purple-300">
                            {item.category}
                          </span>
                        </div>
                        <code className="text-xs font-mono text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                          {item.file} {item.line ? `:${item.line}` : ""}
                        </code>
                      </div>

                      <p className="text-sm text-slate-300 leading-relaxed">
                        {item.explanation}
                      </p>

                      {item.suggested_fix && (
                        <div className="mt-2 space-y-1">
                          <span className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider block">
                            Suggested Fix
                          </span>
                          <pre className="p-3 rounded-md bg-slate-900 border border-slate-800 text-xs font-mono text-slate-200 overflow-x-auto">
                            {item.suggested_fix}
                          </pre>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            {/* Impact & Blast Radius Detail */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card className="border-slate-800 bg-slate-900/60 backdrop-blur-sm">
                <CardHeader>
                  <CardTitle className="text-sm font-semibold text-slate-200">
                    Downstream Affected Files ({reviewResult.impact_analysis.affected_files.length})
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {reviewResult.impact_analysis.affected_files.length === 0 ? (
                    <p className="text-xs text-slate-500">No downstream files impacted.</p>
                  ) : (
                    reviewResult.impact_analysis.affected_files.map((file, i) => (
                      <div key={i} className="p-2 rounded bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 flex items-center justify-between">
                        <span>{file}</span>
                        <ArrowRight className="h-3 w-3 text-slate-600" />
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>

              <Card className="border-slate-800 bg-slate-900/60 backdrop-blur-sm">
                <CardHeader>
                  <CardTitle className="text-sm font-semibold text-slate-200">
                    Impacted Symbols ({reviewResult.impact_analysis.affected_symbols.length})
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {reviewResult.impact_analysis.affected_symbols.length === 0 ? (
                    <p className="text-xs text-slate-500">No symbol definitions impacted.</p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {reviewResult.impact_analysis.affected_symbols.map((sym, i) => (
                        <span key={i} className="px-2 py-1 rounded bg-slate-950 border border-slate-800 text-xs font-mono text-purple-300">
                          {sym}
                        </span>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Markdown Output Preview */}
            <Card className="border-slate-800 bg-slate-900/60 backdrop-blur-sm">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-semibold text-slate-200">
                  Generated GitHub PR Review Output (Markdown)
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={copyMarkdownSummary}
                  className="text-xs text-purple-400 hover:text-purple-300"
                >
                  {copied ? "Copied!" : "Copy Output"}
                </Button>
              </CardHeader>
              <CardContent>
                <pre className="p-4 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-96">
                  {reviewResult.github_review_summary}
                </pre>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
