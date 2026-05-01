"use client"

import * as React from "react"
import { Database, FileCode, GraduationCap, Loader2, Dna, File, Upload, Trash2, Plus } from "lucide-react"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { UploadZone } from "@/components/datasets/upload-zone"
import { ProjectSettingsDialog } from "@/components/projects/project-settings-dialog"
import { useProject } from "@/hooks/use-projects"
import { useProjectDatasets, useDatasetFiles, useDeleteDataset, useDeleteDatasetFile } from "@/hooks/use-datasets"
import { Dataset } from "@/lib/types"
import Link from "next/link"

interface ProjectPageProps {
  params: React.Usable<{ id: string }>
}

function DatasetRow({ dataset }: { dataset: Dataset }) {
  const { data: files = [] } = useDatasetFiles(dataset.id)
  const deleteDatasetMutation = useDeleteDataset()
  const deleteFileMutation = useDeleteDatasetFile()
  
  const genomeFiles = files.filter(f => f.file_type.includes('genome'))
  const knowledgeFiles = files.filter(f => !f.file_type.includes('genome'))

  const handleDeleteDataset = () => {
    if (confirm(`Are you sure you want to delete the dataset "${dataset.name}"?`)) {
      deleteDatasetMutation.mutate(dataset.id)
    }
  }

  const handleDeleteFile = (fileId: string) => {
    if (confirm("Are you sure you want to delete this file?")) {
      deleteFileMutation.mutate({ fileId, datasetId: dataset.id })
    }
  }

  return (
    <div className="p-6 space-y-4 hover:bg-stone-50/50 transition-colors group">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-bold text-stone-900">{dataset.name}</h3>
            <span className="text-[10px] bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full font-bold uppercase tracking-widest border border-emerald-100">
              Cultivar
            </span>
          </div>
          <p className="text-sm text-stone-500 font-medium">{dataset.description || "No description provided."}</p>
          <p className="text-[10px] font-mono text-stone-400">ID: {dataset.id}</p>
        </div>
        
        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
           <Button variant="outline" size="sm" className="h-8 rounded-lg border-stone-200" asChild>
              <Link href={`/projects/${dataset.project_id}/upload?datasetId=${dataset.id}`}>
                <Upload className="size-3.5 mr-1.5" /> Upload
              </Link>
           </Button>
           <Button 
             variant="ghost" 
             size="icon-sm" 
             className="text-stone-400 hover:text-red-500"
             onClick={handleDeleteDataset}
             disabled={deleteDatasetMutation.isPending}
           >
              {deleteDatasetMutation.isPending ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
           </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
           <p className="text-[10px] font-bold text-stone-400 uppercase tracking-widest flex items-center gap-1.5">
             <Dna className="size-3" /> Genomic Data ({genomeFiles.length})
           </p>
           <div className="bg-white rounded-xl border border-stone-100 divide-y divide-stone-50 overflow-hidden shadow-sm min-h-[60px]">
              {genomeFiles.length === 0 ? (
                <p className="p-3 text-[11px] text-stone-400 italic">No sequences uploaded.</p>
              ) : (
                genomeFiles.map(f => (
                  <div key={f.id} className="p-2 flex items-center justify-between group/file hover:bg-red-50/30 transition-colors">
                     <div className="flex items-center gap-2 text-[11px] text-stone-600 font-medium min-w-0">
                        <span className="truncate">{f.file_name}</span>
                     </div>
                     <button 
                       onClick={() => handleDeleteFile(f.id)}
                       className="opacity-0 group-hover/file:opacity-100 p-1 text-stone-300 hover:text-red-500 transition-all"
                     >
                       <Trash2 className="size-3" />
                     </button>
                  </div>
                ))
              )}
           </div>
        </div>
        <div className="space-y-2">
           <p className="text-[10px] font-bold text-stone-400 uppercase tracking-widest flex items-center gap-1.5">
             <File className="size-3" /> Knowledge Base ({knowledgeFiles.length})
           </p>
           <div className="bg-white rounded-xl border border-stone-100 divide-y divide-stone-50 overflow-hidden shadow-sm min-h-[60px]">
              {knowledgeFiles.length === 0 ? (
                <p className="p-3 text-[11px] text-stone-400 italic">No documents uploaded.</p>
              ) : (
                knowledgeFiles.map(f => (
                  <div key={f.id} className="p-2 flex items-center justify-between group/file hover:bg-red-50/30 transition-colors">
                     <div className="flex items-center gap-2 text-[11px] text-stone-600 font-medium min-w-0">
                        <span className="truncate">{f.file_name}</span>
                     </div>
                     <button 
                       onClick={() => handleDeleteFile(f.id)}
                       className="opacity-0 group-hover/file:opacity-100 p-1 text-stone-300 hover:text-red-500 transition-all"
                     >
                       <Trash2 className="size-3" />
                     </button>
                  </div>
                ))
              )}
           </div>
        </div>
      </div>
    </div>
  )
}

export default function ProjectPage({ params }: ProjectPageProps) {
  const { id } = React.use(params)
  
  return <ProjectContent id={id} />
}

function ProjectContent({ id }: { id: string }) {
  const { data: project, isLoading: projectLoading } = useProject(id)
  const { data: datasets = [], isLoading: datasetsLoading } = useProjectDatasets(id)
  
  if (projectLoading || datasetsLoading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-stone-300" />
      </div>
    )
  }

  if (!project) {
    return (
      <div className="p-8 text-center">
        <h2 className="text-xl font-bold text-stone-800">Project not found</h2>
        <p className="text-stone-500">The requested research project could not be located.</p>
      </div>
    )
  }

  // Calculate stats
  const totalDatasets = datasets.length

  const stats = [
    {
      title: "Datasets",
      value: totalDatasets.toString(),
      description: "Cultivars in this project",
      icon: Database,
    },
    {
      title: "Project Status",
      value: "Active",
      description: "Ready for analysis",
      icon: FileCode,
    },
    {
      title: "Created",
      value: new Date(project.created_at).toLocaleDateString(),
      description: "Project inception date",
      icon: GraduationCap,
    },
  ]

  return (
    <div className="space-y-8 p-8">
      <div className="flex items-end justify-between">
        <div>
          <p className="text-[10px] font-bold text-emerald-700 uppercase tracking-[0.3em] mb-1">Genomic Research Workspace</p>
          <h1 className="text-4xl font-bold tracking-tight text-stone-900">{project.name}</h1>
          <p className="text-stone-500 mt-2 font-medium max-w-2xl text-base">
            {project.description || "Overview and data management for your sugarcane research project."}
          </p>
        </div>
        <div className="flex items-center gap-3">
           <ProjectSettingsDialog project={project} />
           <Button className="bg-emerald-700 hover:bg-emerald-800 rounded-xl font-bold shadow-lg shadow-emerald-700/20" asChild>
              <Link href={`/projects/${id}/chat`}>
                <Upload className="mr-2 size-4" /> Start Analysis
              </Link>
           </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {stats.map((stat) => (
          <Card key={stat.title} className="border-stone-200 shadow-sm rounded-2xl bg-white/50 backdrop-blur-sm">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-[10px] font-bold text-stone-400 uppercase tracking-widest">
                {stat.title}
              </CardTitle>
              <div className="bg-stone-50 p-2 rounded-lg border border-stone-100">
                <stat.icon className="h-4 w-4 text-emerald-600" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-stone-900 tracking-tight">{stat.value}</div>
              <p className="text-xs text-stone-400 font-semibold mt-1">
                {stat.description}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8 space-y-6">
           <Card className="border-stone-200 shadow-md rounded-2xl overflow-hidden bg-white">
            <CardHeader className="bg-stone-900 text-white p-6">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-xl font-bold flex items-center gap-2">
                    <Database className="h-5 w-5 text-emerald-500" />
                    Project Datasets
                  </CardTitle>
                  <CardDescription className="text-stone-400 font-medium">
                    Manage cultivar references and knowledge documents.
                  </CardDescription>
                </div>
                <Button variant="outline" className="bg-white/5 border-white/10 text-white hover:bg-white/10 rounded-xl font-bold" asChild>
                   <Link href={`/projects/${id}/upload`}>
                      <Plus className="mr-2 size-4" /> Add Dataset
                   </Link>
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {datasets.length === 0 ? (
                <div className="p-12 text-center space-y-4">
                  <div className="bg-stone-50 w-16 h-16 rounded-full flex items-center justify-center mx-auto border border-stone-100">
                    <Database className="size-8 text-stone-300" />
                  </div>
                  <div className="space-y-1">
                    <h3 className="font-bold text-stone-900">No Datasets Found</h3>
                    <p className="text-sm text-stone-500 max-w-xs mx-auto">Create your first dataset to start uploading genomic sequences or documents.</p>
                  </div>
                  <Button className="bg-emerald-700 hover:bg-emerald-800 rounded-xl font-bold px-6" asChild>
                    <Link href={`/projects/${id}/upload`}>Create Dataset</Link>
                  </Button>
                </div>
              ) : (
                <div className="divide-y divide-stone-100">
                  {datasets.map((ds) => (
                    <DatasetRow key={ds.id} dataset={ds} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
        <div className="lg:col-span-4">
          <UploadZone />
        </div>
      </div>
    </div>
  )
}
