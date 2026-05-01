"use client"

import { AppSidebar } from "@/components/layout/sidebar"
import { WorkspaceHeader } from "@/components/layout/workspace-header"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { WorkspaceProvider, useWorkspace } from "@/hooks/use-workspace"

function WorkspaceLayoutContent({ children }: { children: React.ReactNode }) {
  const { activeProjectId } = useWorkspace()
  
  return (
    <SidebarProvider>
      {activeProjectId && <AppSidebar />}
      <SidebarInset className="bg-stone-50">
        <WorkspaceHeader />
        <div className="flex flex-1 flex-col overflow-auto">
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}

export default function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <WorkspaceProvider>
      <WorkspaceLayoutContent>
        {children}
      </WorkspaceLayoutContent>
    </WorkspaceProvider>
  )
}
