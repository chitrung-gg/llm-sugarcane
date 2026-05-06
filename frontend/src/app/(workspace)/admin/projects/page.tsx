"use client"

import * as React from "react"
import { FolderKanban, Loader2, Sprout, User, Calendar, ExternalLink } from "lucide-react"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useProjects } from "@/hooks/use-projects"
import Link from "next/link"

export default function AdminProjectsPage() {
  const { data: projects = [], isLoading } = useProjects()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-stone-300" />
      </div>
    )
  }

  return (
    <div className="space-y-8 p-8">
      <div>
        <p className="text-[10px] font-bold text-emerald-600 uppercase tracking-[0.3em] mb-1">Administrative Dashboard</p>
        <h1 className="text-4xl font-bold tracking-tight text-stone-900">Global Research Projects</h1>
        <p className="text-stone-500 mt-2 font-medium max-w-2xl text-base">
          Overview of all research workspaces active in the system across all users.
        </p>
      </div>

      <div className="grid gap-6">
        <Card className="border-stone-200 shadow-md rounded-2xl overflow-hidden bg-white">
          <CardHeader className="bg-stone-900 text-white p-6">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-xl font-bold flex items-center gap-2">
                  <FolderKanban className="h-5 w-5 text-emerald-400" />
                  System-wide Projects ({projects.length})
                </CardTitle>
                <CardDescription className="text-stone-400 font-medium">
                  Monitor and manage research workspaces.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {projects.length === 0 ? (
              <div className="p-12 text-center space-y-4 text-stone-500 italic">
                No projects found in the system.
              </div>
            ) : (
              <div className="divide-y divide-stone-100">
                {projects.map((project) => (
                  <div key={project.id} className="p-6 hover:bg-stone-50/50 transition-colors group">
                    <div className="flex items-start justify-between">
                      <div className="space-y-2">
                        <div className="flex items-center gap-3">
                          <div className="bg-emerald-100 p-2 rounded-xl border border-emerald-200">
                             <Sprout className="size-5 text-emerald-700" />
                          </div>
                          <div>
                            <h3 className="text-lg font-bold text-stone-900">{project.name}</h3>
                            <div className="flex items-center gap-4 mt-1">
                               <div className="flex items-center gap-1.5 text-[10px] font-bold text-stone-400 uppercase tracking-widest">
                                  <User className="size-3" /> 
                                  Owner: {project.owner_id === "00000000-0000-0000-0000-000000000000" ? "Admin" : "Standard User"}
                               </div>
                               <div className="flex items-center gap-1.5 text-[10px] font-bold text-stone-400 uppercase tracking-widest">
                                  <Calendar className="size-3" /> 
                                  Created: {new Date(project.created_at).toLocaleDateString()}
                               </div>
                            </div>
                          </div>
                        </div>
                        <p className="text-sm text-stone-500 font-medium ml-12">
                          {project.description || "No description provided."}
                        </p>
                        <p className="text-[10px] font-mono text-stone-400 ml-12">UUID: {project.id}</p>
                      </div>

                      <Button variant="outline" size="sm" className="h-9 rounded-xl border-stone-200 group-hover:border-emerald-200 group-hover:bg-emerald-50 group-hover:text-emerald-700 transition-all" asChild>
                         <Link href={`/projects/${project.id}`}>
                            View Details <ExternalLink className="ml-2 size-3.5" />
                         </Link>
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
