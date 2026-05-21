"use client"

import * as React from "react"
import { Sprout, Menu, X, LogOut } from "lucide-react"
import { useSidebar } from "@/components/ui/sidebar"
import { Separator } from "@/components/ui/separator"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useWorkspace } from "@/hooks/use-workspace"
import { logout, getCurrentUser } from "@/lib/auth"

export function WorkspaceHeader() {
  const { toggleSidebar, open } = useSidebar()
  const { activeProjectId } = useWorkspace()
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => { setMounted(true) }, [])

  const user = mounted ? getCurrentUser() : null
  const initials = user?.email ? user.email.slice(0, 2).toUpperCase() : "RU"

  return (
    <header className="w-full px-4 py-3 flex items-center justify-between border-b border-stone-200 bg-white/80 backdrop-blur-md z-10 sticky top-0">
      <div className="flex items-center gap-4">
        {activeProjectId && (
          <>
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleSidebar}
              className="text-stone-500 hover:bg-stone-100 rounded-lg transition-all"
            >
              {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </Button>
            <Separator orientation="vertical" className="h-4 bg-stone-200" />
          </>
        )}
        <div className="flex items-center gap-2.5">
          <div className="bg-emerald-700 p-1.5 rounded-lg shadow-sm">
            <Sprout className="h-4 w-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-stone-900 leading-none">SugarcaneChatbot</h1>
            <p className="text-[9px] uppercase tracking-widest font-bold text-emerald-700/70">Workspace</p>
          </div>
        </div>
      </div>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <div className="flex items-center gap-3 pr-2 cursor-pointer hover:bg-stone-50 p-1.5 rounded-xl transition-colors group">
            <div className="text-right hidden sm:block">
              <p className="text-[11px] font-bold text-stone-900 leading-none">{user?.email || "Research User"}</p>
              <p className="text-[9px] text-stone-400 font-bold uppercase tracking-tighter group-hover:text-emerald-700 transition-colors capitalize">{user?.role || "user"}</p>
            </div>
            <Avatar className="h-7 w-7 border border-stone-100 shadow-sm">
              <AvatarFallback className="bg-emerald-50 text-emerald-700 text-[10px] font-bold">{initials}</AvatarFallback>
            </Avatar>
          </div>
        </DropdownMenuTrigger>
        <DropdownMenuContent side="bottom" align="end" className="w-52">
          <DropdownMenuLabel className="font-normal">
            <p className="text-xs font-bold text-stone-800 truncate">{user?.email}</p>
            <p className="text-[10px] text-stone-400 uppercase tracking-widest font-bold capitalize">{user?.role}</p>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="text-red-500 font-bold hover:text-red-600 focus:text-red-600 cursor-pointer gap-2"
            onClick={logout}
          >
            <LogOut className="size-4" />
            Sign Out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  )
}
