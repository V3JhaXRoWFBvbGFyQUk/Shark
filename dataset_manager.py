#!/usr/bin/env python3
"""
SHARK AI Dataset Manager
Handles import, normalization, validation, deduplication, and versioning of
external cybersecurity datasets for RAG and training pipelines.
"""

import json
import os
import re
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

import pandas as pd


class DatasetInfo:
    """Metadata for a dataset."""
    
    def __init__(
        self,
        name: str,
        source: str,
        format_type: str,
        size: int,
        license: str,
        provenance: Dict[str, Any],
        categories: Set[str],
        created: Optional[datetime] = None,
        modified: Optional[datetime] = None,
        dataset_id: Optional[str] = None,
    ):
        self.name = name
        self.source = source
        self.format_type = format_type
        self.size = size
        self.license = license
        self.provenance = provenance
        self.categories = categories
        self.created = created or datetime.now()
        self.modified = modified or datetime.now()
        self.dataset_id = dataset_id or hashlib.sha256(
            f"{name}{source}{format_type}".encode()
        ).hexdigest()[:16]


class DatasetRecord:
    """Record of a single data entry with provenance."""
    
    def __init__(
        self,
        id: str,
        content: str,
        metadata: Dict[str, Any],
        source: str,
        category: str,
        license: str,
        chunk_id: Optional[str] = None,
    ):
        self.id = id
        self.content = content
        self.metadata = metadata
        self.source = source
        self.category = category
        self.license = license
        self.chunk_id = chunk_id or str(uuid.uuid4())[:8]


class DatasetManager:
    """
    Manager for SHARK's external knowledge datasets.
    
    Supports:
    - Import from multiple sources (Hugging Face, GitHub, CVE, NVD, local files, URLs)
    - Format normalization (JSON, JSONL, CSV, TXT, PDF, Parquet)
    - Validation and cleaning
    - Duplicate removal
    - License tracking and provenance
    - Categorization of cybersecurity information
    - Dataset versioning
    - Quality reporting
    - Dataset selection for training or RAG
    """
    
    def __init__(self, base_dir: str = "datasets"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        
        # Dataset metadata registry
        self.registry_path = self.base_dir / "registry.json"
        self.registry: Dict[str, DatasetInfo] = {}
        self._load_registry()
        
        # Records storage
        self.records_dir = self.base_dir / "records"
        self.records_dir.mkdir(exist_ok=True)
        
        # Categories definition
        self.cyber_categories = {
            "cve": "Common Vulnerabilities and Exposures",
            "nvd": "National Vulnerability Database",
            "attack": "MITRE ATT&CK",
            "kev": "CISA Known Exploited Vulnerabilities",
            "owasp": "OWASP Top Ten / Projects",
            "research": "Security research publications",
            "github": "GitHub security repositories",
            "tool": "Security tools and scripts",
            "malware": "Malware analysis and samples",
            "vuln": "Vulnerability patterns and exploitation",
            "defensive": "Defensive security and mitigation",
            "ctf": "CTF challenges and writeups",
        }
        
        # Available datasets for selection
        self.available_datasets: List[str] = []
        
    def _load_registry(self):
        """Load the dataset registry from disk."""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.registry = {
                    k: DatasetInfo(**v) for k, v in data.get("datasets", {}).items()
                }
                self.available_datasets = data.get("available_datasets", [])
            except Exception as e:
                print(f"Warning: Could not load registry: {e}")
                self.registry = {}
                self.available_datasets = []
    
    def _save_registry(self):
        """Save the dataset registry to disk."""
        data = {
            "datasets": {
                k: {
                    "name": v.name,
                    "source": v.source,
                    "format_type": v.format_type,
                    "size": v.size,
                    "license": v.license,
                    "provenance": v.provenance,
                    "categories": list(v.categories),
                    "created": v.created.isoformat(),
                    "modified": v.modified.isoformat(),
                    "dataset_id": v.dataset_id,
                } for k, v in self.registry.items()
            },
            "available_datasets": self.available_datasets,
        }
        with open(self.registry_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    # ---- Import Methods ----
    
    def import_huggingface(self, dataset_name: str, split: str = "train") -> DatasetInfo:
        """Import from Hugging Face datasets."""
        try:
            from datasets import load_dataset
            ds = load_dataset(dataset_name, split=split)
            
            # Convert to records
            records = []
            for i, example in enumerate(ds):
                content = json.dumps(example) if isinstance(example, dict) else str(example)
                record = DatasetRecord(
                    id=f"hf_{dataset_name}_{i}",
                    content=content,
                    metadata={"hf_dataset": dataset_name, "index": i},
                    source=f"huggingface:{dataset_name}",
                    category=self._categorize_content(content),
                    license=self._detect_license(dataset_name, example),
                )
                records.append(record)
            
            dataset_name_safe = dataset_name.replace("/", "_")
            di = DatasetInfo(
                name=dataset_name,
                source=f"huggingface:{dataset_name}",
                format_type="huggingface",
                size=len(records),
                license="check_hf_license",  # To be verified
                provenance={"type": "huggingface", "dataset": dataset_name, "split": split},
                categories={self._categorize_content(r.content) for r in records[:5]},
            )
            
            self._register_dataset(dataset_name_safe, di)
            self._save_records(records, f"hf_{dataset_name_safe}")
            return di
            
        except ImportError:
            print("Error: 'datasets' library not installed. Install with: pip install datasets")
            raise
        except Exception as e:
            print(f"Error importing from Hugging Face: {e}")
            raise
    
    def import_github_repo(self, repo_url: str, branch: str = "main", 
                           path_filter: Optional[str] = None) -> DatasetInfo:
        """Import security-related files from a GitHub repository."""
        import urllib.request
        
        # Parse repo URL
        match = re.match(r'https?://github.com/([^/]+)/([^/]+)', repo_url)
        if not match:
            raise ValueError(f"Invalid GitHub URL: {repo_url}")
        
        owner, name = match.groups()
        api_url = f"https://api.github.com/repos/{owner}/{name}/contents"
        
        records = []
        seen_contents = set()
        
        try:
            # Get directory listing
            with urllib.request.urlopen(api_url) as response:
                contents = json.load(response)
            
            def process_items(items, depth=0):
                if depth > 3:  # Max depth 3
                    return
                
                for item in items:
                    if item["type"] == "file":
                        filename = item["name"]
                        # Filter by path if specified
                        if path_filter and not filename.startswith(path_filter):
                            continue
                        
                        # Only process common text/format files
                        if not any(filename.endswith(ext) for ext in [
                            '.json', '.jsonl', '.csv', '.txt', '.py', '.sh', '.yml', '.yaml'
                        ]):
                            continue
                        
                        try:
                            # Download file content
                            file_path = item["path"]
                            raw_url = item["download_url"]
                            
                            with urllib.request.urlopen(raw_url) as f:
                                raw_content = f.read().decode('utf-8', errors='replace')
                            
                            # Parse based on format
                            if filename.endswith('.json'):
                                try:
                                    parsed = json.loads(raw_content)
                                    content = json.dumps(parsed, ensure_ascii=False)
                                except:
                                    content = raw_content
                            elif filename.endswith('.csv'):
                                df = pd.read_csv(io.StringIO(raw_content))
                                content = df.to_json(orient="records")
                            elif filename.endswith('.jsonl'):
                                lines = raw_content.strip().split('\n')
                                records_list = []
                                for line in lines:
                                    try:
                                        records_list.append(json.loads(line))
                                    except:
                                        pass
                                content = json.dumps(records_list, ensure_ascii=False)
                            else:
                                content = raw_content
                            
                            # Content hash for dedup
                            content_hash = hashlib.sha256(content.encode()).hexdigest()
                            if content_hash in seen_contents:
                                continue
                            seen_contents.add(content_hash)
                            
                            record = DatasetRecord(
                                id=f"github_{owner}_{name}_{filename}_{content_hash[:8]}",
                                content=content,
                                metadata={
                                    "source": "github",
                                    "repo": repo_url,
                                    "file": filename,
                                    "depth": depth,
                                },
                                source=repo_url,
                                category=self._categorize_content(content),
                                license=self._check_github_license(repo_url, filename),
                            )
                            records.append(record)
                            
                        except Exception as e:
                            print(f"Warning: Could not process {filename}: {e}")
                            continue
                    
                    if item["type"] == "dir":
                        # Recursively process subdirectories
                        try:
                            with urllib.request.urlopen(item["url"]) as resp:
                                sub_contents = json.load(resp)
                            process_items(sub_contents, depth + 1)
                        except:
                            continue
            
            process_items(contents)
            
            dataset_name = f"github_{owner}_{name}"
            category = self._categorize_content("\n".join([r.content[:200] for r in records[:5]]))
            
            di = DatasetInfo(
                name=repo_url,
                source=repo_url,
                format_type="github_repo",
                size=len(records),
                license="check_github_repo_license",
                provenance={"type": "github", "repo": repo_url, "branch": branch},
                categories={category},
            )
            
            self._register_dataset(dataset_name, di)
            self._save_records(records, f"github_{owner}_{name.replace('/', '_')}")
            return di
            
        except Exception as e:
            print(f"Error importing from GitHub: {e}")
            raise
    
    def import_cve_data(self, cve_ids: Optional[List[str]] = None) -> DatasetInfo:
        """Import CVE data from NVD or other CVE sources."""
        # In a real implementation, this would query NVD API or use cached data
        # For now, we'll create a framework that can load CVE data
        
        records = []
        
        if cve_ids:
            # Specific CVE IDs requested
            for cve_id in cve_ids:
                # Placeholder - in production would query NVD API
                record = DatasetRecord(
                    id=f"cve_{cve_id}",
                    content=f"CVE {cve_id}: Placeholder CVE data - would be fetched from NVD API",
                    metadata={"source": "nvd", "cve_id": cve_id, "type": "cve_placeholder"},
                    source="nvd",
                    category="cve",
                    license="nvd_dataset_license",
                )
                records.append(record)
        else:
            # Bulk import framework - would integrate with NVD API
            record = DatasetRecord(
                id="cve_bulk_framework",
                content="CVE bulk import framework - integrate with NVD API or use cached NVD JSON datasets",
                metadata={"source": "nvd", "type": "bulk_import_framework"},
                source="nvd",
                category="cve",
                license="nvd_dataset_license",
            )
            records.append(record)
        
        dataset_name = "cve_data"
        di = DatasetInfo(
            name="CVE Data",
            source="nvd_api_or_cache",
            format_type="cve_json",
            size=len(records),
            license="nvd_dataset_license",
            provenance={"type": "nvd", "method": "api_or_cache"},
            categories={"cve"},
        )
        
        self._register_dataset(dataset_name, di)
        self._save_records(records, f"cve_{dataset_name}")
        return di
    
    def import_kev_database(self) -> DatasetInfo:
        """Import CISA Known Exploited Vulnerabilities database."""
        # Framework for KEV import - would integrate with CISA API
        records = [
            DatasetRecord(
                id="kev_framework",
                content="CISA KEV database import framework - integrates with https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
                metadata={"source": "cisa_kev", "type": "import_framework"},
                source="cisa_kev",
                category="kev",
                license="cisa_kev_license",
            )
        ]
        
        dataset_name = "kev_database"
        di = DatasetInfo(
            name="CISA KEV Database",
            source="cisa_kev",
            format_type="kev_json",
            size=len(records),
            license="cisa_kev_license",
            provenance={"type": "cisa_kev"},
            categories={"kev"},
        )
        
        self._register_dataset(dataset_name, di)
        self._save_records(records, f"kev_{dataset_name}")
        return di
    
    def import_owsawa_resources(self, resource_type: str = "top_ten") -> DatasetInfo:
        """Import OWASP resources."""
        records = []
        
        if resource_type == "top_ten":
            record = DatasetRecord(
                id="owsawa_top_ten",
                content="OWASP Top Ten 2021/2024 - framework for web application security risks",
                metadata={"source": "owsawa", "resource": "top_ten", "type": "framework"},
                source="owsawa",
                category="owasp",
                license="owsawa_license",
            )
            records.append(record)
        
        dataset_name = f"owsawa_{resource_type}"
        di = DatasetInfo(
            name=f"OWASP {resource_type}",
            source="owsawa",
            format_type="owsawa_text",
            size=len(records),
            license="owsawa_license",
            provenance={"type": "owsawa", "resource": resource_type},
            categories={"owasp"},
        )
        
        self._register_dataset(dataset_name, di)
        self._save_records(records, f"owsawa_{dataset_name}")
        return di
    
    def import_local_file(self, file_path: str) -> DatasetInfo:
        """Import data from a local file (JSON, JSONL, CSV, TXT, PDF, Parquet)."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        format_type = file_path.suffix.lower()
        records = []
        
        try:
            if format_type == '.json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for i, item in enumerate(data):
                        content = json.dumps(item, ensure_ascii=False) if not isinstance(item, str) else item
                        record = DatasetRecord(
                            id=f"local_{file_path.name}_{i}",
                            content=content,
                            metadata={"source": "local", "file": str(file_path), "index": i},
                            source=str(file_path),
                            category=self._categorize_content(content),
                            license=self._detect_local_license(file_path),
                        )
                        records.append(record)
                else:
                    # Single document
                    record = DatasetRecord(
                        id=f"local_{file_path.name}",
                        content=json.dumps(data, ensure_ascii=False),
                        metadata={"source": "local", "file": str(file_path), "type": "json_object"},
                        source=str(file_path),
                        category=self._categorize_content(json.dumps(data)),
                        license=self._detect_local_license(file_path),
                    )
                    records.append(record)
            
            elif format_type == '.jsonl':
                with open(file_path, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            content = json.dumps(data, ensure_ascii=False)
                            record = DatasetRecord(
                                id=f"local_{file_path.name}_{i}",
                                content=content,
                                metadata={"source": "local", "file": str(file_path), "index": i},
                                source=str(file_path),
                                category=self._categorize_content(content),
                                license=self._detect_local_license(file_path),
                            )
                            records.append(record)
                        except json.JSONDecodeError:
                            # Treat as raw text
                            record = DatasetRecord(
                                id=f"local_{file_path.name}_{i}",
                                content=line,
                                metadata={"source": "local", "file": str(file_path), "index": i, "raw": True},
                                source=str(file_path),
                                category=self._categorize_content(line),
                                license=self._detect_local_license(file_path),
                            )
                            records.append(record)
            
            elif format_type == '.csv':
                df = pd.read_csv(file_path)
                for i, row in df.iterrows():
                    content = json.dumps(row.to_dict(), ensure_ascii=False)
                    record = DatasetRecord(
                        id=f"local_{file_path.name}_{i}",
                        content=content,
                        metadata={"source": "local", "file": str(file_path), "index": i},
                        source=str(file_path),
                        category=self._categorize_content(content),
                        license=self._detect_local_license(file_path),
                    )
                    records.append(record)
            
            elif format_type == '.txt':
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                
                # Split by paragraphs or large chunks
                chunks = self._chunk_text(content, max_size=5000)
                for i, chunk in enumerate(chunks):
                    record = DatasetRecord(
                        id=f"local_{file_path.name}_{i}",
                        content=chunk,
                        metadata={"source": "local", "file": str(file_path), "chunk": i},
                        source=str(file_path),
                        category=self._categorize_content(chunk),
                        license=self._detect_local_license(file_path),
                    )
                    records.append(record)
            
            elif format_type == '.pdf':
                # PDF processing - would use pymupdf or pdfminer
                try:
                    import fitz  # pymupdf
                    doc = fitz.open(file_path)
                    full_text = ""
                    for page in doc:
                        full_text += page.get_text()
                    
                    chunks = self._chunk_text(full_text, max_size=5000)
                    for i, chunk in enumerate(chunks):
                        record = DatasetRecord(
                            id=f"local_{file_path.name}_{i}",
                            content=chunk,
                            metadata={"source": "local", "file": str(file_path), "chunk": i, "format": "pdf"},
                            source=str(file_path),
                            category=self._categorize_content(chunk),
                            license=self._detect_local_license(file_path),
                        )
                        records.append(record)
                except ImportError:
                    print("Warning: pymupdf not installed. PDF processing skipped.")
                    # Fall back to treating as text
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                    chunks = self._chunk_text(content, max_size=5000)
                    for i, chunk in enumerate(chunks):
                        record = DatasetRecord(
                            id=f"local_{file_path.name}_{i}",
                            content=chunk,
                            metadata={"source": "local", "file": str(file_path), "chunk": i, "format": "pdf_fallback"},
                            source=str(file_path),
                            category=self._categorize_content(chunk),
                            license=self._detect_local_license(file_path),
                        )
                        records.append(record)
            
            elif format_type == '.parquet':
                import pyarrow.parquet as pq
                table = pq.read_table(file_path)
                df = table.to_pandas()
                for i, row in df.iterrows():
                    content = json.dumps(row.to_dict(), ensure_ascii=False)
                    record = DatasetRecord(
                        id=f"local_{file_path.name}_{i}",
                        content=content,
                        metadata={"source": "local", "file": str(file_path), "index": i, "format": "parquet"},
                        source=str(file_path),
                        category=self._categorize_content(content),
                        license=self._detect_local_license(file_path),
                    )
                    records.append(record)
            
            else:
                raise ValueError(f"Unsupported file format: {format_type}")
            
            # Deduplicate
            records = self._deduplicate_records(records)
            
            dataset_name = file_path.stem
            di = DatasetInfo(
                name=file_path.name,
                source=str(file_path),
                format_type=format_type.lstrip('.'),
                size=len(records),
                license=self._detect_local_license(file_path),
                provenance={"type": "local", "path": str(file_path)},
                categories={r.category for r in records[:5]},
            )
            
            self._register_dataset(dataset_name, di)
            self._save_records(records, f"local_{dataset_name}")
            return di
            
        except Exception as e:
            print(f"Error importing local file: {e}")
            raise
    
    def import_custom_url(self, url: str) -> DatasetInfo:
        """Import data from a custom URL."""
        import urllib.request
        import io
        
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                content_type = response.headers.get('Content-Type', '')
                raw_content = response.read().decode('utf-8', errors='replace')
            
            # Determine format and process accordingly
            records = []
            
            if 'application/json' in content_type:
                data = json.loads(raw_content)
                if isinstance(data, list):
                    for i, item in enumerate(data):
                        content = json.dumps(item, ensure_ascii=False) if not isinstance(item, str) else item
                        record = DatasetRecord(
                            id=f"url_{hashlib.sha256(url.encode()).hexdigest()[:8]}_{i}",
                            content=content,
                            metadata={"source": "url", "url": url, "index": i},
                            source=url,
                            category=self._categorize_content(content),
                            license="unknown",  # Would need user confirmation
                        )
                        records.append(record)
                else:
                    record = DatasetRecord(
                        id=f"url_{hashlib.sha256(url.encode()).hexdigest()[:8]}",
                        content=json.dumps(data, ensure_ascii=False),
                        metadata={"source": "url", "url": url, "type": "json_object"},
                        source=url,
                        category=self._categorize_content(json.dumps(data)),
                        license="unknown",
                    )
                    records.append(record)
            
            elif 'text/' in content_type or 'csv' in content_type:
                # Text/CSV content
                lines = raw_content.strip().split('\n')
                seen = set()
                for i, line in enumerate(lines):
                    if line.strip() and line.strip() not in seen:
                        seen.add(line.strip())
                        record = DatasetRecord(
                            id=f"url_{hashlib.sha256(url.encode()).hexdigest()[:8]}_{i}",
                            content=line.strip(),
                            metadata={"source": "url", "url": url, "index": i},
                            source=url,
                            category=self._categorize_content(line.strip()),
                            license="unknown",
                        )
                        records.append(record)
            
            else:
                # Unknown format - try as JSON first, then raw text
                try:
                    data = json.loads(raw_content)
                    record = DatasetRecord(
                        id=f"url_{hashlib.sha256(url.encode()).hexdigest()[:8]}",
                        content=json.dumps(data, ensure_ascii=False),
                        metadata={"source": "url", "url": url, "type": "json_unknown"},
                        source=url,
                        category=self._categorize_content(json.dumps(data)),
                        license="unknown",
                    )
                    records.append(record)
                except:
                    # Raw text
                    record = DatasetRecord(
                        id=f"url_{hashlib.sha256(url.encode()).hexdigest()[:8]}",
                        content=raw_content,
                        metadata={"source": "url", "url": url},
                        source=url,
                        category=self._categorize_content(raw_content),
                        license="unknown",
                    )
                    records.append(record)
            
            dataset_name = f"custom_{hashlib.sha256(url.encode()).hexdigest()[:8]}"
            di = DatasetInfo(
                name=f"Custom URL: {url[:50]}",
                source=url,
                format_type="custom",
                size=len(records),
                license="user_approved",  # User must confirm
                provenance={"type": "url", "url": url},
                categories={r.category for r in records[:3]},
            )
            
            self._register_dataset(dataset_name, di)
            self._save_records(records, f"custom_{dataset_name}")
            return di
            
        except Exception as e:
            print(f"Error importing from URL: {e}")
            raise
    
    # ---- Data Processing ----
    
    def _categorize_content(self, content: str) -> str:
        """Automatically categorize cybersecurity content."""
        content_lower = content.lower()
        
        category_keywords = {
            "cve": ["cve-", "cve ", "vulnerability", "cve id"],
            "nvd": ["nvd", "national vulnerability"],
            "attack": ["att&ck", "attck", "mitre", "tactics", "techniques"],
            "kev": ["known exploited", "kev", "cisa"],
            "owasp": ["owasp", "top ten", "web security"],
            "research": ["research", "paper", "study", "analysis"],
            "github": ["github", "repository", "code", "repo"],
            "tool": ["tool", "script", "utility", "utility"],
            "malware": ["malware", "virus", "trojan", "ransomware"],
            "vuln": ["vulnerability", "exploit", "patch"],
            "defensive": ["defensive", "mitigation", "detection", "response"],
            "ctf": ["ctf", "capture the flag", "writeup"],
        }
        
        # Score each category
        scores = {}
        for cat, keywords in category_kwargs.items():
            score = sum(1 for kw in keywords if kw in content_lower)
            if score > 0:
                scores[cat] = score
        
        if scores:
            return max(scores, key=scores.get)
        return "general"
    
    def _chunk_text(self, text: str, max_size: int = 5000) -> List[str]:
        """Split text into chunks of approximately max_size characters."""
        if len(text) <= max_size:
            return [text]
        
        chunks = []
        start = 0
        while start < len(text):
            end = start + max_size
            # Try to break at sentence boundary
            if end < len(text):
                # Look for last period before end
                last_period = text.rfind('.', start, end)
                if last_period > start + max_size // 2:
                    end = last_period + 1
            
            chunks.append(text[start:end].strip())
            start = end
        
        # Filter empty chunks
        chunks = [c for c in chunks if c.strip()]
        return chunks
    
    def _deduplicate_records(self, records: List[DatasetRecord]) -> List[DatasetRecord]:
        """Remove duplicate records based on content hash."""
        seen_hashes = set()
        unique_records = []
        
        for record in records:
            content_hash = hashlib.sha256(record.content.encode()).hexdigest()
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                record.id = f"dedup_{content_hash[:8]}"
                unique_records.append(record)
        
        return unique_records
    
    def _detect_license(self, *args) -> str:
        """Detect license for imported data - placeholder for actual license detection."""
        return "requires_review"
    
    def _detect_local_license(self, file_path: Path) -> str:
        """Detect license from local file."""
        # Check for license file in same directory
        license_path = file_path.parent / "LICENSE"
        if license_path.exists():
            with open(license_path, 'r', encoding='utf-8') as f:
                content = f.read().lower()
            if "opensource" in content or "mit license" in content:
                return "mit"
            if "apache" in content:
                return "apache-2.0"
            if "gpl" in content:
                return "gpl-3.0"
        return "requires_review"
    
    def _check_github_license(self, repo_url: str, filename: str) -> str:
        """Check GitHub repository license."""
        # Framework - would fetch from GitHub API
        return "requires_review"
    
    # ---- Registry Management ----
    
    def _register_dataset(self, name: str, di: DatasetInfo):
        """Register a dataset in the registry."""
        # Check for conflicts
        if name in self.registry:
            print(f"Warning: Dataset '{name}' already being registered. Overwriting.")
        
        self.registry[name] = di
        self.available_datasets.append(name)
        self._save_registry()
    
    def _save_records(self, records: List[DatasetRecord], prefix: str):
        """Save dataset records to disk."""
        records_path = self.records_dir / f"{prefix}.json"
        records_data = []
        
        for record in records:
            record_dict = {
                "id": record.id,
                "content": record.content,
                "metadata": record.metadata,
                "source": record.source,
                "category": record.category,
                "license": record.license,
                "chunk_id": record.chunk_id,
            }
            records_data.append(record_dict)
        
        with open(records_path, 'w', encoding='utf-8') as f:
            json.dump(records_data, f, indent=2)
    
    def _load_records(self, prefix: str) -> List[DatasetRecord]:
        """Load dataset records from disk."""
        records_path = self.records_dir / f"{prefix}.json"
        if not records_path.exists():
            return []
        
        try:
            with open(records_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            records = []
            for item in data:
                record = DatasetRecord(
                    id=item["id"],
                    content=item["content"],
                    metadata=item["metadata"],
                    source=item["source"],
                    category=item["category"],
                    license=item["license"],
                    chunk_id=item.get("chunk_id"),
                )
                records.append(record)
            return records
        except Exception as e:
            print(f"Warning: Could not load records: {e}")
            return []
    
    # ---- Dataset Selection & Quality ----
    
    def list_datasets(self) -> List[Dict[str, Any]]:
        """List all registered datasets with metadata."""
        result = []
        for name, di in self.registry.items():
            result.append({
                "name": di.name,
                "source": di.source,
                "format": di.format_type,
                "size": di.size,
                "license": di.license,
                "categories": list(di.categories),
                "dataset_id": di.dataset_id,
                "created": di.created.isoformat(),
                "modified": di.modified.isoformat(),
            })
        return result
    
    def get_dataset(self, name: str) -> Optional[Tuple[DatasetInfo, List[DatasetRecord]]]:
        """Get dataset info and records by name."""
        if name not in self.registry:
            print(f"Dataset '{name}' not found in registry.")
            return None
        
        records = self._load_records(name)
        return self.registry[name], records
    
    def remove_dataset(self, name: str) -> bool:
        """Remove a dataset from the registry and disk."""
        if name not in self.registry:
            print(f"Dataset '{name}' not found.")
            return False
        
        # Remove records file
        records_path = self.records_dir / f"{name}.json"
        if records_path.exists():
            records_path.unlink()
        
        # Remove from registry
        del self.registry[name]
        if name in self.available_datasets:
            self.available_datasets.remove(name)
        
        self._save_registry()
        print(f"Dataset '{name}' removed.")
        return True
    
    def generate_quality_report(self, name: str) -> Dict[str, Any]:
        """Generate a quality report for a dataset."""
        info, records = self.get_dataset(name)
        if not info:
            return {}
        
        if not records:
            records = self._load_records(name)
        
        if not records:
            return {"error": "No records found"}
        
        # Basic statistics
        total_records = len(records)
        total_chars = sum(len(r.content) for r in records)
        avg_chars = total_chars / total_records if total_records > 0 else 0
        
        # Category distribution
        category_counts = {}
        for r in records:
            cat = r.category
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        # License info
        license_counts = {}
        for r in records:
            lic = r.license
            license_counts[lic] = license_counts.get(lic, 0) + 1
        
        # Source distribution
        source_counts = {}
        for r in records:
            src = r.source
            source_counts[src] = source_counts.get(src, 0) + 1
        
        # Duplicate detection
        content_hashes = [hashlib.sha256(r.content.encode()).hexdigest() for r in records]
        unique_hashes = set(content_hashes)
        duplicates = total_records - len(unique_hashes)
        
        # Word count analysis
        all_text = " ".join(r.content for r in records)
        words = len(all_text.split())
        
        return {
            "dataset_name": info.name,
            "total_records": total_records,
            "total_characters": total_chars,
            "average_characters_per_record": round(avg_chars, 2),
            "word_count": words,
            "category_distribution": category_counts,
            "license_distribution": license_counts,
            "source_distribution": source_counts,
            "duplicate_count": duplicates,
            "duplicate_percentage": round(duplicates / total_records * 100, 2) if total_records > 0 else 0,
            "unique_content_fraction": round(len(unique_hashes) / total_records, 2) if total_records > 0 else 0,
            "date_range": {
                "earliest": min(r.metadata.get("created", datetime.now()) for r in records),
                "latest": max(r.metadata.get("created", datetime.now()) for r in records),
            },
            "quality_score": self._calculate_quality_score(
                total_records, duplicates, len(unique_hashes), category_counts
            ),
        }
    
    def _calculate_quality_score(self, total_records, duplicates, unique_count, category_counts) -> float:
        """Calculate a quality score for the dataset (0-100)."""
        score = 100.0
        
        # Penalize duplicates
        if total_records > 0:
            dedup_penalty = duplicates / total_records * 30
            score -= dedup_penalty
        
        # Reward diverse categories
        category_diversity = len(category_counts) / 12  # 12 possible cyber categories
        score += min(category_diversity * 10, 15)
        
        # Penalize very low record count
        if total_records < 10:
            score -= 20
        elif total_records < 100:
            score -= 10
        
        # Penalize unknown licenses
        unknown_licenses = sum(1 for r in records if r.license in ["unknown", "requires_review"])
        if total_records > 0 and unknown_licenses / total_records > 0.5:
            score -= 20
        
        return max(min(score, 100.0), 0.0)
    
    def approve_dataset_for_training(self, name: str) -> bool:
        """
        Get user approval for using a dataset in training.
        Checks license and provenance before approval.
        """
        if name not in self.registry:
            print(f"Dataset '{name}' not found.")
            return False
        
        di = self.registry[name]
        
        print(f"\n=== Dataset Approval: {di.name} ===")
        print(f"Source: {di.source}")
        print(f"License: {di.license}")
        print(f"Categories: {list(di.categories)}")
        print(f"Records: {di.size}")
        print(f"Provenance: {di.provenance}")
        
        # Simple approval check - in production would prompt user
        if di.license in ["requires_review", "unknown"]:
            print("⚠️  License requires review before training approval.")
            print("   Please verify the license is compatible with model training.")
            approval = input("Approve anyway? (y/N): ").strip().lower()
            return approval in ['y', 'yes']
        
        print("✅ Dataset approved for training.")
        return True


# Example usage
if __name__ == "__main__":
    print("=== SHARK AI Dataset Manager ===\n")
    
    manager = DatasetManager()
    
    # Example: List available datasets (should be empty initially)
    print("Registered datasets:")
    datasets = manager.list_datasets()
    for ds in datasets:
        print(f"  - {ds['name'][:60]}...")
    
    # Example: Import a local file (if exists)
    datasets_dir = Path("datasets")
    if datasets_dir.exists():
        for f in datasets_dir.iterdir():
            if f.is_file() and f.suffix.lower() in ['.json', '.jsonl', '.csv', '.txt']:
                print(f"\nImporting {f.name}...")
                try:
                    di = manager.import_local_file(str(f))
                    print(f"  Imported: {di.name}, {di.size} records, license: {di.license}")
                except Exception as e:
                    print(f"  Error: {e}")
    
    # Generate quality report
    print(f"\n=== Dataset Quality Reports ===")
    for name in manager.available_datasets:
        report = manager.generate_quality_report(name)
        if "error" not in report:
            print(f"\n{report['dataset_name']}:")
            print(f"  Quality Score: {report['quality_score']}/100")
            print(f"  Records: {report['total_records']}")
            print(f"  Duplicates: {report['duplicate_count']} ({report['duplicate_percentage']}%)")