"use client"

import * as React from "react"
import { UploadZone } from "@/components/datasets/upload-zone"
import { useProject } from "@/hooks/use-projects"
import { useParams } from "next/navigation"
import { Loader2, ArrowLeft } from "lucide-react"
import Link from "next/link"
import { Button } from "@/components/ui/button"

export default function UploadPage() {
  const params = useParams()
  const projectId = params.id as string
  const { data: project, isLoading } = useProject(projectId)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-stone-300" />
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-8">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild className="rounded-full">
          <Link href={`/projects/${projectId}`}>
            <ArrowLeft className="h-5 w-5" />
          </Link>
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-stone-900">Upload Data</h1>
          <p className="text-stone-500 font-medium">Add new genomic sequences or knowledge documents to <span className="text-emerald-700 font-bold">{project?.name}</span>.</p>
        </div>
      </div>

      <UploadZone />
    </div>
  )
}
