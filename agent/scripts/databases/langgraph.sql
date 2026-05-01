-- Create the restricted user account specifically for LangGraph
CREATE USER langgraph WITH PASSWORD 'your_secure_password';     -- Don't delete the ''

-- Create the schema and make the new user the absolute owner
CREATE SCHEMA langgraph AUTHORIZATION langgraph;

-- Security Check: Prevent anyone else (except superusers) from looking inside
REVOKE ALL ON SCHEMA langgraph FROM PUBLIC;

-- Set the default schema for this specific user. 
-- Now, whenever langgraph logs in, it defaults to this schema automatically!
ALTER ROLE langgraph SET search_path TO langgraph;

-- Grant all permissions on all current tables in the schema
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA langgraph TO langgraph;

-- Grant all permissions on all current sequences (for auto-incrementing IDs)
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA langgraph TO langgraph;

-- Ensure future tables created in this schema are accessible
ALTER DEFAULT PRIVILEGES IN SCHEMA langgraph 
GRANT ALL PRIVILEGES ON TABLES TO langgraph;

-- Ensure future sequences created in this schema are accessible
ALTER DEFAULT PRIVILEGES IN SCHEMA langgraph 
GRANT ALL PRIVILEGES ON SEQUENCES TO langgraph;

-- 1. Chat Threads (The "Container")
CREATE TABLE langgraph.chat_threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,                        -- Links to your user system
    thread_id UUID NOT NULL UNIQUE,               -- The ID passed to LangGraph (checkpoint key)
    project_id UUID REFERENCES user_projects(id), -- Optional project context
    title TEXT,                                   -- Auto-generated or user-defined title
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Chat Messages (The "Content")
CREATE TABLE langgraph.chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES langgraph.chat_threads(thread_id) ON DELETE CASCADE,
    execution_id UUID,                            -- Links groups of messages to a single agent run
    role TEXT NOT NULL,                           -- 'user' or 'assistant'
    type TEXT NOT NULL DEFAULT 'answer',          -- 'answer', 'thought', or 'error'
    content TEXT NOT NULL,
    metadata JSONB,                               -- Store tool results, RAG sources, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_messages_thread_id ON langgraph.chat_messages(thread_id);
CREATE INDEX idx_threads_user_id ON langgraph.chat_threads(user_id);