-- 1. Setup UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Create Parent Table
CREATE TABLE user_projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_user_projects_name ON user_projects (name);

-- 3. Create Child Table
CREATE TABLE user_datasets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL,
    dataset_name VARCHAR NOT NULL,
    file_id UUID NOT NULL,
    file_name VARCHAR NOT NULL,
    file_type VARCHAR NOT NULL,
    rustfs_uri VARCHAR,
    dataset_metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Key with Cascade Delete (enforcing the SQLModel cascade_delete=True)
    CONSTRAINT fk_user_projects
        FOREIGN KEY (project_id) 
        REFERENCES user_projects(id) 
        ON DELETE CASCADE
);

-- 4. Create Indexes for performance
CREATE INDEX ix_user_datasets_project_id ON user_datasets (project_id);
CREATE INDEX ix_user_datasets_dataset_name ON user_datasets (dataset_name);
CREATE INDEX ix_user_datasets_file_id ON user_datasets (file_id);


----------------------------------------------------------------
-- Create the restricted user account specifically for LangGraph
CREATE USER userdata WITH PASSWORD 'userdata';     -- Don't delete the ''

-- Create the schema and make the new user the absolute owner
CREATE SCHEMA userdata AUTHORIZATION userdata;

-- Security Check: Prevent anyone else (except superusers) from looking inside
REVOKE ALL ON SCHEMA userdata FROM PUBLIC;

-- Set the default schema for this specific user. 
-- Now, whenever userdata logs in, it defaults to this schema automatically!
ALTER ROLE userdata SET search_path TO userdata;

CREATE TABLE IF NOT EXISTS project_dataset_attachments (
    project_id UUID NOT NULL REFERENCES user_projects(id) ON DELETE CASCADE,
    dataset_id UUID NOT NULL REFERENCES user_datasets(id) ON DELETE CASCADE,
    attached_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, dataset_id)
);

-- Ensure user_datasets has the is_public flag indexed (it already exists in model but let's ensure DB index)
CREATE INDEX IF NOT EXISTS ix_user_datasets_is_public ON user_datasets (is_public);