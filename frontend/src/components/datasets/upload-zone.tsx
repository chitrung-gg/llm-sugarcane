"use client"

import * as React from "react"
import { Upload, FileText, Database, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

import { useUploadDatasetFiles, useProjectDatasets } from "@/hooks/use-datasets"
import { useProject } from "@/hooks/use-projects"
import { useParams } from "next/navigation"
import { Sprout } from "lucide-react"
import { cn } from "@/lib/utils"

export function UploadZone() {
  const params = useParams()
  const projectId = params.id as string
  const [dataType, setDataType] = React.useState<"genome" | "knowledge">("genome")
  const [datasetId, setDatasetId] = React.useState<string>("")
  const [file, setFile] = React.useState<File | null>(null)

  const { data: project } = useProject(projectId)
  const { data: datasets } = useProjectDatasets(projectId)
  const uploadMutation = useUploadDatasetFiles()

  const allowedGenomic = [".fasta", ".fa", ".gff", ".gff3", ".fna", ".faa", ".gbk", ".bam"];
  const allowedKnowledge = [".pdf", ".json", ".txt", ".docx", ".csv", ".md"];

  const validateFile = (file: File) => {
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    const allowed = dataType === "genome" ? allowedGenomic : allowedKnowledge;
    
    if (!allowed.includes(ext)) {
      alert(`Invalid file format for ${dataType}. Please upload: ${allowed.join(", ")}`);
      return false;
    }
    return true;
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (validateFile(selectedFile)) {
        setFile(selectedFile);
      } else {
        e.target.value = ""; // Reset input
      }
    }
  }

  const handleUpload = () => {
    if (!file || !datasetId) {
      alert("Please select a file and a dataset")
      return
    }
    
    uploadMutation.mutate({
      datasetId,
      files: [file],
      sourceType: dataType === "genome" ? "user_private_genome" : "user_private_knowledge"
    }, {
      onSuccess: () => {
        alert("Upload successful!")
        setFile(null)
      },
      onError: (error) => {
        console.error("Upload failed:", error)
        alert("Upload failed.")
      }
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      document.getElementById('file-upload')?.click()
    }
  }

  const acceptString = (dataType === "genome" ? allowedGenomic : allowedKnowledge).join(",");

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="font-bold">Upload Dataset</CardTitle>
        <CardDescription>
          Upload genomic or knowledge documents to your project.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Project Context Box */}
        <div className="bg-stone-50 border border-stone-100 rounded-xl p-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-white p-2 rounded-lg border border-stone-100 shadow-sm">
              <Sprout className="h-4 w-4 text-emerald-700" />
            </div>
            <div>
              <p className="text-[9px] font-bold text-stone-400 uppercase tracking-widest leading-none mb-1">Target Project</p>
              <p className="text-xs font-bold text-stone-900">{project?.name || "Loading..."}</p>
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <Label className="font-semibold uppercase text-[10px] text-stone-400 ml-1 tracking-widest">Select Data Category</Label>
          <div className="grid grid-cols-2 gap-3">
            <button 
              onClick={() => {
                setDataType("genome");
                setFile(null);
              }}
              className={cn(
                "flex flex-col items-center justify-center p-4 rounded-xl border-2 transition-all gap-2",
                dataType === "genome" 
                  ? "border-emerald-600 bg-emerald-50 text-emerald-700 shadow-sm" 
                  : "border-stone-100 bg-white text-stone-400 hover:border-stone-200"
              )}
            >
              <Database className="h-5 w-5" />
              <span className="text-xs font-bold uppercase tracking-wider">Genomic Data</span>
            </button>
            <button 
              onClick={() => {
                setDataType("knowledge");
                setFile(null);
              }}
              className={cn(
                "flex flex-col items-center justify-center p-4 rounded-xl border-2 transition-all gap-2",
                dataType === "knowledge" 
                  ? "border-emerald-600 bg-emerald-50 text-emerald-700 shadow-sm" 
                  : "border-stone-100 bg-white text-stone-400 hover:border-stone-200"
              )}
            >
              <FileText className="h-5 w-5" />
              <span className="text-xs font-bold uppercase tracking-wider">Knowledge Base</span>
            </button>
          </div>
        </div>

        <div className="space-y-3">
          <Label htmlFor="dataset" className="font-semibold">Select Dataset</Label>
          <Select onValueChange={(v: string | null) => setDatasetId(v || "")}>
            <SelectTrigger id="dataset">
              <SelectValue placeholder="Select a cultivar reference" />
            </SelectTrigger>
            <SelectContent>
              {datasets?.map((ds) => (
                <SelectItem key={ds.id} value={ds.id}>{ds.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div 
          role="button"
          tabIndex={0}
          aria-label="Upload file"
          className="border-2 border-dashed border-muted-foreground/25 rounded-lg p-10 flex flex-col items-center justify-center gap-2 hover:border-primary/50 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          onClick={() => document.getElementById('file-upload')?.click()}
          onKeyDown={handleKeyDown}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault()
            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
              const droppedFile = e.dataTransfer.files[0];
              if (validateFile(droppedFile)) {
                setFile(droppedFile);
              }
            }
          }}
        >
          <Upload className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
          <p className="text-sm text-muted-foreground text-center font-medium">
            {file ? file.name : `Drag and drop or click to select ${dataType} files`}
          </p>
          <p className="text-[10px] text-stone-400 font-bold uppercase tracking-wider">
            {dataType === "genome" ? "FASTA, GFF, BAM" : "PDF, JSON, TXT, DOCX, CSV"}
          </p>
          <input 
            id="file-upload" 
            type="file" 
            className="hidden" 
            accept={acceptString}
            onChange={handleFileChange}
          />
        </div>
      </CardContent>
      <CardFooter>
        <Button 
          className="w-full font-bold" 
          disabled={!file || !datasetId || uploadMutation.isPending}
          onClick={handleUpload}
        >
          {uploadMutation.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Uploading...
            </>
          ) : (
            "Upload to Project"
          )}
        </Button>
      </CardFooter>
    </Card>
  )
}
