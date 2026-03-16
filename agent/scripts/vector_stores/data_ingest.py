from concurrent.futures import ThreadPoolExecutor, as_completed
import gc
import sys
from pathlib import Path
import time
import uuid

from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger
from transformers import AutoTokenizer



# Resolve path so that script can understand where app.core...
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

# Load env
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    logger.info("Cannot find .env, please recheck file location")

from app.utils.document.document_splitter_registry import DocumentSplitterRegistry
from app.core.embeddings.gemini_embeddings_model import GeminiEmbeddingModel
from app.core.vector_store.vector_store import VectorStore 
from app.utils.document_processor import DocumentProcessor

MAX_WORKERS = 1

def sanitize_metadata(metadata: dict) -> dict:
    """
        Cleans metadata to prevent Qdrant Rust backend crashes.
        1. Removes any existing 'id' fields that confuse Qdrant.
        2. Converts massively large Python integers into strings.
        3. Drops complex nested objects (lists/dicts).
    """
    clean = {}
    for key, value in metadata.items():
        if key in ["id", "_id"]:
            continue
            
        # If it's an integer larger than a 64-bit signed integer max, cast to string
        if isinstance(value, int):
            if value > 9223372036854775800 or value < -9223372036854775800:
                clean[key] = str(value)
            else:
                clean[key] = value
        elif isinstance(value, (str, float, bool)):
            clean[key] = value
            
    return clean

def process_single_file(file_path, processor, fallback_splitter, vector_store):
    try:
        raw_chunks = processor.process_and_get_chunks(str(file_path))
        safe_chunks = fallback_splitter.split_documents(raw_chunks)
        
        safe_ids = []
        for chunk in safe_chunks:
            chunk.metadata = sanitize_metadata(chunk.metadata)
            safe_ids.append(str(uuid.uuid4()))

        chunks_inserted = 0
        if safe_chunks:
            # Micro batching to overcome Gemini Limits
            BATCH_SIZE = 16  # How many chunks to send at once
            SLEEP_TIME = 10  # Seconds to pause between batches

            for i in range(0, len(safe_chunks), BATCH_SIZE):
                batch_chunks = safe_chunks[i : i + BATCH_SIZE]
                batch_ids = safe_ids[i : i + BATCH_SIZE]
                
                logger.info(f"  -> Sending chunks {i} to {i + len(batch_chunks)} out of {len(safe_chunks)}...")
                
                # Send just this small batch to Qdrant/Gemini
                inserted_ids = vector_store.add_documents(documents=batch_chunks, ids=batch_ids)
                chunks_inserted += len(inserted_ids) if inserted_ids else 0
                
                # If there are more chunks left, sleep to cool down the API quota
                if i + BATCH_SIZE < len(safe_chunks):
                    logger.info(f"  -> ⏳ Sleeping {SLEEP_TIME}s to respect Gemini Free Tier limits...")
                    time.sleep(SLEEP_TIME)
            # ==========================================

        # Explicitly delete massive variables from memory
        del raw_chunks
        del safe_chunks
        del safe_ids
        
        # Force Python to hand the memory back to the OS immediately
        gc.collect() 

        return chunks_inserted
    except Exception as e:
        logger.info(f"❌ Fail on {file_path.name}: {str(e)}")
        return -1 # Indicate failure
    

def ingest_folder(folder_path: str):
    target_dir = Path(folder_path)
    
    if not target_dir.exists() or not target_dir.is_dir():
        logger.info(f"Folder '{folder_path}' doesn't exist!")
        return
    
    logger.info("Registering file type to process.")
    # DocumentSplitterRegistry.register(".pdf", PDFDocumentSplitter(chunk_size=6000, chunk_overlap=300))
    # DocumentSplitterRegistry.register(".md", MarkdownDocumentSplitter())

    logger.info(f"Scanning folder: {target_dir.absolute()}")

    logger.info("Initializing Qdrant (Hybrid Search) and Gemini Embeddings...")
    
    gemini_embedding = GeminiEmbeddingModel()
    # local_embedding = HuggingFaceEmbeddings(
    #     model_name="sentence-transformers/all-MiniLM-L6-v2"
    # )
    qdrant_config = VectorStore(
        collection_name="sugarcane_docs", 
        dense_embedding=gemini_embedding
        # dense_embedding=local_embedding
    )
    
    # Get object QdrantVectorStore from Langchain
    qdrant_hybrid_store = qdrant_config.get_vector_store()
    
    # Initialize Service Processor
    processor = DocumentProcessor(vector_store=qdrant_hybrid_store)

    tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
    fallback_splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
        tokenizer,
        chunk_size=500,
        chunk_overlap=50
    )

    # Find files to embed
    # Use 'rglob' to find both files in sub-directories (use 'glob' if only need in folder directly)
    pdf_files = list(target_dir.rglob("*.pdf"))
    md_files = list(target_dir.rglob("*.md"))
    html_files = list(target_dir.rglob("*.html"))
    
    # Append all files
    all_files = pdf_files + md_files + html_files
    logger.info(f"Found {len(pdf_files)} PDF(s) and {len(md_files)} Markdown(s) and {len(html_files)} HTML(s). \n")
    
    if not all_files:
        logger.info("Cannot find any files appropriate for tools.")
        return
    
    # Filter out already processed files
    ledger_path = Path(__file__).resolve().parent / ".processed_files.txt"
    processed_files = set()
    
    if ledger_path.exists():
        with open(ledger_path, "r") as f:
            processed_files = set(line.strip() for line in f)

    # Filter out files we've already done
    files_to_process = [f for f in all_files if f.name not in processed_files]

    if not files_to_process:
        logger.info("✅ All files are already in the vector store! Nothing new to ingest.")
        return

    skipped_count = len(all_files) - len(files_to_process)
    if skipped_count > 0:
        logger.info(f"⏭️ Skipped {skipped_count} files that were already ingested.")
        
    logger.info(f"🚀 Found {len(files_to_process)} NEW files to ingest. \n")

    # Start processing
    total_chunks = 0
    success_count = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all jobs to the thread pool
        future_to_file = {
            executor.submit(process_single_file, fp, processor, fallback_splitter, qdrant_hybrid_store): fp 
            for fp in files_to_process
        }

        # Process results as they finish
        for future in as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                chunks_inserted = future.result()
                if chunks_inserted >= 0:
                    success_count += 1
                    total_chunks += chunks_inserted
                    logger.info(f"✅ [{success_count}/{len(files_to_process)}] Finished {file_path.name}")
                    
                    with open(ledger_path, "a") as f:
                        f.write(f"{file_path.name}\n")

                    # Force the script to sleep for 60 seconds to respect the rate limit
                    
            except Exception as exc:
                logger.info(f"❌ {file_path.name} generated an exception: {exc}")

    logger.info("\n" + "="*50)
    logger.info(f"Processing done! Success: {success_count}/{len(files_to_process)} files. Total Chunks: {total_chunks}")
    logger.info("="*50)

    
if __name__ == "__main__":
    DATA_FOLDER = str(project_root / "data")
    
    ingest_folder(DATA_FOLDER)