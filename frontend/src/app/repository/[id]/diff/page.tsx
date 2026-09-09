"use client";

import React, { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { fetchApi } from "@/lib/api";
import { AppLayout } from "@/components/shared/app-layout";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { 
  GitCompare, Sparkles, Loader2, Play, AlertTriangle, 
  Bug, ShieldAlert, FileText, Check, ArrowRight, Activity, Zap, Code
} from "lucide-react";

interface DiffFileChange {
  path: string;
  change_type: string;
  additions: number;
  deletions: number;
  changed_symbols: string[];
  hunks: any[];
}

interface DiffFinding {
  severity: string;
  category: string;
  file: string;
  line?: any;
  explanation: string;
  suggested_fix?: string;
  finding_type?: string;
}

interface DiffReviewResponse {
  repository_id: string;
  base_revision: string;
  target_revision: string;
  total_files_changed: number;
  total_additions: number;
  total_deletions: number;
  changed_symbols: string[];
  files: DiffFileChange[];
  impact_analysis: {
    impact_risk: string;
    blast_radius_score: number;
    affected_symbols_count: number;
    affected_files_count: number;
    affected_symbols: string[];
    affected_files: string[];
  };
  ai_review: {
    summary: {
      diff_summary: string;
      findings_count: number;
      severity_breakdown: Record<string, number>;
      blast_radius_score: number;
      impact_risk: string;
    };
    findings: DiffFinding[];
  };
}

export default function RepositoryDiffPage() {
  const params = useParams();
  const repoId = params.id as string;

  const [repo, setRepo] = useState<any>(null);
  const [baseRevision, setBaseRevision] = useState("main");
  const [targetRevision, setTargetRevision] = useState("HEAD");
  const [diffText, setDiffText] = useState("");
  const [showRawInput, setShowRawInput] = useState(false);

  const [loadingRepo, setLoadingRepo] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [reviewResult, setReviewResult] = useState<DiffReviewResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    async function loadRepo() {
      try {
        const repoData = await fetchApi(`/repositories/${repoId}`);
        setRepo(repoData);
      } catch (err: any) {
        console.error("Failed to load repo:", err);
      } finally {
        setLoadingRepo(false);
      }
    }
    loadRepo();
  }, [repoId]);

  const handleRunDiffReview = async () => {
    setAnalyzing(true);
    setErrorMsg(null);
    try {
      const payload: any = {
        base_revision: baseRevision || "main",
        target_revision: targetRevision || "HEAD"
      };
      if (diffText.trim()) {
        payload.diff_text = diffText;
      }

      const data: DiffReviewResponse = await fetchApi(`/repositories/${repoId}/diffs/review`, {
        method: "POST",
        body: JSON.stringify(payload)
      });
      setReviewResult(data);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to execute AI Diff Review.");
    } finally {
      setAnalyzing(false);
    }
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity.toLowerCase()) {
      case "critical":
        return "bg-red-500/10 text-red-400 border-red-500/30";
      case "high":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "medium":
        return "bg-yellow-500/10 text-yellow-400 border-yellow-500/30";
      default:
        return "bg-blue-500/10 text-blue-400 border-blue-500/30";
    }
  };

  return (
    <AppLayout repositoryId={repoId} repositoryName={repo?.name}>
      <div className="p-6 md:p-8 space-y-6 max-w-7xl mx-auto">
        {/* Header Banner */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-900 pb-6">
          <div>
            <div className="flex items-center gap-2 text-purple-400 text-sm font-semibold mb-1">
              <GitCompare className="h-4 w-4" />
              <span>Phase 6 Intelligence</span>
            </div>
            <h1 className="text-2xl font-bold text-slate-100">Git Diff & Code Change Review</h1>
            <p className="text-slate-400 text-sm mt-1">
              Repository-aware change analysis using Knowledge Graph impact tracking and AI review.
            </p>
          </div>
        </div>

        {/* Diff Controls Card */}
        <Card className="bg-slate-900/40 border-slate-900">
          <CardHeader>
            <CardTitle className="text-base font-semibold text-slate-200 flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-purple-400" />
              Diff Target & Revisions
            </CardTitle>
            <CardDescription>
              Select Git base and target revisions, or paste unified diff output directly.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-semibold text-slate-400 block mb-1.5">
                  Base Revision (Branch / Tag / Commit)
                </label>
                <Input
                  value={baseRevision}
                  onChange={(e) => setBaseRevision(e.target.value)}
                  placeholder="main"
                  className="bg-slate-950 border-slate-800 text-slate-200"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-400 block mb-1.5">
                  Target Revision (Branch / Tag / Commit)
                </label>
                <Input
                  value={targetRevision}
                  onChange={(e) => setTargetRevision(e.target.value)}
                  placeholder="HEAD"
                  className="bg-slate-950 border-slate-800 text-slate-200"
                />
              </div>
            </div>

            <div className="pt-2">
              <button
                type="button"
                onClick={() => setShowRawInput(!showRawInput)}
                className="text-xs text-purple-400 hover:text-purple-300 font-medium underline flex items-center gap-1"
              >
                {showRawInput ? "Hide Raw Diff Payload Input" : "Paste Raw Git Diff Payload (Optional)"}
              </button>

              {showRawInput && (
                <textarea
                  value={diffText}
                  onChange={(e) => setDiffText(e.target.value)}
                  placeholder="Paste git diff --git a/... b/... output here..."
                  rows={6}
                  className="mt-2 w-full p-3 bg-slate-950 border border-slate-800 rounded-lg text-xs font-mono text-slate-300 focus:outline-none focus:border-purple-500"
                />
              )}
            </div>

            {errorMsg && (
              <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-xs flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <Button
                onClick={handleRunDiffReview}
                disabled={analyzing}
                className="bg-purple-600 hover:bg-purple-500 text-white font-medium gap-2"
              >
                {analyzing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Analyzing Code Changes...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    Run AI Diff Review
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Results Display Section */}
        {reviewResult && (
          <div className="space-y-6">
            {/* Overview & Impact Summary Banner */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card className="bg-slate-900/40 border-slate-900 p-4">
                <div className="text-xs text-slate-400 font-semibold uppercase tracking-wider mb-1">Files Changed</div>
                <div className="text-2xl font-bold text-slate-100 flex items-center gap-2">
                  <FileText className="h-5 w-5 text-purple-400" />
                  {reviewResult.total_files_changed}
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  <span className="text-emerald-400">+{reviewResult.total_additions}</span> / <span className="text-rose-400">-{reviewResult.total_deletions}</span>
                </div>
              </Card>

              <Card className="bg-slate-900/40 border-slate-900 p-4">
                <div className="text-xs text-slate-400 font-semibold uppercase tracking-wider mb-1">Impact Risk</div>
                <div className="text-2xl font-bold text-slate-100 flex items-center gap-2">
                  <Activity className="h-5 w-5 text-amber-400" />
                  {reviewResult.impact_analysis?.impact_risk || "Low"}
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  Blast Radius: {reviewResult.impact_analysis?.blast_radius_score || 0}/100
                </div>
              </Card>

              <Card className="bg-slate-900/40 border-slate-900 p-4">
                <div className="text-xs text-slate-400 font-semibold uppercase tracking-wider mb-1">Changed Symbols</div>
                <div className="text-2xl font-bold text-slate-100 flex items-center gap-2">
                  <Code className="h-5 w-5 text-indigo-400" />
                  {reviewResult.changed_symbols?.length || 0}
                </div>
                <div className="text-xs text-slate-500 mt-1 truncate">
                  {reviewResult.changed_symbols?.slice(0, 3).join(", ") || "None"}
                </div>
              </Card>

              <Card className="bg-slate-900/40 border-slate-900 p-4">
                <div className="text-xs text-slate-400 font-semibold uppercase tracking-wider mb-1">Review Findings</div>
                <div className="text-2xl font-bold text-slate-100 flex items-center gap-2">
                  <ShieldAlert className="h-5 w-5 text-rose-400" />
                  {reviewResult.ai_review?.findings?.length || 0}
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  Critical: {reviewResult.ai_review?.summary?.severity_breakdown?.Critical || 0} | High: {reviewResult.ai_review?.summary?.severity_breakdown?.High || 0}
                </div>
              </Card>
            </div>

            {/* AI Review Findings */}
            <Card className="bg-slate-900/40 border-slate-900">
              <CardHeader>
                <CardTitle className="text-base font-semibold text-slate-200 flex items-center gap-2">
                  <Bug className="h-4 w-4 text-rose-400" />
                  AI Diff Review Findings
                </CardTitle>
                <CardDescription>
                  Issues detected in changed code, exposed risks, or potential downstream breaks.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {(!reviewResult.ai_review?.findings || reviewResult.ai_review.findings.length === 0) ? (
                  <div className="p-8 text-center border border-dashed border-slate-800 rounded-lg">
                    <Check className="h-8 w-8 text-emerald-400 mx-auto mb-2" />
                    <h3 className="text-sm font-semibold text-slate-200">No Security Risks or Bugs Found</h3>
                    <p className="text-xs text-slate-400 mt-1">The AI review did not find any critical issues in this diff.</p>
                  </div>
                ) : (
                  reviewResult.ai_review.findings.map((f, idx) => (
                    <div key={idx} className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 text-[11px] font-bold rounded border uppercase ${getSeverityBadge(f.severity)}`}>
                            {f.severity}
                          </span>
                          <span className="px-2 py-0.5 text-[11px] font-semibold bg-slate-900 text-slate-300 rounded border border-slate-800">
                            {f.category}
                          </span>
                          <span className="text-xs font-mono text-purple-300">
                            {f.file} {f.line ? `(Line ${f.line})` : ""}
                          </span>
                        </div>

                        {f.finding_type && (
                          <span className="text-[10px] text-slate-400 italic">
                            [{f.finding_type}]
                          </span>
                        )}
                      </div>

                      <p className="text-xs text-slate-300 leading-relaxed">
                        {f.explanation}
                      </p>

                      {f.suggested_fix && (
                        <div className="mt-2 p-2.5 bg-slate-900 border border-slate-800/80 rounded text-xs font-mono text-emerald-300 overflow-x-auto">
                          <span className="text-[10px] text-slate-500 uppercase tracking-wider block font-sans mb-1 font-bold">Suggested Fix</span>
                          <pre className="whitespace-pre-wrap">{f.suggested_fix}</pre>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            {/* Changed Files Breakdown & Blast Radius */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Changed Files List */}
              <Card className="bg-slate-900/40 border-slate-900">
                <CardHeader>
                  <CardTitle className="text-base font-semibold text-slate-200 flex items-center gap-2">
                    <FileText className="h-4 w-4 text-purple-400" />
                    Changed Files ({reviewResult.files.length})
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 max-h-96 overflow-y-auto pr-1">
                  {reviewResult.files.map((file, idx) => (
                    <div key={idx} className="p-3 bg-slate-950 border border-slate-800 rounded-lg flex items-center justify-between text-xs">
                      <div className="min-w-0 pr-2">
                        <div className="font-mono text-slate-200 truncate">{file.path}</div>
                        {file.changed_symbols && file.changed_symbols.length > 0 && (
                          <div className="text-[10px] text-purple-400 truncate mt-0.5">
                            Symbols: {file.changed_symbols.join(", ")}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-3 shrink-0">
                        <span className="text-[10px] uppercase font-bold text-slate-400 px-1.5 py-0.5 bg-slate-900 rounded border border-slate-800">
                          {file.change_type}
                        </span>
                        <span className="font-mono text-emerald-400">+{file.additions}</span>
                        <span className="font-mono text-rose-400">-{file.deletions}</span>
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>

              {/* Blast Radius & Affected Symbols */}
              <Card className="bg-slate-900/40 border-slate-900">
                <CardHeader>
                  <CardTitle className="text-base font-semibold text-slate-200 flex items-center gap-2">
                    <Zap className="h-4 w-4 text-amber-400" />
                    Knowledge Graph Blast Radius
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 text-xs">
                  <div>
                    <span className="text-slate-400 font-semibold block mb-1">Potentially Affected Symbols (Callers / Subclasses)</span>
                    {(!reviewResult.impact_analysis?.affected_symbols || reviewResult.impact_analysis.affected_symbols.length === 0) ? (
                      <p className="text-slate-500 italic">No downstream symbol callers affected.</p>
                    ) : (
                      <div className="flex flex-wrap gap-1.5">
                        {reviewResult.impact_analysis.affected_symbols.map((sym, i) => (
                          <span key={i} className="px-2 py-1 bg-slate-950 border border-slate-800 text-indigo-300 font-mono rounded">
                            {sym}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div>
                    <span className="text-slate-400 font-semibold block mb-1">Potentially Affected Files</span>
                    {(!reviewResult.impact_analysis?.affected_files || reviewResult.impact_analysis.affected_files.length === 0) ? (
                      <p className="text-slate-500 italic">No downstream file dependencies affected.</p>
                    ) : (
                      <div className="space-y-1">
                        {reviewResult.impact_analysis.affected_files.map((fp, i) => (
                          <div key={i} className="p-2 bg-slate-950 border border-slate-800 text-slate-300 font-mono rounded flex items-center gap-2">
                            <ArrowRight className="h-3 w-3 text-purple-400" />
                            <span>{fp}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
