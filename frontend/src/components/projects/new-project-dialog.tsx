"use client"

import * as React from "react"
import { Dialog, DialogContent, DialogTitle, DialogTrigger, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { FolderPlus, Sprout } from "lucide-react"

import { useCreateProject } from "@/hooks/use-projects"

export function NewProjectDialog({ 
  children, 
  nativeButton = true 
}: { 
  children: React.ReactNode;
  nativeButton?: boolean;
}) {
  const [open, setOpen] = React.useState(false)
  const [name, setName] = React.useState("")
  const [description, setDescription] = React.useState("")

  const createMutation = useCreateProject()

  const handleCreate = () => {
    if (!name) return

    createMutation.mutate({
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
        <div className="bg-emerald-700 p-8 text-white relative overflow-hidden">
          <Sprout className="absolute -right-4 -bottom-4 h-32 w-32 text-white/10 rotate-12" />
          <div className="relative z-10 space-y-1">
            <div className="bg-white/20 w-10 h-10 rounded-xl flex items-center justify-center mb-2">
              <FolderPlus className="h-5 w-5 text-white" />
            </div>
            <DialogTitle className="text-2xl font-bold">New Analysis Project</DialogTitle>
            <DialogDescription className="text-emerald-100 font-medium">
              Initialize a new research workspace for sugarcane genomics.
            </DialogDescription>
          </div>
        </div>

        <div className="p-8 space-y-6">
          <div className="space-y-2">
            <Label className="text-[10px] font-bold uppercase tracking-[0.2em] text-stone-400 ml-1">Project Name</Label>
            <Input 
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., R570 Yield Analysis 2026" 
              className="h-12 rounded-xl border-stone-200 bg-stone-50/50 focus-visible:ring-emerald-500 focus-visible:border-emerald-500 font-medium" 
            />
          </div>

          <div className="space-y-2">
            <Label className="text-[10px] font-bold uppercase tracking-[0.2em] text-stone-400 ml-1">Description (Optional)</Label>
            <Input 
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Primary goals and dataset scope..." 
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
            {createMutation.isPending ? "Creating..." : "Create Project"}
          </Button>

        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
