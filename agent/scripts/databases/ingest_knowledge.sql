-- Create the restricted user account specifically for LangGraph
CREATE USER knowledge WITH PASSWORD 'knowledge';     -- Don't delete the ''

-- Create the schema and make the new user the absolute owner
CREATE SCHEMA knowledge AUTHORIZATION knowledge;

-- Security Check: Prevent anyone else (except superusers) from looking inside
REVOKE ALL ON SCHEMA knowledge FROM PUBLIC;

-- Set the default schema for this specific user. 
-- Now, whenever knowledge logs in, it defaults to this schema automatically!
ALTER ROLE knowledge SET search_path TO knowledge;