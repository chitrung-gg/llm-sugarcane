"use client";

import { useEffect, Suspense } from "react";
import { useRouter, useParams, useSearchParams } from "next/navigation";
import { v4 as uuidv4 } from "uuid";
import { useProjectThreads } from "@/hooks/use-chat";

function ChatRedirectContent() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = params.id as string;
  const forceNew = searchParams.get("new") === "true";
  
  const { data: threads, isLoading } = useProjectThreads(projectId);

  useEffect(() => {
    if (isLoading) return;

    if (!forceNew && threads && threads.length > 0) {
      // Sort by updated_at descending if available, otherwise created_at
      const sortedThreads = [...threads].sort((a, b) => {
        const timeA = new Date(a.updated_at || a.created_at).getTime();
        const timeB = new Date(b.updated_at || b.created_at).getTime();
        return timeB - timeA;
      });
      
      const mostRecent = sortedThreads[0];
      router.replace(`/projects/${projectId}/chat/${mostRecent.id}`);
    } else {
      const newThreadId = uuidv4();
      router.replace(`/projects/${projectId}/chat/${newThreadId}`);
    }
  }, [projectId, router, threads, isLoading, forceNew]);

  return (
    <div className="h-full flex items-center justify-center bg-stone-50/50">
      <div className="animate-pulse text-stone-400 font-medium">
        {isLoading ? "Fetching conversations..." : "Initializing chat..."}
      </div>
    </div>
  );
}

export default function ChatRedirectPage() {
  return (
    <Suspense fallback={
      <div className="h-full flex items-center justify-center bg-stone-50/50">
        <div className="animate-pulse text-stone-400 font-medium">Loading session...</div>
      </div>
    }>
      <ChatRedirectContent />
    </Suspense>
  );
}
