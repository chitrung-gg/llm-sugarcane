"use client"

import * as React from "react"
import { Upload, FileText, Database, Loader2, Sprout, CheckCircle2, AlertCircle, Clock, Plus, X, FileCode } from "lucide-react"
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
import { useIngestionStatus } from "@/hooks/use-ingestion"
import { useProject } from "@/hooks/use-projects"
import { useParams, useSearchParams } from "next/navigation"
import { cn } from "@/lib/utils"
import { AddDatasetDialog } from "./add-dataset-dialog"

function TaskProgress({ taskId, onComplete }: { taskId: string; onComplete: () => void }) {
  const { data: status } = useIngestionStatus(taskId);

  React.useEffect(() => {
    if (status?.ready) {
      const timer = setTimeout(onComplete, 5000); // Remove after 5s when complete
      return () => clearTimeout(timer);
    }
  }, [status?.ready, onComplete]);

  if (!status) return null;

  const isSuccess = status.status === "SUCCESS";
  const isFailure = status.status === "FAILURE";
  const progress = status.meta?.percent || (isSuccess ? 100 : 0);

  return (
    <div className="bg-white border border-stone-100 rounded-xl p-3 shadow-sm flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isSuccess ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : 
           isFailure ? <AlertCircle className="h-4 w-4 text-red-500" /> : 
           <Clock className="h-4 w-4 text-stone-400 animate-pulse" />}
          <span className="text-[11px] font-bold text-stone-700 uppercase tracking-tight">
            {status.meta?.message || (isSuccess ? "Ingestion Complete" : "Processing...")}
          </span>
        </div>
        <span className="text-[10px] font-bold text-stone-400">{progress}%</span>
      </div>
      <div className="h-1.5 w-full bg-stone-100 rounded-full overflow-hidden">
        <div 
          className={cn(
            "h-full transition-all duration-500",
            isSuccess ? "bg-emerald-500" : isFailure ? "bg-red-500" : "bg-emerald-600"
          )}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

export function UploadZone() {
  const params = useParams()
  const searchParams = useSearchParams()
  const projectId = params.id as string
  const initialDatasetId = searchParams.get("datasetId") || ""
  
  const [dataType, setDataType] = React.useState<"genome" | "knowledge">("genome")
  const [datasetId, setDatasetId] = React.useState<string>(initialDatasetId)
  const [files, setFiles] = React.useState<File[]>([])
  const [activeTaskIds, setActiveTaskIds] = React.useState<string[]>([])

  const { data: project } = useProject(projectId)
  const { data: datasets } = useProjectDatasets(projectId)
  const uploadMutation = useUploadDatasetFiles()

  // Update datasetId if URL param changes
  React.useEffect(() => {
    if (initialDatasetId) {
      setDatasetId(initialDatasetId);
    }
  }, [initialDatasetId]);

  const allowedGenomic = [".fasta", ".fa", ".gff", ".gff3", ".fna", ".faa", ".gbk", ".bam", ".gz"];
  const allowedKnowledge = [".pdf", ".json", ".txt", ".docx", ".csv", ".md"];

  const validateFile = (file: File) => {
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    const allowed = dataType === "genome" ? allowedGenomic : allowedKnowledge;
    
    if (!allowed.includes(ext)) {
      alert(`Invalid file format: ${file.name}. Please upload: ${allowed.join(", ")}`);
      return false;
    }
    return true;
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFiles = Array.from(e.target.files);
      const validFiles = selectedFiles.filter(validateFile);
      setFiles(prev => [...prev, ...validFiles]);
      e.target.value = ""; // Reset input
    }
  }

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  }

  const handleUpload = () => {
    if (files.length === 0 || !datasetId) {
      alert("Please select at least one file and a dataset")
      return
    }
    
    uploadMutation.mutate({
      datasetId,
      files: files,
      sourceType: dataType === "genome" ? "user_private_genome" : "user_private_document"
    }, {
      onSuccess: (data: any) => {
        if (data.task_ids && data.task_ids.length > 0) {
          setActiveTaskIds(prev => [...prev, ...data.task_ids]);
        }
        setFiles([]);
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
    <div className="space-y-4">
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
                  setFiles([]);
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
                  setFiles([]);
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
            <div className="flex items-center justify-between">
              <Label htmlFor="dataset" className="font-semibold">Select Dataset</Label>
              <AddDatasetDialog projectName={project?.name} nativeButton={true}>
                <Button variant="ghost" size="xs" className="text-emerald-700 hover:text-emerald-800 hover:bg-emerald-50 h-6 gap-1 font-bold">
                  <Plus className="size-3" /> Add New
                </Button>
              </AddDatasetDialog>
            </div>
            <Select 
              value={datasetId} 
              onValueChange={(v: string | null) => setDatasetId(v || "")}
            >
              <SelectTrigger id="dataset">
                <SelectValue placeholder="Select a cultivar reference">
                   {datasets?.find(ds => ds.id === datasetId)?.name}
                </SelectValue>
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
              if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                const droppedFiles = Array.from(e.dataTransfer.files);
                const validFiles = droppedFiles.filter(validateFile);
                setFiles(prev => [...prev, ...validFiles]);
              }
            }}
          >
            <Upload className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm text-muted-foreground text-center font-medium">
              Drag and drop or click to select {dataType} files
            </p>
            <p className="text-[10px] text-stone-400 font-bold uppercase tracking-wider">
              {dataType === "genome" ? "FASTA, GFF, BAM" : "PDF, JSON, TXT, DOCX, CSV"}
            </p>
            <input 
              id="file-upload" 
              type="file" 
              className="hidden" 
              accept={acceptString}
              multiple
              onChange={handleFileChange}
            />
          </div>

          {files.length > 0 && (
            <div className="space-y-3">
               <Label className="font-semibold uppercase text-[10px] text-stone-400 ml-1 tracking-widest">Selected Files ({files.length})</Label>
               <div className="max-h-[200px] overflow-y-auto space-y-2 pr-1 no-scrollbar">
                  {files.map((f, i) => (
                    <div key={`${f.name}-${i}`} className="bg-stone-50 border border-stone-100 rounded-xl p-2.5 flex items-center justify-between group transition-all hover:bg-stone-100/50">
                       <div className="flex items-center gap-3 overflow-hidden">
                          <div className="bg-white p-1.5 rounded-lg border border-stone-100 shadow-sm shrink-0">
                             {dataType === "genome" ? <Database className="size-3.5 text-emerald-600" /> : <FileCode className="size-3.5 text-blue-600" />}
                          </div>
                          <span className="text-xs font-bold text-stone-700 truncate" title={f.name}>{f.name}</span>
                          <span className="text-[10px] text-stone-400 font-mono">{(f.size / 1024 / 1024).toFixed(2)} MB</span>
                       </div>
                       <Button 
                         variant="ghost" 
                         size="xs" 
                         onClick={(e) => {
                           e.stopPropagation();
                           removeFile(i);
                         }}
                         className="h-7 px-2 text-stone-400 hover:text-red-500 hover:bg-red-50 gap-1.5 transition-all"
                       >
                          <X className="size-3.5" />
                          <span className="text-[10px] font-bold uppercase tracking-tight">Remove</span>
                       </Button>
                    </div>
                  ))}
               </div>
            </div>
          )}
        </CardContent>
        <CardFooter>
          <Button 
            className="w-full font-bold h-12 bg-emerald-700 hover:bg-emerald-800 shadow-lg shadow-emerald-700/20 rounded-xl transition-all" 
            disabled={files.length === 0 || !datasetId || uploadMutation.isPending}
            onClick={handleUpload}
          >
            {uploadMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                Processing {files.length} {files.length === 1 ? 'File' : 'Files'}...
              </>
            ) : (
              <>
                <Upload className="mr-2 h-5 w-5" />
                Confirm & Upload {files.length} {files.length === 1 ? 'File' : 'Files'}
              </>
            )}
          </Button>
        </CardFooter>
      </Card>

      {activeTaskIds.length > 0 && (
        <div className="space-y-3">
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-stone-400 ml-1">Active Ingestion Tasks</p>
          {activeTaskIds.map(taskId => (
            <TaskProgress 
              key={taskId} 
              taskId={taskId} 
              onComplete={() => setActiveTaskIds(prev => prev.filter(id => id !== taskId))} 
            />
          ))}
        </div>
      )}
    </div>
  )
}
