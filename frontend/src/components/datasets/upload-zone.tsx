"use client"

import * as React from "react"
import { Upload, FileText, Database, Loader2 } from "lucide-react"
import { useMutation } from "@tanstack/react-query"
import { api } from "@/lib/api-client"
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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export function UploadZone() {
  const [dataType, setDataType] = React.useState<"genome" | "knowledge">("genome")
  const [datasetId, setDatasetId] = React.useState<string>("")
  const [file, setFile] = React.useState<File | null>(null)

  const mutation = useMutation({
    mutationFn: async () => {
      if (!file || !datasetId) return
      
      const formData = new FormData()
      formData.append("files", file)
      // Map frontend type to backend IngestionSourceType
      const sourceType = dataType === "genome" 
        ? "user_private_genome" 
        : "user_private_knowledge"
      formData.append("source_type", sourceType)

      return api.post(`/workspace/datasets/${datasetId}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })
    },
    onSuccess: () => {
      alert("Upload successful!")
      setFile(null)
    },
    onError: (error) => {
      console.error("Upload failed:", error)
      alert("Upload failed. Please check console for details.")
    }
  })

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
    }
  }

  const handleUpload = () => {
    if (!file || !datasetId) {
      alert("Please select a file and a dataset")
      return
    }
    mutation.mutate()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      document.getElementById('file-upload')?.click()
    }
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Upload Dataset</CardTitle>
        <CardDescription>
          Upload genomic or knowledge documents to your project.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-3">
          <Label>Data Type</Label>
          <RadioGroup
            defaultValue="genome"
            onValueChange={(v) => setDataType(v as "genome" | "knowledge")}
            className="flex gap-4"
          >
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="genome" id="genome" />
              <Label htmlFor="genome" className="flex items-center gap-1.5 cursor-pointer">
                <Database className="h-4 w-4" aria-hidden="true" />
                Genome
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="knowledge" id="knowledge" />
              <Label htmlFor="knowledge" className="flex items-center gap-1.5 cursor-pointer">
                <FileText className="h-4 w-4" aria-hidden="true" />
                Knowledge
              </Label>
            </div>
          </RadioGroup>
        </div>

        <div className="space-y-3">
          <Label htmlFor="dataset">Select Dataset</Label>
          <Select onValueChange={(v: string | null) => setDatasetId(v || "")}>
            <SelectTrigger id="dataset">
              <SelectValue placeholder="Select a cultivar reference" />
            </SelectTrigger>
            <SelectContent>
              {/* These IDs should ideally come from an API call to /workspace/projects/{id}/datasets */}
              <SelectItem value="ds1">R570 Reference</SelectItem>
              <SelectItem value="ds2">SP80-3280 Hybrid</SelectItem>
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
              setFile(e.dataTransfer.files[0])
            }
          }}
        >
          <Upload className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
          <p className="text-sm text-muted-foreground text-center">
            {file ? file.name : "Drag and drop or click to select files"}
          </p>
          <input 
            id="file-upload" 
            type="file" 
            className="hidden" 
            onChange={handleFileChange}
          />
        </div>
      </CardContent>
      <CardFooter>
        <Button 
          className="w-full" 
          disabled={!file || !datasetId || mutation.isPending}
          onClick={handleUpload}
        >
          {mutation.isPending ? (
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
