"use client";

import React, { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { fetchApi } from "@/lib/api";
import { AppLayout } from "@/components/shared/app-layout";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { 
  ShieldCheck, ShieldAlert, Sparkles, Loader2, Play, 
  Trash2, AlertTriangle, Bug, Code, Zap, Copy, FileText, Cpu, Check
} from "lucide-react";

interface CodeReview {
  id: string;
  branch_or_pr: string;
  code_smells: Array<{
    file: string;
    line: number;
    type: string;
    description: string;
    severity: string;
  }>;
  duplicate_code: Array<{
    file: string;
    line: number;
    duplicate_file: string;
    duplicate_line: number;
    description: string;
  }>;
  security_risks: Array<{
    file: string;
    line: number;
    type: string;
    description: string;
    severity: string;
  }>;
  performance_issues: Array<{
    file: string;
    line: number;
    type: string;
    description: string;
    severity: string;
  }>;
  created_at: string;
}

interface AICodeReviewFinding {
  severity: string;
  category: string;
  file: string;
  line?: any;
  explanation: string;
  suggested_fix?: string;
}

interface AICodeReviewData {
  target: string;
  overall_summary: string;
  findings: AICodeReviewFinding[];
  impact_analysis: {
    target: string;
    impact_risk: string;
    blast_radius_score: number;
    affected_symbols_count: number;
    affected_files_count: number;
    directly_affected_symbols: string[];
    dependent_files: string[];
    limitations_notice: string;
  };
}

export default function RepositoryReviewPage() {
  const params = useParams();
  const repoId = params.id as string;

  const [repo, setRepo] = useState<any>(null);
  const [reviews, setReviews] = useState<CodeReview[]>([]);
  const [activeReview, setActiveReview] = useState<CodeReview | null>(null);
  const [scanning, setScanning] = useState(false);
  const [loading, setLoading] = useState(true);

  // AI Review states
  const [targetInput, setTargetInput] = useState("");
  const [aiReviewData, setAiReviewData] = useState<AICodeReviewData | null>(null);
  const [aiReviewing, setAiReviewing] = useState(false);

  const loadData = async () => {
    try {
      const repoData = await fetchApi(`/repositories/${repoId}`);
      setRepo(repoData);

      const reviewsList = await fetchApi(`/repositories/${repoId}/reviews`);
      setReviews(reviewsList);
      
      if (reviewsList.length > 0) {
        setActiveReview(reviewsList[0]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [repoId]);

  const handleRunScan = async () => {
    setScanning(true);
    try {
      const newReview = await fetchApi(`/repositories/${repoId}/reviews`, {
        method: "POST",
        body: JSON.stringify({ branch_or_pr: repo?.branch || "main" }),
      });
      setReviews((prev) => [newReview, ...prev]);
      setActiveReview(newReview);
      
      const repoData = await fetchApi(`/repositories/${repoId}`);
      setRepo(repoData);
    } catch (err) {
      console.error(err);
    } finally {
      setScanning(false);
    }
  };

  const handleRunAIReview = async () => {
    setAiReviewing(true);
    try {
      const payload: any = {};
      if (targetInput.includes("/") || targetInput.includes(".")) {
        payload.file_path = targetInput.trim();
      } else if (targetInput.trim()) {
        payload.symbol_name = targetInput.trim();
      }

      const res = await fetchApi(`/repositories/${repoId}/ai-review`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setAiReviewData(res);
    } catch (err) {
      console.error(err);
    } finally {
      setAiReviewing(false);
    }
  };

  const getSeverityBadge = (severity: string) => {
    const colorMap: Record<string, string> = {
      critical: "bg-red-500/10 text-red-400 border-red-500/20",
      high: "bg-orange-500/10 text-orange-400 border-orange-500/20",
      medium: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
      low: "bg-blue-500/10 text-blue-400 border-blue-500/20",
      info: "bg-slate-500/10 text-slate-400 border-slate-500/20",
    };
    const c = severity.toLowerCase();
    const style = colorMap[c] || "bg-slate-500/10 text-slate-400 border-slate-500/20";
    return (
      <span className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold uppercase border tracking-wider ${style}`}>
        {severity}
      </span>
    );
  };

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
        <div className="border-b border-slate-900 pb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
              AI Code Review & Impact Analysis
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              Repository-aware code auditing combining AST rules, Knowledge Graph structural analysis, and Hybrid RAG.
            </p>
          </div>
          <Button 
            onClick={handleRunScan} 
            disabled={scanning} 
            variant="outline"
            className="border-slate-800 text-slate-300 hover:bg-slate-900 gap-1.5"
          >
            {scanning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4 text-purple-400" />}
            Trigger Static Scan
          </Button>
        </div>

        {/* AI Code Reviewer Box */}
        <Card className="border-slate-800 bg-slate-900/40 p-6 space-y-4">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-slate-800/80 pb-4">
            <div>
              <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                <Cpu className="h-5 w-5 text-purple-400" />
                AI Repository-Aware Reviewer
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Enter a target file path (e.g., <code className="text-purple-300">app/routes/auth.py</code>) or symbol name (e.g., <code className="text-purple-300">AuthService</code>), or leave blank for full workspace analysis.
              </p>
            </div>
            <div className="flex items-center gap-3 w-full md:w-auto">
              <Input
                placeholder="Target file or symbol (optional)..."
                value={targetInput}
                onChange={(e) => setTargetInput(e.target.value)}
                className="bg-slate-950/80 border-slate-800 text-slate-200 text-xs w-full md:w-64"
              />
              <Button
                onClick={handleRunAIReview}
                disabled={aiReviewing}
                className="bg-purple-600 hover:bg-purple-500 text-white font-semibold gap-1.5 shadow-lg shadow-purple-600/20 whitespace-nowrap"
              >
                {aiReviewing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                Run AI Review
              </Button>
            </div>
          </div>

          {/* AI Review Results Output */}
          {aiReviewData && (
            <div className="space-y-6 pt-2">
              {/* Summary Header Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card className="border-slate-800/80 bg-slate-950/60 p-4">
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Target Scope</span>
                  <p className="text-sm font-bold text-purple-300 mt-1 truncate">{aiReviewData.target}</p>
                </Card>
                <Card className="border-slate-800/80 bg-slate-950/60 p-4">
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Impact Blast Radius Risk</span>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-base font-bold ${
                      aiReviewData.impact_analysis.impact_risk === 'High' ? 'text-red-400' :
                      aiReviewData.impact_analysis.impact_risk === 'Medium' ? 'text-yellow-400' : 'text-green-400'
                    }`}>
                      {aiReviewData.impact_analysis.impact_risk} Risk
                    </span>
                    <span className="text-xs text-slate-400">
                      (Score: {aiReviewData.impact_analysis.blast_radius_score}/100)
                    </span>
                  </div>
                </Card>
                <Card className="border-slate-800/80 bg-slate-950/60 p-4">
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Potentially Affected Scope</span>
                  <p className="text-xs font-semibold text-slate-300 mt-1">
                    {aiReviewData.impact_analysis.affected_symbols_count} symbols across {aiReviewData.impact_analysis.affected_files_count} files
                  </p>
                </Card>
              </div>

              {/* Findings Section */}
              <div className="space-y-4">
                <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-purple-400" />
                  Structured Findings ({aiReviewData.findings.length})
                </h3>

                {aiReviewData.findings.length === 0 ? (
                  <div className="p-6 bg-slate-950/50 border border-slate-800/80 rounded-lg text-slate-400 text-xs flex items-center gap-2">
                    <Check className="h-4 w-4 text-green-400" />
                    No specific security risks or bug patterns detected for this target!
                  </div>
                ) : (
                  <div className="space-y-3">
                    {aiReviewData.findings.map((f, idx) => (
                      <Card key={idx} className="border-slate-800/80 bg-slate-950/70 p-4 space-y-2">
                        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                          <div className="flex items-center gap-2">
                            {getSeverityBadge(f.severity)}
                            <span className="text-xs font-bold text-slate-200 border border-slate-800 px-2 py-0.5 rounded bg-slate-900/50">
                              {f.category}
                            </span>
                          </div>
                          <span className="text-[11px] font-mono text-purple-300">
                            {f.file} {f.line ? `: Line ${f.line}` : ''}
                          </span>
                        </div>
                        <p className="text-xs text-slate-300 leading-relaxed">{f.explanation}</p>
                        {f.suggested_fix && (
                          <div className="pt-2">
                            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block mb-1">Suggested Fix</span>
                            <pre className="bg-slate-900 border border-slate-800 p-3 rounded text-[11px] font-mono text-slate-200 overflow-x-auto">
                              <code>{f.suggested_fix}</code>
                            </pre>
                          </div>
                        )}
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </Card>

        {/* Overview cards for static scans */}
        {activeReview && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Card className="border-slate-900 bg-slate-900/25 p-4 flex flex-col justify-between">
              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Health Index</span>
              <span className={`text-2xl font-black mt-2 ${
                repo?.health_score >= 85 ? "text-green-400" : repo?.health_score >= 60 ? "text-yellow-400" : "text-red-400"
              }`}>{repo?.health_score || 100}%</span>
            </Card>
            <Card className="border-slate-900 bg-slate-900/25 p-4 flex flex-col justify-between">
              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Security Risks</span>
              <span className={`text-2xl font-black mt-2 ${activeReview.security_risks.length > 0 ? "text-red-400" : "text-slate-400"}`}>
                {activeReview.security_risks.length}
              </span>
            </Card>
            <Card className="border-slate-900 bg-slate-900/25 p-4 flex flex-col justify-between">
              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Code Smells</span>
              <span className="text-2xl font-black mt-2 text-indigo-400">
                {activeReview.code_smells.length}
              </span>
            </Card>
            <Card className="border-slate-900 bg-slate-900/25 p-4 flex flex-col justify-between">
              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Duplicate Blocks</span>
              <span className="text-2xl font-black mt-2 text-yellow-400">
                {activeReview.duplicate_code.length}
              </span>
            </Card>
          </div>
        )}

        {/* Tab logs for Static Scans */}
        {activeReview && (
          <Tabs defaultValue="security" className="w-full">
            <TabsList className="bg-slate-950/80 border border-slate-900 w-full justify-start p-1 h-11 gap-1">
              <TabsTrigger value="security" className="text-xs font-semibold px-4 data-[state=active]:bg-purple-600/10 data-[state=active]:text-purple-400">
                <ShieldAlert className="h-4 w-4 mr-1.5" /> Security Risks ({activeReview.security_risks.length})
              </TabsTrigger>
              <TabsTrigger value="smells" className="text-xs font-semibold px-4 data-[state=active]:bg-purple-600/10 data-[state=active]:text-purple-400">
                <Bug className="h-4 w-4 mr-1.5" /> Code Smells ({activeReview.code_smells.length})
              </TabsTrigger>
              <TabsTrigger value="duplicates" className="text-xs font-semibold px-4 data-[state=active]:bg-purple-600/10 data-[state=active]:text-purple-400">
                <Copy className="h-4 w-4 mr-1.5" /> Duplicates ({activeReview.duplicate_code.length})
              </TabsTrigger>
              <TabsTrigger value="performance" className="text-xs font-semibold px-4 data-[state=active]:bg-purple-600/10 data-[state=active]:text-purple-400">
                <Zap className="h-4 w-4 mr-1.5" /> Performance ({activeReview.performance_issues.length})
              </TabsTrigger>
            </TabsList>

            {/* Security Tab */}
            <TabsContent value="security" className="mt-6 space-y-4 focus-visible:outline-none">
              {activeReview.security_risks.length === 0 ? (
                <p className="text-sm text-slate-500 italic py-6">No security alerts discovered. Looking solid!</p>
              ) : (
                <div className="space-y-4">
                  {activeReview.security_risks.map((item, idx) => (
                    <Card key={idx} className="border-slate-900/60 bg-slate-900/10 p-5 flex flex-col md:flex-row gap-4 justify-between items-start md:items-center">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-slate-200">{item.type}</span>
                          {getSeverityBadge(item.severity)}
                        </div>
                        <p className="text-xs text-slate-400">{item.description}</p>
                        <span className="text-[10px] font-mono text-purple-400 block pt-1.5">{item.file} : Line {item.line}</span>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </TabsContent>

            {/* Code Smells Tab */}
            <TabsContent value="smells" className="mt-6 space-y-4 focus-visible:outline-none">
              {activeReview.code_smells.length === 0 ? (
                <p className="text-sm text-slate-500 italic py-6">Clean structures, no code odors detected.</p>
              ) : (
                <div className="space-y-4">
                  {activeReview.code_smells.map((item, idx) => (
                    <Card key={idx} className="border-slate-900/60 bg-slate-900/10 p-5 flex flex-col md:flex-row gap-4 justify-between items-start md:items-center">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-slate-200">{item.type}</span>
                          {getSeverityBadge(item.severity)}
                        </div>
                        <p className="text-xs text-slate-400">{item.description}</p>
                        <span className="text-[10px] font-mono text-purple-400 block pt-1.5">{item.file} : Line {item.line}</span>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </TabsContent>

            {/* Duplicates Tab */}
            <TabsContent value="duplicates" className="mt-6 space-y-4 focus-visible:outline-none">
              {activeReview.duplicate_code.length === 0 ? (
                <p className="text-sm text-slate-500 italic py-6">No duplicate logic fragments identified.</p>
              ) : (
                <div className="space-y-4">
                  {activeReview.duplicate_code.map((item, idx) => (
                    <Card key={idx} className="border-slate-900/60 bg-slate-900/10 p-5 flex flex-col gap-2">
                      <span className="text-sm font-bold text-slate-200">Matching Logic Blocks</span>
                      <p className="text-xs text-slate-400 leading-relaxed">{item.description}</p>
                      <div className="flex gap-4 pt-1 text-[10px] font-mono text-purple-400">
                        <span>Original: {item.file} : L{item.line}</span>
                        <span>Copy: {item.duplicate_file} : L{item.duplicate_line}</span>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </TabsContent>

            {/* Performance Tab */}
            <TabsContent value="performance" className="mt-6 space-y-4 focus-visible:outline-none">
              {activeReview.performance_issues.length === 0 ? (
                <p className="text-sm text-slate-500 italic py-6">No performance bottlenecks scanned.</p>
              ) : (
                <div className="space-y-4">
                  {activeReview.performance_issues.map((item, idx) => (
                    <Card key={idx} className="border-slate-900/60 bg-slate-900/10 p-5 flex flex-col md:flex-row gap-4 justify-between items-start md:items-center">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-slate-200">{item.type}</span>
                          {getSeverityBadge(item.severity)}
                        </div>
                        <p className="text-xs text-slate-400">{item.description}</p>
                        <span className="text-[10px] font-mono text-purple-400 block pt-1.5">{item.file} : Line {item.line}</span>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </TabsContent>
          </Tabs>
        )}
      </div>
    </AppLayout>
  );
}
