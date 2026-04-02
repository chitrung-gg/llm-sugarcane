CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Entity Registry
CREATE TABLE cultivars (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,          
    species VARCHAR(255) DEFAULT 'Saccharum spp.',
    traits JSONB,                               
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE genes_markers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,          
    entity_type VARCHAR(50) NOT NULL,           
    associated_trait VARCHAR(255),             
    reference_sequence TEXT,                  
    ncbi_accession_id VARCHAR(100),             
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE knowledge_references (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    authors TEXT,
    publication_year INT,
    doi_or_url VARCHAR(255),
    abstract TEXT,
    vector_doc_id UUID,                       
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE paper_gene_mapping (
    paper_id UUID REFERENCES knowledge_references(id) ON DELETE CASCADE,
    gene_marker_id UUID REFERENCES genes_markers(id) ON DELETE CASCADE,
    extracted_context TEXT,                    
    PRIMARY KEY (paper_id, gene_marker_id)
);


CREATE TABLE user_genomes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100),                       
    genome_name VARCHAR(255) NOT NULL,          
    fasta_s3_uri VARCHAR(500),                  
    gff3_s3_uri VARCHAR(500),                  
    blast_db_path VARCHAR(500),                 
    status VARCHAR(50) DEFAULT 'RAW',          
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE genome_features (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    genome_id UUID REFERENCES user_genomes(id) ON DELETE CASCADE,
    seqid VARCHAR(100) NOT NULL,                
    source VARCHAR(100),                        
    feature_type VARCHAR(50) NOT NULL,          
    start_pos BIGINT NOT NULL,                  
    end_pos BIGINT NOT NULL,                   
    strand CHAR(1) CHECK (strand IN ('+', '-', '.')),
    attributes JSONB,                           -- LƯU Ý: Toàn bộ cột 9 của GFF3 (Key=Value;...) chuyển thành JSON
    inferred_marker_id UUID REFERENCES genes_markers(id) ON DELETE SET NULL, -- CẦU NỐI TRI THỨC (Kết quả do Tool BLAST map vào)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);







CREATE INDEX idx_genes_markers_name ON genes_markers(name);
CREATE INDEX idx_cultivars_name ON cultivars(name);


CREATE INDEX idx_genome_features_genome_id ON genome_features(genome_id);
CREATE INDEX idx_genome_features_seqid_pos ON genome_features(seqid, start_pos, end_pos);
CREATE INDEX idx_genome_features_type ON genome_features(feature_type);


CREATE INDEX idx_genome_features_attributes ON genome_features USING GIN (attributes);




CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';


CREATE TRIGGER update_cultivars_modtime BEFORE UPDATE ON cultivars FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_genes_markers_modtime BEFORE UPDATE ON genes_markers FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_user_genomes_modtime BEFORE UPDATE ON user_genomes FOR EACH ROW EXECUTE FUNCTION update_modified_column();