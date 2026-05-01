"use client";

import { useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { v4 as uuidv4 } from "uuid";

export default function ChatRedirectPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params.id as string;

  useEffect(() => {
    const newThreadId = uuidv4();
    router.replace(`/projects/${projectId}/chat/${newThreadId}`);
  }, [projectId, router]);

  return (
    <div className="h-full flex items-center justify-center bg-stone-50/50">
      <div className="animate-pulse text-stone-400 font-medium">Initializing chat...</div>
    </div>
  );
}
