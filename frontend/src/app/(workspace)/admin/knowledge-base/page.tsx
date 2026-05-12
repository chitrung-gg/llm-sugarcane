"use client"

import * as React from "react"
import { 
  Database, 
  Loader2, 
  Plus, 
  Globe, 
  Lock, 
  Trash2, 
  Search, 
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  FolderKanban,
  ChevronDown
} from "lucide-react"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { AddDatasetDialog } from "@/components/datasets/add-dataset-dialog"
import { useProjects } from "@/hooks/use-projects"
import { useUserDatasets, useUpdateDataset, useDeleteDataset } from "@/hooks/use-datasets"
import { SYSTEM_OWNER_ID } from "@/lib/constants"
import Link from "next/link"

export default function AdminKnowledgeBasePage() {
  const { data: projects = [], isLoading: projectsLoading } = useProjects(true)
  const adminProjects = projects.filter(p => p.owner_id === SYSTEM_OWNER_ID)
  
  const { data: datasets = [], isLoading: datasetsLoading } = useUserDatasets(SYSTEM_OWNER_ID)
  const updateDatasetMutation = useUpdateDataset()
  const deleteDatasetMutation = useDeleteDataset()

  const [searchQuery, setSearchQuery] = React.useState("")
  const [selectedProjectId, setSelectedProjectId] = React.useState<string | null>(null)

  const selectedProject = adminProjects.find(p => p.id === (selectedProjectId || adminProjects[0]?.id))

  const filteredDatasets = datasets.filter(d => 
    d.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    d.description?.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const handleTogglePublic = (datasetId: string, currentStatus: boolean) => {
    updateDatasetMutation.mutate({
      datasetId,
      isPublic: !currentStatus
    })
  }

  const handleDelete = (datasetId: string) => {
    if (confirm("Are you sure you want to delete this global dataset? This action is irreversible.")) {
      deleteDatasetMutation.mutate(datasetId)
    }
  }

  if (projectsLoading) {
    return (
      <div className="flex h-[80vh] items-center justify-center">
        <Loader2 className="size-8 animate-spin text-emerald-600" />
      </div>
    )
  }

  if (adminProjects.length === 0) {
    return (
      <div className="p-8">
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-8 text-center space-y-4">
          <AlertCircle className="size-12 text-amber-600 mx-auto" />
          <h2 className="text-2xl font-bold text-amber-900">No Administrative Projects Found</h2>
          <p className="text-amber-700 max-w-md mx-auto">
            You need at least one project owned by the system to manage global datasets. 
            Please create a project first.
          </p>
          <Button asChild className="bg-amber-600 hover:bg-amber-700 text-white font-bold rounded-xl h-12 px-6">
            <Link href="/dashboard">Go to Dashboard</Link>
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8 p-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] font-bold text-emerald-600 uppercase tracking-[0.3em] mb-1">Administrative Dashboard</p>
          <h1 className="text-4xl font-bold tracking-tight text-stone-900">Global Knowledge Base</h1>
          <p className="text-stone-500 mt-2 font-medium max-w-2xl text-base">
            Manage system-wide datasets and genomic references available in the Reference Library.
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex flex-col items-end">
            <span className="text-[10px] font-bold text-stone-400 uppercase tracking-widest mb-1.5 px-1">Target Project</span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild nativeButton={true}>
                <Button variant="outline" className="h-12 px-6 rounded-xl border-emerald-200 text-emerald-700 font-bold shadow-sm hover:bg-emerald-50 transition-all flex items-center gap-2">
                  <FolderKanban className="size-4" />
                  {selectedProject?.name || "Select Project"}
                  <ChevronDown className="size-4 opacity-50" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-64 rounded-xl shadow-xl border-stone-100 p-1">
                {adminProjects.map((p) => (
                  <DropdownMenuItem 
                    key={p.id} 
                    onClick={() => setSelectedProjectId(p.id)}
                    className={`rounded-lg p-3 font-bold cursor-pointer flex flex-col items-start gap-1 ${selectedProjectId === p.id ? 'bg-emerald-50 text-emerald-700' : 'text-stone-600 hover:bg-stone-50'}`}
                  >
                    <span>{p.name}</span>
                    <span className="text-[10px] font-mono opacity-50">{p.id}</span>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          
          <div className="flex items-end h-full pt-6">
            <AddDatasetDialog projectName={selectedProject?.name || ""} projectId={selectedProject?.id || ""} isGlobal={true} nativeButton={true}>
              <Button className="h-12 px-6 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white font-bold shadow-lg shadow-emerald-700/20" disabled={!selectedProjectId}>
                <Plus className="mr-2 size-5" /> Create Global Dataset
              </Button>
            </AddDatasetDialog>
          </div>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-4">
        <Card className="md:col-span-3 border-stone-200 shadow-sm rounded-2xl overflow-hidden bg-white">
          <CardHeader className="border-b border-stone-100 bg-stone-50/50 p-6">
            <div className="flex items-center justify-between gap-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-stone-400" />
                <Input 
                  placeholder="Search global datasets..." 
                  className="pl-10 h-11 rounded-xl border-stone-200 bg-white"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              <Badge variant="outline" className="h-11 px-4 rounded-xl border-stone-200 bg-white text-stone-600 font-bold">
                {filteredDatasets.length} Global Datasets
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {datasetsLoading ? (
              <div className="p-20 text-center">
                <Loader2 className="size-8 animate-spin text-emerald-600 mx-auto" />
              </div>
            ) : filteredDatasets.length > 0 ? (
              <div className="divide-y divide-stone-100">
                {filteredDatasets.map((dataset) => (
                  <div key={dataset.id} className="p-6 flex items-center justify-between hover:bg-stone-50/50 transition-colors group">
                    <div className="flex items-start gap-4">
                      <div className="bg-stone-100 p-3 rounded-xl group-hover:bg-emerald-100 group-hover:text-emerald-700 transition-colors">
                        <Database className="size-6" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="font-bold text-stone-900">{dataset.name}</h3>
                          {dataset.is_public ? (
                            <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200 text-[9px] font-black uppercase tracking-widest px-1.5 py-0">Public</Badge>
                          ) : (
                            <Badge className="bg-stone-100 text-stone-500 border-stone-200 text-[9px] font-black uppercase tracking-widest px-1.5 py-0">Private</Badge>
                          )}
                        </div>
                        <p className="text-sm text-stone-500 font-medium mt-1">{dataset.description || "No description provided."}</p>
                        <div className="flex items-center gap-4 mt-2">
                           <p className="text-[10px] font-mono text-stone-400">{dataset.id}</p>
                           <div className="flex items-center gap-1 text-[9px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-100">
                              <FolderKanban className="size-3" />
                              Project: {adminProjects.find(p => p.id === dataset.project_id)?.name || "System"}
                           </div>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-8">
                      <div className="flex flex-col items-end gap-1.5">
                        <div className="flex items-center gap-2">
                          {dataset.is_public ? <Globe className="size-3.5 text-emerald-600" /> : <Lock className="size-3.5 text-stone-400" />}
                          <span className="text-[10px] font-bold text-stone-500 uppercase tracking-widest">Library Visible</span>
                          <Switch 
                            checked={dataset.is_public}
                            onCheckedChange={() => handleTogglePublic(dataset.id, dataset.is_public)}
                            disabled={updateDatasetMutation.isPending}
                          />
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <Button variant="ghost" size="icon" className="rounded-xl text-stone-400 hover:text-red-600 hover:bg-red-50" onClick={() => handleDelete(dataset.id)}>
                          <Trash2 className="size-5" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-20 text-center space-y-4">
                <div className="bg-stone-100 size-16 rounded-full flex items-center justify-center mx-auto">
                   <Search className="size-8 text-stone-400" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-stone-900">No datasets found</h3>
                  <p className="text-stone-500 font-medium">Try adjusting your search or create a new global dataset.</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="border-stone-200 shadow-sm rounded-2xl bg-stone-900 text-white overflow-hidden">
            <CardHeader className="p-6 pb-0">
               <div className="bg-emerald-700/20 p-2 rounded-lg w-fit mb-4">
                 <ShieldCheck className="size-6 text-emerald-400" />
               </div>
               <CardTitle className="text-lg font-bold">Admin Controls</CardTitle>
               <CardDescription className="text-stone-400">Master Catalog Management</CardDescription>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
               <div className="space-y-4 text-sm text-stone-300 font-medium">
                 <div className="flex gap-3">
                    <CheckCircle2 className="size-5 text-emerald-500 shrink-0" />
                    <p>Global datasets can be stored in <strong>any administrative project</strong>.</p>
                 </div>
                 <div className="flex gap-3">
                    <CheckCircle2 className="size-5 text-emerald-500 shrink-0" />
                    <p>Toggle <strong>Library Visible</strong> to make references available for user attachment.</p>
                 </div>
                 <div className="flex gap-3">
                    <CheckCircle2 className="size-5 text-emerald-500 shrink-0" />
                    <p>Switch the <strong>Target Project</strong> above to organize your global data.</p>
                 </div>
               </div>
            </CardContent>
          </Card>

          <Card className="border-stone-200 shadow-sm rounded-2xl bg-white">
            <CardHeader>
               <CardTitle className="text-sm font-bold text-stone-900">Administrative Projects</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
               <div className="flex items-center justify-between text-xs">
                 <span className="text-stone-500 font-bold uppercase tracking-widest">Project Count</span>
                 <span className="font-mono text-emerald-700 font-bold">{adminProjects.length}</span>
               </div>
               <div className="h-1.5 w-full bg-stone-100 rounded-full overflow-hidden">
                 <div className="h-full w-full bg-emerald-500" />
               </div>
               <p className="text-[10px] text-stone-400 font-medium leading-relaxed">
                 All datasets owned by these projects are listed in this dashboard.
               </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
