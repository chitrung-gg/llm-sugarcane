import * as React from "react"
import { Database, FileCode, GraduationCap } from "lucide-react"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { UploadZone } from "@/components/datasets/upload-zone"

interface ProjectPageProps {
  params: Promise<{ id: string }>
}

export default async function ProjectPage({ params }: ProjectPageProps) {
  const { id } = await params
  
  // Mock data for stats
  const stats = [
    {
      title: "Datasets",
      value: "12",
      description: "Total cultivars tracked",
      icon: Database,
    },
    {
      title: "Genomic Files",
      value: "45",
      description: ".fasta, .gff, .bam files",
      icon: FileCode,
    },
    {
      title: "Knowledge Docs",
      value: "128",
      description: ".pdf, .json research docs",
      icon: GraduationCap,
    },
  ]

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight uppercase">{id}</h1>
        <p className="text-muted-foreground">
          Overview and data management for your sugarcane research project.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {stats.map((stat) => (
          <Card key={stat.title}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {stat.title}
              </CardTitle>
              <stat.icon className="h-4 w-4 text-primary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
              <p className="text-xs text-muted-foreground">
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
        <Card className="md:col-span-1 lg:col-span-3">
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm text-muted-foreground">
              No recent activity to show. Upload some data to get started.
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
