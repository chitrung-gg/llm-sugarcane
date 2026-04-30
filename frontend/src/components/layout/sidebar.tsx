"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import {
  Database,
  Dna,
  File,
  LayoutDashboard,
  Plus,
  Settings,
  LogOut,
  Sprout,
  Check,
  ChevronsUpDown,
  MessageSquarePlus,
  MessageSquare,
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
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
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
import { AddDatasetDialog } from "@/components/datasets/add-dataset-dialog"
import { NewProjectDialog } from "@/components/projects/new-project-dialog"

import { useProjects } from "@/hooks/use-projects"
import { useProjectDatasets } from "@/hooks/use-datasets"

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const router = useRouter()
  const { data: apiProjects = [] } = useProjects()
  
  // Dev fallback: Use mock data if API returns empty list
  const projects = apiProjects.length > 0 ? apiProjects : [
    { id: "p1", name: "Sugarcane Genomes (Mock)", created_at: new Date().toISOString() },
    { id: "p2", name: "Biofuel Research (Mock)", created_at: new Date().toISOString() },
  ]
  
  const [selectedProjectId, setSelectedProjectId] = React.useState<string | null>(null)
  
  const activeProject = projects.find(p => p.id === selectedProjectId) || projects[0] || null
  
  const { data: datasets = [] } = useProjectDatasets(activeProject?.id || "")

  const handleSignOut = () => {
    router.push("/login")
  }

  // Mock threads for now
  const threads = [
    { id: "t1", title: "Yield Analysis Q1" },
    { id: "t2", title: "Genotype Comparison" },
  ]

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader className="border-b border-stone-100/50">
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <SidebarMenuButton
                    size="lg"
                    className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
                  >
                    <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-emerald-700 text-white">
                      <Sprout className="size-4" aria-hidden="true" />
                    </div>
                    <div className="grid flex-1 text-left text-sm leading-tight">
                      <span className="truncate font-bold text-stone-900">{activeProject?.name || "Select Project"}</span>
                      <span className="truncate text-[10px] font-bold text-emerald-700/60 uppercase tracking-widest leading-none mt-0.5">Assistant</span>
                    </div>
                    <ChevronsUpDown className="ml-auto size-4" aria-hidden="true" />
                  </SidebarMenuButton>
                }
              />
              <DropdownMenuContent className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg" side="bottom" align="start" sideOffset={4}>
                <DropdownMenuLabel className="text-xs text-stone-500 uppercase tracking-widest font-bold">Projects</DropdownMenuLabel>
                {projects.map((project) => (
                  <DropdownMenuItem key={project.id} onClick={() => setSelectedProjectId(project.id)} className="gap-2 p-2">
                    <div className="flex size-6 items-center justify-center rounded-sm border">
                      <Sprout className="size-4 shrink-0" />
                    </div>
                    {project.name}
                    {activeProject?.id === project.id && <Check className="ml-auto size-4" />}
                  </DropdownMenuItem>
                ))}
                <DropdownMenuSeparator />
                <NewProjectDialog>
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
          <SidebarGroupLabel className="text-[10px] font-bold uppercase tracking-[0.2em] text-stone-400">Hub</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  tooltip="Dashboard"
                  className="font-bold text-stone-600"
                  render={
                    <Link href="/dashboard">
                      <LayoutDashboard aria-hidden="true" />
                      <span>Dashboard</span>
                    </Link>
                  }
                />
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
                    <Link href={`/projects/${activeProject?.id}/chat`}>
                      <MessageSquarePlus className="size-4" />
                      <span>New Chat</span>
                    </Link>
                  }
                />
              </SidebarMenuItem>
              {threads.map((thread) => (
                <SidebarMenuItem key={thread.id}>
                  <SidebarMenuButton
                    className="text-stone-600 font-medium"
                    render={
                      <Link href={`/projects/${activeProject?.id}/chat?threadId=${thread.id}`}>
                        <MessageSquare className="size-4" />
                        <span className="truncate">{thread.title}</span>
                      </Link>
                    }
                  />
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel className="text-[10px] font-bold uppercase tracking-[0.2em] text-stone-400">Datasets</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {datasets.map((dataset) => (
                <SidebarMenuItem key={dataset.id}>
                  <SidebarMenuButton tooltip={dataset.name} className="font-bold text-stone-600">
                    <Database aria-hidden="true" />
                    <span>{dataset.name}</span>
                  </SidebarMenuButton>
                  {dataset.files && dataset.files.length > 0 && (
                    <SidebarMenuSub>
                      {/* Separate Genome and Knowledge if file_type allows */}
                      {dataset.files.map((file) => (
                        <SidebarMenuSubItem key={file.id}>
                          <SidebarMenuSubButton className="text-stone-400 font-semibold" render={<div />}>
                            {file.file_type.includes('genome') ? <Dna className="size-4" /> : <File className="size-4" />}
                            <span className="truncate">{file.file_name}</span>
                          </SidebarMenuSubButton>
                        </SidebarMenuSubItem>
                      ))}
                    </SidebarMenuSub>
                  )}
                </SidebarMenuItem>
              ))}
              <SidebarMenuItem>
                <AddDatasetDialog>
                  <SidebarMenuButton className="text-stone-400 font-bold hover:text-emerald-700">
                    <Plus className="size-4" />
                    <span>Add Dataset</span>
                  </SidebarMenuButton>
                </AddDatasetDialog>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="border-t border-stone-100/50">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              tooltip="Settings"
              className="font-bold text-stone-600"
              render={
                <Link href="/settings">
                  <Settings aria-hidden="true" />
                  <span>System Info</span>
                </Link>
              }
            />
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
