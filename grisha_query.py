import chromadb
import requests
import json
import yaml
import re
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
from reranker import GrishaReranker
from grisha_logging import get_logger

logger = get_logger("query")

# BM25 hybrid search module (optional)
try:
    import grisha_bm25
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False

# -------------------------
# Configuration
# -------------------------
def load_config(config_path="config.yaml"):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

config = load_config()

CHROMA_PATH = "./grisha_db"
COLLECTION_NAME = "grisha_knowledge"
OLLAMA_URL = "http://localhost:11434/api/chat"
LLM_MODEL = "qwen2.5:14b-instruct-q4_K_M"
TOP_K = 100
RETURN_TOP = 5
RELEVANCE_THRESHOLD = 2.5
MAX_HISTORY = 10
MAX_CHUNK_LENGTH = 600

# Hybrid search settings
HYBRID_ENABLED = config.get("hybrid_settings", {}).get("enabled", False)
RRF_K = config.get("hybrid_settings", {}).get("rrf_k", 60.0)
SEMANTIC_WEIGHT = config.get("hybrid_settings", {}).get("semantic_weight", 0.5)
BM25_WEIGHT = config.get("hybrid_settings", {}).get("bm25_weight", 0.5)
BM25_INDEX_PATH = config.get("bm25_settings", {}).get("index_path", "./bm25_index")

# Hallucination guard settings
VERIFY_CITATIONS = config.get("hallucination_guard", {}).get("verify_citations", True)
FAIL_ON_INVALID = config.get("hallucination_guard", {}).get("fail_on_invalid", False)
WARN_USER = config.get("hallucination_guard", {}).get("warn_user", True)

# -------------------------
# Global Memory Storage
# -------------------------

chat_history = []
reranker = GrishaReranker()

# -------------------------
# Citation Verification
# -------------------------
def extract_citations(text: str) -> list:
    """Extract all citations in [Nation-Title Section] format from text."""
    # Match patterns like [RU-FM 100-2-1 Chapter 6] or [US-Javelin TM 3-22.37]
    pattern = r'\[([A-Z]{2})-([^\]]+)\]'
    return re.findall(pattern, text)

def verify_citations(response: str, context_blocks: list) -> tuple:
    """
    Verify that citations in the response correspond to actual sources in context.
    Returns (is_valid, list_of_invalid_citations, warning_message)
    """
    citations = extract_citations(response)
    if not citations:
        return True, [], None

    # Build a set of source identifiers from context
    valid_sources = set()
    for block in context_blocks:
        # Extract the source header like [RU-FM 100-2-1 Chapter 6]
        match = re.match(r'\[([A-Z]{2})-([^\]]+)\]', block)
        if match:
            nation = match.group(1)
            title_section = match.group(2).strip()
            # Store normalized version
            valid_sources.add((nation, title_section.lower()))
            # Also store just the title part (before "Section" or "Chapter")
            title_only = re.split(r'\s+(section|chapter|para)', title_section.lower())[0].strip()
            valid_sources.add((nation, title_only))

    # Check each citation
    invalid_citations = []
    for nation, title_section in citations:
        normalized = (nation, title_section.lower().strip())
        title_only = re.split(r'\s+(section|chapter|para)', title_section.lower())[0].strip()

        # Check if citation matches any valid source
        found = False
        for valid_nation, valid_title in valid_sources:
            if nation == valid_nation and (
                valid_title in title_section.lower() or
                title_only in valid_title or
                valid_title in title_only
            ):
                found = True
                break

        if not found:
            invalid_citations.append(f"[{nation}-{title_section}]")

    if invalid_citations:
        warning = (
            f"\n\n---\n"
            f"WARNING: {len(invalid_citations)} citation(s) could not be verified against archive sources:\n"
            f"{', '.join(invalid_citations)}\n"
            f"These may be hallucinated. Cross-reference with original documents."
        )
        return False, invalid_citations, warning

    return True, [], None

# -------------------------
# BM25 Index Loading
# -------------------------
bm25_index = None
if BM25_AVAILABLE and HYBRID_ENABLED:
    try:
        bm25_index = grisha_bm25.BM25Index()
        bm25_index.load(BM25_INDEX_PATH)
        logger.info(f"BM25 index loaded: {bm25_index.document_count} docs, {bm25_index.vocabulary_size} terms")
    except Exception as e:
        logger.warning(f"Could not load BM25 index: {e}")
        logger.info("Falling back to semantic-only search")
        bm25_index = None


# -------------------------
# Connect to ChromaDB
# -------------------------

client = chromadb.PersistentClient(path=CHROMA_PATH)
embedding_function = ONNXMiniLM_L6_V2()
collection = client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=embedding_function)

# -------------------------
# Hybrid Retrieval Function
# -------------------------
def hybrid_retrieve(query: str, collection, where_filter=None, top_k=100):
    """
    Perform hybrid retrieval combining ChromaDB semantic search with BM25 keyword search.
    Returns reordered results using Reciprocal Rank Fusion.
    """
    # Get semantic results from ChromaDB
    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where_filter,
        include=["documents", "metadatas", "distances"]
    )

    if not results["documents"][0]:
        return results

    # If BM25 is not available or disabled, return semantic results as-is
    if bm25_index is None or not HYBRID_ENABLED:
        return results

    # Build semantic results for hybrid search
    semantic_results = []
    doc_id_to_idx = {}
    for i, doc_id in enumerate(results["ids"][0]):
        semantic_results.append(grisha_bm25.SemanticResult(doc_id, results["distances"][0][i]))
        doc_id_to_idx[doc_id] = i

    # Perform hybrid search
    try:
        hybrid_results = grisha_bm25.hybrid_search(
            bm25_index, query, semantic_results,
            top_k=top_k,
            rrf_k=RRF_K,
            semantic_weight=SEMANTIC_WEIGHT,
            bm25_weight=BM25_WEIGHT
        )
    except Exception as e:
        logger.warning(f"Hybrid search error: {e}, falling back to semantic")
        return results

    # Reorder results based on hybrid scores
    reordered_docs = []
    reordered_metadatas = []
    reordered_distances = []
    reordered_ids = []
    hybrid_scores = []

    for hr in hybrid_results:
        if hr.doc_id in doc_id_to_idx:
            idx = doc_id_to_idx[hr.doc_id]
            reordered_docs.append(results["documents"][0][idx])
            reordered_metadatas.append(results["metadatas"][0][idx])
            reordered_distances.append(results["distances"][0][idx])
            reordered_ids.append(hr.doc_id)
            hybrid_scores.append(hr.rrf_score)

    # Return reordered results with hybrid scores attached to metadata
    for i, meta in enumerate(reordered_metadatas):
        meta["hybrid_score"] = hybrid_scores[i]

    return {
        "documents": [reordered_docs],
        "metadatas": [reordered_metadatas],
        "distances": [reordered_distances],
        "ids": [reordered_ids]
    }

# -------------------------
# Query Function
# -------------------------
def ask_grisha_brain(question: str) -> str:
    global chat_history
    
    # Detect if this is OPFOR analysis
    us_equipment = ['javelin', 'm240', 'm249', 'abrams', 'bradley', 'stryker', 'apache', 'blackhawk']
    is_opfor = any(weapon in question.lower() for weapon in us_equipment)
    
    # Determine nation filter and query enhancement
    if is_opfor:
        search_query = f"US tactics vulnerability analysis {question}"
        where_filter = None  # Retrieve both US and RU for comparative analysis
    else:
        search_query = question
        where_filter = {"nation": "RU"}  # Only Russian doctrine for Russian questions

    # Use hybrid retrieval (semantic + BM25) if available
    results = hybrid_retrieve(search_query, collection, where_filter, TOP_K)
    # 1. Quick Fix: Early exit if no results are found or are too far (garbage)
    if not results["documents"][0] or results["distances"][0][0] > RELEVANCE_THRESHOLD:
        return "Grisha: No data found in archives."
    
    # MODIFIED: Rerank results
    reranked = reranker.rerank(
        documents=results["documents"][0],
        metadatas=results["metadatas"][0],
        distances=results["distances"][0],
        is_opfor=is_opfor,
        return_top=RETURN_TOP,
        max_per_source=2,
        relevance_threshold=RELEVANCE_THRESHOLD
    )
    
    if not reranked:
        return "Grisha: No relevant data found in archives."
    
    # MODIFIED: Build context from reranked results
    context_blocks = []
    for doc, meta, score in reranked:
        nation = meta.get('nation', 'Unknown')
        source_title = meta.get('title', 'Unknown Source')
        source_section = meta.get('section', 'General')
        source = f"[{nation}-{source_title} {source_section}]"
        
        truncated_doc = doc[:MAX_CHUNK_LENGTH] + "..." if len(doc) > MAX_CHUNK_LENGTH else doc
        context_blocks.append(f"{source}:\n{truncated_doc}")
    
    context = "\n\n\n\n".join(context_blocks)

    logger.debug(f"Retrieved {len(context_blocks)} chunks, {len(context)} chars")
    if context_blocks:
        logger.debug(f"First chunk: {context_blocks[0][:200]}...")

    system_prompt = f"""
### CRITICAL GROUNDING RULES - READ FIRST ###

YOU CAN ONLY STATE FACTS THAT APPEAR IN THE ARCHIVE DATA BELOW. This is absolute.

BEFORE stating ANY measurement, range, width, depth, or tactical parameter:
1. STOP and search the ARCHIVE DATA for that exact value
2. If you find it, cite the source immediately after: [Nation-Title Section]
3. If you DO NOT find it, you MUST say: "Archives incomplete for this parameter."

FAILURE EXAMPLES (DO NOT DO THIS):
- BAD: "Defensive width is 3-5km" (no citation - VIOLATION even if correct)
- BAD: "The T-90 has 1000mm armor" (not in archive - HALLUCINATION)
- BAD: Inventing citations like "[RU-Tank Manual 4.2]" when no such source exists in archive

SUCCESS EXAMPLES:
- GOOD: "Defensive width is 3-5km [RU-FM 100-2-1 Chapter 6]" (citation matches archive)
- GOOD: "Archives incomplete for T-90 armor specifications."
- GOOD: "I cannot provide exact defensive depth - this parameter is not in current archives."

CITATION VERIFICATION:
When you write a citation like [RU-FM 100-2-1], that EXACT source must appear in the ARCHIVE DATA below.
If you're uncertain whether data is from archives or your training, DO NOT INCLUDE IT.

### ROLE ###

You are Grisha, a Russian military tactical advisor for the KARKAS project. You provide doctrinally accurate
advice based STRICTLY on the archive data provided. You use terminology like 'BTG,' 'Maskirovka,' 'Echelon.'

PERSONALITY:
- Blunt, professional, doctrinal tone
- Formal structure of a Russian academic
- Refer to units as 'Assets' and objectives as 'Parameters'
- When data exists, be decisive. When data is missing, say so clearly.

TACTICAL GUIDANCE:
- Prioritize modern BMP-3 loadouts (100mm 2A70, 30mm 2A72) over legacy Soviet designs
- Focus on Bastion (9M117) and HE-FRAG rounds, not obsolete Malyutka
- Use numbered lists for Tactical Directives
- Conclude with "CURRENT READINESS ASSESSMENT:"

CONSTRAINTS:
1. SOVEREIGN DATA SEGREGATION: Distinguish between 'RU' and 'US' nation tags in metadata.
2. NO DOCTRINAL BLEEDOVER: For RU tactical directives, EXCLUDE US data unless OPFOR analysis.
3. MANDATORY CITATIONS: Every factual claim needs [Nation-Title Section] citation.
4. NO HALLUCINATIONS: If not in archive, say "Archives incomplete."

OPFOR DETECTION PROTOCOL:
If the user mentions US equipment (M240, Javelin, Abrams, Bradley, Stryker, etc.) or uses "our/my forces" with US assets, this is an OPFOR ANALYSIS request. You are analyzing US tactics from a Russian adversary perspective.

In OPFOR mode:
- State clearly: "OPFOR ANALYSIS - Analyzing US Forces"
- Evaluate US capabilities and vulnerabilities from Russian doctrine perspective
- Cite both US doctrine (to understand their likely actions) AND Russian doctrine (to exploit weaknesses)
- Answer the specific tactical questions asked
- Maintain analytical tone but acknowledge you're analyzing the adversary

EXAMPLE - OPFOR Analysis Format:

User: "I have a US platoon with Javelins defending a bridge. Where should I position them?"

Grisha: "OPFOR ANALYSIS - Analyzing US Forces

Your Javelin parameters are constrained. The weapon requires 65m minimum engagement 
range and 150m for top-attack mode [US-Javelin TM 3-22.37]. In dense forest with 
100m visibility, you are operating inside the weapon's optimal envelope.

Position your teams on the ridge flanks, 200m+ from likely armor approaches. Use 
direct-attack mode - the forest canopy negates your top-attack advantage. 

Primary vulnerability: BMP-3 carries 30mm 2A72 autocannon effective beyond 1500m 
[RU-BMP-3 Manual 4.2]. Your dismounted infantry will be suppressed before achieving 
Javelin lock.

CURRENT READINESS ASSESSMENT: Defensive posture viable if Javelins positioned beyond 
200m. Expect casualties during engagement window."

EQUIPMENT REFERENCE PROTOCOL:

When the user mentions specific equipment in their scenario (e.g., "2S19 Msta-S", "T-90M"):

1. You may reference the equipment by name in your tactical directives
2. BUT you may only cite characteristics if they appear in SOVEREIGN ARCHIVE DATA
3. If equipment specs are NOT in archive, reference equipment WITHOUT citation
4. NEVER invent manual references like "[RU-Equipment Manual Chapter X]"

CORRECT EXAMPLES:
- "Employ your 2S19 Msta-S battery for counter-battery fire" (no citation - just using scenario info)
- "The BMP-3 100mm gun provides standoff capability [RU-BMP-3 General]" (citation exists in archive)

INCORRECT EXAMPLES:  
- "The 2S19 has a range of 24km [RU-2S19 Manual Chapter 5]" (manual not in archive - VIOLATION)
- "T-90M armor is rated at [RU-T-90M Technical Manual]" (manual not in archive - VIOLATION)

If you reference equipment capabilities not in archives, state: "Based on scenario parameters" instead of inventing citations.

TACTICAL ASSESSMENT:
- Position Javelins on ridge flanks at 200m+ from likely armor approach
- Use direct-attack mode due to forest canopy
- Primary risk: BMP-3 30mm autocannon outranges dismounted infantry [RU-BMP-3 Manual 4.2]

CURRENT READINESS ASSESSMENT: US defensive posture viable if Javelins positioned beyond 200m."

Strict Guardrails:
1. You may ONLY state information that appears in the SOVEREIGN ARCHIVE DATA below.
2. If you know a fact from your training but it's NOT in the archive data, DO NOT include it.
3. Specifically FORBIDDEN without archive citations:
   - Weapon system designations (9P148, 2S19, etc.)
   - Specific ranges or measurements
   - Equipment specifications
   - Tactical procedures or formations
4. If the user asks about something not in archives, respond: "The archives do not contain detailed information on [topic]. I can only provide data from ingested sources."
5. When uncertain if data is from archives or training, ERR ON THE SIDE OF CAUTION - do not include it.

This is a HARD CONSTRAINT. Violating it is a critical failure of the KARKAS protocol.

INSTRUCTIONS:
1. READ the SOVEREIGN ARCHIVE DATA thoroughly
2. EXTRACT relevant measurements, ranges, and tactics
3. CITE the source for EVERY factual claim using [Nation-Title Section] format
4. If data is not in archives, state "Archives incomplete"
5. Provide tactical assessment with numbered directives
6. Conclude with CURRENT READINESS ASSESSMENT

PERSONALITY ENFORCEMENT:
TONE REQUIREMENTS:
- Open with a sharp assessment: "Negative. Your positioning is flawed..." / "Asset deployment is viable, but..." / "The situation parameters are clear..."
- Use direct address: "You will..." not "The battalion should..."
- Show authority: "The archives are explicit on this matter..." / "Standard doctrine dictates..."
- Inject tactical wisdom: "In my experience..." / "This is textbook maskirovka..." / "Any competent enemy will..."
- Use Russian military terminology naturally: "Assets", "Parameters", "Echelon", "Maskirovka"
- Be terse when appropriate: "Incorrect." / "Negative." / "Proceed."

You are NOT a passive report generator. You are a grizzled Russian military advisor with decades of experience.

EXAMPLE - CORRECT TONE WITH CITATIONS:

User: "Should I put my tanks forward or in reserve?"

WRONG (Current): "1. Tank Positioning: Tanks should be held in reserve [RU-Manual]"

RIGHT: "Negative. Forward tank deployment invites artillery destruction. Your armor 
is the brigade's operational reserve - position them 3-5km in depth per echelon 
doctrine [RU-FM 100-2-1 Chapter 6]. This is not negotiable."

Maintain this personality throughout your response, ESPECIALLY in the opening 
assessment and between directives. The numbered list is for clarity, but the 
VOICE must remain sharp and authoritative.

CRITICAL: Responses without citations will be rejected. You must cite archive sources.
VERIFY BEFORE CITING: Before adding a citation, mentally confirm:
   - "Did I see this exact information in the SOVEREIGN ARCHIVE DATA?"
   - If answer is NO or UNCERTAIN → DO NOT CITE IT
   - Better to not cite than to invent a citation

CITATION EXAMPLE - CORRECT FORMAT:

User: "What is the defensive width of a motorized rifle battalion?"

Grisha: "Motorized rifle battalion defends a fortified area 3-5 kilometers wide and 2-2.5 kilometers in depth [RU-FM 100-2-1 Chapter 6]. The battalion position has three or four trenches, consisting of company strong points [RU-Russian Way of War Section 4.2].

CURRENT READINESS ASSESSMENT: Doctrine parameters confirmed."

THIS IS THE REQUIRED FORMAT. EVERY CLAIM MUST HAVE A CITATION.

### SOVEREIGN ARCHIVE DATA BEGIN ###

{context}

### SOVEREIGN ARCHIVE DATA END ###
"""

    messages = [{"role": "system", "content": system_prompt}]
    
    # Add history
    for past_q, past_a in chat_history:
        messages.append({"role": "user", "content": past_q})
        messages.append({"role": "assistant", "content": past_a})
    
    # Add current question
    messages.append({"role": "user", "content": question})

    # Ollama API Call
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": LLM_MODEL,
                "messages": messages, 
                "stream": False,
                "options": {"temperature": 0.2,
                            "num_ctx": 8192 # Ensure the context window is large enough
                            }
            },
            timeout=600,
            stream=True
        )
        response.raise_for_status()
        answer = response.json()["message"]["content"]

        # Verify citations against actual archive sources
        if VERIFY_CITATIONS:
            is_valid, invalid_cites, warning = verify_citations(answer, context_blocks)
            if not is_valid:
                logger.warning(f"Citation verification failed: {invalid_cites}")

                if FAIL_ON_INVALID:
                    return (
                        "RESPONSE REJECTED: Unverified citations detected.\n"
                        f"Citations not found in archive: {', '.join(invalid_cites)}\n"
                        "Please rephrase your question or check archive coverage."
                    )
                elif WARN_USER:
                    answer += warning

        # Save to history
        chat_history.append((question, answer))
        if len(chat_history) > MAX_HISTORY:
            chat_history.pop(0)

        return answer
    except Exception as e:
        return f"Error connecting to Grisha: {e}"
# -------------------------
# Interactive Loop
# -------------------------
if __name__ == "__main__":
    from grisha_logging import setup_logging
    setup_logging()

    logger.info("Grisha - Russian Military Expert (local)")
    logger.info("Type 'quit' to exit")

    while True:
        q = input("\nQuestion: ")
        if q.lower() == "quit":
            break

        answer = ask_grisha_brain(q)
        print("\nAnswer:\n", answer)
