import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Search as SearchIcon, Filter, Database, FileText, Sprout } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"

const suggestedResources = [
  {
    title: "R570 Reference Genome v2",
    type: "Dataset",
    tags: ["Genome", "Reference"],
    project: "Drought Resistance"
  },
  {
    title: "Sucrose metabolic pathways annotation",
    type: "Document",
    tags: ["Metabolism", "QTL"],
    project: "Sucrose Content Genetics"
  },
  {
    title: "SP80-3280 Hybrid assembly",
    type: "Dataset",
    tags: ["Hybrid", "Assembly"],
    project: "General Research"
  }
]

export default function SearchPage() {
  return (
    <div className="p-8 max-w-5xl mx-auto space-y-10">
      <div className="flex flex-col gap-6">
        <div className="space-y-2">
          <h1 className="text-4xl font-black text-stone-900 tracking-tight">Resource Explorer</h1>
          <p className="text-stone-500 font-medium">Browse and discover indexed sugarcane genomic data and research papers.</p>
        </div>

        <div className="relative group">
          <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-stone-300 group-focus-within:text-emerald-600 transition-colors" />
          <Input 
            className="pl-12 h-14 bg-white shadow-xl shadow-stone-200/40 border-stone-200 rounded-2xl focus-visible:ring-emerald-500 text-base font-medium" 
            placeholder="Search genes, pathways, or cultivars..." 
          />
        </div>

        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" className="gap-2 rounded-full border-stone-200 font-bold text-stone-500 hover:bg-emerald-50 hover:text-emerald-700 hover:border-emerald-200 transition-all">
            <Filter className="h-3.5 w-3.5" />
            Cultivars
          </Button>
          <Button variant="outline" size="sm" className="gap-2 rounded-full border-stone-200 font-bold text-stone-500 hover:bg-emerald-50 hover:text-emerald-700 hover:border-emerald-200 transition-all">
            <Filter className="h-3.5 w-3.5" />
            Project Origin
          </Button>
          <Button variant="outline" size="sm" className="gap-2 rounded-full border-stone-200 font-bold text-stone-500 hover:bg-emerald-50 hover:text-emerald-700 hover:border-emerald-200 transition-all">
            <Database className="h-3.5 w-3.5" />
            FASTA Data
          </Button>
        </div>
      </div>

      <div className="space-y-6">
        <h2 className="text-xs font-black text-stone-400 uppercase tracking-[0.3em] ml-1">Available Resources</h2>
        <div className="grid gap-4">
          {suggestedResources.map((res, i) => (
            <Card key={i} className="hover:border-emerald-200 hover:shadow-lg hover:shadow-emerald-700/5 transition-all cursor-pointer group rounded-2xl border-stone-200 bg-white overflow-hidden">
              <CardContent className="p-5 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="bg-stone-50 p-3 rounded-xl border border-stone-100 group-hover:bg-emerald-50 group-hover:border-emerald-100 transition-colors">
                    {res.type === "Dataset" ? (
                      <Database className="h-5 w-5 text-stone-400 group-hover:text-emerald-600" />
                    ) : (
                      <FileText className="h-5 w-5 text-stone-400 group-hover:text-emerald-600" />
                    )}
                  </div>
                  <div>
                    <p className="font-black text-stone-800 text-lg group-hover:text-emerald-800 transition-colors">{res.title}</p>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-xs font-bold text-stone-400 uppercase tracking-widest">{res.project}</span>
                      <div className="flex gap-1.5">
                        {res.tags.map(tag => (
                          <Badge key={tag} variant="secondary" className="bg-stone-100 text-[10px] font-black uppercase text-stone-500 tracking-tighter rounded-md">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
                <Button variant="ghost" size="sm" className="rounded-xl font-black uppercase text-[10px] tracking-widest text-emerald-700 hover:bg-emerald-50 hover:text-emerald-800">
                  Access Data
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      <div className="bg-stone-900 rounded-2xl p-8 flex items-center justify-between text-white overflow-hidden relative shadow-2xl shadow-stone-900/20">
        <div className="relative z-10">
          <h3 className="text-xl font-black mb-1">Genome Knowledge Graph</h3>
          <p className="text-stone-400 text-sm font-medium">All indexed data is automatically linked via the Sugarcane AI Assistant.</p>
        </div>
        <Sprout className="h-24 w-24 text-emerald-500/10 absolute -right-4 -bottom-4 rotate-12" />
        <Button className="bg-emerald-500 hover:bg-emerald-400 text-stone-900 font-black rounded-xl relative z-10">
          Sync Database
        </Button>
      </div>
    </div>
  )
}
