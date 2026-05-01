"use client";

import React, { useState, useRef, useEffect } from "react";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Send, User, Bot, Loader2, Database, ChevronDown, ChevronRight, ExternalLink, Wrench, Brain } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { useProjectDatasets } from "@/hooks/use-datasets";
import { useChatHistory, useSendMessage } from "@/hooks/use-chat";
import { Message } from "@/lib/types";
import { v4 as uuidv4 } from "uuid";

export function ChatWindow() {
  const params = useParams();
  const projectId = params.id as string;
  const threadId = params.threadId as string;
  
  const [input, setInput] = useState("");
  const [selectedDatasets, setSelectedDatasets] = useState<string[]>([]);
  const [expandedSources, setExpandedSources] = useState<Record<string, boolean>>({});
  const [expandedThoughts, setExpandedThoughts] = useState<Record<string, boolean>>({});
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: datasets, isLoading: datasetsLoading } = useProjectDatasets(projectId);
  
  // Fetch history for this thread
  const { data: history, isLoading: historyLoading } = useChatHistory(threadId);
  
  // Mutation for sending messages
  const sendMessage = useSendMessage();

  const [localMessages, setLocalMessages] = useState<Message[]>([]);

  // Sync history to local state
  useEffect(() => {
    if (history?.messages) {
      const formatted: Message[] = [];
      let currentThoughts: string[] = [];

      history.messages.forEach((m, idx) => {
        if (m.type === "thought") {
          currentThoughts.push(m.content);
        } else if (m.role === "assistant" && (!m.type || m.type === "answer" || m.type === "error")) {
          formatted.push({
            id: m.id || m.execution_id || `hist-${idx}`,
            role: m.role,
            content: m.content,
            type: m.type as any,
            execution_id: m.execution_id,
            thoughts: [...currentThoughts]
          });
          currentThoughts = []; // Reset for next group
        } else {
          formatted.push({
            id: m.id || m.execution_id || `hist-${idx}`,
            role: m.role,
            content: m.content,
            type: m.type as any,
            execution_id: m.execution_id
          });
        }
      });
      setLocalMessages(formatted);
    }
  }, [history]);

  const handleSend = () => {
    if (!input.trim() || sendMessage.isPending) return;

    const userMessage = input.trim();
    const tempId = uuidv4();
    
    setLocalMessages((prev) => [
      ...prev, 
      { id: tempId, role: "user", content: userMessage }
    ]);
    
    setInput("");
    
    sendMessage.mutate({
      query: userMessage,
      threadId: threadId,
      projectId: projectId,
      datasetIds: selectedDatasets
    }, {
      onSuccess: (data) => {
        setLocalMessages((prev) => [
          ...prev,
          { 
            id: data.execution_id || uuidv4(), 
            role: "assistant", 
            content: data.answer,
            type: "answer",
            execution_id: data.execution_id,
            thoughts: data.thoughts || [],
            rag_sources: data.rag_sources,
            web_results: data.web_results,
            tool_executions: data.tool_executions
          },
        ]);
      },
      onError: () => {
        setLocalMessages((prev) => [
          ...prev,
          { id: uuidv4(), role: "assistant", content: "Sorry, I encountered an error processing your request." },
        ]);
      }
    });
  };

  const toggleDataset = (id: string) => {
    setSelectedDatasets(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const toggleSource = (msgId: string) => {
    setExpandedSources(prev => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  const toggleThoughts = (msgId: string) => {
    setExpandedThoughts(prev => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [localMessages, sendMessage.isPending]);

  return (
    <div className="flex flex-col h-full bg-stone-50/50">
      {/* Context Selection Bar */}
      <div className="border-b bg-white p-3 flex items-center gap-3 overflow-x-auto min-h-[56px]">
        <span className="text-[10px] font-bold text-stone-400 uppercase tracking-[0.2em] whitespace-nowrap ml-2">Active Context:</span>
        {datasetsLoading ? (
          <Loader2 className="h-4 w-4 animate-spin text-stone-300" />
        ) : datasets?.length === 0 ? (
          <span className="text-xs text-stone-400 italic">No datasets in this project.</span>
        ) : (
          datasets?.map((ds) => (
            <button
              key={ds.id}
              onClick={() => toggleDataset(ds.id)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-semibold transition-all whitespace-nowrap",
                selectedDatasets.includes(ds.id)
                  ? "bg-emerald-50 border-emerald-200 text-emerald-700 shadow-sm"
                  : "bg-stone-50 border-stone-200 text-stone-500 hover:bg-stone-100"
              )}
            >
              <Database className="h-3 w-3" />
              {ds.name}
            </button>
          ))
        )}
      </div>

      <ScrollArea className="flex-1 p-4">
        <div className="max-w-3xl mx-auto space-y-6">
          {historyLoading ? (
            <div className="flex justify-center py-20">
              <Loader2 className="h-6 w-6 animate-spin text-stone-300" />
            </div>
          ) : localMessages.length === 0 && (
            <div className="text-center py-20 text-stone-500">
              <div className="bg-emerald-100 w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4">
                <Bot className="h-6 w-6 text-emerald-700" />
              </div>
              <h2 className="text-xl font-bold mb-2 text-stone-800 tracking-tight">Sugarcane Research Assistant</h2>
              <p className="max-w-xs mx-auto text-sm font-medium text-stone-500 leading-relaxed">Select biological datasets above to provide context for your queries.</p>
            </div>
          )}
          
          {localMessages.map((message) => (
            <div
              key={message.id}
              className={cn(
                "flex w-full gap-3",
                message.role === "user" ? "flex-row-reverse" : "flex-row"
              )}
            >
              <div className={cn(
                "flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-md border shadow",
                message.role === "user" 
                  ? "bg-stone-200 text-stone-700 border-stone-300" 
                  : "bg-emerald-100 text-emerald-800 border-emerald-200"
              )}>
                {message.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
              </div>
              <div className="flex flex-col gap-2 max-w-[85%]">
                <div className={cn(
                  "rounded-lg px-4 py-2 text-sm shadow-sm",
                  message.role === "user" 
                    ? "bg-stone-100 text-stone-900 border border-stone-200" 
                    : "bg-white text-stone-800 border border-emerald-100"
                )}>
                  <div className="prose prose-sm max-w-none dark:prose-invert prose-p:leading-relaxed prose-pre:bg-stone-900 prose-pre:text-stone-50">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {message.content}
                    </ReactMarkdown>
                  </div>
                </div>

                {/* Metadata Sections (Assistant Only) */}
                {message.role === "assistant" && (
                  <div className="space-y-2">
                    {/* Reasoning / Thoughts */}
                    {message.thoughts && message.thoughts.length > 0 && (
                      <div className="border border-stone-200 rounded-md bg-stone-50 overflow-hidden">
                        <button 
                          onClick={() => toggleThoughts(message.id)}
                          className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold text-stone-600 hover:bg-stone-100 transition-colors"
                        >
                          <div className="flex items-center gap-2">
                            <Brain className="h-3.5 w-3.5" />
                            Reasoning Process
                          </div>
                          {expandedThoughts[message.id] ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                        </button>
                        {expandedThoughts[message.id] && (
                          <div className="p-3 bg-white text-sm text-stone-600 border-t border-stone-200 space-y-2">
                            {message.thoughts.map((thought, idx) => (
                              <div key={idx} className="prose prose-sm max-w-none prose-p:leading-relaxed">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                  {thought}
                                </ReactMarkdown>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Tool Executions */}
                    {message.tool_executions && message.tool_executions.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {message.tool_executions.map((tool, idx) => (
                          <div key={idx} className="flex items-center gap-1.5 px-2 py-1 rounded border border-stone-200 bg-stone-50 text-[10px] font-bold text-stone-500 uppercase tracking-tight">
                            <Wrench className="h-3 w-3" />
                            {tool.tool_name}: {tool.status}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* RAG Sources */}
                    {message.rag_sources && message.rag_sources.length > 0 && (
                      <div className="border border-emerald-100 rounded-md bg-white overflow-hidden">
                        <button 
                          onClick={() => toggleSource(message.id)}
                          className="w-full flex items-center justify-between px-3 py-1.5 text-[10px] font-bold text-emerald-700 uppercase tracking-widest bg-emerald-50/50 hover:bg-emerald-50 transition-colors"
                        >
                          <div className="flex items-center gap-2">
                            <Database className="h-3 w-3" />
                            Research Sources ({message.rag_sources.length})
                          </div>
                          {expandedSources[message.id] ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                        </button>
                        {expandedSources[message.id] && (
                          <div className="p-2 space-y-1 divide-y divide-stone-50">
                            {message.rag_sources.map((source, idx) => (
                              <div key={idx} className="pt-1 first:pt-0 flex items-center justify-between gap-4">
                                <span className="text-xs font-semibold text-stone-600 truncate">{source.source_file}</span>
                                <div className="flex items-center gap-2 shrink-0">
                                  <span className="text-[10px] text-stone-400 font-medium">Relevance: {source.highest_score ? (source.highest_score * 100).toFixed(0) : "N/A"}%</span>
                                  <ExternalLink className="h-3 w-3 text-stone-300" />
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          {sendMessage.isPending && (
            <div className="flex w-full gap-3 flex-row">
              <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-md border shadow bg-emerald-100 text-emerald-800 border-emerald-200">
                <Bot className="h-4 w-4" />
              </div>
              <div className="rounded-lg px-4 py-3 bg-white text-stone-800 border border-emerald-100 shadow-sm flex items-center gap-3">
                <Loader2 className="h-4 w-4 animate-spin text-emerald-600" />
                <span className="text-xs font-bold text-stone-400 uppercase tracking-widest animate-pulse">Agent is reasoning...</span>
              </div>
            </div>
          )}
          <div ref={scrollRef} />
        </div>
      </ScrollArea>

      <div className="border-t bg-white p-4">
        <div className="max-w-3xl mx-auto relative">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about sugarcane genetics..."
            className="min-h-[60px] w-full resize-none bg-stone-50 pr-12 focus-visible:ring-emerald-500 border-stone-200"
            rows={1}
          />
          <Button
            size="icon"
            onClick={handleSend}
            disabled={!input.trim() || sendMessage.isPending}
            className="absolute right-2 bottom-2 bg-emerald-700 hover:bg-emerald-800 text-white transition-colors"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
        <p className="max-w-3xl mx-auto text-[10px] text-stone-400 mt-2 text-center italic">
          Genomic Assistant • Powered by LLM Sugarcane
        </p>
      </div>
    </div>
  );
}
