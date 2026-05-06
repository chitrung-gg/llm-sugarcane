"use client"

import * as React from "react"
import { Dna, Loader2, Upload, File, Database, ShieldCheck, CheckCircle2, FlaskConical } from "lucide-react"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useUploadDatasetFiles } from "@/hooks/use-datasets"
import { useProjects } from "@/hooks/use-projects"

export default function AdminReferencesPage() {
  const { data: projects = [] } = useProjects()
  const uploadMutation = useUploadDatasetFiles()
  
  const [selectedProjectId, setSelectedProjectId] = React.useState("")
  const [selectedDatasetId, setSelectedDatasetId] = React.useState("")
  const [selectedFiles, setSelectedFiles] = React.useState<File[]>([])
  const [uploadType, setUploadType] = React.useState<"user_private_genome" | "knowledge_base">("user_private_genome")

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setSelectedFiles(Array.from(e.target.files))
    }
  }

  const handleUpload = () => {
    if (!selectedDatasetId || selectedFiles.length === 0) return

    uploadMutation.mutate({
      datasetId: selectedDatasetId,
      files: selectedFiles,
      sourceType: uploadType
    }, {
      onSuccess: () => {
        alert("System reference files uploaded successfully!")
        setSelectedFiles([])
      }
    })
  }

  return (
    <div className="space-y-8 p-8">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] font-bold text-emerald-600 uppercase tracking-[0.3em] mb-1">Administrative Dashboard</p>
          <h1 className="text-4xl font-bold tracking-tight text-stone-900">System References</h1>
          <p className="text-stone-500 mt-2 font-medium max-w-2xl text-base">
            Upload global genomic reference files and knowledge base documents available system-wide.
          </p>
        </div>
        <div className="bg-emerald-50 px-4 py-3 rounded-2xl border border-emerald-100 flex items-center gap-3">
           <ShieldCheck className="size-6 text-emerald-700" />
           <div>
             <p className="text-[10px] font-black uppercase tracking-widest text-emerald-800">Admin Authorization</p>
             <p className="text-[11px] font-bold text-emerald-600/70 leading-none">Global Write Access Enabled</p>
           </div>
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <div className="space-y-6">
          <Card className="border-stone-200 shadow-md rounded-2xl overflow-hidden bg-white">
            <CardHeader className="bg-stone-900 text-white p-6">
              <CardTitle className="text-xl font-bold flex items-center gap-2">
                <Upload className="h-5 w-5 text-emerald-500" />
                Global Reference Upload
              </CardTitle>
              <CardDescription className="text-stone-400 font-medium">
                Add data to system-managed datasets.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-8 space-y-6">
              <div className="space-y-2">
                <Label className="text-xs font-bold text-stone-500 uppercase tracking-widest ml-1">Select System Project</Label>
                <div className="grid grid-cols-1 gap-2">
                   {projects.filter(p => p.owner_id === "00000000-0000-0000-0000-000000000000").map(p => (
                     <button 
                       key={p.id}
                       onClick={() => setSelectedProjectId(p.id)}
                       className={`flex items-center gap-3 p-3 rounded-xl border transition-all text-left ${selectedProjectId === p.id ? 'bg-emerald-50 border-emerald-200 shadow-sm' : 'bg-stone-50 border-stone-100 hover:bg-stone-100'}`}
                     >
                        <FlaskConical className={`size-5 ${selectedProjectId === p.id ? 'text-emerald-700' : 'text-stone-400'}`} />
                        <div>
                          <p className={`text-sm font-bold ${selectedProjectId === p.id ? 'text-emerald-900' : 'text-stone-700'}`}>{p.name}</p>
                          <p className="text-[10px] text-stone-400 font-medium">{p.id}</p>
                        </div>
                        {selectedProjectId === p.id && <CheckCircle2 className="ml-auto size-4 text-emerald-700" />}
                     </button>
                   ))}
                </div>
              </div>

              {selectedProjectId && (
                <div className="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
                  <div className="space-y-2">
                    <Label className="text-xs font-bold text-stone-500 uppercase tracking-widest ml-1">Upload Type</Label>
                    <div className="grid grid-cols-2 gap-3">
                       <button 
                        onClick={() => setUploadType("user_private_genome")}
                        className={`flex flex-col items-center gap-2 p-4 rounded-xl border transition-all ${uploadType === "user_private_genome" ? 'bg-emerald-50 border-emerald-200 text-emerald-700 shadow-sm' : 'bg-stone-50 border-stone-100 text-stone-500 hover:bg-stone-100'}`}
                       >
                         <Dna className="size-6" />
                         <span className="text-[10px] font-bold uppercase tracking-widest">Genomic Data</span>
                       </button>
                       <button 
                        onClick={() => setUploadType("knowledge_base")}
                        className={`flex flex-col items-center gap-2 p-4 rounded-xl border transition-all ${uploadType === "knowledge_base" ? 'bg-blue-50 border-blue-200 text-blue-700 shadow-sm' : 'bg-stone-50 border-stone-100 text-stone-500 hover:bg-stone-100'}`}
                       >
                         <File className="size-6" />
                         <span className="text-[10px] font-bold uppercase tracking-widest">Knowledge Base</span>
                       </button>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-xs font-bold text-stone-500 uppercase tracking-widest ml-1">Target Dataset UUID</Label>
                    <Input 
                      placeholder="Paste Dataset ID here..." 
                      className="h-11 rounded-xl bg-stone-50/50 border-stone-200 font-mono text-xs"
                      value={selectedDatasetId}
                      onChange={(e) => setSelectedDatasetId(e.target.value)}
                    />
                    <p className="text-[10px] text-stone-400 font-medium italic ml-1">* Admins must manually target system datasets via ID for safety.</p>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-xs font-bold text-stone-500 uppercase tracking-widest ml-1">Select Files</Label>
                    <Input 
                      type="file" 
                      multiple 
                      className="h-11 rounded-xl bg-stone-50/50 border-stone-200 pt-2 text-xs"
                      onChange={handleFileChange}
                    />
                  </div>

                  <Button 
                    className="w-full h-12 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white font-bold shadow-lg shadow-emerald-700/20 mt-4"
                    disabled={!selectedDatasetId || selectedFiles.length === 0 || uploadMutation.isPending}
                    onClick={handleUpload}
                  >
                    {uploadMutation.isPending ? (
                      <Loader2 className="mr-2 size-4 animate-spin" />
                    ) : (
                      <Upload className="mr-2 size-4" />
                    )}
                    Deploy System Reference
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
           <Card className="border-stone-200 shadow-sm rounded-2xl bg-white/50 backdrop-blur-sm">
            <CardHeader>
              <CardTitle className="text-sm font-bold text-stone-900 flex items-center gap-2">
                <Database className="h-4 w-4 text-stone-400" />
                Admin Deployment Guide
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-stone-500 space-y-4 font-medium leading-relaxed">
              <p>
                Files uploaded here are treated as <strong>System References</strong>. They will be indexed globally and made available to LLM agents for all users depending on system configuration.
              </p>
              <div className="bg-stone-100/50 p-4 rounded-xl border border-stone-100">
                 <h4 className="text-[10px] font-black text-stone-400 uppercase tracking-[0.2em] mb-3">Best Practices</h4>
                 <ul className="space-y-3">
                   <li className="flex gap-3">
                      <div className="bg-emerald-100 h-5 w-5 rounded-full flex items-center justify-center shrink-0">
                        <span className="text-[10px] font-bold text-emerald-700">1</span>
                      </div>
                      <p className="text-xs">Ensure FASTA/GFF3 files are validated for coordinate consistency before global deployment.</p>
                   </li>
                   <li className="flex gap-3">
                      <div className="bg-emerald-100 h-5 w-5 rounded-full flex items-center justify-center shrink-0">
                        <span className="text-[10px] font-bold text-emerald-700">2</span>
                      </div>
                      <p className="text-xs">Use meaningful filenames as they will be used as citation keys in agent responses.</p>
                   </li>
                 </ul>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
