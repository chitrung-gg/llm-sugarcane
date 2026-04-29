import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Cpu, Database, Info, Server } from "lucide-react"

export default function SettingsPage() {
  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8">
      <div className="space-y-2">
        <h1 className="text-4xl font-black text-stone-900 tracking-tight">System Information</h1>
        <p className="text-stone-500 font-medium">Workspace configuration and platform status.</p>
      </div>

      <div className="grid gap-6">
        <Card className="rounded-2xl border-stone-200 shadow-sm overflow-hidden">
          <CardHeader className="bg-stone-50/50">
            <div className="flex items-center gap-2 mb-1">
              <Cpu className="h-4 w-4 text-emerald-700" />
              <CardTitle className="text-lg font-black text-stone-800">Model Engine</CardTitle>
            </div>
            <CardDescription className="font-medium text-stone-500">Current AI core configuration.</CardDescription>
          </CardHeader>
          <CardContent className="p-6 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold text-stone-500 uppercase tracking-widest">Provider</span>
              <Badge variant="outline" className="rounded-full border-stone-200 font-black text-stone-700">Google Gemini</Badge>
            </div>
            <Separator className="bg-stone-100" />
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold text-stone-500 uppercase tracking-widest">Version</span>
              <span className="text-sm font-black text-stone-800">1.5 Pro (Genomics Optimized)</span>
            </div>
            <Separator className="bg-stone-100" />
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold text-stone-500 uppercase tracking-widest">Knowledge Cutoff</span>
              <span className="text-sm font-black text-stone-800">April 2026</span>
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-stone-200 shadow-sm overflow-hidden">
          <CardHeader className="bg-stone-50/50">
            <div className="flex items-center gap-2 mb-1">
              <Database className="h-4 w-4 text-emerald-700" />
              <CardTitle className="text-lg font-black text-stone-800">Storage Status</CardTitle>
            </div>
            <CardDescription className="font-medium text-stone-500">Indexed genomic data overview.</CardDescription>
          </CardHeader>
          <CardContent className="p-6 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold text-stone-500 uppercase tracking-widest">Knowledge Base</span>
              <span className="text-sm font-black text-emerald-700">1,248 Nodes Indexed</span>
            </div>
            <Separator className="bg-stone-100" />
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold text-stone-500 uppercase tracking-widest">Vector Store</span>
              <span className="text-sm font-black text-stone-800">FAISS / HNSW</span>
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-stone-200 shadow-sm bg-emerald-900 text-white overflow-hidden relative">
          <CardContent className="p-8 space-y-4">
            <div className="flex items-center gap-3">
              <div className="bg-emerald-500/20 p-2 rounded-lg">
                <Info className="h-5 w-5 text-emerald-300" />
              </div>
              <h3 className="text-xl font-black">Thesis Demo Mode</h3>
            </div>
            <p className="text-emerald-100/70 font-medium text-sm leading-relaxed">
              This platform is running in Thesis Demonstration mode. System settings are locked to ensure 
              reproducible analysis results for the graduation project defense.
            </p>
            <div className="flex gap-2 pt-2">
              <Badge className="bg-emerald-500 text-emerald-950 font-black border-none uppercase tracking-tighter">Verified Build</Badge>
              <Badge className="bg-white/10 text-emerald-100 font-bold border-none">v2.4.0-stable</Badge>
            </div>
          </CardContent>
          <Server className="absolute -right-6 -bottom-6 h-32 w-32 text-white/5 -rotate-12" />
        </Card>
      </div>
    </div>
  )
}
