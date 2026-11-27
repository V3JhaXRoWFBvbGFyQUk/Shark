#!/usr/bin/env python3
"""
SHARK AI Complete Knowledge System

Integrates dataset management, RAG retrieval, and training pipeline into a
coherent system that allows SHARK to continuously expand its cybersecurity
knowledge through external datasets while maintaining its core model capabilities.

Architecture: Hybrid RAG + LoRA Specialization
- Core cybersecurity skills from base model
- External knowledge via RAG (current, dynamic info)
- LoRA adapters for sub-domain specialization
- Dataset validation, licensing, and provenance tracking
"""

import sys
import os
from typing import Any, Dict, List, Optional, Tuple

# Add local directories
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dataset_manager import DatasetManager, DatasetInfo, DatasetRecord
from rag_system import RAGSystem, RetrievalResult, Citation
from training.train import TrainingPipeline, CybersecurityDataset, DataValidator

# SHARK system prompt
SHARK_SYSTEM_PROMPT = """You are SHARK, the SHARK Cybersecurity Assistant.
You are a specialized cybersecurity AI for advanced security research, 
vulnerability analysis, authorized penetration testing, red-team simulations, 
exploit research in isolated labs, reverse engineering, CTFs, and defensive security.
You possess extensive knowledge of vulnerability assessment, threat intelligence, 
reverse engineering, cryptography, network security, CTF challenges, and 
defensive security operations. Always operate within authorized, legal, and 
ethical boundaries. Identify yourself as SHARK."""

# Default knowledge base names
DEFAULT_KNOWLEDGE_BASES = {
    "core_skills": "Core cybersecurity skills and model capabilities",
    "cve_data": "CVE and vulnerability database entries",
    "attack_framework": "MITRE ATT&CK framework and techniques",
    "kev_db": "CISA Known Exploited Vulnerabilities",
    "owasp": "OWASP Top Ten and security projects",
    "github_security": "Security-related GitHub repositories",
    "research_publications": "Security research papers and analyses",
}


class SHARKKnowledgeSystem:
    """
    Main knowledge system for SHARK AI.
    
    Orchestrates:
    - Dataset import and management
    - RAG-based external knowledge retrieval
    - LoRA-based specialization
    - Training pipeline integration
    - License and provenance tracking
    """
    
    def __init__(self, 
                 base_dir: str = "datasets",
                 rag_db_path: str = "shark_rag_db",
                 model_name: str = "ollama/shark:latest"):
        
        self.base_dir = base_dir
        self.rag_db_path = rag_db_path
        self.model_name = model_name
        
        # Initialize components
        self.dataset_manager = DatasetManager(base_dir)
        self.rag_system = RAGSystem(
            embedding_model_name="all-MiniLM-L6-v2",
            db_path=rag_db_path,
            max_context_tokens=3840,
        )
        self.training_pipeline = TrainingPipeline(model_name=model_name)
        
        # System state
        self.initialized = False
        self.active_adapter: Optional[str] = None
        self.dataset_approvals: Dict[str, bool] = {}
        
        # Register default knowledge bases
        self._register_default_knowledge_bases()
    
    def _register_default_knowledge_bases(self):
        """Register default knowledge bases for the RAG system."""
        for kb_name, description in DEFAULT_KNOWLEDGE_BASES.items():
            self.rag_system.add_knowledge_base(
                name=kb_name,
                description=description,
                source_type="vector_db"
            )
    
    def initialize(self) -> bool:
        """Initialize the full knowledge system."""
        try:
            print("Initializing SHARK Knowledge System...")
            
            # Load dataset registry
            self.dataset_manager._load_registry()
            
            # Load RAG system
            # Note: embedding model and vector DB may need reinitialization
            
            # Try to load the model for training pipeline
            model_loaded = self.training_pipeline.load_model(
                load_in_4bit=True,
                use_gradient_checkpointing=True
            )
            
            if not model_loaded:
                print("Warning: Could not load model, but system will function with RAG only.")
            
            self.initialized = True
            
            # Report status
            info = self.get_system_info()
            rag_info = self.rag_system.get_system_info()
            print(f"System initialized. Ready with {len(info['knowledge_bases'])} knowledge bases.")
            print(f"  Embedding: {info['embedding_model']}")
            print(f"  Vector DB: {info['vector_db_path']}.chroma")
            print(f"  Reranker: {rag_info.get('reranker', 'none')}")
            
            return True
            
        except Exception as e:
            print(f"Error initializing knowledge system: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def import_dataset(self, 
                       source: str, 
                       source_type: str = "local",
                       **kwargs) -> Optional[DatasetInfo]:
        """
        Import a dataset from various sources.
        
        Supported source types:
        - "local": Local file path
        - "huggingface": Hugging Face dataset name
        - "github": GitHub repository URL
        - "cve": CVE data import
        - "kev": CISA KEV database
        - "owsawa": OWASP resources
        - "url": Custom URL
        """
        print(f"\n=== Importing Dataset: {source} ===")
        
        try:
            if source_type == "local":
                di = self.dataset_manager.import_local_file(source)
            
            elif source_type == "huggingface":
                di = self.dataset_manager.import_huggingface(source, **kwargs)
            
            elif source_type == "github":
                repo_url = source
                if "branch" in kwargs:
                    di = self.dataset_manager.import_github_repo(repo_url, kwargs["branch"])
                else:
                    di = self.dataset_manager.import_github_repo(repo_url)
            
            elif source_type == "cve":
                cve_ids = kwargs.get("cve_ids", None)
                di = self.dataset_manager.import_cve_data(cve_ids)
            
            elif source_type == "kev":
                di = self.dataset_manager.import_kev_database()
            
            elif source_type == "owsawa":
                resource_type = kwargs.get("resource_type", "top_ten")
                di = self.dataset_manager.import_owsawa_resources(resource_type)
            
            elif source_type == "url":
                di = self.dataset_manager.import_custom_url(source)
            
            else:
                print(f"Unknown source type: {source_type}")
                return None
            
            # Validate license and get user approval for training
            di = self.dataset_manager.approve_dataset_for_training(
                di.name  # type: ignore[arg-type]  # dynamical attribute access
            )
            
            # Import records into RAG system
            if di and di.size > 0:
                # Get the records
                info, records = self.dataset_manager.get_dataset(di.name)
                if info and records:
                    # Import into RAG
                    chunk_ids = self.rag_system.import_dataset_records(
                        records, di.name
                    )
                    print(f"  Imported {len(chunk_ids)} chunks into RAG system.")
                    
                    # Update knowledge base registration
                    kb_name = di.name.replace("/", "_").replace(".", "_")[:30]
                    self.rag_system.add_knowledge_base(
                        name=kb_name,
                        description=f"Imported from: {di.source}",
                        source_type="imported_dataset"
                    )
            
            return di
            
        except Exception as e:
            print(f"Error importing dataset: {e}")
            import traceback
            traceback.print_capped_exc()
            return None
    
    def retrieve_knowledge(self, 
                           query: str, 
                           k: int = 5,
                           knowledge_base: Optional[str] = None,
                           use_reranker: bool = True,
                           use_mmr: bool = False) -> Dict[str, Any]:
        """
        Retrieve relevant knowledge for a query.
        
        Returns dict with context_text and citations for prompt injection.
        """
        if not self.initialized:
            print("Error: Knowledge system not initialized.")
            return {"context_text": "", "citations": [], "retrieval_count": 0}
        
        # Build the prompt-ready context
        context = self.rag_system.build_context(
            query=query,
            k=k,
            knowledge_base=knowledge_base,
            include_citations=True,
        )
        
        return {
            "context_text": context["context_text"],
            "citations": context["citations"],
            "retrieval_count": context["retrieval_count"],
        }
    
    def answer_query(self, 
                     query: str,
                     system_prompt: str = SHARK_SYSTEM_PROMPT,
                     k: int = 5,
                     knowledge_base: Optional[str] = None,
                     use_training: bool = False) -> str:
        """
        Generate an answer to a query using RAG + optionally training data.
        
        Returns the formatted prompt that can be sent to the model.
        """
        # Build context from RAG
        rag_context = self.retrieve_knowledge(query, k=k, knowledge_base=knowledge_base)
        
        # Format the complete prompt
        formatted_prompt = f"""<|system|>
{system_prompt}</|system|>

<|user|>
Answer the user's question based on the following context:

{rag_context['context_text']}

User question: {query}

Instructions:
- Provide a comprehensive, accurate answer based on the context above
- If the context doesn't contain sufficient information, say so clearly
- Cite your sources using the citation format: [{i}] where i corresponds to 
  the source number (1-indexed from the cited sources)
- Only share information that is clearly present in the cited sources
- If multiple sources provide information, synthesize them cohesively
- Maintain SHARK's cybersecurity expertise while being grounded in the provided context
- If you're uncertain about any detail, acknowledge the limitation
- Operate within authorized, legal, and ethical boundaries at all times

<|user|>"""
        
        return formatted_prompt
    
    def train_on_dataset(self, 
                         dataset_name: str,
                         use_qlora: bool = True,
                         epochs: int = 3,
                         **kwargs) -> Dict[str, Any]:
        """
        Train SHARK on an imported dataset.
        
        Requires prior approval (checked via dataset_manager).
        Uses LoRA/QLoRA for efficient fine-tuning.
        """
        if dataset_name not in self.dataset_manager.registry:
            print(f"Dataset '{dataset_name}' not found in registry.")
            return {"status": "failed", "error": "Dataset not registered"}
        
        # Check approval
        di = self.dataset_manager.registry[dataset_name]
        if di.license in ["requires_review", "unknown"]:
            print(f"⚠️  Dataset '{di.name}' license requires review.")
            approved = input("Have you verified the license is training-compatible? (y/n): ").strip().lower()
            if approved not in ['y', 'yes']:
                print("Training aborted - license not approved.")
                return {"status": "aborted", "reason": "license_not_approved"}
        
        # Load records
        info, records = self.dataset_manager.get_dataset(dataset_name)
        if not records:
            print(f"No records found for dataset '{dataset_name}'.")
            return {"status": "failed", "error": "No records"}
        
        # Validate dataset
        validator = DataValidator()
        clean_records = validator.clean_dataset(records)
        
        if not clean_records:
            print("No valid records after cleaning.")
            return {"status": "failed", "error": "No valid records after cleaning"}
        
        # Create training dataset
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, trust_remote_code=True
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        
        train_dataset = CybersecurityDataset(clean_records, tokenizer, max_length=512)
        
        # Train
        print(f"\nTraining SHARK on dataset: {di.name}")
        print(f"  Records: {len(clean_records)} (after cleaning from {len(records)})")
        
        result = self.training_pipeline.train_lora(
            train_dataset=train_dataset,
            use_qlora=use_qlora,
            num_train_epochs=epochs,
        )
        
        if result.get("status") == "success":
            # After training, reload RAG with new adapter knowledge
            self._refresh_after_training()
            
            # Merge adapter for deployment
            print(f"Training complete. Adapter saved to: {result.get('model_path')}")
        
        return result
    
    def _refresh_after_training(self):
        """Refresh system state after training."""
        # In a production system, would reload the model with new adapters
        # and potentially update the RAG system with new patterns learned
        print("  • System state refreshed after training.")
        # Re-register the knowledge base if it was trained on
        if dataset_name in self.dataset_manager.registry:
            di = self.dataset_manager.registry[dataset_name]
            kb_name = di.name.replace("/", "_").replace(".", "_")[:30]
            if kb_name not in self.rag_system.knowledge_bases:
                self.rag_system.add_knowledge_base(
                    name=kb_name,
                    description=f"Trained on: {di.name}",
                    source_type="trained_adapter"
                )
    
    def list_datasets(self) -> List[Dict[str, Any]]:
        """List all registered datasets with metadata."""
        return self.dataset_manager.list_datasets()
    
    def generate_quality_report(self, dataset_name: str) -> Dict[str, Any]:
        """Generate a quality report for a dataset."""
        return self.dataset_manager.generate_quality_report(dataset_name)
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get overall system configuration."""
        rag_info = self.rag_system.get_system_info()
        dataset_info = self.list_datasets()
        
        # Count approved datasets
        approved = sum(
            1 for name, di in self.dataset_manager.registry.items()
            if di.license not in ["requires_review", "unknown"] or 
            name in self.dataset_approvals
        )
        
        vector_db_path = rag_info.get("vector_db_path", "chroma_db")
        
        return {
            "model_name": self.model_name,
            "initialized": self.initialized,
            "active_adapter": self.active_adapter,
            "embedding_model": rag_info.get("embedding_model", "all-MiniLM-L6-v2"),
            "vector_db_path": vector_db_path,
            "knowledge_bases": {
                k: {"description": v["description"], "source_type": v["source_type"]}
                for k, v in self.rag_system.knowledge_bases.items()
            },
            "registered_datasets": len(dataset_info),
            "approved_for_training": approved,
            "total_records_in_rag": self._count_rag_records(),
            "training_history_count": len(self.training_pipeline.training_history),
        }
    
    def _count_rag_records(self) -> int:
        """Count total records in the RAG vector database."""
        # This is a simplified count - in production would query the DB
        # For now, sum up from dataset records
        total = 0
        for name in self.dataset_manager.available_datasets:
            _, records = self.dataset_manager.get_dataset(name)
            total += len(records) if records else 0
        return total
    
    def export_system_state(self, export_path: str) -> str:
        """Export the complete system state for backup or transfer."""
        state = {
            "system_info": self.get_system_info(),
            "dataset_registry": {
                name: {
                    "name": di.name,
                    "source": di.source,
                    "license": di.license,
                    "categories": list(di.categories),
                    "size": di.size,
                } for name, di in self.dataset_manager.registry.items()
            },
            "rag_configuration": {
                "embedding_model": self.rag_system.embedding_model.model_name,
                "db_path": self.rag_system.vector_db.db_path,
                "collection_name": self.rag_system.vector_db.collection_name,
                "knowledge_bases": list(self.rag_system.knowledge_bases.keys()),
            },
            "timestamp": datetime.now().isoformat(),
        }
        
        export_file = Path(export_path)
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
        
        print(f"System state exported to {export_file}")
        return str(export_file)


# CLI entry point
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="SHARK AI Knowledge System")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Initialize command
    subparsers.add_parser("initialize", help="Initialize the knowledge system")
    
    # Import commands
    import_parser = subparsers.add_parser("import", help="Import a dataset")
    import_parser.add_argument("source", help="Dataset source (file path, URL, or dataset name)")
    import_parser.add_argument("--type", choices=["local", "huggingface", "github", "cve", "kev", "owsawa", "url"],
                               default="local", help="Source type")
    import_parser.add_argument("--kb", help="Knowledge base name")
    
    # Query command
    query_parser = subparsers.add_parser("query", help="Query SHARK with RAG")
    query_parser.add_argument("question", help="Question to ask SHARK")
    query_parser.add_argument("--kb", help="Knowledge base to search")
    query_parser.add_argument("--k", type=int, default=5, help="Number of results")
    
    # Train command
    train_parser = subparsers.add_parser("train", help="Train SHARK on dataset")
    train_parser.add_argument("dataset", help="Dataset name from registry")
    train_parser.add_argument("--qlora", action="store_true", default=True, help="Use QLoRA")
    train_parser.add_argument("--epochs", type=int, default=3, help="Number of epochs")
    
    # List datasets
    subparsers.add_parser("list", help="List registered datasets")
    
    # Report command
    subparsers.add_parser("report", help="Generate quality report")
    report_parser = subparsers.add_parser("report", help="Generate quality report")
    report_parser.add_argument("dataset", help="Dataset name")
    
    # System info
    subparsers.add_parser("info", help="Show system information")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Initialize system
    system = SHARKKnowledgeSystem()
    
    if args.command == "initialize":
        system.initialize()
    
    elif args.command == "import":
        di = system.import_dataset(args.source, source_type=args.type)
        if di:
            print(f"\nImported: {di.name}")
            print(f"  Records: {di.size}")
            print(f"  License: {di.license}")
            print(f"  Categories: {list(di.categories)}")
    
    elif args.command == "query":
        result = system.answer_query(args.question, k=args.k, knowledge_base=args.kb)
        print(f"\n=== Query: {args.question} ===")
        print(f"\nPrompt length: {len(result)} characters")
        # Don't print the full prompt - just show it's ready
        print(f"\nPrompt ready for model inference. First 200 chars:")
        print(result[:200] + "..." if len(result) > 200 else result)
    
    elif args.command == "train":
        result = system.train_on_dataset(args.dataset, use_qlora=args.qlora, epochs=args.epochs)
        print(f"\nTraining result: {result.get('status')}")
        if result.get("status") == "success":
            print(f"  Model path: {result.get('model_path')}")
    
    elif args.command == "list":
        datasets = system.list_datasets()
        print(f"\nRegistered datasets ({len(datasets)}):")
        for ds in datasets:
            print(f"  - {ds['name'][:60]:60s} | {ds['size']} records | {ds['license']}")
    
    elif args.command == "report":
        report = system.generate_quality_report(args.dataset)
        if "error" in report:
            print(f"Error: {report['error']}")
        else:
            print(f"\n=== Quality Report: {report['dataset_name']} ===")
            print(f"  Quality Score: {report['quality_score']}/100")
            print(f"  Records: {report['total_records']}")
            print(f"  Duplicates: {report['duplicate_count']} ({report['duplicate_percentage']}%)")
            print(f"  Category distribution: {report['category_distribution']}")
    
    elif args.command == "info":
        info = system.get_system_info()
        print(f"\n=== SHARK Knowledge System Info ===")
        for key, value in info.items():
            print(f"  {key}: {value}")