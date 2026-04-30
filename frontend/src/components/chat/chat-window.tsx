"use client";

import React, { useState, useRef, useEffect } from "react";
import { useParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/lib/api-client";
import { v4 as uuidv4 } from "uuid";
import { Send, User, Bot, Loader2, Database } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { useProjectDatasets } from "@/hooks/use-datasets";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface ChatResponse {
  answer: string;
  thread_id: string;
}

export function ChatWindow() {
  const params = useParams();
  const projectId = params.id as string;
  const [threadId] = useState(() => uuidv4());
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [selectedDatasets, setSelectedDatasets] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Fetch real project datasets
  const { data: datasets, isLoading: datasetsLoading } = useProjectDatasets(projectId);

  const mutation = useMutation({
    mutationFn: async (query: string) => {
      const formData = new FormData();
      formData.append("query", query);
      formData.append("thread_id", threadId);
      if (projectId) {
        formData.append("project_id", projectId);
      }
      if (selectedDatasets.length > 0) {
        // Send as JSON string as required by the backend fix
        formData.append("dataset_ids", JSON.stringify(selectedDatasets));
      }

      const response = await api.post<ChatResponse>("/agent", formData);
      return response.data;
    },
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        { id: uuidv4(), role: "assistant", content: data.answer },
      ]);
    },
    onError: (error) => {
      console.error("Chat error:", error);
      setMessages((prev) => [
        ...prev,
        { id: uuidv4(), role: "assistant", content: "Sorry, I encountered an error processing your request." },
      ]);
    },
  });

  const handleSend = () => {
    if (!input.trim() || mutation.isPending) return;

    const userMessage = input.trim();
    setMessages((prev) => [...prev, { id: uuidv4(), role: "user", content: userMessage }]);
    setInput("");
    mutation.mutate(userMessage);
  };

  const toggleDataset = (id: string) => {
    setSelectedDatasets(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
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
  }, [messages]);

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
          {messages.length === 0 && (
            <div className="text-center py-20 text-stone-500">
              <div className="bg-emerald-100 w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4">
                <Bot className="h-6 w-6 text-emerald-700" />
              </div>
              <h2 className="text-xl font-bold mb-2 text-stone-800 tracking-tight">Sugarcane Research Assistant</h2>
              <p className="max-w-xs mx-auto text-sm font-medium text-stone-500 leading-relaxed">Select biological datasets above to provide context for your queries.</p>
            </div>
          )}
          
          {messages.map((message) => (
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
              <div className={cn(
                "rounded-lg px-4 py-2 max-w-[85%] text-sm shadow-sm",
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
            </div>
          ))}
          {mutation.isPending && (
            <div className="flex w-full gap-3 flex-row">
              <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-md border shadow bg-emerald-100 text-emerald-800 border-emerald-200">
                <Bot className="h-4 w-4" />
              </div>
              <div className="rounded-lg px-4 py-3 bg-white text-stone-800 border border-emerald-100 shadow-sm">
                <Loader2 className="h-4 w-4 animate-spin text-emerald-600" />
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
            disabled={!input.trim() || mutation.isPending}
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
