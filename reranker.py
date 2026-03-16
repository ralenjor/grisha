"""
Grisha Reranker Module
Reranks ChromaDB retrieval results based on multiple signals for improved relevance.
"""

from typing import List, Dict, Tuple, Any
from grisha_logging import get_logger

logger = get_logger("rerank")


class GrishaReranker:
    """
    Reranks retrieved chunks based on semantic similarity, metadata, and context.
    """
    
    def __init__(self):
        # Document type priorities
        self.doc_priority = {
            "doctrine_primary": 4,      # Field manuals, regulations
            "operational_level": 3,     # Campaign/operational art
            "tactical_level": 3,        # Battalion/company tactics
            "technical_specs": 2,       # Equipment specifications
            "general_reference": 1      # Wikipedia, general sources
        }
        
        # Source type priorities
        self.source_priority = {
            "field_manual": 3,
            "academic_paper": 2,
            "wikipedia": 1
        }
        
        # Scoring weights
        self.weights = {
            "semantic": 3.0,      # ChromaDB distance score
            "doc_type": 1.5,      # Document classification
            "source_type": 1.0,   # Source authority
            "nation": 2.0,        # Nation tag relevance
            "length": 0.5         # Content substantiveness
        }
    
    def rerank(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        distances: List[float],
        is_opfor: bool = False,
        return_top: int = 3,
        max_per_source: int = 2,
        relevance_threshold: float = 2.0,
        use_hybrid_scores: bool = True
    ) -> List[Tuple[str, Dict[str, Any], float]]:
        """
        Rerank retrieved chunks based on multiple signals.

        Args:
            documents: List of document texts from ChromaDB
            metadatas: List of metadata dicts from ChromaDB
            distances: List of semantic distances from ChromaDB
            is_opfor: True if analyzing US forces (OPFOR analysis)
            return_top: Number of top chunks to return
            max_per_source: Maximum chunks from same source (diversity control)
            relevance_threshold: Distance threshold for filtering
            use_hybrid_scores: Use hybrid RRF scores from metadata if available

        Returns:
            List of (doc, meta, score) tuples, sorted by score descending
        """
        
        scored_chunks = []
        source_counts = {}
        
        for doc, meta, dist in zip(documents, metadatas, distances):
            # Skip if beyond relevance threshold
            if dist > relevance_threshold:
                continue
            
            nation = meta.get('nation', 'Unknown')
            doc_type = meta.get('doc_type', 'general_reference')
            source_type = meta.get('source_type', 'wikipedia')
            title = meta.get('title', 'Unknown')
            
            # Skip US doctrine for Russian-only queries
            if not is_opfor and nation == "US":
                continue
            
            # Enforce diversity: limit chunks per source
            source_key = f"{nation}-{title}"
            current_count = source_counts.get(source_key, 0)
            if current_count >= max_per_source:
                continue
            
            # Calculate individual scores
            # Use hybrid score if available, otherwise use semantic distance
            hybrid_score = meta.get('hybrid_score') if use_hybrid_scores else None
            if hybrid_score is not None:
                # Hybrid score already incorporates semantic + BM25 via RRF
                # Scale it to match our scoring range (RRF scores are typically 0.01-0.03)
                semantic_score = hybrid_score * 100  # Scale up for comparable weighting
            else:
                semantic_score = self._calculate_semantic_score(dist)

            type_score = self._calculate_type_score(doc_type)
            source_score = self._calculate_source_score(source_type)
            nation_score = self._calculate_nation_score(nation, is_opfor)
            length_score = self._calculate_length_score(doc)

            # Composite score
            final_score = (
                semantic_score * self.weights["semantic"] +
                type_score * self.weights["doc_type"] +
                source_score * self.weights["source_type"] +
                nation_score * self.weights["nation"] +
                length_score * self.weights["length"]
            )
            
            scored_chunks.append({
                'doc': doc,
                'meta': meta,
                'score': final_score,
                'dist': dist,
                'source_key': source_key,
                'hybrid_score': hybrid_score,
                'breakdown': {
                    'semantic': semantic_score,
                    'type': type_score,
                    'source': source_score,
                    'nation': nation_score,
                    'length': length_score,
                    'hybrid': hybrid_score
                }
            })
            
            # Update source count
            source_counts[source_key] = current_count + 1
        
        # Sort by score descending
        scored_chunks.sort(key=lambda x: x['score'], reverse=True)

        # Debug output
        if scored_chunks:
            hybrid_mode = any(c.get('hybrid_score') is not None for c in scored_chunks[:return_top])
            logger.debug(f"Reranker mode: {'HYBRID (semantic + BM25)' if hybrid_mode else 'SEMANTIC ONLY'}")
            for i, chunk in enumerate(scored_chunks[:return_top], 1):
                hybrid_str = f" | HYBRID: {chunk['hybrid_score']:.4f}" if chunk.get('hybrid_score') else ""
                logger.debug(
                    f"{i}. SCORE: {chunk['score']:.2f} | DIST: {chunk['dist']:.3f}{hybrid_str} | "
                    f"{chunk['meta'].get('nation')} | {chunk['meta'].get('doc_type')} | "
                    f"{chunk['meta'].get('title', 'Unknown')[:40]}..."
                )

        # Return top N as (doc, meta, score) tuples
        return [(c['doc'], c['meta'], c['score']) for c in scored_chunks[:return_top]]
    
    def _calculate_semantic_score(self, distance: float) -> float:
        """Convert ChromaDB distance to score (lower distance = higher score)"""
        return 1.0 / (distance + 0.1)
    
    def _calculate_type_score(self, doc_type: str) -> float:
        """Score based on document type priority"""
        return float(self.doc_priority.get(doc_type, 0))
    
    def _calculate_source_score(self, source_type: str) -> float:
        """Score based on source authority"""
        return float(self.source_priority.get(source_type, 0))
    
    def _calculate_nation_score(self, nation: str, is_opfor: bool) -> float:
        """Score based on nation relevance to query type"""
        if is_opfor:
            # OPFOR analysis: Both nations valuable, prefer US doctrine slightly
            return 2.0 if nation == "US" else 1.5
        else:
            # Russian tactical: Only RU doctrine
            return 3.0 if nation == "RU" else 0.0
    
    def _calculate_length_score(self, doc: str) -> float:
        """Score based on content substantiveness (normalized 0-1)"""
        return min(len(doc) / 500.0, 1.0)
