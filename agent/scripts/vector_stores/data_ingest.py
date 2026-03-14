import sys
from pathlib import Path

from dotenv import load_dotenv



# Resolve path so that script can understand where app.core...
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

# Load env
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    print("Cannot find .env, please recheck file location")

from app.utils.document.document_splitter_registry import DocumentSplitterRegistry
from app.core.embeddings.gemini_embeddings_model import GeminiEmbeddingModel
from app.core.vector_store.vector_store import VectorStore 
from app.utils.document_processor import DocumentProcessor
from app.utils.document.markdown_document_splitter import MarkdownDocumentSplitter

def ingest_folder(folder_path: str):
    target_dir = Path(folder_path)
    
    if not target_dir.exists() or not target_dir.is_dir():
        print(f"Folder '{folder_path}' doesn't exist!")
        return
    
    print("Registering file type to process.")
    # DocumentSplitterRegistry.register(".pdf", PDFDocumentSplitter(chunk_size=1500, chunk_overlap=300))
    # DocumentSplitterRegistry.register(".md", MarkdownDocumentSplitter())

    print(f"Scanning folder: {target_dir.absolute()}")

    print("Initializing Qdrant (Hybrid Search) and Gemini Embeddings...")
    
    gemini_model = GeminiEmbeddingModel()
    qdrant_config = VectorStore(
        collection_name="sugarcane_docs", 
        dense_embedding=gemini_model
    )
    
    # Get object QdrantVectorStore from Langchain
    qdrant_hybrid_store = qdrant_config.get_vector_store()
    
    # Initialize Service Processor
    processor = DocumentProcessor(vector_store=qdrant_hybrid_store)

    # Find files to embed
    # Use 'rglob' to find both files in sub-directories (use 'glob' if only need in folder directly)
    pdf_files = list(target_dir.rglob("*.pdf"))
    md_files = list(target_dir.rglob("*.md"))
    
    # Append all files
    all_files = pdf_files + md_files
    
    if not all_files:
        print("Cannot find any files appropriate for tools.")
        return

    print(f"Found {len(pdf_files)} PDF(s) and {len(md_files)} Markdown(s). \n")

    # Start processing
    total_chunks = 0
    success_count = 0

    for i, file_path in enumerate(all_files, 1):
        print(f"\n [{i}/{len(all_files)}] Currently processing: {file_path.name}")
        
        try:
            inserted_ids = processor.process_and_store(str(file_path))
            
            if inserted_ids:
                total_chunks += len(inserted_ids)
                success_count += 1
                
        except Exception as e:
            print(f"Fail when read file {file_path.name}: {str(e)}")
            continue

    
    print("\n" + "="*50)
    print("Processing done!")
    print(f"Succeed file processed: {success_count}/{len(all_files)}")
    print(f"Number of Chunks saved into Qdrant: {total_chunks}")
    print("="*50)

if __name__ == "__main__":
    DATA_FOLDER = str(project_root / "data")
    
    ingest_folder(DATA_FOLDER)