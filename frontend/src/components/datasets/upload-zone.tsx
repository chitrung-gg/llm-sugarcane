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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

import { useUploadDatasetFiles, useProjectDatasets } from "@/hooks/use-datasets"
import { useParams } from "next/navigation"

export function UploadZone() {
  const params = useParams()
  const projectId = params.id as string
  const [dataType, setDataType] = React.useState<"genome" | "knowledge">("genome")
  const [datasetId, setDatasetId] = React.useState<string>("")
  const [file, setFile] = React.useState<File | null>(null)

  const { data: datasets } = useProjectDatasets(projectId)
  const uploadMutation = useUploadDatasetFiles()

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

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="font-bold">Upload Dataset</CardTitle>
        <CardDescription>
          Upload genomic or knowledge documents to your project.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-3">
          <Label className="font-semibold">Data Type</Label>
          <RadioGroup
            defaultValue="genome"
            onValueChange={(v) => setDataType(v as "genome" | "knowledge")}
            className="flex gap-4"
          >
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="genome" id="genome" />
              <Label htmlFor="genome" className="flex items-center gap-1.5 cursor-pointer font-medium">
                <Database className="h-4 w-4" aria-hidden="true" />
                Genome
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="knowledge" id="knowledge" />
              <Label htmlFor="knowledge" className="flex items-center gap-1.5 cursor-pointer font-medium">
                <FileText className="h-4 w-4" aria-hidden="true" />
                Knowledge
              </Label>
            </div>
          </RadioGroup>
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
              setFile(e.dataTransfer.files[0])
            }
          }}
        >
          <Upload className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
          <p className="text-sm text-muted-foreground text-center font-medium">
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
