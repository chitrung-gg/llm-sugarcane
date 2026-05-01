"use client"

import * as React from "react"
import { Dialog, DialogContent, DialogTitle, DialogTrigger, DialogDescription, DialogFooter, DialogHeader } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Settings2, Trash2, AlertTriangle, Loader2 } from "lucide-react"
import { useUpdateProject, useDeleteProject } from "@/hooks/use-projects"
import { Project } from "@/lib/types"
import { useRouter } from "next/navigation"

export function ProjectSettingsDialog({ project }: { project: Project }) {
  const [open, setOpen] = React.useState(false)
  const [confirmDelete, setConfirmDelete] = React.useState(false)
  const [name, setName] = React.useState(project.name)
  const [description, setDescription] = React.useState(project.description || "")
  
  const router = useRouter()
  const updateMutation = useUpdateProject()
  const deleteMutation = useDeleteProject()

  const handleUpdate = () => {
    updateMutation.mutate({
      projectId: project.id,
      name,
      description
    }, {
      onSuccess: () => setOpen(false)
    })
  }

  const handleDelete = () => {
    deleteMutation.mutate(project.id, {
      onSuccess: () => {
        setOpen(false)
        router.push("/dashboard")
      }
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={
        <Button variant="outline" className="rounded-xl border-stone-200 font-bold">
          <Settings2 className="mr-2 size-4" /> Project Settings
        </Button>
      } />
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
           <div className="flex items-center gap-3 mb-2">
             <div className="bg-stone-100 p-2 rounded-xl">
               <Settings2 className="h-5 w-5 text-stone-600" />
             </div>
             <div>
               <DialogTitle className="text-xl font-bold text-stone-900">Project Settings</DialogTitle>
               <p className="text-[10px] text-stone-400 font-bold uppercase tracking-widest leading-none">Manage Properties</p>
             </div>
          </div>
          <DialogDescription>
            Update the metadata for <span className="text-emerald-700 font-bold">{project.name}</span>.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          <div className="space-y-2">
            <Label htmlFor="name" className="font-bold text-stone-700">Project Name</Label>
            <Input 
              id="name" 
              value={name} 
              onChange={(e) => setName(e.target.value)}
              className="rounded-xl border-stone-200 focus-visible:ring-emerald-500"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="desc" className="font-bold text-stone-700">Description</Label>
            <Textarea 
              id="desc" 
              value={description} 
              onChange={(e) => setDescription(e.target.value)}
              className="rounded-xl border-stone-200 focus-visible:ring-emerald-500 min-h-[100px]"
            />
          </div>

          <div className="pt-4 border-t border-stone-100">
             {!confirmDelete ? (
               <Button 
                 variant="ghost" 
                 className="text-red-500 hover:text-red-600 hover:bg-red-50 w-full justify-start font-bold"
                 onClick={() => setConfirmDelete(true)}
               >
                 <Trash2 className="mr-2 size-4" /> Delete Project
               </Button>
             ) : (
               <div className="bg-red-50 border border-red-100 rounded-xl p-4 space-y-3">
                  <div className="flex items-center gap-2 text-red-700">
                     <AlertTriangle className="size-5" />
                     <p className="font-bold text-sm">Dangerous Action</p>
                  </div>
                  <p className="text-xs text-red-600 font-medium">This will permanently delete the project and all associated datasets and files. This cannot be undone.</p>
                  <div className="flex gap-2">
                     <Button 
                       variant="destructive" 
                       size="sm" 
                       className="rounded-lg font-bold flex-1"
                       onClick={handleDelete}
                       disabled={deleteMutation.isPending}
                     >
                       {deleteMutation.isPending ? "Deleting..." : "Confirm Delete"}
                     </Button>
                     <Button 
                       variant="outline" 
                       size="sm" 
                       className="rounded-lg font-bold flex-1 bg-white"
                       onClick={() => setConfirmDelete(false)}
                     >
                       Cancel
                     </Button>
                  </div>
               </div>
             )}
          </div>
        </div>

        <DialogFooter>
          <Button 
            className="w-full bg-emerald-700 hover:bg-emerald-800 rounded-xl font-bold shadow-lg shadow-emerald-700/20"
            onClick={handleUpdate}
            disabled={updateMutation.isPending}
          >
            {updateMutation.isPending ? "Saving..." : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
