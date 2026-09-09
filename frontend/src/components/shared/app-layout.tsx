"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { 
  LayoutDashboard, FolderKanban, MessageSquare, BookOpen, 
  Network, ShieldCheck, Settings, LogOut, Code2, Menu, X, ArrowLeft, GitCompare
} from "lucide-react";
import { Button } from "@/components/ui/button";

interface AppLayoutProps {
  children: React.ReactNode;
  repositoryId?: string;
  repositoryName?: string;
}

export function AppLayout({ children, repositoryId, repositoryName }: AppLayoutProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = React.useState(false);

  const navigation = [
    { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { name: "Projects", href: "/projects", icon: FolderKanban },
  ];

  // Repository contextual options
  const repoNavigation = repositoryId ? [
    { name: "Repo Dashboard", href: `/repository/${repositoryId}`, icon: LayoutDashboard },
    { name: "AI Code Chat", href: `/repository/${repositoryId}/chat`, icon: MessageSquare },
    { name: "Documentation", href: `/repository/${repositoryId}/documentation`, icon: BookOpen },
    { name: "Architecture", href: `/repository/${repositoryId}/architecture`, icon: Network },
    { name: "Code Quality", href: `/repository/${repositoryId}/review`, icon: ShieldCheck },
    { name: "Diff Review", href: `/repository/${repositoryId}/diff`, icon: GitCompare },
  ] : [];

  const footerNavigation = [
    { name: "Settings", href: "/settings", icon: Settings },
  ];

  const LinkItem = ({ item }: { item: any }) => {
    const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
    const Icon = item.icon;
    return (
      <Link
        href={item.href}
        className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
          isActive 
            ? "bg-purple-600/10 text-purple-400 border-l-2 border-purple-500 font-semibold" 
            : "text-slate-400 hover:text-slate-100 hover:bg-slate-900/50"
        }`}
        onClick={() => setMobileOpen(false)}
      >
        <Icon className={`h-4.5 w-4.5 ${isActive ? "text-purple-400" : "text-slate-400"}`} />
        {item.name}
      </Link>
    );
  };

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      {/* Mobile Toggle */}
      <div className="md:hidden fixed top-4 right-4 z-50">
        <Button 
          variant="outline" 
          size="icon" 
          onClick={() => setMobileOpen(!mobileOpen)}
          className="border-slate-800 bg-slate-950 text-slate-100 hover:bg-slate-900"
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </Button>
      </div>

      {/* Sidebar Navigation */}
      <aside className={`
        fixed inset-y-0 left-0 z-40 w-64 border-r border-slate-900 bg-slate-950 flex flex-col justify-between p-4 transition-transform duration-300
        md:translate-x-0 md:static md:h-screen
        ${mobileOpen ? "translate-x-0" : "-translate-x-full"}
      `}>
        <div className="flex flex-col gap-6 overflow-y-auto pr-1">
          {/* Logo */}
          <div className="flex items-center gap-2.5 px-2 py-1.5 border-b border-slate-900 pb-4">
            <Code2 className="h-6 w-6 text-purple-500" />
            <span className="font-bold text-lg bg-gradient-to-r from-purple-400 to-indigo-400 bg-clip-text text-transparent">
              GitHub AI Engineer
            </span>
          </div>

          {/* Active Context Marker */}
          {repositoryName && (
            <div className="px-3 py-2 bg-slate-900/40 border border-slate-900 rounded-lg">
              <span className="text-[10px] uppercase tracking-wider text-slate-500 font-bold block mb-0.5">Active Repository</span>
              <span className="text-sm font-semibold text-purple-300 line-clamp-1">{repositoryName}</span>
              <Link href="/dashboard" className="text-[11px] text-slate-400 hover:text-slate-100 flex items-center gap-1 mt-1.5 font-medium transition-colors">
                <ArrowLeft className="h-3 w-3" /> Switch Repo
              </Link>
            </div>
          )}

          {/* Menu Sections */}
          <nav className="flex flex-col gap-1.5">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-widest px-3 mb-1">General</span>
            {navigation.map((item) => (
              <LinkItem key={item.name} item={item} />
            ))}

            {repositoryId && (
              <>
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-widest px-3 mt-4 mb-1">Analysis Context</span>
                {repoNavigation.map((item) => (
                  <LinkItem key={item.name} item={item} />
                ))}
              </>
            )}
          </nav>
        </div>

        {/* Footer & User Profile */}
        <div className="border-t border-slate-900 pt-4 flex flex-col gap-2">
          {footerNavigation.map((item) => (
            <LinkItem key={item.name} item={item} />
          ))}
          
          <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-slate-900/30 border border-slate-900/40 mt-1">
            <div className="min-w-0 flex flex-col">
              <span className="text-xs font-semibold text-slate-200 truncate">{user?.full_name || "Code Inquirer"}</span>
              <span className="text-[10px] text-slate-400 truncate uppercase tracking-wider">{user?.role || "User"}</span>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={logout}
              className="text-slate-400 hover:text-red-400 hover:bg-red-500/10 h-8 w-8"
              title="Logout"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 md:h-screen md:overflow-y-auto bg-slate-950">
        {mobileOpen && (
          <div 
            className="md:hidden fixed inset-0 bg-black/60 z-30 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
        )}
        <div className="flex-1 p-6 md:p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
