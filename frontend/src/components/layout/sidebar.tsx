"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter, useParams } from "next/navigation"
import {
  Database,
  Dna,
  File as LucideFile,
  LayoutDashboard,
  Plus,
  Settings,
  LogOut,
  Sprout,
  Check,
  ChevronsUpDown,
  MessageSquarePlus,
  MessageSquare,
  Upload,
  ChevronRight,
  Trash2,
  FolderKanban,
} from "lucide-react"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { AddDatasetDialog } from "@/components/datasets/add-dataset-dialog"
import { NewProjectDialog } from "@/components/projects/new-project-dialog"

import { useProjects } from "@/hooks/use-projects"
import { useProjectThreads } from "@/hooks/use-chat"
import { useProjectDatasets, useDatasetFiles, useDeleteDatasetFile } from "@/hooks/use-datasets"
import { useWorkspace } from "@/hooks/use-workspace"
import { Thread, Dataset } from "@/lib/types"
import { logout, getCurrentUser } from "@/lib/auth"

function DatasetInfoDialog({ dataset }: { dataset: Dataset }) {
  const { data: files = [] } = useDatasetFiles(dataset.id)
  const [open, setOpen] = React.useState(false)
  const deleteFileMutation = useDeleteDatasetFile()

  const genomeFiles = files.filter(f => f.file_type.includes('genome'))
  const knowledgeFiles = files.filter(f => !f.file_type.includes('genome'))

  const handleDeleteFile = (fileId: string) => {
    if (confirm("Are you sure you want to delete this file?")) {
      deleteFileMutation.mutate({ fileId, datasetId: dataset.id })
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <SidebarMenuButton tooltip={dataset.name} className="font-bold text-stone-600">
            <Database aria-hidden="true" />
            <span>{dataset.name}</span>
          </SidebarMenuButton>
        }
      />
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <div className="flex items-center gap-3 mb-2">
             <div className="bg-emerald-100 p-2 rounded-xl">
               <Database className="h-5 w-5 text-emerald-700" />
             </div>
             <div>
               <DialogTitle className="text-xl font-bold text-stone-900">{dataset.name}</DialogTitle>
               <p className="text-[10px] text-stone-400 font-bold uppercase tracking-widest leading-none">Dataset Info</p>
             </div>
          </div>
          <DialogDescription className="text-stone-500 font-medium">
            {dataset.description || "No description available for this dataset."}
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4 space-y-5">
          <div className="bg-stone-50 p-3 rounded-xl border border-stone-100 flex items-center justify-between">
             <div>
               <p className="text-[9px] font-bold text-stone-400 uppercase tracking-widest">Dataset ID</p>
               <p className="text-[10px] font-mono text-stone-600">{dataset.id}</p>
             </div>
             <div className="text-right">
                <p className="text-[9px] font-bold text-stone-400 uppercase tracking-widest">Files</p>
                <p className="text-xs font-bold text-emerald-700">{files.length}</p>
             </div>
          </div>

          <div className="space-y-4 max-h-[300px] overflow-auto pr-1 no-scrollbar">
            {genomeFiles.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-[10px] font-bold uppercase tracking-[0.2em] text-stone-400 ml-1">Genomic Data ({genomeFiles.length})</h4>
                <div className="bg-white rounded-xl border border-stone-100 divide-y divide-stone-50 overflow-hidden shadow-sm">
                  {genomeFiles.map((file) => (
                    <div key={file.id} className="p-2.5 flex items-center gap-3 hover:bg-stone-50 transition-colors group/file">
                      <div className="bg-emerald-50 p-1.5 rounded-lg border border-emerald-100">
                        <Dna className="size-3.5 text-emerald-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-bold text-stone-700 truncate" title={file.file_name}>{file.file_name}</p>
                      </div>
                      <button 
                        onClick={() => handleDeleteFile(file.id)}
                        className="opacity-0 group-hover/file:opacity-100 p-1 text-stone-300 hover:text-red-500 transition-all"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {knowledgeFiles.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-[10px] font-bold uppercase tracking-[0.2em] text-stone-400 ml-1">Knowledge Base ({knowledgeFiles.length})</h4>
                <div className="bg-white rounded-xl border border-stone-100 divide-y divide-stone-50 overflow-hidden shadow-sm">
                  {knowledgeFiles.map((file) => (
                    <div key={file.id} className="p-2.5 flex items-center gap-3 hover:bg-stone-50 transition-colors group/file">
                      <div className="bg-blue-50 p-1.5 rounded-lg border border-blue-100">
                        <LucideFile className="size-3.5 text-blue-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-bold text-stone-700 truncate" title={file.file_name}>{file.file_name}</p>
                      </div>
                      <button 
                        onClick={() => handleDeleteFile(file.id)}
                        className="opacity-0 group-hover/file:opacity-100 p-1 text-stone-300 hover:text-red-500 transition-all"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {files.length === 0 && (
              <div className="py-8 text-center bg-stone-50 rounded-2xl border-2 border-dashed border-stone-200">
                 <p className="text-sm text-stone-400 font-medium">No files uploaded yet.</p>
              </div>
            )}
          </div>

          <Button asChild className="w-full bg-emerald-700 hover:bg-emerald-800 h-11 rounded-xl shadow-lg shadow-emerald-700/20" onClick={() => setOpen(false)}>
             <Link href={`/projects/${dataset.project_id}/upload?datasetId=${dataset.id}`}>
               <Upload className="mr-2 h-4 w-4" /> Upload New Files
             </Link>
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function DatasetMenuItem({ dataset, projectId }: { dataset: Dataset; projectId: string }) {
  return (
    <SidebarMenuItem>
      <DatasetInfoDialog dataset={dataset} />
      <SidebarMenuAction
        title="Upload to Dataset"
        className="text-emerald-600 hover:bg-emerald-50"
        render={
          <Link href={`/projects/${projectId}/upload?datasetId=${dataset.id}`}>
            <Upload className="size-3.5" />
          </Link>
        }
      />
    </SidebarMenuItem>
  )
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const router = useRouter()
  const { activeProject, activeProjectId } = useWorkspace()
  const { data: projects = [] } = useProjects()
  
  const { data: datasets = [] } = useProjectDatasets(activeProjectId || "")
  const { data: threads = [] } = useProjectThreads(activeProjectId || "")

  const user = getCurrentUser()
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => {
    setMounted(true)
  }, [])

  const handleSignOut = () => {
    logout()
  }

  const handleProjectSwitch = (projectId: string) => {
    router.push(`/projects/${projectId}/chat`)
  }

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader className="border-b border-stone-100/50 p-4 pb-2">
        <p className="text-[9px] font-bold uppercase tracking-[0.2em] text-emerald-700/60 mb-2 ml-1 group-data-[collapsible=icon]:hidden">Research Project</p>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <SidebarMenuButton
                    size="lg"
                    className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground border border-stone-200/50 shadow-sm"
                  >
                    <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-emerald-700 text-white">
                      <Sprout className="size-4" aria-hidden="true" />
                    </div>
                    <div className="grid flex-1 text-left text-sm leading-tight">
                      <span className="truncate font-bold text-stone-900">{activeProject?.name || "Select Project"}</span>
                      <span className="truncate text-[10px] font-bold text-emerald-700/60 uppercase tracking-widest leading-none mt-0.5">Active Workspace</span>
                    </div>
                    <ChevronsUpDown className="ml-auto size-4" aria-hidden="true" />
                  </SidebarMenuButton>
                }
              />
              <DropdownMenuContent className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg" side="bottom" align="start" sideOffset={4}>
                <DropdownMenuLabel className="text-xs text-stone-500 uppercase tracking-widest font-bold">Switch Project</DropdownMenuLabel>
                {projects.map((project) => (
                  <DropdownMenuItem key={project.id} onClick={() => handleProjectSwitch(project.id)} className="gap-2 p-2">
                    <div className="flex size-6 items-center justify-center rounded-sm border">
                      <Sprout className="size-4 shrink-0" />
                    </div>
                    {project.name}
                    {activeProjectId === project.id && <Check className="ml-auto size-4" />}
                  </DropdownMenuItem>
                ))}
                <DropdownMenuSeparator />
                <NewProjectDialog nativeButton={false}>
                  <DropdownMenuItem className="gap-2 p-2" onSelect={(e) => e.preventDefault()}>
                    <div className="flex size-6 items-center justify-center rounded-md border bg-stone-50">
                      <Plus className="size-4" />
                    </div>
                    <div className="font-semibold text-stone-500">Create Project</div>
                  </DropdownMenuItem>
                </NewProjectDialog>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel className="text-[10px] font-bold uppercase tracking-[0.2em] text-stone-400">Global Hub</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  tooltip="Main Dashboard"
                  className="font-bold text-stone-600"
                  render={
                    <Link href="/dashboard">
                      <LayoutDashboard aria-hidden="true" />
                      <span>Main Dashboard</span>
                    </Link>
                  }
                />
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Admin Portal Section */}
        {mounted && user?.role === 'admin' && (
          <SidebarGroup>
            <SidebarGroupLabel className="text-[10px] font-bold uppercase tracking-[0.2em] text-emerald-700/60">Admin Portal</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                <SidebarMenuItem>
                  <SidebarMenuButton
                    tooltip="All Projects"
                    className="font-bold text-emerald-700 hover:bg-emerald-50"
                    render={
                      <Link href="/admin/projects">
                        <FolderKanban aria-hidden="true" className="text-emerald-700" />
                        <span>Global Projects</span>
                      </Link>
                    }
                  />
                </SidebarMenuItem>
                <SidebarMenuItem>
                  <SidebarMenuButton
                    tooltip="System References"
                    className="font-bold text-emerald-700 hover:bg-emerald-50"
                    render={
                      <Link href="/admin/references">
                        <Dna aria-hidden="true" className="text-emerald-700" />
                        <span>System References</span>
                      </Link>
                    }
                  />
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}

        {activeProjectId && (
          <>
            <SidebarGroup>
              <SidebarGroupLabel className="text-[10px] font-bold uppercase tracking-[0.2em] text-emerald-700/60">Active Research</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <SidebarMenuButton
                      tooltip="Manage Project & Data"
                      className="font-bold text-emerald-700 bg-emerald-50/50 hover:bg-emerald-50"
                      render={
                        <Link href={`/projects/${activeProjectId}`}>
                          <FolderKanban aria-hidden="true" className="text-emerald-700" />
                          <span>Project Overview</span>
                        </Link>
                      }
                    />
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>

            <SidebarGroup>
              <SidebarGroupLabel className="text-[10px] font-bold uppercase tracking-[0.2em] text-stone-400">Datasets</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {datasets.map((dataset) => (
                    <DatasetMenuItem 
                      key={dataset.id} 
                      dataset={dataset} 
                      projectId={activeProjectId || ""} 
                    />
                  ))}
                  <SidebarMenuItem>
                    <AddDatasetDialog projectName={activeProject?.name}>
                      <SidebarMenuButton className="text-stone-400 font-bold hover:text-emerald-700">
                        <Plus className="size-4" />
                        <span>Add Dataset</span>
                      </SidebarMenuButton>
                    </AddDatasetDialog>
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>

            <SidebarGroup>
              <SidebarGroupLabel className="text-[10px] font-bold uppercase tracking-[0.2em] text-stone-400">Threads</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <SidebarMenuButton
                      className="text-emerald-700 font-bold hover:bg-emerald-50"
                      render={
                        <Link href={`/projects/${activeProjectId}/chat?new=true`}>
                          <MessageSquarePlus className="size-4" />
                          <span>New Chat</span>
                        </Link>
                      }
                    />
                  </SidebarMenuItem>
                  {threads.map((thread: Thread) => (
                    <SidebarMenuItem key={thread.id}>
                      <SidebarMenuButton
                        tooltip={thread.title}
                        className="text-stone-600 font-medium"
                        render={
                          <Link href={`/projects/${activeProjectId}/chat/${thread.id}`}>
                            <MessageSquare className="size-4" />
                            <span className="truncate" title={thread.title}>{thread.title}</span>
                          </Link>
                        }
                      />
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </>
        )}
      </SidebarContent>
      <SidebarFooter className="border-t border-stone-100/50">
        <SidebarMenu>
          {mounted && user && (
            <SidebarMenuItem className="px-4 py-2 mb-2">
               <p className="text-[10px] font-bold text-stone-400 uppercase tracking-widest leading-tight">Signed in as</p>
               <p className="text-xs font-bold text-emerald-700 truncate">{user.email}</p>
            </SidebarMenuItem>
          )}
          <SidebarMenuItem>
            <DropdownMenu>
               <DropdownMenuTrigger render={
                 <SidebarMenuButton
                   tooltip="Settings"
                   className="font-bold text-stone-600"
                 >
                   <Settings aria-hidden="true" />
                   <span>Settings</span>
                 </SidebarMenuButton>
               } />
               <DropdownMenuContent side="top" align="start" className="w-48">
                  <DropdownMenuItem render={
                    <Link href="/settings" className="flex items-center gap-2">
                       <Settings className="size-4" /> System Info
                    </Link>
                  } />
               </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton tooltip="Sign Out" onClick={handleSignOut} className="text-red-500 font-bold hover:text-red-600 hover:bg-red-50">
              <LogOut aria-hidden="true" />
              <span>Sign Out</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  )
}
