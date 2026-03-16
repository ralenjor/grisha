# Grisha BM25 Hybrid Search Module

C++ implementation of BM25 keyword search with Reciprocal Rank Fusion (RRF) for hybrid retrieval.

## Building

```bash
cd cpp
pip install pybind11 scikit-build-core
pip install -e .
```

## Usage

```python
import grisha_bm25

# Create and populate index
index = grisha_bm25.BM25Index(k1=1.2, b=0.75)
index.add_document("doc_0", "BMP-3 engagement range...")
index.add_document("doc_1", "Battalion tactical group...")
index.finalize()
index.save("./bm25_index")

# Load existing index
index = grisha_bm25.BM25Index()
index.load("./bm25_index")

# BM25-only search
results = index.search("BMP-3 engagement range", top_k=10)
for r in results:
    print(f"{r.doc_id}: {r.score:.3f}")

# Hybrid search with semantic results
semantic_results = [
    grisha_bm25.SemanticResult("doc_5", 0.45),
    grisha_bm25.SemanticResult("doc_2", 0.52),
]

hybrid_results = grisha_bm25.hybrid_search(
    index, "BMP-3 engagement range", semantic_results,
    top_k=10, rrf_k=60.0,
    semantic_weight=0.5, bm25_weight=0.5
)

for r in hybrid_results:
    print(f"{r.doc_id}: RRF={r.rrf_score:.4f} (sem_rank={r.semantic_rank}, bm25_rank={r.bm25_rank})")
```

## API

### BM25Index

- `BM25Index(k1=1.2, b=0.75)` - Create index with BM25 parameters
- `add_document(external_id, text)` - Add document
- `finalize()` - Finalize index (required before search)
- `search(query, top_k=10)` - Search and return BM25Results
- `save(path)` / `load(path)` - Persist/load index
- `document_count`, `vocabulary_size`, `average_doc_length` - Properties

### hybrid_search()

```python
hybrid_search(index, query, semantic_results,
              top_k=100, rrf_k=60.0,
              semantic_weight=0.5, bm25_weight=0.5)
```

Returns list of HybridResult with:
- `doc_id` - Document ID
- `rrf_score` - Combined RRF score
- `semantic_rank` / `bm25_rank` - Original ranks (0 if not present)
- `semantic_score` / `bm25_score` - Original scores
