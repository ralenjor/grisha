# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Grisha is a RAG (Retrieval-Augmented Generation) system that uses ChromaDB for vector storage and Ollama for LLM inference. It ingests military doctrine documents (PDFs, JSONL) and provides a query interface with a specialized "Russian military advisor" persona.

## Commands

### Running the System
```bash
# Start the interactive query interface (activates venv, starts Ollama, pre-loads model)
./grisha.sh

# Run just the query engine directly (assumes venv active and Ollama running)
python3 grisha_query.py
```

### Ingesting Documents
```bash
# Ingest a single file or directory
python3 grisha_ingestor.py <file_or_folder>

# Example: ingest all PDFs in brain/
python3 grisha_ingestor.py brain/
```

### Running the API
```bash
# Start FastAPI search endpoint on port 8000
python3 grisha_api.py
```

### Building the C++ BM25 Module
```bash
# Install build dependencies and compile
cd cpp
pip install pybind11 scikit-build-core
pip install -e .

# Verify installation
python -c "import grisha_bm25; print('OK')"
```

## Architecture

### Data Flow
1. **Ingestion** (`grisha_ingestor.py`): PDFs/JSONL → text extraction → sentence chunking → ChromaDB embeddings + BM25 index
2. **Query** (`grisha_query.py`): User question → hybrid search (ChromaDB + BM25) → RRF fusion → reranking → LLM context injection → response
3. **API** (`grisha_api.py`): FastAPI wrapper for ChromaDB search (returns raw context for external LLM integration)

### Key Components

- **ChromaDB** (`./grisha_db/`): Persistent vector store with `grisha_knowledge` collection
- **Embedding**: Uses `ONNXMiniLM_L6_V2` (local, no API)
- **LLM**: Ollama with `llama3.3:70b` model
- **Reranker** (`reranker.py`): Multi-signal scoring (semantic distance, doc type, source authority, nation tag)
- **BM25 Index** (`./bm25_index/`): C++ keyword search index with Porter stemming
- **Hybrid Search** (`cpp/`): C++ module combining semantic + BM25 via Reciprocal Rank Fusion (RRF)

### Document Classification
The ingestor classifies documents into tiers that affect retrieval priority:
- `doctrine_primary`: Field manuals, regulations (highest priority)
- `operational_level`: Campaign/planning documents
- `tactical_level`: Battalion/company tactics
- `technical_specs`: Equipment specifications
- `general_reference`: Wikipedia (lowest priority)

### Nation Segregation
Documents are tagged with `nation` metadata (`RU` or `US`). The query system:
- Filters to RU-only for standard queries
- Includes both for OPFOR analysis (detected by US equipment keywords: javelin, abrams, bradley, etc.)

### Hybrid Search (BM25 + Semantic)
The system supports hybrid retrieval combining:
- **Semantic search** (ChromaDB): Dense vector similarity for concept matching
- **BM25 keyword search** (C++ module): Sparse term matching for exact terms

Results are fused using Reciprocal Rank Fusion (RRF):
```
score(d) = semantic_weight * 1/(k + semantic_rank) + bm25_weight * 1/(k + bm25_rank)
```

The C++ module (`cpp/`) implements:
- Porter stemmer for word normalization
- Domain-aware stopwords (preserves military terms like "fire", "range", "unit")
- VByte-compressed inverted index
- Memory-mapped persistence for fast loading

### Configuration
`config.yaml` controls:
- `model_settings.max_tokens`: Chunk size for ingestion (900)
- `model_settings.overlap_tokens`: Chunk overlap (150)
- `database_settings.path`: ChromaDB location
- `bm25_settings.index_path`: BM25 index storage location
- `bm25_settings.k1`, `bm25_settings.b`: BM25 tuning parameters
- `hybrid_settings.enabled`: Enable/disable hybrid search
- `hybrid_settings.rrf_k`: RRF constant (60.0 default)
- `hybrid_settings.semantic_weight`, `hybrid_settings.bm25_weight`: Fusion weights

### Directory Structure
- `brain/`: Source documents organized by type (manuals, papers, strategy, us_doctrine, wiki)
- `data/`: Additional PDFs for ingestion
- `grisha_db/`: ChromaDB persistent storage
- `bm25_index/`: BM25 keyword index (created during ingestion)
- `cpp/`: C++ BM25 hybrid search module source code
- `Modelfile`: Ollama model configuration with system prompt
