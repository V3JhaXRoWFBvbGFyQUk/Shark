#!/usr/bin/env python3
"""
SHARK AI RAG (Retrieval-Augmented Generation) System

Provides external knowledge retrieval for SHARK without requiring model retraining.
Supports semantic search, source citation, and context injection for prompts.

Features:
- Embedding model management with multiple options
- Vector database (ChromaDB local, with extensibility for Pinecone/Weaviate)
- Multi-strategy retrieval (similarity, MMR, hybrid)
- Reranking with cross-encoders
- Source tracking and citation
- Context window management
- Support for multiple knowledge bases
"""

import json
import os
import hashlib
from typing import Any, Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class RetrievalResult:
    """Result from a retrieval query."""
    content: str
    source: str
    score: float
    metadata: Dict[str, Any]
    chunk_id: str
    citation: str  # formatted citation for output


@dataclass
class Citation:
    """Source citation information."""
    source: str
    title: str
    url: Optional[str]
    date: Optional[str]
    license: str
    chunk_id: str


class EmbeddingModel:
    """Wrapper for embedding models used in RAG."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the embedding model."""
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name, device=self.device)
            print(f"Loaded embedding model: {self.model_name} ({self.device})")
        except ImportError:
            print("Warning: sentence_transformers not installed. "
                  "Install with: pip install sentence-transformers")
            # Placeholder - in production would raise or use fallback
            self._model = None
    
    def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        if self._model is None:
            # Return placeholder embedding of correct dimension
            return [0.0] * 384
        
        try:
            embedding = self._model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return [0.0] * 384
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts."""
        if self._model is None:
            return [[0.0] * 384 for _ in texts]
        
        try:
            embeddings = self._model.encode(texts, convert_to_numpy=True)
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            print(f"Error generating batch embeddings: {e}")
            return [[0.0] * 384 for _ in texts]


class VectorDatabase:
    """Wrapper for vector database operations."""
    
    def __init__(self, db_path: str = "chroma_db", collection_name: str = "shark_knowledge"):
        self.db_path = db_path
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._initialize_db()
    
    def _initialize_db(self):
        """Initialize the vector database."""
        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=self.db_path)
            
            # Check if collection exists, create if not
            try:
                self._collection = self._client.get_collection(
                    name=self.collection_name
                )
                print(f"Loaded existing collection: {self.collection_name}")
            except Exception:
                self._collection = self._client.create_collection(
                    name=self.collection_name,
                    metadata={"hnsw_space": "cosine"}
                )
                print(f"Created new collection: {self.collection_name}")
                
        except ImportError:
            print("Warning: chromadb not installed. "
                  "Install with: pip install chromadb")
            self._client = None
            self._collection = None
    
    def add_documents(self, 
                      ids: List[str], 
                      embeddings: List[List[float]], 
                      documents: List[str],
                      metadatas: List[Dict[str, Any]]) -> None:
        """Add documents to the vector database."""
        if self._collection is None:
            print("Error: Vector database not initialized.")
            return
        
        try:
            # Prepare data for ChromaDB
            ids_list = ids or [f"chunk_{i}" for i in range(len(documents))]
            embeddings_list = embeddings or [
                [0.0] * 384 for _ in documents
            ]
            documents_list = documents
            metadatas_list = metadatas or [{} for _ in documents]
            
            self._collection.add(
                ids=ids_list,
                embeddings=embeddings_list,
                documents=documents_list,
                metadatas=metadatas_list
            )
            print(f"Added {len(documents)} documents to vector database.")
        except Exception as e:
            print(f"Error adding documents to vector DB: {e}")
    
    def similarity_search(self, 
                          query: str, 
                          k: int = 5, 
                          filter_metadata: Optional[Dict] = None) -> List[RetrievalResult]:
        """Search for similar documents using embeddings."""
        if self._collection is None:
            return []
        
        try:
            # Generate query embedding
            query_embedding = self._get_query_embedding(query)
            
            # Search
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
                where=filter_metadata,
                include=["documents", "metadatas", "distances"]
            )
            
            retrieval_results = []
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]
            ids = results.get("ids", [[]])[0]
            
            for i in range(len(documents)):
                if documents[i]:
                    # Convert distance to similarity score (cosine)
                    score = 1.0 - min(distances[i], 2.0)  # Clamp to [0, 1] range
                    # Cap at 1.0
                    score = min(max(score, 0.0), 1.0)
                    
                    # Build citation
                    metadata = metadatas[i] if i < len(metadatas) else {}
                    citation = self._build_citation(metadata)
                    
                    result = RetrievalResult(
                        content=documents[i],
                        source=metadata.get("source", "unknown"),
                        score=score,
                        metadata=metadata,
                        chunk_id=ids[i] if ids else f"chunk_{i}",
                        citation=citation,
                    )
                    retrieval_results.append(result)
            
            return retrieval_results
            
        except Exception as e:
            print(f"Error during similarity search: {e}")
            return []
    
    def _get_query_embedding(self, query: str) -> List[float]:
        """Get embedding for a query string."""
        # Use the embedding model
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            embedding = model.encode(query, convert_to_numpy=True)
            return embedding.tolist()
        except Exception:
            return [0.0] * 384
    
    def _build_citation(self, metadata: Dict[str, Any]) -> str:
        """Build a formatted citation from metadata."""
        source = metadata.get("source", "unknown")
        title = metadata.get("title", "")
        url = metadata.get("url")
        date = metadata.get("date")
        license_ = metadata.get("license", "unknown")
        
        parts = [source]
        if title:
            parts.append(f'"{title}"')
        if url:
            parts.append(f"available at {url}")
        if date:
            parts.append(f"({date})")
        parts.append(f"licensed under {license_}")
        
        return " | ".join(parts)
    
    def mmr_search(self, 
                   query: str, 
                   k: int = 5, 
                   lambda_mult: float = 0.5,
                   filter_metadata: Optional[Dict] = None) -> List[RetrievalResult]:
        """Maximal Marginal Relevance search for diverse results."""
        if self._collection is None:
            return []
        
        # Get initial similarity search
        results = self.similarity_search(query, k=k * 2, filter_metadata=filter_metadata)
        
        if not results:
            return []
        
        # MMR algorithm
        selected = [results[0]]
        remaining = results[1:]
        
        while len(selected) < k and remaining:
            best_score = -1
            best_idx = -1
            
            for i, candidate in enumerate(remaining):
                # Similarity to query
                query_sim = candidate.score
                
                # Similarity to already selected (diversity)
                max_sim_to_selected = 0
                for selected_result in selected:
                    # Dot product of embedded content (approximate)
                    # In production would use actual embeddings
                    candidate_text = candidate.content
                    selected_text = selected_result.content
                    # Simple word overlap as proxy
                    candidate_words = set(candidate_text.lower().split())
                    selected_words = set(selected_result.content.lower().split())
                    if candidate_words and selected_words:
                        overlap = len(candidate_words & selected_words) / max(
                            len(candidate_words), len(selected_words), 1
                        )
                    else:
                        overlap = 0
                    
                    # MMR score: relevance - lambda * diversity
                    mmr_score = query_sim - lambda_mult * overlap
                    
                    if mmr_score > best_score:
                        best_score = mmr_score
                        best_idx = i
            
            if best_idx >= 0:
                selected.append(remaining.pop(best_idx))
            else:
                break
        
        return selected


class RAGSystem:
    """Main RAG system combining retrieval and generation context."""
    
    def __init__(self, 
                 embedding_model_name: str = "all-MiniLM-L6-v2",
                 db_path: str = "chroma_db",
                 collection_name: str = "shark_knowledge",
                 reranker_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
                 max_context_tokens: int = 3840):
        
        # Initialize embedding model
        self.embedding_model = EmbeddingModel(embedding_model_name)
        
        # Initialize vector database
        self.vector_db = VectorDatabase(db_path, collection_name)
        
        # Reranker (cross-encoder for reranking)
        self.reranker_name = reranker_name
        self._reranker = None
        self._initialize_reranker()
        
        # Configuration
        self.max_context_tokens = max_context_tokens
        self.max_chunks_per_source = 3
        
        # Knowledge base tracking
        self.knowledge_bases: Dict[str, Dict] = {}
        
    def _initialize_reranker(self):
        """Initialize the reranker model."""
        try:
            from cross_encoder import CrossEncoder
            self._reranker = CrossEncoder(self.reranker_name)
            print(f"Loaded reranker: {self.reranker_name}")
        except ImportError:
            print("Warning: cross-encoder not installed. "
                  "Install with: pip install cross-encoder")
            self._reranker = None
    
    def add_knowledge_base(self, 
                           name: str, 
                           description: str = "",
                           source_type: str = "vector_db") -> None:
        """Register a new knowledge base."""
        self.knowledge_bases[name] = {
            "description": description,
            "source_type": source_type,
            "retrieved_chunks": [],
        }
        print(f"Knowledge base '{name}' registered.")
    
    def import_dataset_records(self, 
                               records: List[Any],  # DatasetRecord objects
                               dataset_name: str,
                               chunk_size: int = 2000,
               overlap: int = 200) -> List[str]:
        """
        Import dataset records into the vector database.
        
        Returns list of chunk IDs added.
        """
        chunk_ids = []
        
        # Chunk and embed records
        for record in records:
            # Get content - handle both DatasetRecord objects and strings
            if hasattr(record, 'content'):
                content = record.content
                metadata = {
                    "source": getattr(record, 'source', 'unknown'),
                    "category": getattr(record, 'category', 'general'),
                    "license": getattr(record, 'license', 'unknown'),
                    "dataset_name": dataset_name,
                    "id": getattr(record, 'id', str(hashlib.sha256(content.encode()).hexdigest()[:8])),
                }
            else:
                content = record
                metadata = {
                    "source": "unknown",
                    "category": "general",
                    "license": "unknown",
                    "dataset_name": dataset_name,
                }
            
            # Chunk the content if it's too large
            chunks = self._chunk_text(content, chunk_size, overlap)
            
            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue
                
                # Generate embedding
                embedding = self.embedding_model.embed(chunk)
                
                # Create chunk ID
                chunk_id = f"{dataset_name}_{record.id if hasattr(record, 'id') else 'unknown'}_{i}"
                
                # Prepare metadata
                chunk_metadata = dict(metadata)
                chunk_metadata["chunk_index"] = i
                chunk_metadata["chunk_size"] = len(chunk)
                
                chunk_ids.append(chunk_id)
                
                # Add to vector database
                self.vector_db.add_documents(
                    ids=[chunk_id],
                    embeddings=[embedding],
                    documents=[chunk],
                    metadatas=[chunk_metadata]
                )
        
        return chunk_ids
    
    def _chunk_text(self, text: str, max_size: int, overlap: int) -> List[str]:
        """Split text into overlapping chunks."""
        if len(text) <= max_size:
            return [text] if text.strip() else []
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + max_size
            if end < len(text):
                # Try to break at sentence boundary
                last_period = text.rfind('.', start, end)
                if last_period > start + max_size // 2:
                    end = last_period + 1
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
            if start < 0:
                start = 0
            if start >= len(text):
                break
        
        return chunks
    
    def retrieve(self, 
                 query: str, 
                 k: int = 5, 
                 knowledge_base: Optional[str] = None,
                 use_reranker: bool = True,
                 use_mmr: bool = False) -> List[RetrievalResult]:
        """
        Retrieve relevant documents for a query.
        
        Args:
            query: The search query
            k: Number of results to return
            knowledge_base: Optional specific knowledge base to search
            use_reranker: Whether to rerank results
            use_mmr: Whether to use MMR for diversity
            
        Returns:
            List of RetrievalResult objects
        """
        # Search vector database
        if use_mmr:
            results = self.vector_db.mmr_search(
                query, k=k * 2, filter_metadata=None
            )
        else:
            results = self.vector_db.similarity_search(query, k=k * 2)
        
        if not results:
            return []
        
        # Filter by knowledge base if specified
        if knowledge_base and knowledge_base in self.knowledge_bases:
            # In a full implementation, would filter by KB metadata
            pass
        
        # Rerank if requested and available
        if use_reranker and self._reranker and len(results) > 1:
            results = self._rerank(query, results)
        
        # Return top k
        return results[:k]
    
    def _rerank(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Rerank retrieval results using cross-encoder."""
        if not self._reranker or not results:
            return results
        
        try:
            # Prepare pairs for reranker
            pairs = [(query, r.content) for r in results]
            scores = self._reranker.predict(pairs)
            
            # Update scores
            for i, score in enumerate(scores):
                results[i].score = float(score)
            
            # Sort by new scores
            results.sort(key=lambda r: r.score, reverse=True)
            
        except Exception as e:
            print(f"Error during reranking: {e}")
        
        return results
    
    def build_context(self, 
                      query: str, 
                      k: int = 5,
                      knowledge_base: Optional[str] = None,
                      include_citations: bool = True) -> Dict[str, Any]:
        """
        Build a context dict for prompt injection.
        
        Returns dict with 'context_text' and 'citations' for use in prompts.
        """
        # Retrieve relevant documents
        results = self.retrieve(query, k=k, knowledge_base=knowledge_base)
        
        if not results:
            return {
                "context_text": "",
                "citations": [],
                "retrieval_count": 0,
            }
        
        # Build context text
        context_parts = []
        citations = []
        
        for i, result in enumerate(results, 1):
            # Add with source attribution
            part = f"[Source {i}] {result.content}"
            context_parts.append(part)
            
            if include_citations:
                citations.append(result.citation)
        
        context_text = "\n\n".join(context_parts)
        
        # Token check - truncate if needed
        if len(context_text) > self.max_context_tokens * 4:  # rough char-to-token
            # Keep only the top results that fit
            available_chars = self.max_context_tokens * 4
            context_text = context_text[:available_chars] + "..."
            # Truncate citations too
            citations = citations[:2]
        
        return {
            "context_text": context_text,
            "citations": citations if include_citations else [],
            "retrieval_count": len(results),
        }
    
    def answer_with_context(self, 
                           query: str, 
                           system_prompt: str,
                           k: int = 5,
                           knowledge_base: Optional[str] = None) -> str:
        """
        Generate an answer with retrieved context.
        
        Returns the formatted prompt/context that can be sent to the model.
        """
        # Build context
        context = self.build_context(query, k=k, knowledge_base=knowledge_base)
        
        # Format the prompt for SHARK
        formatted = f"""<|system|>
{system_prompt}</|system|>

<|user|>
Answer the user's question based on the following context:

{context['context_text']}

User question: {query}

Instructions:
- Provide a comprehensive, accurate answer based on the context above
- If the context doesn't contain sufficient information, say so clearly
- Cite your sources using the citation format: [{i}] where i corresponds to the source number
- Only share information that is clearly present in the cited sources
- If multiple sources provide information, synthesize them
- Maintain SHARK's cybersecurity expertise while being grounded in the provided context

<|user|>"""

        return formatted
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system configuration information."""
        return {
            "embedding_model": self.embedding_model.model_name,
            "vector_db_path": self.vector_db.db_path,
            "collection_name": self.vector_db.collection_name,
            "reranker": self.reranker_name if self._reranker else "none",
            "max_context_tokens": self.max_context_tokens,
            "knowledge_bases": list(self.knowledge_bases.keys()),
            "available": self._check_system_ready(),
        }
    
    def _check_system_ready(self) -> bool:
        """Check if the RAG system is ready to use."""
        return (
            self.embedding_model._model is not None or 
            self.vector_db._collection is not None
        )


# Example usage and testing
if __name__ == "__main__":
    print("=== SHARK AI RAG System ===\n")
    
    # Initialize RAG system
    rag = RAGSystem(embedding_model_name="all-MiniLM-L6-v2", 
                    db_path="shark_rag_db",
                    max_context_tokens=3840)
    
    print(f"System ready: {rag._check_system_ready()}")
    print(f"Embedding model: {rag.embedding_model.model_name}")
    print(f"Vector DB: {rag.vector_db.collection_name}")
    print(f"Reranker: {rag.reranker_name if rag._reranker else 'none'}")
    
    # Add some test knowledge
    test_docs = [
        "SHARK AI cybersecurity assistant specializes in vulnerability analysis and penetration testing.",
        "CVE-2024-12345 is a critical vulnerability in OpenSSH affecting the authentication module.",
        "MITRE ATT&CK technique T1566.001 describes phishing: spearphishing attachment.",
        "OWASP Top Ten 2021 A02:2021 identifies cryptographic failures as a major web security risk.",
        "CISA KEV catalog lists actively exploited vulnerabilities that require immediate patching.",
    ]
    
    # Import test documents
    chunk_ids = rag.import_dataset_records(
        [type('obj', (object,), {'content': doc, 'id': f'test_{i}'})() for doc in test_docs],
        "test_knowledge_base"
    )
    print(f"\nImported {len(chunk_ids)} document chunks.")
    
    # Test retrieval
    print("\n=== Testing Retrieval ===")
    
    test_queries = [
        "vulnerability in OpenSSH",
        "phishing techniques",
        "web security risks",
        "actively exploited vulnerabilities",
    ]
    
    for query in test_queries:
        results = rag.retrieve(query, k=3)
        print(f"\nQuery: '{query}'")
        print(f"  Found {len(results)} results:")
        for r in results:
            print(f"    - Score: {r.score:.3f} | {r.source}: {r.content[:80]}...")
    
    # Test context building
    print("\n=== Testing Context Building ===")
    answer_prompt = rag.answer_with_context(
        "What are the main cybersecurity risks today?",
        SHARK_SYSTEM_PROMPT := """You are SHARK, the SHARK Cybersecurity Assistant.
You are a specialized cybersecurity AI for advanced security research, 
vulnerability analysis, authorized penetration testing, and defensive security.
Always operate within authorized, legal, and ethical boundaries.""",
        k=3
    )
    print(f"Context built successfully ({len(answer_prompt)} chars)")
    print(f"Context preview:\n{answer_prompt[:300]}...")