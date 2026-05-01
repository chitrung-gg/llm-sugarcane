CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS public.knowledge_entities
(
    global_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name character varying NOT NULL,               -- Removed UNIQUE here
    entity_type character varying NOT NULL,       -- Enum: 'Gene', 'Trait', 'Disease', 'Tissue'
    reference_sequence text,                      
    owner_id UUID DEFAULT '00000000-0000-0000-0000-000000000000', -- Added
    is_public BOOLEAN DEFAULT FALSE,                               -- Added
    knowledge_entities_metadata JSONB,            
    created_at timestamp with time zone DEFAULT now(),
    
    -- Added the composite constraint
    CONSTRAINT unique_name_per_owner UNIQUE (name, owner_id)
);

CREATE TABLE IF NOT EXISTS public.knowledge_references
(
    global_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title text NOT NULL,
    doi_or_url character varying,
    publication_year integer,
    created_at timestamp with time zone DEFAULT now()
);

ALTER TABLE public.genomes 
    ADD COLUMN IF NOT EXISTS global_id UUID UNIQUE DEFAULT uuid_generate_v4(),
    ADD COLUMN IF NOT EXISTS genome_metadata JSONB;

ALTER TABLE public.genes 
    ADD COLUMN IF NOT EXISTS global_id UUID UNIQUE DEFAULT uuid_generate_v4(),
    ADD COLUMN IF NOT EXISTS gene_metadata JSONB,  -- Replaces attributes
    ADD COLUMN IF NOT EXISTS knowledge_entity_id UUID; 

CREATE INDEX idx_genome_metadata ON public.genomes USING GIN (genome_metadata);
CREATE INDEX idx_gene_metadata ON public.genes USING GIN (gene_metadata);

CREATE TABLE IF NOT EXISTS public.file_ingestion_status
(
    task_id text PRIMARY KEY,
    filename text NOT NULL,
    status text NOT NULL,           -- 'queued', 'processing', 'completed', 'failed'
    source_type text,
    vector_store text,
    chunks_total integer DEFAULT 0,
    chunks_processed integer DEFAULT 0,
    error_message text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_file_ingestion_filename ON public.file_ingestion_status(filename);
CREATE INDEX IF NOT EXISTS idx_file_ingestion_created_at ON public.file_ingestion_status(created_at DESC);