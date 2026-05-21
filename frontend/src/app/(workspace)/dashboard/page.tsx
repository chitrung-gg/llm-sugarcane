"use client"

import Link from "next/link"
import { 
  Plus, 
  Folder, 
  Trash2, 
  MessageSquare, 
  Clock, 
  Loader2
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useProjects } from "@/hooks/use-projects"
import { NewProjectDialog } from "@/components/projects/new-project-dialog"

export default function DashboardPage() {
  const { data: projects = [], isLoading } = useProjects()

  return (
    <div className="p-8 lg:p-12">
      <div className="max-w-6xl mx-auto">
        {/* WELCOME SECTION */}
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-10 gap-4">
          <div className="space-y-1">
            <h2 className="text-4xl font-bold tracking-tight text-stone-900">Research Projects</h2>
            <p className="text-stone-500 font-medium leading-relaxed max-w-xl text-sm">
              Continue your analysis or upload new datasets to the sugarcane knowledge base.
            </p>
          </div>
          <NewProjectDialog>
            <Button className="bg-emerald-700 hover:bg-emerald-800 text-white font-bold h-12 px-6 rounded-xl shadow-lg shadow-emerald-700/20 transition-all active:scale-[0.98]">
              <Plus className="mr-2 h-5 w-5" /> New Project
            </Button>
          </NewProjectDialog>
        </div>

        {/* PROJECT GRID */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-stone-300" />
          </div>
        ) : projects.length === 0 ? (
          <div className="text-center py-20 border-2 border-dashed border-stone-200 rounded-2xl bg-white/50">
            <p className="text-stone-400 font-bold uppercase tracking-widest mb-4">No projects yet</p>
            <NewProjectDialog>
              <Button variant="outline" className="border-emerald-700 text-emerald-700 font-bold rounded-xl">
                Create First Project
              </Button>
            </NewProjectDialog>
          </div>
        ) : (
          <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-2">
            {projects.map((project) => (
              <Card key={project.id} className="group hover:shadow-2xl hover:shadow-stone-200/50 transition-all duration-500 border-stone-200 rounded-2xl overflow-hidden bg-white flex flex-col">
                <CardHeader className="p-6 border-b border-stone-50 bg-stone-50/30">
                  <div className="flex items-center justify-between mb-4">
                    <div className="bg-emerald-100 p-2.5 rounded-xl border border-emerald-200/50">
                      <Folder className="h-5 w-5 text-emerald-700" />
                    </div>
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="icon" className="h-9 w-9 text-stone-400 hover:text-red-500 hover:bg-red-50 rounded-full transition-colors">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  <CardTitle className="text-2xl font-bold text-stone-800 group-hover:text-emerald-700 transition-colors">
                    {project.name}
                  </CardTitle>
                  <div className="flex items-center gap-2 mt-1">
                    <Clock className="h-3.5 w-3.5 text-stone-300" />
                    <span className="text-[11px] font-bold text-stone-400 uppercase tracking-widest">
                      Created {new Date(project.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </CardHeader>

                <CardContent className="p-6 flex-1">
                  <div className="space-y-4">
                    <p className="text-sm text-stone-500 line-clamp-2">
                      {project.description || "No description provided."}
                    </p>
                  </div>
                </CardContent>

                <div className="px-6 pb-6 pt-2">
                  <Button asChild className="w-full h-12 bg-white hover:bg-emerald-700 hover:text-white border-2 border-emerald-700 text-emerald-700 font-bold rounded-xl transition-all group/btn shadow-sm">
                    <Link href={`/projects/${project.id}/chat`}>
                      <MessageSquare className="mr-2 h-5 w-5 transition-transform group-hover/btn:scale-110" /> 
                      Enter Assistant
                    </Link>
                  </Button>
                </div>
              </Card>
            ))}
            
            {/* PLACEHOLDER FOR NEW PROJECT */}
            <NewProjectDialog>
              <button className="flex flex-col items-center justify-center border-2 border-dashed border-stone-200 rounded-2xl p-12 hover:border-emerald-500 hover:bg-emerald-50/30 transition-all group bg-white/50 h-full w-full">
                <div className="bg-stone-100 p-5 rounded-2xl mb-4 group-hover:bg-emerald-100 transition-all group-hover:scale-110 shadow-sm">
                  <Plus className="h-8 w-8 text-stone-400 group-hover:text-emerald-700" />
                </div>
                <span className="text-base font-bold text-stone-400 group-hover:text-emerald-800 uppercase tracking-widest">New Project</span>
                <span className="text-xs text-stone-400 mt-2 font-medium">Add datasets for analysis</span>
              </button>
            </NewProjectDialog>
          </div>
        )}
      </div>
    </div>
  )
}
