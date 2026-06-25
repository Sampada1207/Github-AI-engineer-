"use client";

import Link from "next/link";
import { ArrowRight, Code2, Bot, Shield, Cpu, RefreshCw, BarChart2 } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="relative min-h-screen flex flex-col justify-between overflow-hidden bg-slate-950">
      {/* Visual background glowing effects */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-purple-600/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-indigo-600/10 rounded-full blur-[120px] pointer-events-none" />

      {/* Navigation Header */}
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-md sticky top-0 z-50 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Code2 className="h-7 w-7 text-purple-500" />
            <span className="text-xl font-bold bg-gradient-to-r from-purple-400 to-indigo-400 bg-clip-text text-transparent">
              GitHub AI Engineer
            </span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/login" className="text-sm font-medium text-slate-300 hover:text-white transition-colors">
              Login
            </Link>
            <Link
              href="/register"
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-lg shadow-lg hover:shadow-purple-500/20 transition-all duration-300"
            >
              Get Started <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1 flex flex-col justify-center px-6 py-20 max-w-7xl mx-auto w-full relative z-10">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-purple-500/20 bg-purple-500/5 text-purple-300 text-xs font-semibold mb-6">
            <Bot className="h-3.5 w-3.5" /> Next-Gen Repository Intelligence
          </div>
          <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight mb-6">
            AI-Powered Code Intelligence for{" "}
            <span className="bg-gradient-to-r from-purple-400 via-pink-400 to-indigo-400 bg-clip-text text-transparent">
              Entire Codebases
            </span>
          </h1>
          <p className="text-lg md:text-xl text-slate-400 leading-relaxed mb-8">
            Submit a GitHub repository URL to clone, parse AST structures, generate semantic Qdrant embeddings,
            and interact with your code using LangGraph AI agents. Get automated architecture charts, tests, and code smell audits.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/register"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-8 py-3 text-base font-semibold bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-lg shadow-xl shadow-purple-500/10 hover:shadow-purple-500/20 hover:scale-[1.02] active:scale-[0.98] transition-all duration-300"
            >
              Analyze Your First Repo <ArrowRight className="h-5 w-5" />
            </Link>
            <Link
              href="/login"
              className="w-full sm:w-auto inline-flex items-center justify-center px-8 py-3 text-base font-semibold border border-slate-800 bg-slate-900/40 hover:bg-slate-900/80 text-slate-200 rounded-lg hover:text-white transition-all duration-300"
            >
              Demo Dashboard
            </Link>
          </div>
        </div>

        {/* Feature Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="border border-slate-800/80 bg-slate-900/30 backdrop-blur-sm rounded-xl p-6 hover:border-purple-500/30 transition-all duration-300 group">
            <div className="p-3 rounded-lg bg-purple-500/10 text-purple-400 w-fit mb-4 group-hover:scale-110 transition-transform">
              <Cpu className="h-6 w-6" />
            </div>
            <h3 className="text-lg font-bold text-slate-100 mb-2">AST & Dependency Parsing</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Extract classes, functions, imports, and relationships to map complete module interactions and dependency hierarchies.
            </p>
          </div>

          <div className="border border-slate-800/80 bg-slate-900/30 backdrop-blur-sm rounded-xl p-6 hover:border-indigo-500/30 transition-all duration-300 group">
            <div className="p-3 rounded-lg bg-indigo-500/10 text-indigo-400 w-fit mb-4 group-hover:scale-110 transition-transform">
              <Bot className="h-6 w-6" />
            </div>
            <h3 className="text-lg font-bold text-slate-100 mb-2">LangGraph AI Dialogue</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Ask detailed questions about your codebase, trace function call trees, or explain complex logic with RAG powered by Qdrant.
            </p>
          </div>

          <div className="border border-slate-800/80 bg-slate-900/30 backdrop-blur-sm rounded-xl p-6 hover:border-pink-500/30 transition-all duration-300 group">
            <div className="p-3 rounded-lg bg-pink-500/10 text-pink-400 w-fit mb-4 group-hover:scale-110 transition-transform">
              <Shield className="h-6 w-6" />
            </div>
            <h3 className="text-lg font-bold text-slate-100 mb-2">Code Quality & Smells</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Scan repositories to flag code duplicate percentages, nested loops, structural violations, and hardcoded credential risks.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 py-8 px-6 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
          <p>© 2026 GitHub AI Engineer. Open-source enterprise repository intelligence.</p>
          <div className="flex gap-4">
            <span className="hover:text-slate-400 cursor-pointer">Security Policy</span>
            <span className="hover:text-slate-400 cursor-pointer">API Agreement</span>
            <span className="hover:text-slate-400 cursor-pointer">Support Documentation</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
