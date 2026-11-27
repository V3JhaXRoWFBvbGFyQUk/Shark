# SHARK AI Knowledge System Initialization
# This module sets up the package imports

from .shark_knowledge_system import SHARKKnowledgeSystem, SHARK_SYSTEM_PROMPT, DatasetManager, RAGSystem, TrainingPipeline
from .dataset_manager import DatasetManager as DM, DatasetInfo, DatasetRecord
from .rag_system import RAGSystem as RS, RetrievalResult, Citation
from .training.train import TrainingPipeline as TP, CybersecurityDataset, DataValidator

__all__ = [
    "SHARKKnowledgeSystem",
    "SHARK_SYSTEM_PROMPT", 
    "DatasetManager",
    "DatasetInfo",
    "DatasetRecord",
    "RAGSystem",
    "RetrievalResult",
    "Citation",
    "TrainingPipeline",
    "CybersecurityDataset",
    "DataValidator",
]