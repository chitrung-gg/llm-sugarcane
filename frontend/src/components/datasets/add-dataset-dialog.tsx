"use client"

import * as React from "react"
import { Dialog, DialogContent, DialogTitle, DialogTrigger, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Database, Sprout, FileText } from "lucide-react"

import { useCreateDataset } from "@/hooks/use-datasets"
import { useParams } from "next/navigation"
import { cn } from "@/lib/utils"

export function AddDatasetDialog({ 
  children, 
  projectName,
  nativeButton = true
}: { 
  children: React.ReactElement;
  projectName?: string;
  nativeButton?: boolean;
}) {
  const params = useParams()
  const projectId = params.id as string
  const [open, setOpen] = React.useState(false)
  const [name, setName] = React.useState("")
  const [description, setDescription] = React.useState("")
  const [dataType, setDataType] = React.useState<"genome" | "knowledge">("genome")
  
  const createMutation = useCreateDataset()

  const handleCreate = () => {
    if (!name || !projectId) return
    
    createMutation.mutate({
      projectId,
      name,
      description
    }, {
      onSuccess: () => {
        setOpen(false)
        setName("")
        setDescription("")
      }
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={children} nativeButton={nativeButton} />
      <DialogContent className="sm:max-w-[480px] rounded-2xl border-stone-200 bg-white p-0 overflow-hidden shadow-2xl">
        <div className="bg-stone-900 p-8 text-white">
          <div className="space-y-1">
            <div className="bg-emerald-700 w-10 h-10 rounded-xl flex items-center justify-center mb-2">
              <Database className="h-5 w-5 text-white" />
            </div>
            <DialogTitle className="text-2xl font-bold">New Dataset</DialogTitle>
            <DialogDescription className="text-stone-400 font-medium">
              Create a container for genomic data or research papers.
            </DialogDescription>
          </div>
        </div>
        
        <div className="p-8 space-y-6">
          {/* Project Context Box */}
          <div className="bg-stone-50 border border-stone-100 rounded-xl p-4 flex items-center justify-between">
            <div>
              <p className="text-[10px] font-bold text-stone-400 uppercase tracking-widest leading-none mb-1.5">Target Project</p>
              <p className="text-sm font-bold text-stone-900">{projectName || "Active Project"}</p>
            </div>
            <div className="bg-white p-2 rounded-lg border border-stone-100 shadow-sm">
              <Sprout className="h-4 w-4 text-emerald-700" />
            </div>
          </div>

          <div className="space-y-4">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-stone-400 ml-1">Dataset Category</p>
            <div className="grid grid-cols-2 gap-3">
              <button 
                onClick={() => setDataType("genome")}
                className={cn(
                  "flex flex-col items-center justify-center p-4 rounded-xl border-2 transition-all gap-2",
                  dataType === "genome" 
                    ? "border-emerald-600 bg-emerald-50 text-emerald-700 shadow-sm" 
                    : "border-stone-100 bg-white text-stone-400 hover:border-stone-200"
                )}
              >
                <Database className="h-5 w-5" />
                <span className="text-xs font-bold uppercase tracking-wider">Genome</span>
              </button>
              <button 
                onClick={() => setDataType("knowledge")}
                className={cn(
                  "flex flex-col items-center justify-center p-4 rounded-xl border-2 transition-all gap-2",
                  dataType === "knowledge" 
                    ? "border-emerald-600 bg-emerald-50 text-emerald-700 shadow-sm" 
                    : "border-stone-100 bg-white text-stone-400 hover:border-stone-200"
                )}
              >
                <FileText className="h-5 w-5" />
                <span className="text-xs font-bold uppercase tracking-wider">Knowledge</span>
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <Label className="text-[10px] font-bold uppercase tracking-[0.2em] text-stone-400 ml-1">Dataset Alias / Cultivar</Label>
            <Input 
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={dataType === "genome" ? "e.g., Cultivar R570 Reference" : "e.g., Metabolic Pathway Study"} 
              className="h-12 rounded-xl border-stone-200 bg-stone-50/50 focus-visible:ring-emerald-500 focus-visible:border-emerald-500 font-medium" 
            />
          </div>

          <div className="space-y-2">
            <Label className="text-[10px] font-bold uppercase tracking-[0.2em] text-stone-400 ml-1">Description</Label>
            <Input 
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g., Brazilian hybrid reference" 
              className="h-12 rounded-xl border-stone-200 bg-stone-50/50 focus-visible:ring-emerald-500 focus-visible:border-emerald-500 font-medium" 
            />
          </div>
        </div>

        <DialogFooter className="p-8 pt-0 flex gap-3">
          <Button variant="ghost" onClick={() => setOpen(false)} className="flex-1 h-12 rounded-xl font-bold text-stone-500 hover:bg-stone-100">
            Cancel
          </Button>
          <Button 
            onClick={handleCreate} 
            disabled={!name || createMutation.isPending}
            className="flex-[2] h-12 bg-emerald-700 hover:bg-emerald-800 text-white font-bold rounded-xl shadow-lg shadow-emerald-700/20"
          >
            {createMutation.isPending ? "Creating..." : "Create Dataset"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
