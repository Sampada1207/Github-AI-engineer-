"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { fetchApi } from "@/lib/api";
import { AppLayout } from "@/components/shared/app-layout";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { FolderKanban, Plus, ExternalLink, Calendar, Loader2 } from "lucide-react";

interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [createLoading, setCreateLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadProjects = async () => {
    try {
      const data = await fetchApi("/projects");
      setProjects(data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateLoading(true);
    setError(null);

    try {
      const newProj = await fetchApi("/projects", {
        method: "POST",
        body: JSON.stringify({ name, description }),
      });
      setProjects((prev) => [newProj, ...prev]);
      setName("");
      setDescription("");
      setOpen(false);
    } catch (err: any) {
      setError(err.message || "Failed to create project");
    } finally {
      setCreateLoading(false);
    }
  };

  return (
    <AppLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-100">Projects</h1>
            <p className="text-slate-400 text-sm mt-1">
              Organize your code repositories into project containers.
            </p>
          </div>

          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger
              render={
                <Button className="bg-purple-600 hover:bg-purple-500 text-white font-semibold gap-1.5 shadow-lg shadow-purple-600/10">
                  <Plus className="h-4.5 w-4.5" /> Create Project
                </Button>
              }
            />
            <DialogContent className="border-slate-800 bg-slate-900 text-slate-100">
              <DialogHeader>
                <DialogTitle className="text-slate-100">New Project Workspace</DialogTitle>
                <DialogDescription className="text-slate-400">
                  Provide a name and outline for your repository containers.
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleCreate}>
                <div className="space-y-4 py-4">
                  {error && (
                    <div className="p-3 text-xs bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg">
                      {error}
                    </div>
                  )}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Project Name</label>
                    <Input
                      placeholder="E.g., Payment Microservices"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="bg-slate-950 border-slate-800 focus:border-purple-500 text-slate-100"
                      required
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300">Description (Optional)</label>
                    <textarea
                      placeholder="Identify modules or focus areas of this project workspace."
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      className="w-full h-24 p-3 text-sm rounded-lg bg-slate-950 border border-slate-800 focus:border-purple-500 text-slate-100 focus:outline-none focus:ring-1 focus:ring-purple-500"
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button type="button" variant="ghost" onClick={() => setOpen(false)} className="text-slate-300 hover:bg-slate-800">
                    Cancel
                  </Button>
                  <Button type="submit" disabled={createLoading} className="bg-purple-600 hover:bg-purple-500 text-white font-semibold">
                    {createLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Create"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        {loading ? (
          <div className="flex justify-center items-center py-20">
            <Loader2 className="h-8 w-8 text-purple-500 animate-spin" />
          </div>
        ) : projects.length === 0 ? (
          <Card className="border-dashed border-slate-800 bg-slate-900/10 text-center p-12">
            <CardContent className="flex flex-col items-center justify-center space-y-4">
              <div className="p-4 rounded-full bg-slate-900 border border-slate-800 text-slate-400">
                <FolderKanban className="h-8 w-8" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-slate-200">No Projects Found</h3>
                <p className="text-slate-400 text-sm mt-1">Get started by creating a project workspace.</p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.map((project) => (
              <Card key={project.id} className="border-slate-900 bg-slate-900/40 hover:bg-slate-900/80 transition-all duration-300 hover:border-slate-800/80 flex flex-col justify-between">
                <CardHeader>
                  <div className="flex justify-between items-start gap-2">
                    <FolderKanban className="h-6 w-6 text-purple-400" />
                    <span className="text-[10px] text-slate-500 font-bold flex items-center gap-1">
                      <Calendar className="h-3.5 w-3.5" />
                      {new Date(project.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <CardTitle className="text-lg font-bold text-slate-200 mt-3">{project.name}</CardTitle>
                  <CardDescription className="text-slate-400 text-sm line-clamp-2 min-h-[40px] mt-1.5">
                    {project.description || "No description provided."}
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-0 border-t border-slate-900/50 mt-4 p-4 flex justify-end">
                  <Link href={`/dashboard?project=${project.id}`} className="w-full">
                    <Button variant="outline" className="w-full border-slate-800 hover:bg-purple-600/10 hover:text-purple-400 hover:border-purple-600/20 text-slate-300 gap-1.5 font-semibold text-sm">
                      Open Project <ExternalLink className="h-3.5 w-3.5" />
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
