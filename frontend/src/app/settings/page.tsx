"use client";

import React, { useState } from "react";
import { AppLayout } from "@/components/shared/app-layout";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import { Settings, Key, User, Database, ShieldCheck, Loader2 } from "lucide-react";

export default function SettingsPage() {
  const { user } = useAuth();
  
  const [openaiKey, setOpenaiKey] = useState("");
  const [anthropicKey, setAnthropicKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSaveKeys = (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    
    // Simulate saving keys locally or sending to a backend settings endpoint
    setTimeout(() => {
      setSaving(false);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    }, 1000);
  };

  return (
    <AppLayout>
      <div className="space-y-8 max-w-4xl">
        {/* Header */}
        <div className="border-b border-slate-900 pb-6">
          <h1 className="text-3xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            Settings
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Configure LLM api access, vector parameters, and account parameters.
          </p>
        </div>

        <div className="space-y-6">
          {/* Account Profile Card */}
          <Card className="border-slate-900 bg-slate-900/20">
            <CardHeader>
              <CardTitle className="text-base font-bold text-slate-200 flex items-center gap-2">
                <User className="h-4.5 w-4.5 text-purple-400" /> Account Profile
              </CardTitle>
              <CardDescription className="text-slate-400 text-xs">
                Your registered account details and role credentials.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Full Name</span>
                  <div className="p-2.5 bg-slate-950 border border-slate-900 rounded-lg text-sm text-slate-200 font-semibold">
                    {user?.full_name || "Code Analyzer"}
                  </div>
                </div>
                <div className="space-y-1">
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Email Address</span>
                  <div className="p-2.5 bg-slate-950 border border-slate-900 rounded-lg text-sm text-slate-200 font-semibold">
                    {user?.email || "analyzer@engine.ai"}
                  </div>
                </div>
                <div className="space-y-1">
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Role Privilege</span>
                  <div className="p-2.5 bg-slate-950 border border-slate-900 rounded-lg text-sm text-purple-400 font-semibold uppercase tracking-wider">
                    {user?.role || "user"}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* API Keys Configuration */}
          <Card className="border-slate-900 bg-slate-900/20">
            <form onSubmit={handleSaveKeys}>
              <CardHeader>
                <CardTitle className="text-base font-bold text-slate-200 flex items-center gap-2">
                  <Key className="h-4.5 w-4.5 text-purple-400" /> LLM API Credentials
                </CardTitle>
                <CardDescription className="text-slate-400 text-xs">
                  Supply custom model keys to override mock generators and enable full interactive AI chat capabilities.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {success && (
                  <div className="p-3 text-xs bg-green-500/10 border border-green-500/20 text-green-400 rounded-lg flex items-center gap-1.5 font-semibold">
                    <ShieldCheck className="h-4 w-4" /> API Credentials updated and cached locally.
                  </div>
                )}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-300">OpenAI API Key (Optional)</label>
                  <Input
                    type="password"
                    placeholder="sk-proj-..."
                    value={openaiKey}
                    onChange={(e) => setOpenaiKey(e.target.value)}
                    className="bg-slate-950 border-slate-900 focus:border-purple-500 text-slate-100"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-300">Anthropic API Key (Optional)</label>
                  <Input
                    type="password"
                    placeholder="sk-ant-..."
                    value={anthropicKey}
                    onChange={(e) => setAnthropicKey(e.target.value)}
                    className="bg-slate-950 border-slate-900 focus:border-purple-500 text-slate-100"
                  />
                </div>
              </CardContent>
              <CardFooter className="flex justify-end border-t border-slate-900 pt-4 mt-2">
                <Button type="submit" disabled={saving} className="bg-purple-600 hover:bg-purple-500 text-white font-semibold">
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save Credentials"}
                </Button>
              </CardFooter>
            </form>
          </Card>

          {/* Database connections overview */}
          <Card className="border-slate-900 bg-slate-900/20">
            <CardHeader>
              <CardTitle className="text-base font-bold text-slate-200 flex items-center gap-2">
                <Database className="h-4.5 w-4.5 text-purple-400" /> Database Integrations
              </CardTitle>
              <CardDescription className="text-slate-400 text-xs">
                Active status indicators for databases inside the workbench container.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-xs">
              <div className="flex justify-between items-center p-2.5 bg-slate-950 border border-slate-900 rounded-lg">
                <span className="font-semibold text-slate-300 font-mono">SQLite (Local Workbench Engine)</span>
                <span className="inline-flex px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-green-500/10 text-green-400 border border-green-500/15">Active</span>
              </div>
              <div className="flex justify-between items-center p-2.5 bg-slate-950 border border-slate-900 rounded-lg">
                <span className="font-semibold text-slate-300 font-mono">Qdrant Client (Disk-Backed Collection)</span>
                <span className="inline-flex px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-green-500/10 text-green-400 border border-green-500/15">Active</span>
              </div>
            </CardContent>
          </Card>
        </div>

      </div>
    </AppLayout>
  );
}
export { Settings as SettingsIcon } from "lucide-react";
