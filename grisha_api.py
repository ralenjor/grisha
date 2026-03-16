import chromadb
from fastapi import FastAPI
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
import uvicorn
from grisha_logging import setup_logging, get_logger

setup_logging()
logger = get_logger("api")

# --- CONFIGURATION (Matches your query script) ---
CHROMA_PATH = "./grisha_db"
COLLECTION_NAME = "grisha_knowledge"
RELEVANCE_THRESHOLD = 1.5 
TOP_K = 5

app = FastAPI()

# --- INITIALIZE CHROMA ---
# We do this at the global level so it only loads once when the API starts
client = chromadb.PersistentClient(path=CHROMA_PATH)
embedding_function = ONNXMiniLM_L6_V2()
collection = client.get_collection(name=COLLECTION_NAME, embedding_function=embedding_function)

@app.get("/search")
def search(q: str):
    """
    This endpoint mimics the logic of your 'ask_grisha_brain' 
    but only returns the RAW CONTEXT for the WebUI to use.
    """
    results = collection.query(
        query_texts=[q],
        n_results=TOP_K,
        include=["documents", "metadatas", "distances"]
    )

    # Check for empty results or low relevance
    if not results["documents"][0] or results["distances"][0][0] > RELEVANCE_THRESHOLD:
        return {"context": "The archives for this asset are incomplete or no relevant data was found."}

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    context_blocks = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        if dist < RELEVANCE_THRESHOLD:
            # Reconstruct the source citation just like your script did
            source_title = meta.get('title', 'Unknown Source')
            source_section = meta.get('section', 'General')
            # Extract Nation Tag for Grisha's guardrails [RU/US]
            nation = meta.get('nation', 'Unknown')
            
            block = f"[{nation} - {source_title} ({source_section})]: {doc}"
            context_blocks.append(block)

    # Join with triple newlines to give the LLM clear separation
    full_context = "\n\n\n".join(context_blocks)
    
    return {"context": full_context}

if __name__ == "__main__":
    logger.info("Starting Grisha API server on 0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
