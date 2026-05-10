import asyncio
import os
import json
from pathlib import Path
from loguru import logger

import os

# 1. Import Synthesizer, Evolution, and EvolutionConfig
from deepeval.synthesizer import Synthesizer, Evolution 
from deepeval.synthesizer.config import EvolutionConfig
from app.configs.loggings.loggings import setup_logging
from app.configs.settings.settings import get_settings
from app.utils.document.docling_generic_splitter import DoclingGenericSplitter
from evaluation.llm_judge import GoogleGeminiJudge 

setup_logging()

async def generate_folder_data(input_folder: str, output_folder: str):
    settings = get_settings()
    folder_path = Path(input_folder)
    valid_extensions = {".pdf", ".docx", ".doc", ".md", ".html"}
    files_to_process = [f for f in folder_path.iterdir() if f.is_file() and f.suffix.lower() in valid_extensions]
    
    os.makedirs(output_folder, exist_ok=True)
    splitter = DoclingGenericSplitter()
    gemini_model = GoogleGeminiJudge(model_name=settings.GEMINI_SECONDARY_MODEL)

    for file_path in files_to_process:
        # 1. CHECKPOINT LOGIC: Define the output path first
        output_filename = f"{file_path.stem}_goldens.json"
        output_filepath = os.path.join(output_folder, output_filename)

        # 2. If the file already exists, we skip the entire heavy process!
        if os.path.exists(output_filepath):
            logger.info(f"⏭️ Skipping {file_path.name}: Already completed!")
            continue

        logger.info(f"📄 Processing: {file_path.name}")

        # --- Heavy processing starts here ---
        docs = splitter.process(str(file_path))
        chunks = [doc.page_content for doc in docs if len(doc.page_content.strip()) > 100]

        if not chunks:
            logger.warning(f"⚠️ Skipping {file_path.name}: No valid text found.")
            continue

        if len(chunks) > 5:
            step = len(chunks) / 5
            selected_chunks = [chunks[int(i * step)] for i in range(5)]
        else:
            selected_chunks = chunks

        contexts = [[chunk] for chunk in selected_chunks]

        evo_config = EvolutionConfig(
            num_evolutions=1,
            evolutions={
                Evolution.REASONING: 0.2,
                Evolution.MULTICONTEXT: 0.2,
                Evolution.CONCRETIZING: 0.2,
                Evolution.COMPARATIVE: 0.2,
                Evolution.IN_BREADTH: 0.2,
            }
        )

        synthesizer = Synthesizer(
            model=gemini_model, 
            evolution_config=evo_config
        )

        logger.info(f"🧠 Generating {len(selected_chunks)} goldens for {file_path.name}...")
        
        try:
            synthesizer.generate_goldens_from_contexts(
                contexts=contexts,
                max_goldens_per_context=1
            )
        except Exception as e:
            # 🌟 Catch API errors so one bad file doesn't crash the whole folder run
            logger.error(f"❌ Failed to generate goldens for {file_path.name}: {e}")
            continue

        # Save to the JSON File
        golden_dicts = [golden.model_dump() for golden in synthesizer.synthetic_goldens]
        
        with open(output_filepath, "w", encoding="utf-8") as f:
            json.dump(golden_dicts, f, indent=4, ensure_ascii=False)
            
        logger.info(f"✅ Saved Goldens to {output_filepath}\n")

if __name__ == "__main__":
    # Sit at agent/ for testing
    INPUT_DOCS_FOLDER = "../knowledge/test"
    OUTPUT_JSON_FOLDER = "./evaluation/synthetic_test_data"
    
    asyncio.run(generate_folder_data(INPUT_DOCS_FOLDER, OUTPUT_JSON_FOLDER))