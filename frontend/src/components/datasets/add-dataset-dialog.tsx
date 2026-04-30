"use client"

import * as React from "react"
import { Dialog, DialogContent, DialogTitle, DialogTrigger, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Database } from "lucide-react"

import { useCreateDataset } from "@/hooks/use-datasets"
import { useParams } from "next/navigation"

export function AddDatasetDialog({ children }: { children: React.ReactNode }) {
  const params = useParams()
  const projectId = params.id as string
  const [open, setOpen] = React.useState(false)
  const [name, setName] = React.useState("")
  const [description, setDescription] = React.useState("")
  
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
      <DialogTrigger render={children} />
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
          <div className="space-y-2">
            <Label className="text-[10px] font-bold uppercase tracking-[0.2em] text-stone-400 ml-1">Dataset Alias / Cultivar</Label>
            <Input 
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., SP80-3280 High Sucrose Variant" 
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
