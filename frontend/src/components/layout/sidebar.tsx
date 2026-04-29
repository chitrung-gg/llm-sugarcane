"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import {
  ChevronRight,
  Database,
  Dna,
  File,
  FlaskConical,
  Folder,
  LayoutDashboard,
  Plus,
  Search,
  Settings,
  LogOut,
  Sprout,
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

// Mock data
const projects = [
  { id: "p1", name: "Sugarcane Genomes" },
  { id: "p2", name: "Biofuel Research" },
  { id: "p3", name: "Pest Resistance" },
]

const datasets = [
  {
    id: "ds1",
    name: "R570 Reference",
    genomeData: [
      { id: "f1", name: "r570_v2.fasta", type: "fasta" },
      { id: "f2", name: "annotations.gff3", type: "gff" },
    ],
    knowledgeBase: [
      { id: "f3", name: "QTL_analysis.pdf", type: "pdf" },
      { id: "f4", name: "metabolic_pathways.json", type: "json" },
    ],
  },
  {
    id: "ds2",
    name: "SP80-3280 Hybrid",
    genomeData: [
      { id: "f5", name: "sp80_3280.fa", type: "fasta" },
    ],
    knowledgeBase: [],
  },
]

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const activeProject = projects[0]
  const router = useRouter()

  const handleSignOut = () => {
    router.push("/login")
  }

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground">
              <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-emerald-700 text-white">
                <Sprout className="size-4" aria-hidden="true" />
              </div>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-bold text-stone-900">{activeProject.name}</span>
                <span className="truncate text-[10px] font-bold text-emerald-700/60 uppercase tracking-widest">Assistant</span>
              </div>
              <ChevronRight className="ml-auto size-4" aria-hidden="true" />
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel className="text-[10px] font-black uppercase tracking-[0.2em] text-stone-400">Hub</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton 
                  tooltip="Dashboard" 
                  className="font-bold text-stone-600"
                  render={<Link href="/dashboard" />}
                >
                  <LayoutDashboard aria-hidden="true" />
                  <span>Dashboard</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton 
                  tooltip="Resource Hub" 
                  className="font-bold text-stone-600"
                  render={<Link href="/search" />}
                >
                  <Search aria-hidden="true" />
                  <span>Resource Hub</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel className="text-[10px] font-black uppercase tracking-[0.2em] text-stone-400">Datasets</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {datasets.map((dataset) => (
                <SidebarMenuItem key={dataset.id}>
                  <SidebarMenuButton tooltip={dataset.name} className="font-bold text-stone-600">
                    <Database aria-hidden="true" />
                    <span>{dataset.name}</span>
                  </SidebarMenuButton>
                  <SidebarMenuSub>
                    {/* Genome Data Group */}
                    {dataset.genomeData.length > 0 && (
                      <SidebarMenuSubItem>
                        <SidebarMenuSubButton className="font-bold text-stone-500" render={<div />}>
                          <Dna className="size-4" aria-hidden="true" />
                          <span>Genome Data</span>
                        </SidebarMenuSubButton>
                        <SidebarMenuSub>
                          {dataset.genomeData.map((file) => (
                            <SidebarMenuSubItem key={file.id}>
                              <SidebarMenuSubButton className="text-stone-400 font-medium" render={<div />}>
                                <File className="size-4" aria-hidden="true" />
                                <span className="truncate">{file.name}</span>
                              </SidebarMenuSubButton>
                            </SidebarMenuSubItem>
                          ))}
                        </SidebarMenuSub>
                      </SidebarMenuSubItem>
                    )}
                    
                    {/* Knowledge Base Group */}
                    {dataset.knowledgeBase.length > 0 && (
                      <SidebarMenuSubItem>
                        <SidebarMenuSubButton className="font-bold text-stone-500" render={<div />}>
                          <Folder className="size-4" aria-hidden="true" />
                          <span>Knowledge Base</span>
                        </SidebarMenuSubButton>
                        <SidebarMenuSub>
                          {dataset.knowledgeBase.map((file) => (
                            <SidebarMenuSubItem key={file.id}>
                              <SidebarMenuSubButton className="text-stone-400 font-medium" render={<div />}>
                                <File className="size-4" aria-hidden="true" />
                                <span className="truncate">{file.name}</span>
                              </SidebarMenuSubButton>
                            </SidebarMenuSubItem>
                          ))}
                        </SidebarMenuSub>
                      </SidebarMenuSubItem>
                    )}
                  </SidebarMenuSub>
                </SidebarMenuItem>
              ))}
              <SidebarMenuItem>
                <SidebarMenuButton className="text-stone-400 font-bold hover:text-emerald-700">
                  <Plus className="size-4" />
                  <span>Add Dataset</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton 
              tooltip="Settings" 
              className="font-bold text-stone-600"
              render={<Link href="/settings" />}
            >
              <Settings aria-hidden="true" />
              <span>System Info</span>
            </SidebarMenuButton>
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
