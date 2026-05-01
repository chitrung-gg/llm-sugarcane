"use client"

import * as React from "react"
import { useParams, usePathname } from "next/navigation"
import { Project } from "@/lib/types"
import { useProjects } from "@/hooks/use-projects"

interface WorkspaceContextType {
  activeProjectId: string | null
  activeProject: Project | null
  isLoading: boolean
}

const WorkspaceContext = React.createContext<WorkspaceContextType | null>(null)

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const params = useParams()
  const { data: projects = [], isLoading } = useProjects()
  
  // Extract project ID from URL if present
  const urlProjectId = params.id as string | undefined
  
  const activeProjectId = urlProjectId || null
  
  const activeProject = React.useMemo(() => {
    if (!activeProjectId) return null
    return projects.find(p => p.id === activeProjectId) || null
  }, [activeProjectId, projects])

  return (
    <WorkspaceContext.Provider value={{ activeProjectId, activeProject, isLoading }}>
      {children}
    </WorkspaceContext.Provider>
  )
}

export function useWorkspace() {
  const context = React.useContext(WorkspaceContext)
  if (!context) {
    throw new Error("useWorkspace must be used within a WorkspaceProvider")
  }
  return context
}
