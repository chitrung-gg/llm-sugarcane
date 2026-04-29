"use client"

import { useState } from "react"
import Link from "next/link"
import { 
  SidebarProvider, 
  Sidebar, 
  SidebarContent, 
  SidebarHeader, 
  SidebarGroup, 
  SidebarGroupContent, 
  SidebarMenu, 
  SidebarMenuItem, 
  SidebarMenuButton 
} from "@/components/ui/sidebar"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Separator } from "@/components/ui/separator"
import { 
  Search, 
  Send, 
  FileText, 
  ChevronRight, 
  History, 
  Sparkles, 
  Database, 
  FlaskConical, 
  ArrowLeft,
  LayoutDashboard,
  Clock
} from "lucide-react"

export default function ChatRoomPage() {
  const [activeCitation, setActiveCitation] = useState<any>(null)

  const messages = [
    {
      role: "assistant",
      content: "Based on the CIRAD research papers provided, the SAC-1 gene in sugarcane shows a strong correlation with sucrose accumulation in mature stalks [1]. It appears to be highly expressed in the internodes during the peak ripening stage.",
      citations: [
        {
          id: "1",
          title: "CIRAD Research Paper (2024)",
          text: "Section 3.2: Gene SAC-1 showed 40% higher expression in mature stalks compared to immature nodes in cultivars R570 and SP80-3280.",
          metadata: { score: 0.98, source: "sugarcane_genetics_v4.pdf", method: "RNA-seq Analysis" }
        }
      ]
    }
  ]

  return (
    <SidebarProvider>
      <div className="flex h-screen w-full overflow-hidden bg-slate-50 font-sans antialiased">
        
        {/* SHARED ACADEMIC SIDEBAR */}
        <Sidebar className="border-r border-slate-200 bg-white">
          <SidebarHeader className="p-6 border-b border-slate-100">
            <Link href="/dashboard" className="flex items-center gap-3 font-bold text-slate-800 hover:opacity-80 transition-opacity">
              <div className="bg-emerald-700 p-2 rounded-lg shadow-sm">
                <FlaskConical className="h-5 w-5 text-white" />
              </div>
              <span className="tracking-tight text-lg">Thesis Lab</span>
            </Link>
          </SidebarHeader>
          
          <SidebarContent className="p-2">
            <SidebarGroup>
              <div className="px-4 py-2">
                 <p className="text-[10px] font-black uppercase tracking-widest text-slate-400">Navigation</p>
              </div>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <SidebarMenuButton 
                      className="py-6 px-4 hover:bg-slate-50 transition-colors text-slate-600"
                      render={<Link href="/dashboard" />}
                    >
                      <LayoutDashboard className="h-4 w-4 mr-1 opacity-70" />
                      Dashboard
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>

            <SidebarGroup className="mt-4">
              <div className="px-4 py-2 flex items-center justify-between">
                 <p className="text-[10px] font-black uppercase tracking-widest text-slate-400">Analysis History</p>
                 <Clock className="h-3 w-3 text-slate-300" />
              </div>
              <SidebarGroupContent>
                <SidebarMenu className="space-y-1">
                  <SidebarMenuItem>
                    <SidebarMenuButton isActive className="bg-emerald-50 text-emerald-700 hover:bg-emerald-50 hover:text-emerald-700 font-bold py-6 px-4 rounded-xl shadow-sm border border-emerald-100/50">
                      <History className="h-4 w-4 mr-1 opacity-70" />
                      Sucrose Analysis
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton className="py-6 px-4 hover:bg-slate-50 transition-colors text-slate-500">
                      <History className="h-4 w-4 mr-1 opacity-40" />
                      Drought Stress
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>

        {/* MAIN INTERFACE */}
        <Sheet>
          <div className="flex flex-1 flex-col overflow-hidden bg-slate-50">
            
            {/* GLOBAL ACADEMIC HEADER (Synchronized with Dashboard) */}
            <header className="w-full px-8 py-4 flex items-center justify-between border-b border-slate-200 bg-white shadow-sm z-10 sticky top-0">
              <div className="flex items-center gap-4">
                <Link href="/dashboard">
                  <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full text-slate-400 hover:text-emerald-700 hover:bg-emerald-50 transition-all">
                    <ArrowLeft className="h-4 w-4" />
                  </Button>
                </Link>
                <Separator orientation="vertical" className="h-6" />
                <div>
                  <h2 className="text-sm font-bold text-slate-900 leading-tight">Drought Resistance Analysis</h2>
                  <div className="flex items-center gap-2">
                     <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                     <p className="text-[10px] uppercase tracking-wider font-semibold text-slate-400">Active Thesis Workspace</p>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-6">
                <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-slate-100 rounded-full border border-slate-200">
                   <Database className="h-3.5 w-3.5 text-emerald-700" />
                   <span className="text-xs font-bold text-slate-600">Context: 4 Datasets</span>
                </div>
                <div className="flex items-center gap-3">
                  <Avatar className="h-8 w-8 border border-slate-200 shadow-sm">
                    <AvatarFallback className="bg-emerald-100 text-emerald-700 text-xs font-bold">DR</AvatarFallback>
                  </Avatar>
                </div>
              </div>
            </header>

            {/* RESEARCH CHAT COLUMN */}
            <div className="flex-1 flex flex-col items-center overflow-hidden">
              <main className="flex h-full w-full max-w-4xl flex-col bg-white shadow-lg ring-1 ring-slate-200/50">
                <ScrollArea className="flex-1 px-10 py-8">
                  <div className="space-y-10 max-w-3xl mx-auto">
                    {messages.map((msg, i) => (
                      <div key={i} className={`flex gap-5 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                        <Avatar className={`h-10 w-10 border shadow-sm ${msg.role === "assistant" ? "border-emerald-100" : "border-slate-100"}`}>
                          <AvatarImage src={msg.role === "assistant" ? "/bot-avatar.png" : ""} />
                          <AvatarFallback className={msg.role === "assistant" ? "bg-emerald-700 text-white" : "bg-slate-100 text-slate-600"}>
                            {msg.role === "assistant" ? <Sparkles className="h-4 w-4" /> : "DR"}
                          </AvatarFallback>
                        </Avatar>
                        <div className={`relative group flex flex-col gap-3 ${msg.role === "user" ? "items-end" : "items-start"}`}>
                          <div className={`rounded-2xl px-6 py-5 shadow-sm ring-1 leading-relaxed text-[15px] ${
                            msg.role === "user" 
                              ? "bg-emerald-700 text-white ring-emerald-800" 
                              : "bg-slate-50 text-slate-700 ring-slate-100"
                          }`}>
                            <p>
                              {msg.content.split(/(\[1\])/).map((part, idx) => 
                                part === "[1]" ? (
                                  <SheetTrigger key={idx} asChild>
                                    <span 
                                      role="button"
                                      onClick={() => setActiveCitation(msg.citations[0])}
                                      className="inline-flex items-center justify-center rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-black text-emerald-700 hover:bg-emerald-200 cursor-help transition-all transform hover:scale-110 ml-1.5 shadow-sm border border-emerald-200"
                                    >
                                      1
                                    </span>
                                  </SheetTrigger>
                                ) : part
                              )}
                            </p>
                          </div>
                          {msg.role === "assistant" && (
                            <div className="flex items-center gap-3 px-1">
                              <div className="flex items-center gap-1.5">
                                <Database className="h-3 w-3 text-emerald-600" />
                                <span className="text-[10px] text-emerald-600 font-bold uppercase tracking-wider">Source Verified</span>
                              </div>
                              <span className="h-1 w-1 rounded-full bg-slate-300" />
                              <span className="text-[10px] text-slate-400 font-medium tracking-tight italic">Relevance: 98.4%</span>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>

                {/* INPUT AREA */}
                <div className="p-8 border-t border-slate-100 bg-white">
                  <div className="relative max-w-3xl mx-auto">
                    <Textarea 
                      placeholder="Enter research query (e.g., Identify SAC-1 variants in R570)..." 
                      className="min-h-[100px] w-full rounded-2xl border-slate-200 bg-slate-50/50 p-5 focus:bg-white focus:ring-4 focus:ring-emerald-500/10 transition-all resize-none text-[15px] shadow-inner"
                    />
                    <div className="absolute bottom-4 right-4 flex gap-2">
                      <Button size="icon" className="h-10 w-10 rounded-xl bg-emerald-700 hover:bg-emerald-800 shadow-lg shadow-emerald-900/20 transition-all hover:translate-y-[-2px] active:scale-95">
                        <Send className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  <div className="mt-4 flex items-center justify-center gap-2 opacity-60">
                    <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
                    <p className="text-center text-[10px] text-slate-500 font-bold uppercase tracking-widest">
                      Sugarcane RAG Engine • Thesis Analytics Build
                    </p>
                  </div>
                </div>
              </main>
            </div>
          </div>

          {/* CITATION DRAWER (Perplexity Style) */}
          <SheetContent side="right" className="w-[400px] sm:w-[600px] border-l border-slate-200 bg-white shadow-2xl p-0">
            {activeCitation && (
              <div className="flex flex-col h-full font-sans">
                <SheetHeader className="p-8 border-b border-slate-100 bg-slate-50/50">
                  <SheetTitle className="flex items-center gap-4 text-slate-900">
                    <div className="bg-emerald-100 p-2.5 rounded-xl text-emerald-700 shadow-sm border border-emerald-200">
                      <FileText className="h-5 w-5" />
                    </div>
                    <div>
                      <span className="block text-xl font-black leading-tight tracking-tight">{activeCitation.title}</span>
                      <span className="text-[10px] text-slate-400 font-bold uppercase tracking-[0.2em] mt-1 block">Thesis Source Evidence</span>
                    </div>
                  </SheetTitle>
                </SheetHeader>
                
                <ScrollArea className="flex-1 p-10">
                  <div className="space-y-10 pr-2">
                    {/* Metadata Grid */}
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-white rounded-xl p-5 border border-slate-100 shadow-sm">
                        <span className="text-[10px] text-slate-400 font-black uppercase tracking-widest block mb-2">Original File</span>
                        <span className="text-sm font-bold text-slate-700 flex items-center gap-2">
                           <FileText className="h-3.5 w-3.5 text-emerald-600" />
                           {activeCitation.metadata.source}
                        </span>
                      </div>
                      <div className="bg-white rounded-xl p-5 border border-slate-100 shadow-sm">
                        <span className="text-[10px] text-slate-400 font-black uppercase tracking-widest block mb-2">Analysis Method</span>
                        <span className="text-sm font-bold text-emerald-700">{activeCitation.metadata.method}</span>
                      </div>
                    </div>
                    
                    {/* Context Snapshot */}
                    <div className="space-y-4">
                      <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                         <h5 className="text-[10px] font-black uppercase tracking-widest text-slate-400">Verbatim Context</h5>
                         <div className="px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-bold border border-emerald-100 shadow-sm">98.4% Confidence</div>
                      </div>
                      <div className="relative">
                        <div className="absolute -left-5 top-0 bottom-0 w-1.5 bg-emerald-700 rounded-full opacity-20" />
                        <div className="rounded-2xl border border-slate-100 bg-slate-50/50 p-8 font-serif text-[17px] leading-relaxed text-slate-800 shadow-inner italic">
                          "{activeCitation.text}"
                        </div>
                      </div>
                    </div>

                    {/* Technical Metadata */}
                    <div className="space-y-4">
                      <h5 className="text-[10px] font-black uppercase tracking-widest text-slate-400 border-b border-slate-100 pb-2">Technical JSON Reference</h5>
                      <pre className="overflow-auto rounded-2xl bg-slate-900 p-8 text-[12px] text-emerald-400 shadow-xl font-mono leading-relaxed ring-1 ring-white/10">
                        {JSON.stringify(activeCitation.metadata, null, 2)}
                      </pre>
                    </div>

                    <Button variant="outline" className="w-full h-14 rounded-2xl border-slate-200 hover:bg-slate-50 text-slate-700 font-bold shadow-md transition-all active:scale-[0.98]">
                      Request Full Document Access <ChevronRight className="ml-2 h-4 w-4 opacity-50" />
                    </Button>
                    
                    <div className="pb-10 pt-4 text-center">
                       <p className="text-[10px] text-slate-400 font-medium">Verified by Sugarcane Genomics RAG Build 2026.04</p>
                    </div>
                  </div>
                </ScrollArea>
              </div>
            )}
          </SheetContent>
        </Sheet>
      </div>
    </SidebarProvider>
  )
}
