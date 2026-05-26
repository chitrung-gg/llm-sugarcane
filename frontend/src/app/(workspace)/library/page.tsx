"use client"

import { useState, useMemo, useEffect } from "react"
import Link from "next/link"
import { Library, Database, Globe, Download, Plus, Loader2, Upload, Trash2 } from "lucide-react"
import { useUserDatasets, useLibraryDatasets, useUpdateDataset, useAttachDataset, useDatasetFiles, useDownloadFile, useDeleteDatasetFile, useAvailableProjects } from "@/hooks/use-datasets"
import { useProjects } from "@/hooks/use-projects"
import { getCurrentUser } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Switch } from "@/components/ui/switch"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"

export default function LibraryPage() {
  const [mounted, setMounted] = useState(false)
  const user = getCurrentUser()
  const { data: myDatasets = [], isLoading: isLoadingMy } = useUserDatasets(user?.uuid || "")
  const { data: publicDatasets = [], isLoading: isLoadingPublic } = useLibraryDatasets()
  const { data: userProjects = [] } = useProjects()
  const updateDataset = useUpdateDataset()

  useEffect(() => {
    setMounted(true)
  }, [])

  // Map to identify which projects the user owns
  const userOwnedProjectIds = useMemo(() => new Set(userProjects.map(p => p.id)), [userProjects])

  const handleTogglePublic = (datasetId: string, currentStatus: boolean) => {
    updateDataset.mutate({ datasetId, isPublic: !currentStatus })
  }

  if (!mounted) return null

  return (
    <div className="p-8 lg:p-12">
      <div className="max-w-6xl mx-auto space-y-10">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
             <div className="bg-emerald-700 p-2 rounded-xl text-white shadow-lg shadow-emerald-700/20">
               <Library className="h-6 w-6" />
             </div>
             <h1 className="text-4xl font-bold tracking-tight text-stone-900">Data Library</h1>
          </div>
          <p className="text-stone-500 font-medium ml-1">Manage your datasets and discover public resources.</p>
        </div>

        <Tabs defaultValue="mine" className="w-full">
          <TabsList className="grid w-[400px] grid-cols-2 mb-8 bg-stone-100 p-1 rounded-xl">
            <TabsTrigger value="mine" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm">My Datasets</TabsTrigger>
            <TabsTrigger value="public" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm">Public Library</TabsTrigger>
          </TabsList>
          
          <TabsContent value="mine" className="space-y-6">
            {isLoadingMy ? (
              <div className="flex justify-center p-12"><Loader2 className="animate-spin h-8 w-8 text-stone-300" /></div>
            ) : myDatasets.length === 0 ? (
              <div className="text-center py-20 border-2 border-dashed border-stone-200 rounded-2xl bg-stone-50/50">
                <p className="text-stone-400 font-bold uppercase tracking-widest">No datasets found</p>
              </div>
            ) : (
              <div className="grid gap-6 md:grid-cols-2">
                {myDatasets.map(ds => (
                  <Card key={ds.id} className="rounded-2xl border-stone-200 hover:shadow-xl transition-all duration-300 overflow-hidden bg-white flex flex-col">
                    <CardHeader className="p-5 border-b border-stone-50 flex flex-row items-start justify-between bg-stone-50/30">
                      <div className="flex items-center gap-3">
                        <div className="bg-emerald-100 p-2.5 rounded-xl text-emerald-700 border border-emerald-200/50"><Database className="h-5 w-5" /></div>
                        <div>
                          <CardTitle className="text-lg font-bold text-stone-800">{ds.name}</CardTitle>
                          <p className="text-[10px] font-bold text-stone-400 uppercase tracking-widest mt-1">ID: {ds.id.split('-')[0]}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-full border border-stone-200 shadow-sm">
                        <span className="text-[10px] font-bold uppercase text-stone-500 tracking-tighter">{ds.is_public ? 'Public' : 'Private'}</span>
                        <Switch 
                          checked={ds.is_public} 
                          onCheckedChange={() => handleTogglePublic(ds.id, ds.is_public)} 
                        />
                      </div>
                    </CardHeader>
                    <CardContent className="p-5 flex-1 flex flex-col">
                      <p className="text-sm text-stone-500 mb-6 line-clamp-2 min-h-[2.5rem]">{ds.description || "No description provided."}</p>
                      <DatasetFilesList datasetId={ds.id} isOwner={true} />
                      <div className="mt-auto pt-6">
                        <Button asChild variant="outline" className="w-full border-emerald-700 text-emerald-700 hover:bg-emerald-50 font-bold rounded-xl h-11">
                          <Link href={`/projects/${ds.project_id}/upload?datasetId=${ds.id}`}>
                            <Upload className="h-4 w-4 mr-2" /> Upload New Files
                          </Link>
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="public" className="space-y-6">
            {isLoadingPublic ? (
               <div className="flex justify-center p-12"><Loader2 className="animate-spin h-8 w-8 text-stone-300" /></div>
            ) : publicDatasets.length === 0 ? (
              <div className="text-center py-20 border-2 border-dashed border-stone-200 rounded-2xl bg-stone-50/50">
                <p className="text-stone-400 font-bold uppercase tracking-widest">No public datasets</p>
              </div>
            ) : (
              <div className="grid gap-6 md:grid-cols-2">
                {publicDatasets.map(ds => {
                  const isOwner = userOwnedProjectIds.has(ds.project_id)
                  return (
                    <Card key={ds.id} className="rounded-2xl border-stone-200 hover:shadow-xl transition-all duration-300 overflow-hidden bg-white flex flex-col">
                      <CardHeader className="p-5 border-b border-stone-50 flex flex-row items-center justify-between bg-stone-50/30">
                        <div className="flex items-center gap-3">
                          <div className="bg-blue-100 p-2.5 rounded-xl text-blue-700 border border-blue-200/50"><Globe className="h-5 w-5" /></div>
                          <div className="flex-1">
                            <CardTitle className="text-lg font-bold text-stone-800">{ds.name}</CardTitle>
                            <p className="text-[10px] font-bold text-stone-400 uppercase tracking-widest mt-1">Shared Resource</p>
                          </div>
                        </div>
                        {isOwner && (
                          <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-full border border-stone-200 shadow-sm">
                            <span className="text-[10px] font-bold uppercase text-stone-500 tracking-tighter">Public</span>
                            <Switch 
                              checked={ds.is_public} 
                              onCheckedChange={() => handleTogglePublic(ds.id, ds.is_public)} 
                            />
                          </div>
                        )}
                      </CardHeader>
                      <CardContent className="p-5 flex-1 flex flex-col space-y-5">
                        <p className="text-sm text-stone-500 line-clamp-2 min-h-[2.5rem]">{ds.description || "No description provided."}</p>
                        <DatasetFilesList datasetId={ds.id} isOwner={isOwner} />
                        <div className="mt-auto space-y-3 pt-2">
                          {isOwner && (
                            <Button asChild variant="outline" className="w-full border-emerald-700 text-emerald-700 hover:bg-emerald-50 font-bold rounded-xl h-11">
                              <Link href={`/projects/${ds.project_id}/upload?datasetId=${ds.id}`}>
                                <Upload className="h-4 w-4 mr-2" /> Upload New Files
                              </Link>
                            </Button>
                          )}
                          <CloneDatasetDialog datasetId={ds.id} />
                        </div>
                      </CardContent>
                    </Card>
                  )
                })}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}

function DatasetFilesList({ datasetId, isOwner }: { datasetId: string, isOwner: boolean }) {
  const { data: files = [] } = useDatasetFiles(datasetId)
  const downloadFile = useDownloadFile()
  const deleteFileMutation = useDeleteDatasetFile()
  const [confirmFileId, setConfirmFileId] = useState<string | null>(null)

  const handleDownload = async (fileId: string) => {
    try {
      const url = await downloadFile.mutateAsync(fileId)
      window.open(url, '_blank')
    } catch (error) {
      console.error("Failed to generate download link", error)
    }
  }

  const handleDelete = (fileId: string) => setConfirmFileId(fileId)

  if (files.length === 0) return (
    <div className="py-4 text-center bg-stone-50 rounded-xl border border-dashed border-stone-200">
       <p className="text-xs text-stone-400 font-medium">No files in this dataset.</p>
    </div>
  )

  return (
    <>
      <ConfirmDialog
        open={!!confirmFileId}
        onOpenChange={(v) => { if (!v) setConfirmFileId(null) }}
        title="Delete File"
        description="Are you sure you want to delete this file? This action cannot be undone."
        onConfirm={() => confirmFileId && deleteFileMutation.mutate({ fileId: confirmFileId, datasetId }, { onSettled: () => setConfirmFileId(null) })}
        isPending={deleteFileMutation.isPending}
      />
      <div className="space-y-2 max-h-40 overflow-auto pr-2 no-scrollbar">
        {files.map(f => (
          <div key={f.id} className="flex items-center justify-between bg-stone-50/50 p-2.5 rounded-xl border border-stone-100 hover:bg-stone-50 transition-colors group">
            <span className="text-xs font-bold text-stone-600 truncate flex-1 mr-4" title={f.file_name}>{f.file_name}</span>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="icon" className="h-7 w-7 text-stone-400 hover:text-emerald-700 hover:bg-emerald-50 rounded-lg transition-all" onClick={() => handleDownload(f.id)}>
                <Download className="h-3.5 w-3.5" />
              </Button>
              {isOwner && (
                <Button variant="ghost" size="icon" className="h-7 w-7 text-stone-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all" onClick={() => handleDelete(f.id)}>
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

function CloneDatasetDialog({ datasetId }: { datasetId: string }) {
  const { data: availableProjects = [], isLoading } = useAvailableProjects(datasetId)
  const attachDataset = useAttachDataset()
  const [selectedProject, setSelectedProject] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

  const handleClone = async () => {
    if (!selectedProject) return
    try {
      await attachDataset.mutateAsync({ projectId: selectedProject, datasetId })
      console.log("Dataset added to project successfully")
      setSelectedProject(null)
      setOpen(false)
    } catch (error) {
      console.error("Failed to add dataset", error)
    }
  }

  const allAttached = !isLoading && availableProjects.length === 0

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger 
        nativeButton={true}
        render={
          <Button 
            disabled={allAttached}
            className={`w-full font-bold rounded-xl shadow-lg h-11 transition-all active:scale-[0.98] ${
              allAttached 
                ? "bg-stone-100 text-stone-400 border border-stone-200 cursor-not-allowed shadow-none" 
                : "bg-stone-900 hover:bg-stone-800 text-white shadow-stone-900/10"
            }`}
          >
            {allAttached ? "Already in All Projects" : <><Plus className="h-4 w-4 mr-2" /> Add to Project</>}
          </Button>
        }
      />
      <DialogContent className="rounded-2xl">
        <DialogHeader>
          <div className="flex items-center gap-3 mb-2">
            <div className="bg-emerald-100 p-2 rounded-xl">
              <Plus className="h-5 w-5 text-emerald-700" />
            </div>
            <div>
              <DialogTitle className="text-xl font-bold text-stone-900">Add to Project</DialogTitle>
              <p className="text-[10px] text-stone-400 font-bold uppercase tracking-widest leading-none">Reference dataset</p>
            </div>
          </div>
        </DialogHeader>
        <div className="py-4 space-y-6">
          <div className="space-y-2">
            <label className="text-[11px] font-bold text-stone-400 uppercase tracking-widest ml-1">Select Destination</label>
            <Select value={selectedProject || ""} onValueChange={(val) => setSelectedProject(val)}>
              <SelectTrigger className="h-12 rounded-xl border-stone-200 focus:ring-emerald-500">
                <SelectValue placeholder="Select a project..." />
              </SelectTrigger>
              <SelectContent className="rounded-xl">
                {availableProjects.map(p => (
                  <SelectItem key={p.id} value={p.id} className="font-medium">{p.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button 
            onClick={handleClone} 
            disabled={!selectedProject || attachDataset.isPending} 
            className="w-full bg-emerald-700 hover:bg-emerald-800 text-white font-bold h-12 rounded-xl shadow-lg shadow-emerald-700/20"
          >
            {attachDataset.isPending ? <Loader2 className="animate-spin h-5 w-5" /> : "Attach Dataset"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
