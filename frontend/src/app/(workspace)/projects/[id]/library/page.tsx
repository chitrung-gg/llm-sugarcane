"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { 
  Database, 
  Loader2, 
  Search, 
  Link as LinkIcon, 
  Unlink, 
  Library, 
  Globe,
  Info,
  CheckCircle2,
  Settings
} from "lucide-react"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { useLibraryDatasets, useProjectDatasets, useAttachDataset, useDetachDataset } from "@/hooks/use-datasets"
import { getCurrentUser } from "@/lib/auth"
import Link from "next/link"

export default function ProjectLibraryPage() {
  const params = useParams()
  const projectId = params.id as string
  const user = getCurrentUser()
  
  const { data: libraryDatasets = [], isLoading: libraryLoading } = useLibraryDatasets()
  const { data: projectDatasets = [], isLoading: projectDatasetsLoading } = useProjectDatasets(projectId)
  
  const attachMutation = useAttachDataset()
  const detachMutation = useDetachDataset()

  const [searchQuery, setSearchQuery] = React.useState("")

  const attachedDatasetIds = new Set(projectDatasets.map(d => d.id))

  const filteredLibrary = libraryDatasets.filter(d => 
    d.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    d.description?.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const handleAttach = (datasetId: string) => {
    attachMutation.mutate({ projectId, datasetId })
  }

  const handleDetach = (datasetId: string) => {
    if (confirm("Remove this reference from your project? You can re-attach it anytime from the library.")) {
      detachMutation.mutate({ projectId, datasetId })
    }
  }

  return (
    <div className="space-y-8 p-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] font-bold text-emerald-600 uppercase tracking-[0.3em] mb-1">Project Resources</p>
          <h1 className="text-4xl font-bold tracking-tight text-stone-900 flex items-center gap-3">
            <Library className="size-8 text-emerald-700" />
            Reference Library
          </h1>
          <p className="text-stone-500 mt-2 font-medium max-w-2xl text-base">
            Attach global genomic datasets and knowledge bases to your project to enhance agent intelligence.
          </p>
        </div>
        
        {user?.role === 'admin' && (
          <Button variant="outline" asChild className="h-10 px-4 rounded-xl border-stone-200 text-stone-600 font-bold text-xs shadow-sm hover:bg-emerald-50 hover:text-emerald-700 hover:border-emerald-200 transition-all">
            <Link href="/admin/knowledge-base">
              <Settings className="mr-2 size-4" /> Manage Global Base
            </Link>
          </Button>
        )}
      </div>

      <Card className="border-stone-200 shadow-sm rounded-2xl overflow-hidden bg-white">
        <CardHeader className="border-b border-stone-100 bg-stone-50/50 p-6">
          <div className="flex items-center justify-between gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-stone-400" />
              <Input 
                placeholder="Search available references..." 
                className="pl-10 h-11 rounded-xl border-stone-200 bg-white"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <Badge variant="outline" className="h-11 px-4 rounded-xl border-stone-200 bg-white text-stone-600 font-bold">
              {filteredLibrary.length} Global References
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {libraryLoading ? (
            <div className="p-20 text-center">
              <Loader2 className="size-8 animate-spin text-emerald-600 mx-auto" />
            </div>
          ) : filteredLibrary.length > 0 ? (
            <div className="divide-y divide-stone-100">
              {filteredLibrary.map((dataset) => {
                const isAttached = attachedDatasetIds.has(dataset.id)
                return (
                  <div key={dataset.id} className="p-6 flex items-center justify-between hover:bg-stone-50/50 transition-colors group">
                    <div className="flex items-start gap-4">
                      <div className="bg-stone-100 p-3 rounded-xl group-hover:bg-emerald-100 group-hover:text-emerald-700 transition-colors">
                        <Database className="size-6" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="font-bold text-stone-900">{dataset.name}</h3>
                          <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[9px] font-black uppercase tracking-widest px-1.5 py-0">Global</Badge>
                          {isAttached && (
                             <Badge className="bg-blue-50 text-blue-700 border-blue-100 text-[9px] font-black uppercase tracking-widest px-1.5 py-0 flex items-center gap-1">
                               <CheckCircle2 className="size-2.5" /> Connected
                             </Badge>
                          )}
                        </div>
                        <p className="text-sm text-stone-500 font-medium mt-1">{dataset.description || "No description provided."}</p>
                        <div className="flex items-center gap-4 mt-2">
                          <div className="flex items-center gap-1.5 text-[10px] text-stone-400 font-bold uppercase tracking-widest">
                            <Globe className="size-3 text-emerald-600" /> System Public
                          </div>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-4">
                      {isAttached ? (
                        <Button 
                          variant="outline" 
                          className="h-10 px-4 rounded-xl border-stone-200 text-stone-500 hover:text-red-600 hover:bg-red-50 hover:border-red-100 font-bold text-xs transition-all"
                          onClick={() => handleDetach(dataset.id)}
                          disabled={detachMutation.isPending}
                        >
                          <Unlink className="mr-2 size-3.5" /> Disconnect
                        </Button>
                      ) : (
                        <Button 
                          className="h-10 px-6 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white font-bold shadow-lg shadow-emerald-700/10 text-xs transition-all"
                          onClick={() => handleAttach(dataset.id)}
                          disabled={attachMutation.isPending}
                        >
                          <LinkIcon className="mr-2 size-3.5" /> Connect to Project
                        </Button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="p-20 text-center space-y-4">
              <div className="bg-stone-100 size-16 rounded-full flex items-center justify-center mx-auto">
                 <Search className="size-8 text-stone-400" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-stone-900">No references available</h3>
                <p className="text-stone-500 font-medium">Global datasets will appear here once administrators publish them.</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-emerald-100 bg-emerald-50/50 rounded-2xl p-6">
        <div className="flex gap-4">
          <div className="bg-emerald-100 p-2 rounded-xl h-fit">
            <Info className="size-5 text-emerald-700" />
          </div>
          <div>
            <h4 className="font-bold text-emerald-900">How Library Attachments Work</h4>
            <p className="text-sm text-emerald-800/70 mt-1 font-medium leading-relaxed">
              Connecting a library dataset does not copy data. It creates a reference link that allows the 
              Sugarcane AI Agent to access those files during your analysis. This ensures you are always 
              working with the most up-to-date system reference data without consuming extra storage.
            </p>
          </div>
        </div>
      </Card>
    </div>
  )
}
