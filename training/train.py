#!/usr/bin/env python3
"""
SHARK AI Training Pipeline

Handles continued pre-training, SFT, and LoRA/QLoRA fine-tuning of the SHARK model.
Integrates with the Dataset Manager and RAG system for a hybrid learning approach.
"""

import json
import os
import hashlib
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import torch
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    BitsAndBytesConfig,
    pipeline,
)


class CybersecurityDataset(Dataset):
    """Dataset class for cybersecurity training data."""
    
    def __init__(self, 
                 records: List[Dict[str, Any]],
                 tokenizer: Any,
                 max_length: int = 512,
                 add_eos_token: bool = True):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.add_eos_token = add_eos_token
        
        # Process records into training examples
        self.examples = []
        for record in records:
            # Handle both DatasetRecord objects and dicts
            if isinstance(record, dict):
                content = record.get("content", "")
                metadata = record.get("metadata", {})
            else:
                content = getattr(record, "content", "")
                metadata = getattr(record, "metadata", {})
            
            if not content.strip():
                continue
            
            # Create training example - format: instruction + response
            # For cybersecurity AI, we use a standard format
            example_text = f"""<|system|>
You are SHARK, the SHARK Cybersecurity Assistant. 
You are a specialized cybersecurity AI for advanced security research, 
vulnerability analysis, authorized penetration testing, red-team simulations, 
exploit research in isolated labs, reverse engineering, CTFs, and defensive security.
Always operate within authorized, legal, and ethical boundaries.</|system|
<|user|>
{content}</|user|
<|assistant|>
""")
            
            if self.add_eos_token:
                example_text += "<|assistant|>"
            
            self.examples.append(example_text)
    
    def __len__(self):
        return len(self.examples)
    
    def __getitem__(self, idx):
        example = self.examples[idx]
        
        # Tokenize
        tokenized = self.tokenizer(
            example,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )
        
        return {
            "input_ids": tokenized["input_ids"][0],
            "attention_mask": tokenized["attention_mask"][0],
            "labels": tokenized["input_ids"][0].clone(),  # For causal LM, labels = input_ids
        }


class TrainingPipeline:
    """
    Training pipeline for SHARK AI.
    
    Supports:
    - Continued pre-training on large cybersecurity corpora
    - SFT (Supervised Fine-Tuning) on instruction following
    - LoRA/QLoRA efficient fine-tuning
    - Dataset validation and quality filtering
    - Training progress tracking
    - Model saving with LoRA adapters
    """
    
    def __init__(self, 
                 model_name: str = "ollama/shark:latest",
                 output_dir: str = "training/outputs",
                 device: str = "auto"):
        self.model_name = model_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.device = device if device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu")
        
        # Model and tokenizer
        self.model = None
        self.tokenizer = None
        
        # Training state
        self.is_training = False
        self.training_history: List[Dict] = []
        
        # LoRA config
        self.lora_config = {
            "r": 64,
            "lora_alpha": 16,
            "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
            "lora_dropout": 0.1,
            "bias": "none",
            "task_type": "CAUSAL_LM",
        }
    
    def load_model(self, 
                   load_in_4bit: bool = True,
                   use_gradient_checkpointing: bool = True) -> bool:
        """Load the SHARK model and tokenizer."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            
            print(f"Loading model: {self.model_name}")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True,
            )
            
            # Set pad token if not set
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Quantization config for efficient loading
            bnb_config = None
            if load_in_4bit:
                bnb_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb4bit_quant_type="nf4",
                    bnb4bit_compute_dtype=torch.float16,
                    bnb4bit_use_double_quant=False,
                )
            
            # Load model
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                quantization_config=bnb_config if load_in_4bit else None,
                device_map=self.device,
                trust_remote_code=True,
                use_gradient_checkpointing=use_gradient_checkpointing,
            )
            
            print(f"Model loaded successfully on {self.device}")
            return True
            
        except Exception as e:
            print(f"Error loading model: {e}")
            # Fallback: try without quantization
            try:
                print("Attempting fallback load without 4-bit quantization...")
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.model_name,
                    trust_remote_code=True,
                )
                if self.tokenizer.pad_token is None:
                    self.tokenizer.pad_token = self.tokenizer.eos_token
                
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    device_map="auto",
                    trust_remote_code=True,
                )
                print("Model loaded in fallback mode.")
                return True
            except Exception as e2:
                print(f"Fallback also failed: {e2}")
                return False
    
    def prepare_training_args(self, 
                              num_train_epochs: int = 3,
                              per_device_train_batch_size: int = 4,
                              learning_rate: float = 2e-4,
                              weight_decay: float = 0.001,
                              fp16: bool = True,
                              logging_steps: int = 10,
                              save_steps: int = 100,
                              max_steps: int = -1,
                              **kwargs) -> TrainingArguments:
        """Prepare training arguments."""
        return TrainingArguments(
            output_dir=str(self.output_dir / "shark_trained"),
            num_train_epochs=num_train_epochs,
            per_device_train_batch_size=per_device_train_batch_size,
            learning_rate=learning_rate,
            weight_decay=weight_decay,
            fp16=fp16,
            logging_steps=logging_steps,
            save_steps=save_steps,
            max_steps=max_steps if max_steps > 0 else None,
            bf16=False,
            remove_unused_columns=False,
            report_to=[],  # Disable logging to wandb/mlflow by default
            **kwargs,
        )
    
    def train_lora(self, 
                   train_dataset: Dataset,
                   eval_dataset: Optional[Dataset] = None,
                   use_qlora: bool = True,
                   **training_kwargs) -> Dict[str, Any]:
        """
        Train with LoRA (or QLoRA for efficient fine-tuning).
        
        Returns training metrics and save info.
        """
        if self.model is None or self.tokenizer is None:
            print("Error: Model not loaded. Call load_model() first.")
            return {}
        
        self.is_training = True
        start_time = datetime.now()
        
        try:
            from peft import LoraConfig, get_peft_model, PeftModel
            
            print("Setting up LoRA configuration...")
            
            # Setup LoRA config
            lora_cfg = LoraConfig(
                r=self.lora_config["r"],
                lora_alpha=self.lora_config["lora_alpha"],
                target_modules=self.lora_config["target_modules"],
                lora_dropout=self.lora_config["lora_dropout"],
                bias=self.lora_config["bias"],
                task_type=self.lora_config["task_type"],
            )
            
            # Apply LoRA to model
            print("Applying LoRA adapters to model...")
            self.model = get_peft_model(self.model, lora_cfg)
            self.model.print_trainable_parameters()
            
            # If QLoRA, enable 4-bit computing
            if use_qlora and self.device.startswith("cuda"):
                try:
                    self.model.is_gradient_checkpointing_enable = True
                    self.model.config.use_cache = False
                    print("QLoRA configuration enabled (4-bit computation).")
                except Exception as e:
                    print(f"Warning: QLoRA setup issue: {e}")
            
            # Prepare training arguments
            training_args = self.prepare_training_args(**training_kwargs)
            
            # Create data loaders
            train_dataloader = DataLoader(
                train_dataset,
                batch_size=training_args.per_device_train_batch_size,
            )
            
            # Initialize trainer (simple implementation)
            from transformers import Trainer
            
            trainer = Trainer(
                model=self.model,
                args=training_args,
                train_dataset=train_dataset if hasattr(train_dataset, '__len__') else None,
                eval_dataset=eval_dataset,
                tokenizer=self.tokenizer,
            )
            
            # Train
            print("Starting training...")
            trainer.train()
            
            # Save model
            end_time = datetime.now()
            training_duration = (end_time - start_time).total_seconds() / 60  # minutes
            
            save_path = self.output_dir / "shark_lora_adapter"
            self.model.save_pretrained(save_path)
            self.tokenizer.save_pretrained(save_path)
            
            print(f"Training complete. Model saved to {save_path}")
            print(f"Training duration: {training_duration:.1f} minutes")
            
            # Record training history
            history_entry = {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_minutes": training_duration,
                "train_samples": len(train_dataset),
                "use_qlora": use_qlora,
                "lora_save_path": str(save_path),
                "status": "completed",
            }
            self.training_history.append(history_entry)
            
            return {
                "status": "success",
                "model_path": str(save_path),
                "training_duration_minutes": training_duration,
                "samples_trained": len(train_dataset),
                "history_entry_index": len(self.training_history) - 1,
            }
            
        except Exception as e:
            print(f"Error during training: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "failed",
                "error": str(e),
            }
        
        finally:
            self.is_training = False
    
    def train_continued_pretraining(self,
                                    dataset: Dataset,
                                    **training_kwargs) -> Dict[str, Any]:
        """
        Continued pre-training on large text corpus.
        Used for major capability upgrades, not frequent knowledge updates.
        """
        if self.model is None or self.tokenizer is None:
            print("Error: Model not loaded.")
            return {}
        
        self.is_training = True
        start_time = datetime.now()
        
        try:
            from transformers import Trainer, TrainingArguments
            
            training_args = self.prepare_training_args(**training_kwargs)
            
            trainer = Trainer(
                model=self.model,
                args=training_args,
                train_dataset=dataset,
                tokenizer=self.tokenizer,
            )
            
            print("Starting continued pre-training...")
            trainer.train()
            
            end_time = datetime.now()
            training_duration = (end_time - start_time).total_seconds() / 60
            
            # Save
            save_path = self.output_dir / "shark_continued_pretrained"
            self.model.save_pretrained(save_path)
            self.tokenizer.save_pretrained(save_path)
            
            print(f"Continued pre-training complete. Saved to {save_path}")
            print(f"Duration: {training_duration:.1f} minutes")
            
            history_entry = {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_minutes": training_duration,
                "train_samples": len(dataset),
                "type": "continued_pretraining",
                "status": "completed",
            }
            self.training_history.append(history_entry)
            
            return {
                "status": "success",
                "model_path": str(save_path),
                "duration_minutes": training_duration,
            }
            
        except Exception as e:
            print(f"Error during continued pre-training: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "failed", "error": str(e)}
        
        finally:
            self.is_training = False
    
    def merge_and_save(self, 
                       output_path: str = None) -> str:
        """
        Merge LoRA adapters with base model and save.
        Useful for deployment where PEFT overhead is unwanted.
        """
        if self.model is None:
            print("Error: No model loaded.")
            return ""
        
        save_path = output_path or str(self.output_dir / "shark_deployed")
        
        try:
            from peft import PeftModel
            
            # Load base model and merge
            base_model_name = self.model_name
            
            # Load base
            base_model = AutoModelForCausalLM.from_pretrained(
                base_model_name,
                low_cpu_mem_usage=True,
                return_dict=True,
                torch_dtype=torch.float16,
                device_map="auto",
            )
            
            # Load and merge LoRA
            merged_model = PeftModel.from_pretrained(
                base_model, save_path if output_path else str(self.output_dir / "shark_lora_adapter")
            )
            
            # Merge and unload
            merged_model = merged_model.merge_and_unload()
            
            # Save merged model
            merged_save_path = save_path if output_path else str(self.output_dir / "shark_merged")
            merged_model.save_pretrained(merged_save_path)
            self.tokenizer.save_pretrained(merged_save_path)
            
            print(f"Merged model saved to {merged_save_path}")
            return merged_save_path
            
        except Exception as e:
            print(f"Error merging model: {e}")
            return ""


class DataValidator:
    """
    Validates and cleans cybersecurity datasets for training.
    Ensures quality, checks licenses, removes problematic content.
    """
    
    @staticmethod
    def validate_record(record: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate a single training record. Returns (is_valid, reason)."""
        
        # Check content exists
        content = record.get("content", "").strip()
        if not content:
            return False, "Empty content"
        
        # Check minimum length
        if len(content) < 20:
            return False, "Content too short (< 20 chars)"
        
        # Check for problematic patterns
        problematic_patterns = [
            r'(?i)password\s*[:=]\s*["\'][^"\']{4,}["\']',  # Hardcoded passwords
            r'(?i)secret\s*[:=]\s*["\'][^"\']{4,}["\']',    # Hardcoded secrets
            r'(?i)api.key\s*[:=]\s*["\'][^"\']{10,}["\']',  # API keys
            r'(?i)token\s*[:=]\s*["\'][^"\']{20,}["\']',    # Tokens
        ]
        
        for pattern in problematic_patterns:
            if re.search(pattern, content):
                return False, f"Contains problematic pattern: {pattern.pattern}"
        
        # Check for malware indicators (basic)
        malware_keywords = ["ransomware", "malware", "exploit code", "shellcode"]
        content_lower = content.lower()
        if any(kw in content_lower for kw in malware_keywords):
            # Warning but not blocking - malware analysis is valid
            pass  # Could add logging here
        
        # Check for injection patterns
        injection_patterns = [r'(?i)<script[^>]*>', r'(?i)javascript:', r'(?i)data:text/html']
        if any(re.search(p, content) for p in injection_patterns):
            return False, "Contains potential injection patterns"
        
        return True, "Valid"
    
    @staticmethod
    def validate_dataset(records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate entire dataset and return report."""
        report = {
            "total_records": len(records),
            "valid_records": 0,
            "invalid_records": 0,
            "issues": [],
            "license_checks": {},
        }
        
        for i, record in enumerate(records):
            is_valid, reason = DataValidator.validate_record(record)
            if is_valid:
                report["valid_records"] += 1
            else:
                report["invalid_records"] += 1
                report["issues"].append({
                    "index": i,
                    "reason": reason,
                    "content_preview": record.get("content", "")[:80] + "..." if len(record.get("content", "")) > 80 else record.get("content", "")[:80],
                })
            
            # Track license
            license_val = record.get("metadata", {}).get("license", "unknown")
            report["license_checks"][license_val] = \
                report["license_checks"].get(license_val, 0) + 1
        
        return report
    
    @staticmethod
    def clean_dataset(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Clean dataset by removing invalid records and standardizing format."""
        cleaned = []
        
        for record in records:
            is_valid, reason = DataValidator.validate_record(record)
            if is_valid:
                # Standardize the record format
                standardized = {
                    "id": record.get("id", hashlib.sha256(
                        f"{record.get('content', '')}{datetime.now()}".encode()
                    ).hexdigest()),
                    "content": record["content"].strip(),
                    "metadata": record.get("metadata", {}),
                    "source": record.get("source", "unknown"),
                    "category": record.get("category", "general"),
                    "license": record.get("license", "requires_review"),
                    "created": record.get("created", datetime.now().isoformat()),
                }
                cleaned.append(standardized)
        
        return cleaned


# Example usage
if __name__ == "__main__":
    print("=== SHARK AI Training Pipeline ===\n")
    
    # Initialize pipeline
    pipeline = TrainingPipeline(model_name="ollama/shark:latest")
    
    # Load model
    print("Loading SHARK model...")
    success = pipeline.load_model(load_in_4bit=True)
    if not success:
        print("Could not load model - exiting.")
        exit(1)
    
    # Create sample dataset
    print("\nCreating sample training dataset...")
    sample_records = [
        {
            "id": "example_1",
            "content": "How to perform vulnerability assessment on web applications?",
            "metadata": {"source": "security_guide", "category": "vuln", "license": "cc-by-4.0"},
            "source": "security_guide",
            "category": "vuln",
            "license": "cc-by-4.0",
            "created": datetime.now().isoformat(),
        },
        {
            "id": "example_2",
            "content": "Explain the MITRE ATT&CK T1566 technique for spearphishing.",
            "metadata": {"source": "mitre_attack", "category": "attack", "license": "public-domain"},
            "source": "mitre_attack",
            "category": "attack",
            "license": "public-domain",
            "created": datetime.now().isoformat(),
        },
        {
            "id": "example_3",
            "content": "OWASP Top Ten A01:2021 - Broken Access Control explanation.",
            "metadata": {"source": "owsawa", "category": "owasp", "license": "cc-by-4.0"},
            "source": "owsawa",
            "category": "owasp",
            "license": "cc-by-4.0",
            "created": datetime.now().isoformat(),
        },
    ]
    
    # Create dataset
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained("ollama/shark:latest", trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    dataset = CybersecurityDataset(sample_records, tokenizer, max_length=512)
    print(f"Created dataset with {len(dataset)} examples")
    
    # Quick test - show first example
    if len(dataset) > 0:
        sample = dataset[0]
        print(f"\nSample input_ids shape: {sample['input_ids'].shape}")
        print(f"Sample attention_mask shape: {sample['attention_mask'].shape}")
        print(f"Sample labels shape: {sample['labels'].shape}")