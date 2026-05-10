"use client";

import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Send, User, Bot, Loader2, Database, ChevronDown, ChevronRight, ExternalLink, Wrench, Brain, Check, X, Download, FileDown, FileCode } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useProjectDatasets, useDatasetFiles } from "@/hooks/use-datasets";
import { useChatHistory } from "@/hooks/use-chat";
import { useChatStream } from "@/hooks/use-chat-stream";
import { useDownload } from "@/hooks/use-download";
import { PlanModificationForm } from "./plan-modification-form";
import { Message, Dataset, DatasetFile } from "@/lib/types";
import { v4 as uuidv4 } from "uuid";

// Helper to extract S3 URIs from text
const extractS3Uris = (text: string): string[] => {
  const s3Regex = /s3:\/\/[^\s"'`<>]+/g;
  return text.match(s3Regex) || [];
};

// Memoized Message Item Component to prevent unnecessary re-renders
const ChatMessageItem = React.memo(({ 
  message, 
  expandedSources, 
  expandedThoughts, 
  toggleSource, 
  toggleThoughts,
  onDownload
}: { 
  message: Message; 
  expandedSources: Record<string, boolean>; 
  expandedThoughts: Record<string, boolean>; 
  toggleSource: (id: string) => void; 
  toggleThoughts: (id: string) => void; 
  onDownload: (params: { fileId?: string; s3Uri?: string }) => void;
}) => {
  return (
    <div
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
                    Thought Process
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
                {message.tool_executions.map((tool, idx) => {
                  const s3Uris = extractS3Uris(tool.output || "");
                  return (
                    <div key={idx} className="flex flex-col gap-1">
                      <div className="flex items-center gap-1.5 px-2 py-1 rounded border border-stone-200 bg-stone-50 text-[10px] font-bold text-stone-500 uppercase tracking-tight">
                        <Wrench className="h-3 w-3" />
                        {tool.tool_name}: {tool.status}
                      </div>
                      {s3Uris.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {s3Uris.map((uri, uIdx) => (
                            <Button 
                              key={uIdx}
                              variant="outline" 
                              size="sm" 
                              className="h-6 px-2 text-[9px] gap-1 bg-white border-emerald-100 text-emerald-700 hover:bg-emerald-50"
                              onClick={() => onDownload({ s3Uri: uri })}
                            >
                              <FileDown className="h-3 w-3" />
                              Download Result
                            </Button>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
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
  );
});

ChatMessageItem.displayName = "ChatMessageItem";

export function ChatWindow() {
  const params = useParams();
  const projectId = params.id as string;
  const threadId = params.threadId as string;
  
  const [input, setInput] = useState("");
  const [selectedDatasets, setSelectedDatasets] = useState<string[]>([]);
  const [expandedSources, setExpandedSources] = useState<Record<string, boolean>>({});
  const [expandedThoughts, setExpandedThoughts] = useState<Record<string, boolean>>({});
  const [activeThoughtsExpanded, setActiveThoughtsExpanded] = useState(true);
  const [isModifyingPlan, setIsModifyingPlan] = useState(false);
  const [planToModify, setPlanToModify] = useState<Message['interrupt_data'] | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: datasets, isLoading: datasetsLoading } = useProjectDatasets(projectId);
  const { downloadFile } = useDownload();
  
  // Fetch history for this thread
  const { data: history, isLoading: historyLoading } = useChatHistory(threadId);
  
  // Streaming hook
  const { streamQuery, isStreaming, currentStream } = useChatStream();

  // Pending user messages (optimistic UI)
  const [pendingUserMessages, setPendingUserMessages] = useState<Message[]>([]);

  // Derived messages from history and pending messages
  const localMessages = useMemo(() => {
    const formatted: Message[] = [];
    let currentThoughts: string[] = [];

    if (history?.messages) {
      history.messages.forEach((m, idx) => {
        if (m.type === "thought") {
          currentThoughts.push(m.content);
        } else if (m.role === "assistant" && (!m.type || m.type === "answer" || m.type === "error")) {
          const existingIdx = formatted.findIndex(f => f.execution_id === m.execution_id && f.role === "assistant" && (m.type === "answer" || !m.type));
          if (existingIdx !== -1 && m.execution_id) {
            // Append if content is unique and not just a sub-string
            const existingContent = formatted[existingIdx].content;
            if (!existingContent.includes(m.content)) {
                formatted[existingIdx].content = existingContent + "\n\n" + m.content;
            }
            
            formatted[existingIdx].thoughts = [...(formatted[existingIdx].thoughts || []), ...currentThoughts];
            
            // Merge tool executions if they exist in history results
            const toolResults = history.tool_results?.filter((tr: any) => tr.execution_id === m.execution_id);
            if (toolResults && toolResults.length > 0) {
                const existingTools = formatted[existingIdx].tool_executions || [];
                const newTools = toolResults.map((tr: any) => ({
                    tool_name: tr.tool,
                    status: tr.status || "complete",
                    output: typeof tr.output === 'string' ? tr.output : JSON.stringify(tr.output)
                }));
                
                // Avoid duplicates by tool name and output hash (simplified here by tool name and first 20 chars of output)
                const mergedTools = [...existingTools];
                newTools.forEach(nt => {
                    if (!mergedTools.some(mt => mt.tool_name === nt.tool_name && mt.output === nt.output)) {
                        mergedTools.push(nt);
                    }
                });
                formatted[existingIdx].tool_executions = mergedTools;
            }
          } else {
            const toolResults = history.tool_results?.filter((tr: any) => tr.execution_id === m.execution_id);
            formatted.push({
              id: m.id || m.execution_id || `hist-${idx}`,
              role: m.role,
              content: m.content,
              type: (m.type as "answer" | "thought" | "error" | "interrupt") || "answer",
              execution_id: m.execution_id,
              thoughts: [...currentThoughts],
              tool_executions: toolResults?.map((tr: any) => ({
                tool_name: tr.tool,
                status: tr.status || "complete",
                output: typeof tr.output === 'string' ? tr.output : JSON.stringify(tr.output)
              }))
            });
          }
          currentThoughts = []; // Reset for next group
        } else {
          formatted.push({
            id: m.id || m.execution_id || `hist-${idx}`,
            role: m.role,
            content: m.content,
            type: m.type as "answer" | "thought" | "error" | "interrupt",
            execution_id: m.execution_id
          });
        }
      });
    }

    // Append pending messages that aren't yet in history
    // We only show pending messages while streaming or if they are genuinely new
    const historyIds = new Set(formatted.map(m => m.id));
    pendingUserMessages.forEach(pm => {
      if (!historyIds.has(pm.id)) {
        formatted.push(pm);
      }
    });

    return formatted;
  }, [history, pendingUserMessages]);

  const handleSend = () => {
    if (!input.trim() || isStreaming) return;

    const userMessage = input.trim();
    const tempId = uuidv4();
    
    setPendingUserMessages((prev) => [
      ...prev, 
      { id: tempId, role: "user", content: userMessage }
    ]);
    
    setInput("");
    setActiveThoughtsExpanded(true); // Ensure expanded for new stream
    
    streamQuery({
      query: userMessage,
      threadId: threadId,
      projectId: projectId,
      datasetIds: selectedDatasets
    }).then(() => {
      setPendingUserMessages([]);
    });
  };

  const handleApprove = () => {
    streamQuery({
      threadId: threadId,
      humanFeedback: { action: "APPROVE" },
      projectId: projectId,
      datasetIds: selectedDatasets
    });
  };

  const handleModify = (feedback: string | Record<string, unknown>) => {
    streamQuery({
      threadId: threadId,
      humanFeedback: feedback,
      projectId: projectId,
      datasetIds: selectedDatasets
    });
    setIsModifyingPlan(false);
    setPlanToModify(null);
  };

  const toggleDataset = (id: string) => {
    setSelectedDatasets(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const toggleSource = useCallback((msgId: string) => {
    setExpandedSources(prev => ({ ...prev, [msgId]: !prev[msgId] }));
  }, []);

  const toggleThoughts = useCallback((msgId: string) => {
    setExpandedThoughts(prev => ({ ...prev, [msgId]: !prev[msgId] }));
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  useEffect(() => {
    if (scrollRef.current) {
      // Use "auto" behavior during streaming to avoid lag from smooth animation
      scrollRef.current.scrollIntoView({ behavior: isStreaming ? "auto" : "smooth" });
    }
  }, [localMessages, isStreaming, currentStream]);

  // Derived state from current stream (memoized to prevent re-computation on every render)
  const activeStreamThoughts = useMemo(() => 
    currentStream
      .filter(e => e.event === 'thought')
      .map(e => (e.data as any).content),
    [currentStream]
  );
  
  const activeStreamTools = useMemo(() => 
    currentStream
      .filter(e => e.event === 'tool_start' || e.event === 'tool_end'),
    [currentStream]
  );
  
  const activeStreamAnswer = useMemo(() => {
    let rawText = "";
    currentStream.forEach(e => {
      if (e.event === 'answer') {
        const content = typeof e.data === 'string' 
          ? e.data 
          : ((e.data as any)?.content || (e.data as any)?.final_answer || "");
        
        if (content) {
          if (rawText && !rawText.includes(content)) {
            rawText += "\n\n" + content;
          } else if (!rawText) {
            rawText = content;
          }
        }
      } else if (e.event === 'token') {
        const token = typeof e.data === 'string' ? e.data : (e.data as any)?.token;
        if (token) {
          if (!rawText.endsWith(token)) {
            rawText += token;
          }
        }
      }
    });

    // --- Real-time JSON Field Extraction ---
    // If the raw text looks like JSON (starts with {), try to extract just the values
    if (rawText.trim().startsWith('{')) {
        // Find "answer": "..." or "direct_response": "..."
        const fieldRegex = /"(?:answer|direct_response)"\s*:\s*"([^"]*)/g;
        let match;
        let extractedValues = [];
        
        while ((match = fieldRegex.exec(rawText)) !== null) {
            if (match[1]) {
                // Unescape common JSON characters
                const cleaned = match[1]
                    .replace(/\\n/g, '\n')
                    .replace(/\\"/g, '"')
                    .replace(/\\\\/g, '\\');
                extractedValues.push(cleaned);
            }
        }
        
        if (extractedValues.length > 0) {
            return extractedValues.join('\n\n');
        }
    }

    return rawText;
  }, [currentStream]);

  const activeStreamInterrupt = useMemo(() => 
    currentStream
      .find(e => e.event === 'interrupt')?.data?.interrupt_payload,
    [currentStream]
  );

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
            <DatasetItem 
                key={ds.id} 
                dataset={ds} 
                isSelected={selectedDatasets.includes(ds.id)} 
                onToggle={() => toggleDataset(ds.id)}
                onDownload={downloadFile}
            />
          ))
        )}
      </div>

      <ScrollArea className="flex-1 p-4">
        <div className="max-w-3xl mx-auto space-y-6">
          {historyLoading ? (
            <div className="flex justify-center py-20">
              <Loader2 className="h-6 w-6 animate-spin text-stone-300" />
            </div>
          ) : localMessages.length === 0 && !isStreaming && (
            <div className="text-center py-20 text-stone-500">
              <div className="bg-emerald-100 w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4">
                <Bot className="h-6 w-6 text-emerald-700" />
              </div>
              <h2 className="text-xl font-bold mb-2 text-stone-800 tracking-tight">Sugarcane Research Assistant</h2>
              <p className="max-w-xs mx-auto text-sm font-medium text-stone-500 leading-relaxed">Select biological datasets above to provide context for your queries.</p>
            </div>
          )}
          
          {localMessages.map((message) => (
            <ChatMessageItem 
              key={message.id} 
              message={message} 
              expandedSources={expandedSources}
              expandedThoughts={expandedThoughts}
              toggleSource={toggleSource}
              toggleThoughts={toggleThoughts}
              onDownload={downloadFile}
            />
          ))}

          {/* Active Stream Result */}
          {(isStreaming || (currentStream.length > 0 && !activeStreamAnswer)) && (
            (() => {
              // Avoid duplicate answer if it's already in history (by checking execution_id if available)
              const streamAnswerEvent = currentStream.find(e => e.event === 'answer');
              const streamExecutionId = streamAnswerEvent?.data?.execution_id;
              const isDuplicate = streamExecutionId && localMessages.some(m => m.execution_id === streamExecutionId);
              
              if (isDuplicate) return null;

              return (
                <div className="flex w-full gap-3 flex-row">
                  <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-md border shadow bg-emerald-100 text-emerald-800 border-emerald-200">
                    <Bot className="h-4 w-4" />
                  </div>
                  <div className="flex flex-col gap-2 max-w-[85%] w-full">
                    {activeStreamAnswer ? (
                      <div className="rounded-lg px-4 py-2 text-sm shadow-sm bg-white text-stone-800 border border-emerald-100">
                        <div className="prose prose-sm max-w-none dark:prose-invert prose-p:leading-relaxed prose-pre:bg-stone-900 prose-pre:text-stone-50">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {activeStreamAnswer}
                          </ReactMarkdown>
                        </div>
                      </div>
                    ) : (
                      <div className="rounded-lg px-4 py-3 bg-white text-stone-800 border border-emerald-100 shadow-sm flex items-center gap-3">
                        <Loader2 className="h-4 w-4 animate-spin text-emerald-600" />
                        <span className="text-xs font-bold text-stone-400 uppercase tracking-widest animate-pulse">Agent is reasoning...</span>
                      </div>
                    )}

                    {/* Active Thoughts */}
                    {activeStreamThoughts.length > 0 && (
                      <div className="border border-stone-200 rounded-md bg-stone-50 overflow-hidden">
                        <button 
                          onClick={() => setActiveThoughtsExpanded(!activeThoughtsExpanded)}
                          className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold text-stone-600 hover:bg-stone-100 transition-colors"
                        >
                          <div className="flex items-center gap-2">
                            <Brain className="h-3.5 w-3.5" />
                            Thought Process
                          </div>
                          {activeThoughtsExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                        </button>
                        {activeThoughtsExpanded && (
                          <div className="p-3 bg-white text-xs text-stone-600 border-t border-stone-200 space-y-2">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {activeStreamThoughts[activeStreamThoughts.length - 1]}
                            </ReactMarkdown>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Active Tools */}
                    {activeStreamTools.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {activeStreamTools.map((t, idx) => {
                          const s3Uris = extractS3Uris(t.data.output || "");
                          return (
                            <div key={idx} className="flex flex-col gap-1">
                                <div className="flex items-center gap-1.5 px-2 py-1 rounded border border-stone-200 bg-stone-50 text-[10px] font-bold text-stone-500 uppercase tracking-tight">
                                    <Wrench className="h-3 w-3" />
                                    {t.data.tool}: {t.event === 'tool_start' ? 'Running...' : 'Complete'}
                                </div>
                                {t.event === 'tool_end' && s3Uris.length > 0 && (
                                    <div className="flex flex-wrap gap-1">
                                        {s3Uris.map((uri, uIdx) => (
                                            <Button 
                                                key={uIdx}
                                                variant="outline" 
                                                size="sm" 
                                                className="h-6 px-2 text-[9px] gap-1 bg-white border-emerald-100 text-emerald-700 hover:bg-emerald-50"
                                                onClick={() => downloadFile({ s3Uri: uri })}
                                            >
                                                <FileDown className="h-3 w-3" />
                                                Download Result
                                            </Button>
                                        ))}
                                    </div>
                                )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              );
            })()
          )}

          {/* Interrupt UI */}
          {activeStreamInterrupt && activeStreamInterrupt.action_required === "APPROVE_PLAN" && (
              <div className="ml-11 border-2 border-emerald-200 rounded-lg p-4 bg-emerald-50/50 space-y-4 shadow-sm animate-in fade-in zoom-in duration-300">
                  <h3 className="text-sm font-bold text-emerald-800 flex items-center gap-2">
                      <Brain className="h-4 w-4" />
                      Proposed Research Plan
                  </h3>
                  <div className="space-y-2">
                    {activeStreamInterrupt.plan && activeStreamInterrupt.plan.length > 0 && activeStreamInterrupt.plan.map((step: { step_id?: string | number; description: string; expected_tool?: string }, idx: number) => (
                      <div key={idx} className="bg-white p-3 rounded border border-emerald-100 text-xs text-stone-700 shadow-sm flex items-start gap-3">
                        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-800 font-bold text-[10px]">
                          {step.step_id || idx + 1}
                        </span>
                        <div className="flex-1">
                          {step.description}
                          {step.expected_tool && (
                            <div className="mt-1 text-[10px] text-stone-400 font-bold uppercase tracking-tight flex items-center gap-1">
                              <Wrench className="h-2.5 w-2.5" /> Requires: {step.expected_tool}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="flex gap-2">
                      <Button size="sm" onClick={handleApprove} className="bg-emerald-700 hover:bg-emerald-800 text-white shadow-md">
                          <Check className="h-4 w-4 mr-1" /> Approve & Execute
                      </Button>
                      <Button 
                        size="sm" 
                        variant="outline" 
                        onClick={() => {
                          setPlanToModify(activeStreamInterrupt.plan);
                          setIsModifyingPlan(true);
                        }} 
                        className="bg-white border-stone-200 text-stone-600 hover:bg-stone-50 shadow-sm"
                      >
                          <X className="h-4 w-4 mr-1" /> Modify Plan
                      </Button>
                  </div>
              </div>
          )}

          <div ref={scrollRef} />
        </div>
      </ScrollArea>

      <div className="border-t bg-white p-4">
        <div className="max-w-3xl mx-auto relative">
          {isModifyingPlan && planToModify && (
            <div className="absolute bottom-full left-0 right-0 z-50 px-4 pb-2">
              <div className="max-w-3xl mx-auto">
                <PlanModificationForm 
                  initialPlan={planToModify}
                  onCancel={() => {
                    setIsModifyingPlan(false);
                    setPlanToModify(null);
                  }}
                  onSubmitEdits={(modifiedSteps) => {
                    handleModify({
                      action: "MODIFY",
                      modified_plan: modifiedSteps
                    });
                  }}
                  onSubmitFeedback={(feedback) => {
                    handleModify({
                      action: "MODIFY",
                      feedback: feedback
                    });
                  }}
                />
              </div>
            </div>
          )}
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
            disabled={!input.trim() || isStreaming}
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

function DatasetItem({ 
    dataset, 
    isSelected, 
    onToggle,
    onDownload
}: { 
    dataset: Dataset; 
    isSelected: boolean; 
    onToggle: () => void;
    onDownload: (params: { fileId?: string; s3Uri?: string }) => void;
}) {
    const { data: files, isLoading } = useDatasetFiles(dataset.id);
    const [isHovered, setIsHovered] = useState(false);

    return (
        <TooltipProvider>
            <Tooltip>
                <TooltipTrigger asChild>
                    <button
                        onClick={onToggle}
                        onMouseEnter={() => setIsHovered(true)}
                        onMouseLeave={() => setIsHovered(false)}
                        className={cn(
                            "group flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-semibold transition-all whitespace-nowrap relative",
                            isSelected
                                ? "bg-emerald-50 border-emerald-200 text-emerald-700 shadow-sm"
                                : "bg-stone-50 border-stone-200 text-stone-500 hover:bg-stone-100"
                        )}
                    >
                        <Database className="h-3 w-3" />
                        {dataset.name}
                        {isSelected && files && files.length > 0 && (
                             <div className="ml-1 flex items-center gap-1">
                                <span className="text-[10px] bg-emerald-200 text-emerald-800 px-1 rounded-sm">{files.length}</span>
                             </div>
                        )}
                    </button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="w-64 p-0 overflow-hidden border-stone-200 bg-white shadow-xl">
                    <div className="bg-stone-50 px-3 py-2 border-b border-stone-200">
                        <h4 className="text-[10px] font-bold text-stone-400 uppercase tracking-widest">Dataset Files</h4>
                    </div>
                    <div className="max-h-48 overflow-y-auto">
                        {isLoading ? (
                            <div className="p-4 flex justify-center">
                                <Loader2 className="h-4 w-4 animate-spin text-stone-300" />
                            </div>
                        ) : !files || files.length === 0 ? (
                            <div className="p-4 text-center text-xs text-stone-400 italic">No files available.</div>
                        ) : (
                            <div className="divide-y divide-stone-100">
                                {files.map((file) => (
                                    <div key={file.id} className="p-2 flex items-center justify-between hover:bg-stone-50 group/file">
                                        <div className="flex items-center gap-2 min-w-0">
                                            <FileCode className="h-3 w-3 text-stone-400 shrink-0" />
                                            <span className="text-[10px] text-stone-600 font-medium truncate">{file.file_name}</span>
                                        </div>
                                        <Button 
                                            size="xs" 
                                            variant="ghost" 
                                            className="h-6 text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 px-2 gap-1 opacity-0 group-hover/file:opacity-100 transition-opacity"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                onDownload({ fileId: file.id });
                                            }}
                                        >
                                            <Download className="h-3 w-3" />
                                            <span className="text-[10px] font-bold uppercase tracking-tight">Download</span>
                                        </Button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </TooltipContent>
            </Tooltip>
        </TooltipProvider>
    );
}
