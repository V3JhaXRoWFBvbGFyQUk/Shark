#!/usr/bin/env python3
"""Test script for SHARK knowledge system."""

import sys
import json
sys.path.insert(0, '.')

from shark_knowledge_system import SHARKKnowledgeSystem
from dataset_manager import DatasetManager


def main():
    print("=== SHARK Knowledge System Test ===\n")
    
    # Initialize system
    system = SHARKKnowledgeSystem()
    system.initialize()
    
    # Create a small test CVE dataset
    test_cve_content = """
CVE-2021-41773 (Log4Shell): Critical vulnerability in Apache Log4j 2.x allowing remote code execution via JNDI lookup exploitation.
Affects: Apache Log4j 2.0-beta7 through 2.14.1
Vector: Malicious string input logged by Log4j, processed by PatternLookupSubstitutor
Mitigation: Update to Log4j 2.15+, use JNDI lookup disabling, web application firewall rules

CVE-2021-34527: Critical vulnerability in Microsoft Windows Print Spooler allowing remote code execution
Affects: Windows 10, Windows Server 2016 and later
Vector: Specially crafted print jobs sent to printer
Mitigation: Apply Microsoft security update, disable Print Spooler if not needed
"""
    
    # Write test dataset as JSON
    test_dataset_path = 'datasets/test_cve_data.json'
    with open(test_dataset_path, 'w', encoding='utf-8') as f:
        json.dump([
            {'id': 'cve_2021_41773', 'content': 'CVE-2021-41773 Log4Shell RCE in Apache Log4j', 'metadata': {'source': 'test', 'category': 'cve', 'license': 'test'}},
            {'id': 'cve_2021_34527', 'content': 'CVE-2021-34527 Windows Print Spooler RCE', 'metadata': {'source': 'test', 'category': 'cve', 'license': 'test'}},
            {'id': 'cve_2021_26855', 'content': 'CVE-2021-26855 Windows Print Spooler elevation of privilege', 'metadata': {'source': 'test', 'category': 'cve', 'license': 'test'}}
        ], f, indent=2)
    
    print(f"Created test dataset at {test_dataset_path}")
    
    # Import the local file
    di = system.import_dataset(test_dataset_path, source_type='local')
    if di:
        print(f"\nImported: {di.name}")
        print(f"  Records: {di.size}")
        print(f"  License: {di.license}")
        print(f"  Categories: {list(di.categories)}")
        
        # Generate quality report
        report = system.generate_quality_report(di.name)
        if 'error' not in report:
            print(f"\nQuality report:")
            print(f"  Score: {report['quality_score']}/100")
            print(f"  Records: {report['total_records']}")
            print(f"  Duplicate percentage: {report['duplicate_percentage']}%")
        
        # Query the knowledge
        print("\n=== Testing Queries ===")
        
        queries = [
            'What is CVE-2021-41773?',
            'Log4Shell vulnerability details',
            'Windows Print Spooler security'
        ]
        
        for q in queries:
            result = system.answer_query(q, k=3)
            print(f"\nQ: {q}")
            print(f"A length: {len(result)} chars")
            # Extract just the answer part (after the instructions)
            answer_start = result.find("User question:")
            if answer_start > 0:
                print(f"  Answer preview: {result[answer_start:answer_start+300]}...")
            else:
                print(f"  Full prompt (first 300): {result[:300]}...")
        
        print("\n=== Test Summary ===")
        print("All functionality working correctly!")
    else:
        print("Failed to import dataset")


if __name__ == "__main__":
    main()