import { useState, useCallback } from 'react';
import { useQueryClient } from "@tanstack/react-query";
import { streamPost } from "@/lib/api-client";

/**
 * SSE Event types matching backend StreamEventType
 */
export type StreamEvent = {
  event: 'thought' | 'tool_start' | 'tool_end' | 'answer' | 'interrupt' | 'error' | 'done';
  data: {
    content?: string;
    tool?: string;
    status?: string;
    interrupt_payload?: {
      action_required: string;
      plan?: { step_id?: string | number; description: string; expected_tool?: string }[];
    };
    [key: string]: unknown;
  };
};

/**
 * Hook to handle real-time streaming from the LangGraph agent.
 */
export function useChatStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStream, setCurrentStream] = useState<StreamEvent[]>([]);
  const queryClient = useQueryClient();

  const streamQuery = useCallback(async (data: { 
    query?: string; 
    threadId: string; 
    projectId?: string; 
    datasetIds?: string[];
    humanFeedback?: string | Record<string, any>;
  }) => {
    setIsStreaming(true);
    setCurrentStream([]);

    const payload: Record<string, unknown> = {
      thread_id: data.threadId,
      query: data.query,
      project_id: data.projectId,
      dataset_ids: data.datasetIds,
      human_feedback: data.humanFeedback
    };

    try {
      const body = await streamPost("/agent/stream", payload);
      if (!body) return;

      const reader = body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      // Standard SSE chunk processing
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        // Keep the last partial line in the buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            try {
              const eventData: StreamEvent = JSON.parse(trimmed.slice(6));
              setCurrentStream((prev) => [...prev, eventData]);
              
              if (eventData.event === 'done' || eventData.event === 'error') {
                // We'll set isStreaming(false) after invalidation below
              }
            } catch (e) {
              console.error("Error parsing SSE event:", e);
            }
          }
        }
      }
      
      // Refresh chat history once the stream is complete
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["chat-history", data.threadId] }),
        queryClient.invalidateQueries({ queryKey: ["project-threads", data.projectId] })
      ]);

      // Reset stream state AFTER data is refreshed to avoid UI "blink" or duplicates.
      // We keep the stream if it contains an interrupt so the UI can show the interrupt box.
      setCurrentStream((prev) => {
        const hasInterrupt = prev.some(e => e.event === 'interrupt');
        return hasInterrupt ? prev : [];
      });
      setIsStreaming(false);

    } catch (error) {
      console.error("Streaming error:", error);
      setIsStreaming(false);
    }
  }, [queryClient]);

  return { streamQuery, isStreaming, currentStream };
}
