import { AppSidebar } from "@/components/layout/sidebar"
import { WorkspaceHeader } from "@/components/layout/workspace-header"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"

export default function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="bg-stone-50">
        <WorkspaceHeader />
        <div className="flex flex-1 flex-col overflow-auto">
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
