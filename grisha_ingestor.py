import sys
import os
import re
import json
import yaml
import nltk
import tiktoken
import chromadb
import pdfplumber
import pytesseract
import logging

from pathlib import Path
from pdf2image import convert_from_path
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
from nltk.tokenize import sent_tokenize
from grisha_logging import get_logger

logger = get_logger("ingest")

# BM25 hybrid search module (optional)
try:
    import grisha_bm25
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    logger.warning("grisha_bm25 module not found. BM25 indexing disabled.")
    logger.info("To enable: cd cpp && pip install -e .")

# -------------------------
# NLTK Setup
# -------------------------
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt")

# -------------------------
# Load Config
# -------------------------
def load_config(config_path="config.yaml"):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

config = load_config()
MODEL_NAME = config["model_settings"]["model_name"]
MAX_TOKENS = config["model_settings"]["max_tokens"]
OVERLAP = config["model_settings"]["overlap_tokens"]

# -------------------------
# Tokenizer
# -------------------------
encoding = tiktoken.get_encoding("cl100k_base")

def token_count(text: str) -> int:
    return len(encoding.encode(text)) if encoding else len(text) // 4

# -------------------------
# Russian Military Relevance Filter
# -------------------------
RUS_MIL_KEYWORDS = [
    "Russian Armed Forces",
    "Russian military",
    "Soviet Army",
    "Red Army",
    "Russian Navy",
    "Russian Air Force",
    "VDV",
    "Spetsnaz",
    "General Staff",
    "Ministry of Defence (Russia)",
    "Chechnya",
    "Georgia (2008)",
    "Syria intervention",
    "Ukraine",
    "Battalion Tactical Group",
    "maskirovka",
    "operational art",
    "reflexive control"
]

def is_relevant(text):
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in RUS_MIL_KEYWORDS)

# -------------------------
# Classification
# -------------------------
def classify_document(title, text):
    t = (title + " " + text).lower()
    
    # Tier 1: Primary Doctrine (Manuals)
    if any(k in t for k in ["fm ", "field manual", "regulations", "statute"]):
        return "doctrine_primary"
    
    # Tier 2: Operational Level (Campaigns/Planning)
    if any(k in t for k in ["operational art", "corps", "army group", "front", "campaign"]):
        return "operational_level"
        
    # Tier 3: Tactical Level (Units/Small Arms)
    if any(k in t for k in ["platoon", "squad", "company", "battalion", "btg", "tactics"]):
        return "tactical_level"
        
    # Tier 4: Technical/Capabilities (Specs/Hardware)
    if any(k in t for k in ["specifications", "range", "armor", "caliber", "mm", "velocity"]):
        return "technical_specs"

    return "general_reference"

# -------------------------
# PDF Extraction
# -------------------------
def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted and extracted.strip():
                text += extracted + "\n"
            else:
                # OCR ONLY the specific empty page, not the whole book
                logger.debug(f"OCR needed for page {page.page_number} of {pdf_path}")
                page_image = page.to_image(resolution=300).original
                text += pytesseract.image_to_string(page_image) + "\n"
    return text.strip()

# -------------------------
# JSONL Streaming
# -------------------------
def stream_wikipedia_jsonl(jsonl_path, nation):
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                title = data.get("title", "Unknown Title")
                text = data.get("text", "").strip()

                if not text or not is_relevant(text):
                    continue

                yield {
                    "title": title,
                    "text": text,
                    "nation": nation,
                    "source_type": "wikipedia",
                    "doc_type": classify_document(title, text)
                }

            except json.JSONDecodeError:
                continue

# -------------------------
# Sentence Chunking
# -------------------------
def split_by_sentence(text, max_tokens):
    sentences = sent_tokenize(text)
    chunks = []
    current = []
    current_tokens = 0

    for sent in sentences:
        sent_tokens = token_count(sent)

        if current_tokens + sent_tokens <= max_tokens:
            current.append(sent)
            current_tokens += sent_tokens
        else:
            chunks.append(" ".join(current))
            current = [sent]
            current_tokens = sent_tokens

    if current:
        chunks.append(" ".join(current))

    return chunks

# -------------------------
# Entity Extraction
# -------------------------
ENTITY_RE = re.compile(r'\b([A-Z][A-Za-z0-9\-]+(?:\s+[A-Z][A-Za-z0-9\-]+)+)\b')

def extract_entities(text):
    return list(set(ENTITY_RE.findall(text)))

def extract_section(text_chunk):
    """Detects Chapter, Section, or Paragraph headers."""
    if not text_chunk:
        return "General"
    
    # Looks for "Chapter 4", "Section 2", etc.
    match = re.search(r'(Chapter|Section|Para|Article)\s+([0-9A-Z\.]+)', text_chunk, re.IGNORECASE)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return "General"

# -------------------------
# Document Chunker
# -------------------------
def chunk_document(doc):
    title = doc["title"]
    text = doc["text"]
    source_type = doc["source_type"]
    doc_type = doc["doc_type"]
    nation = doc.get("nation", "Unknown")  # FIXED: Extract nation tag
 
    doc_wide_section = extract_section(text[:500])

    chunks = split_by_sentence(text, MAX_TOKENS)

    for i, chunk_text in enumerate(chunks):
     
        current_section = extract_section(chunk_text)
        if current_section == "General":
            current_section = doc_wide_section

        yield {
            "text": chunk_text,
            "metadata": {
                "title": title,
                "section": current_section, 
                "chunk_index": i,
                "source_type": source_type,
                "doc_type": doc_type,
                "category": doc_type,
                "nation": nation  # FIXED: Include nation in metadata
            }
        }

# -------------------------
# File Processor
# -------------------------
def process_file(path):
    # Detect nation based on subfolder
    nation = "US" if "grisha/brain/us_doctrine" in str(path) else "RU"
    
    if path.suffix == ".jsonl":
        yield from stream_wikipedia_jsonl(path, nation)
    elif path.suffix == ".pdf":
        extracted_text = extract_text_from_pdf(str(path))
        yield {
            "title": path.name,
            "text": extracted_text,
            "nation": nation,
            "source_type": "field_manual" if "fm" in path.name.lower() else "academic_paper",
            "doc_type": classify_document(path.name, extracted_text)
        }

# -------------------------
# BM25 Index Management
# -------------------------
def create_bm25_index(config):
    """Create a new BM25 index with config parameters."""
    if not BM25_AVAILABLE:
        return None

    bm25_settings = config.get("bm25_settings", {})
    k1 = bm25_settings.get("k1", 1.2)
    b = bm25_settings.get("b", 0.75)

    return grisha_bm25.BM25Index(k1=k1, b=b)

def save_bm25_index(index, config):
    """Save BM25 index to disk."""
    if index is None:
        return

    bm25_settings = config.get("bm25_settings", {})
    index_path = bm25_settings.get("index_path", "./bm25_index")

    index.finalize()
    index.save(index_path)
    logger.info(f"BM25 index saved: {index.document_count} docs, {index.vocabulary_size} terms, avg length {index.average_doc_length:.1f}")

# -------------------------
# Main
# -------------------------
def main():

    if len(sys.argv) < 2:
        print("Usage: python grisha_ingestor.py <file_or_folder>")
        return

    input_path = Path(sys.argv[1])

    client = chromadb.PersistentClient(path="./grisha_db")
    embedding_function = ONNXMiniLM_L6_V2()

    collection = client.get_or_create_collection(
        name="grisha_knowledge",
        embedding_function=embedding_function
    )

    # Initialize BM25 index if available
    bm25_index = create_bm25_index(config)

    batch_docs = []
    batch_metadatas = []
    batch_ids = []
    batch_size = 100
    total_count = 0

    if input_path.is_dir():
        files = list(input_path.rglob("*"))
    else:
        files = [input_path]

    for file_path in files:

        if not file_path.suffix.lower() in [".jsonl", ".pdf"]:
            continue

        logger.info(f"Processing: {file_path}")

        for doc in process_file(file_path):
            for chunk in chunk_document(doc):

                chunk_text = chunk["text"]
                metadata = chunk["metadata"]

                entities = extract_entities(chunk_text)
                metadata["entities"] = ", ".join(entities)

                doc_id = f"id_{total_count}"

                batch_docs.append(chunk_text)
                batch_metadatas.append(metadata)
                batch_ids.append(doc_id)

                # Add to BM25 index
                if bm25_index is not None:
                    bm25_index.add_document(doc_id, chunk_text)

                total_count += 1

                if len(batch_docs) >= batch_size:
                    collection.add(
                        documents=batch_docs,
                        metadatas=batch_metadatas,
                        ids=batch_ids
                    )
                    batch_docs = []
                    batch_metadatas = []
                    batch_ids = []
                    logger.info(f"Uploaded {total_count} chunks")

    if batch_docs:
        collection.add(
            documents=batch_docs,
            metadatas=batch_metadatas,
            ids=batch_ids
        )

    logger.info(f"Success. Total chunks stored: {total_count}")

    # Save BM25 index
    save_bm25_index(bm25_index, config)

if __name__ == "__main__":
    from grisha_logging import setup_logging
    setup_logging()
    main()
