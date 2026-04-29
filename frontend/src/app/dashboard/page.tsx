"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { 
  Plus, 
  Folder, 
  FileText, 
  Trash2, 
  MessageSquare, 
  Database, 
  Clock, 
  ChevronRight,
  LayoutDashboard,
  Settings,
  LogOut,
  Sprout
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

// Mock data for initial thesis UI
const initialProjects = [
  { 
    id: "1", 
    name: "Drought Resistance Analysis", 
    datasets: 4, 
    lastModified: "2 hours ago",
    status: "In Progress",
    files: ["genome_v1.fasta", "transcriptome_results.csv"]
  },
  { 
    id: "2", 
    name: "Sucrose Content Genetics", 
    datasets: 2, 
    lastModified: "Yesterday",
    status: "Completed",
    files: ["sucrose_variants.json"]
  },
]

export default function DashboardPage() {
  const [projects] = useState(initialProjects)
  const router = useRouter()

  const handleSignOut = () => {
    router.push("/login")
  }

  return (
    <div className="min-h-screen flex flex-col bg-stone-50 font-sans antialiased text-stone-900">
      {/* GLOBAL HEADER */}
      <header className="w-full px-8 py-4 flex items-center justify-between border-b border-stone-200 bg-white/80 backdrop-blur-md z-10 sticky top-0">
        <div className="flex items-center gap-3">
          <div className="bg-emerald-700 p-2 rounded-lg shadow-sm">
            <Sprout className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-black tracking-tight text-stone-900">Sugarcane Hub</h1>
            <p className="text-[10px] uppercase tracking-widest font-bold text-emerald-700/70">Workspace</p>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="text-right hidden sm:block">
              <p className="text-xs font-black text-stone-900 leading-none">Research User</p>
              <p className="text-[10px] text-stone-400 font-bold uppercase tracking-tighter">Member</p>
            </div>
            <Avatar className="h-8 w-8 border border-stone-100 shadow-sm">
              <AvatarFallback className="bg-emerald-50 text-emerald-700 text-xs font-black">U</AvatarFallback>
            </Avatar>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* SIDE NAVIGATION */}
        <aside className="w-64 border-r border-stone-200 bg-white/50 hidden md:flex flex-col p-4">
          <nav className="space-y-1 flex-1">
            <Button asChild variant="ghost" className="w-full justify-start gap-3 bg-emerald-50 text-emerald-700 font-black hover:bg-emerald-50 hover:text-emerald-700 rounded-xl">
              <Link href="/dashboard">
                <LayoutDashboard className="h-4 w-4" />
                Projects
              </Link>
            </Button>
            <Button asChild variant="ghost" className="w-full justify-start gap-3 text-stone-500 font-bold hover:text-stone-900 hover:bg-stone-100 rounded-xl">
              <Link href="/search">
                <FileText className="h-4 w-4" />
                Resource Hub
              </Link>
            </Button>
            <Separator className="my-4" />
            <Button asChild variant="ghost" className="w-full justify-start gap-3 text-stone-500 font-bold hover:text-stone-900 hover:bg-stone-100 rounded-xl">
              <Link href="/settings">
                <Settings className="h-4 w-4" />
                System Info
              </Link>
            </Button>
          </nav>
          
          <Button 
            variant="ghost" 
            className="w-full justify-start gap-3 text-red-500 font-bold hover:text-red-600 hover:bg-red-50 rounded-xl transition-colors"
            onClick={handleSignOut}
          >
            <LogOut className="h-4 w-4" />
            Sign Out
          </Button>
        </aside>

        {/* MAIN CONTENT AREA */}
        <main className="flex-1 overflow-y-auto p-8 lg:p-12 bg-[radial-gradient(circle_at_bottom_left,var(--color-emerald-50),transparent_40%)]">
          <div className="max-w-6xl mx-auto">
            {/* WELCOME SECTION */}
            <div className="flex flex-col md:flex-row md:items-end justify-between mb-10 gap-4">
              <div>
                <h2 className="text-4xl font-black tracking-tight text-stone-900 mb-2">Genomics Projects</h2>
                <p className="text-stone-500 font-medium leading-relaxed max-w-xl text-sm">
                  Continue your analysis or upload new datasets to the sugarcane knowledge base.
                </p>
              </div>
              <Button className="bg-emerald-700 hover:bg-emerald-800 text-white font-black h-12 px-6 rounded-xl shadow-lg shadow-emerald-700/20 transition-all active:scale-[0.98]">
                <Plus className="mr-2 h-5 w-5" /> New Project
              </Button>
            </div>

            {/* PROJECT GRID */}
            <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-2">
              {projects.map((project) => (
                <Card key={project.id} className="group hover:shadow-2xl hover:shadow-stone-200/50 transition-all duration-500 border-stone-200 rounded-2xl overflow-hidden bg-white flex flex-col">
                  <CardHeader className="p-6 border-b border-stone-50 bg-stone-50/30">
                    <div className="flex items-center justify-between mb-4">
                      <div className="bg-emerald-100 p-2.5 rounded-xl border border-emerald-200/50">
                        <Folder className="h-5 w-5 text-emerald-700" />
                      </div>
                      <div className="flex items-center gap-2">
                         <span className={`text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full border shadow-sm ${
                           project.status === "Completed" ? "bg-emerald-50 text-emerald-700 border-emerald-100" : "bg-blue-50 text-blue-700 border-blue-100"
                         }`}>
                           {project.status}
                         </span>
                         <Button variant="ghost" size="icon" className="h-9 w-9 text-stone-400 hover:text-red-500 hover:bg-red-50 rounded-full transition-colors">
                           <Trash2 className="h-4 w-4" />
                         </Button>
                      </div>
                    </div>
                    <CardTitle className="text-2xl font-black text-stone-800 group-hover:text-emerald-700 transition-colors">
                      {project.name}
                    </CardTitle>
                    <div className="flex items-center gap-2 mt-1">
                      <Clock className="h-3.5 w-3.5 text-stone-300" />
                      <span className="text-[11px] font-bold text-stone-400 uppercase tracking-widest">Modified {project.lastModified}</span>
                    </div>
                  </CardHeader>

                  <CardContent className="p-6 flex-1">
                    <div className="space-y-4">
                       <h4 className="text-[10px] font-black uppercase tracking-widest text-stone-400">Attached Data</h4>
                       <div className="grid gap-2">
                         {project.files?.map((file, idx) => (
                           <div key={idx} className="flex items-center justify-between group/file p-3 rounded-xl hover:bg-stone-50 border border-transparent hover:border-stone-100 transition-all">
                              <div className="flex items-center text-sm font-bold text-stone-600">
                                 <div className="bg-stone-100 p-1.5 rounded-lg mr-3 group-hover/file:bg-white transition-colors">
                                  <FileText className="h-4 w-4 text-stone-400" />
                                 </div>
                                 <span>{file}</span>
                              </div>
                              <ChevronRight className="h-4 w-4 text-stone-300 opacity-0 group-hover/file:opacity-100 transition-all -translate-x-2 group-hover/file:translate-x-0" />
                           </div>
                         ))}
                       </div>
                    </div>
                  </CardContent>

                  <div className="px-6 pb-6 pt-2">
                    <Button asChild className="w-full h-12 bg-white hover:bg-emerald-700 hover:text-white border-2 border-emerald-700 text-emerald-700 font-black rounded-xl transition-all group/btn shadow-sm">
                      <Link href={`/projects/${project.id}/chat`}>
                        <MessageSquare className="mr-2 h-5 w-5 transition-transform group-hover/btn:scale-110" /> 
                        Enter Assistant
                      </Link>
                    </Button>
                  </div>
                </Card>
              ))}
              
              {/* PLACEHOLDER FOR NEW PROJECT */}
              <button className="flex flex-col items-center justify-center border-2 border-dashed border-stone-200 rounded-2xl p-12 hover:border-emerald-500 hover:bg-emerald-50/30 transition-all group bg-white/50">
                <div className="bg-stone-100 p-5 rounded-2xl mb-4 group-hover:bg-emerald-100 transition-all group-hover:scale-110 shadow-sm">
                  <Plus className="h-8 w-8 text-stone-400 group-hover:text-emerald-700" />
                </div>
                <span className="text-base font-black text-stone-400 group-hover:text-emerald-800 uppercase tracking-widest">New Project</span>
                <span className="text-xs text-stone-400 mt-2 font-medium">Add datasets for analysis</span>
              </button>
            </div>
          </div>
        </main>
      </div>

      <footer className="w-full py-8 border-t border-stone-100 bg-white px-10 flex justify-between items-center">
        <p className="text-[10px] font-black text-stone-300 uppercase tracking-[0.4em]">
          Sugarcane Genomics LLM
        </p>
        <div className="flex gap-2">
           <div className="h-1.5 w-8 bg-emerald-700 rounded-full opacity-20" />
           <div className="h-1.5 w-4 bg-emerald-700 rounded-full opacity-10" />
        </div>
      </footer>
    </div>
  )
}
