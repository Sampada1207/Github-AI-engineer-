"use client";

import React, { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { fetchApi } from "@/lib/api";
import { AppLayout } from "@/components/shared/app-layout";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { 
  ShieldCheck, ShieldAlert, Sparkles, Loader2, Play, 
  Trash2, AlertTriangle, Bug, Code, Zap, Copy 
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

export default function RepositoryReviewPage() {
  const params = useParams();
  const repoId = params.id as string;

  const [repo, setRepo] = useState<any>(null);
  const [reviews, setReviews] = useState<CodeReview[]>([]);
  const [activeReview, setActiveReview] = useState<CodeReview | null>(null);
  const [scanning, setScanning] = useState(false);
  const [loading, setLoading] = useState(true);

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
      
      // Update health score locally
      const repoData = await fetchApi(`/repositories/${repoId}`);
      setRepo(repoData);
    } catch (err) {
      console.error(err);
    } finally {
      setScanning(false);
    }
  };

  const getSeverityBadge = (severity: string) => {
    const colorMap: Record<string, string> = {
      critical: "bg-red-500/10 text-red-400 border-red-500/20",
      high: "bg-orange-500/10 text-orange-400 border-orange-500/20",
      medium: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
      low: "bg-blue-500/10 text-blue-400 border-blue-500/20",
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
              Code Quality & Audit
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              Static review and security audit results scanning for syntax odors, loops, logic duplicates, and secret exposure risks.
            </p>
          </div>
          <Button 
            onClick={handleRunScan} 
            disabled={scanning} 
            className="bg-purple-600 hover:bg-purple-500 text-white font-semibold gap-1.5 shadow-lg shadow-purple-600/15"
          >
            {scanning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4.5 w-4.5" />}
            Trigger Quality Scan
          </Button>
        </div>

        {/* Overview cards */}
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

        {/* Tab logs (Main panel) */}
        {!activeReview ? (
          <Card className="border-dashed border-slate-900 bg-slate-900/10 text-center py-24">
            <CardContent className="flex flex-col items-center justify-center space-y-4">
              <div className="p-4 bg-slate-900 border border-slate-800 text-slate-500 rounded-full">
                <ShieldCheck className="h-8 w-8" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-300">No Quality Scans Run</h3>
                <p className="text-slate-400 text-xs mt-1">Compile code structures to calculate quality indexes.</p>
              </div>
              <Button onClick={handleRunScan} disabled={scanning} className="bg-purple-600 hover:bg-purple-500 text-white font-semibold">
                Run Quality Scan
              </Button>
            </CardContent>
          </Card>
        ) : (
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
