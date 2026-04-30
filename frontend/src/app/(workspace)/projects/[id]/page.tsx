"use client"

import * as React from "react"
import { Database, FileCode, GraduationCap, Loader2 } from "lucide-react"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { UploadZone } from "@/components/datasets/upload-zone"
import { useProject } from "@/hooks/use-projects"
import { useProjectDatasets } from "@/hooks/use-datasets"

interface ProjectPageProps {
  params: React.Usable<{ id: string }>
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
  const totalFiles = datasets.reduce((acc, ds) => acc + (ds.files?.length || 0), 0)
  const genomeFiles = datasets.reduce((acc, ds) => 
    acc + (ds.files?.filter(f => f.file_type.includes('genome')).length || 0), 0)

  const stats = [
    {
      title: "Datasets",
      value: totalDatasets.toString(),
      description: "Cultivars in this project",
      icon: Database,
    },
    {
      title: "Total Files",
      value: totalFiles.toString(),
      description: "Genomes & Research Docs",
      icon: FileCode,
    },
    {
      title: "Genome Assets",
      value: genomeFiles.toString(),
      description: ".fasta, .gff, .bam files",
      icon: GraduationCap,
    },
  ]

  return (
    <div className="space-y-8 p-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight uppercase text-stone-900">{project.name}</h1>
        <p className="text-muted-foreground mt-1">
          {project.description || "Overview and data management for your sugarcane research project."}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {stats.map((stat) => (
          <Card key={stat.title} className="border-stone-200 shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-bold text-stone-500 uppercase tracking-wider">
                {stat.title}
              </CardTitle>
              <stat.icon className="h-4 w-4 text-emerald-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-stone-900">{stat.value}</div>
              <p className="text-xs text-stone-400 font-medium">
                {stat.description}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        <div className="md:col-span-1 lg:col-span-4">
          <UploadZone />
        </div>
        <Card className="md:col-span-1 lg:col-span-3 border-stone-200 shadow-sm">
          <CardHeader>
            <CardTitle className="font-bold text-stone-800">Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm text-stone-400 font-medium italic">
              No recent activity to show. Upload some data to get started.
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
