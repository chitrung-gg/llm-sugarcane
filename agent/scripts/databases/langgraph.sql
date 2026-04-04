-- Create the restricted user account specifically for LangGraph
CREATE USER langgraph WITH PASSWORD 'your_secure_password';     -- Don't delete the ''

-- Create the schema and make the new user the absolute owner
CREATE SCHEMA langgraph AUTHORIZATION langgraph;

-- Security Check: Prevent anyone else (except superusers) from looking inside
REVOKE ALL ON SCHEMA langgraph FROM PUBLIC;

-- Set the default schema for this specific user. 
-- Now, whenever langgraph logs in, it defaults to this schema automatically!
ALTER ROLE langgraph SET search_path TO langgraph;