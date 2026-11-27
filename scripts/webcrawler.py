#!/usr/bin/env python3
"""Web crawling utility for SHARK AI - extracts security-relevant information from websites."""

import argparse
import json
import sys
import time
from typing import Dict, List, Optional, Any

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


def crawl_with_requests(url: str, max_depth: int = 2, delay: float = 1.0) -> Dict[str, Any]:
    """Crawl a website using requests for static content."""
    results = {
        "url": url,
        "status": "failed",
        "depth": 0,
        "pages": [],
        "errors": []
    }
    
    if not REQUESTS_AVAILABLE:
        results["errors"].append("requests library not installed")
        return results
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            results["status"] = "success"
            results["status_code"] = response.status_code
            results["title"] = ""
            results["headings"] = []
            results["links"] []
            
            # Extract basic info
            import re
            title_match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE)
            if title_match:
                results["title"] = title_match.group(1).strip()
            
            # Find headings
            headings = re.findall(r'<h([1-6])>(.*?)</h\1>', response.text, re.IGNORECASE)
            results["headings"] = [h[1].strip() for h in headings]
            
            # Find links
            links = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\']', response.text, re.IGNORECASE)
            results["links"] = list(set(links))[:50]  # Limit to 50 unique links
            
            results["depth"] = 1
        else:
            results["errors"].append(f"HTTP {response.status_code}")
    except Exception as e:
        results["errors"].append(str(e))
    
    return results


def crawl_with_selenium(url: str, max_depth: int = 2, delay: float = 2.0) -> Dict[str, Any]:
    """Crawl a website using Selenium for dynamic content."""
    if not SELENIUM_AVAILABLE:
        return {
            "url": url,
            "status": "failed",
            "errors": ["selenium library not installed. Install with: pip install selenium"],
            "depth": 0
        }
    
    results = {
        "url": url,
        "status": "failed",
        "depth": 0,
        "pages": [],
        "errors": []
    }
    
    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    try:
        service = ChromeService()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        all_pages = []
        
        def crawl_page(driver, current_depth):
            if current_depth > max_depth:
                return
            
            try:
                driver.get(url if current_depth == 0 else driver.current_url)
                time.sleep(delay)
                
                # Get page title
                try:
                    title = driver.title
                except:
                    title = ""
                
                # Find headings
                try:
                    headings = driver.find_elements(By.XPATH, "//h1 | //h2 | //h3 | //h4 | //h5 | //h6")
                    heading_texts = [h.text for h in headings if h.text.strip()]
                except:
                    heading_texts = []
                
                # Find links
                try:
                    links = driver.find_elements(By.TAG_NAME, "a")
                    link_hrefs = []
                    for link in links:
                        href = link.get_attribute("href")
                        if href and href.startswith("http"):
                            link_hrefs.append(href)
                    link_hrefs = list(set(link_hrefs))[:50]
                except:
                    link_hrefs = []
                
                page_data = {
                    "depth": current_depth,
                    "url": driver.current_url,
                    "title": title,
                    "headings": heading_texts,
                    "links": link_hrefs
                }
                all_pages.append(page_data)
                
                # Follow links (only for depth 0, follow one level)
                if current_depth == 0:
                    for link_href in link_hrefs[:5]:  # Limit to 5 links
                        try:
                            driver.execute_script("window.open('" + link_href + "', '_blank')")
                            time.sleep(delay / 2)
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                        except:
                            continue
                
            except TimeoutException:
                results["errors"].append(f"Timeout at depth {current_depth}")
            except WebDriverException as e:
                results["errors"].append(f"WebDriver error at depth {current_depth}: {str(e)}")
        
        crawl_page(driver, 0)
        results["pages"] = all_pages
        results["status"] = "success"
        results["depth"] = max_depth
        
        driver.quit()
        
    except Exception as e:
        results["errors"].append(f"Failed to initialize crawler: {str(e)}")
    
    return results


def extract_security_info(content: str) -> List[Dict[str, str]]:
    """Extract security-relevant information from crawled content."""
    security_keywords = [
        "vulnerability", "exploit", "cve", "sql injection", "xss", "cross-site",
        "authentication", "authorization", "csrf", "header", "cookie",
        "firewall", "waf", "penetration", "reverse engineering", "malware",
        "phishing", "brute force", "dDoS", "botnet", "trojan"
    ]
    
    findings = []
    content_lower = content.lower()
    
    for keyword in security_keywords:
        if keyword in content_lower:
            # Find context around the keyword
            idx = content_lower.index(keyword)
            start = max(0, idx - 100)
            end = min(len(content), idx + 100)
            context = content[start:end]
            
            findings.append({
                "keyword": keyword,
                "context": context.strip()
            })
    
    return findings


def main():
    parser = argparse.ArgumentParser(description="SHARK AI Web Crawler")
    parser.add_argument("url", help="URL to crawl")
    parser.add_argument("-d", "--depth", type=int, default=2, help="Maximum crawl depth (default: 2)")
    parser.add_argument("-m", "--method", choices=["requests", "selenium"], default="selenium",
                        help="Crawling method (default: selenium for dynamic content)")
    parser.add_argument("-o", "--output", help="Output file to save results (JSON)")
    parser.add_argument("--extract", action="store_true",
                        help="Extract security-relevant information")
    
    args = parser.parse_args()
    
    print(f"[SHARK Crawler] Crawling {args.url} with {args.method} (depth: {args.depth})")
    
    # Crawl based on method
    if args.method == "requests":
        results = crawl_with_requests(args.url, args.depth)
    else:
        results = crawl_with_selenium(args.url, args.depth)
    
    # Print results
    print(f"\n[SHARK Crawler] Status: {results['status']}")
    print(f"[SHARK Crawler] Depth reached: {results['depth']}")
    
    if results["status"] == "success":
        for i, page in enumerate(results["pages"]):
            print(f"\n--- Page {i+1} (depth {page['depth']}) ---")
            print(f"Title: {page.get('title', 'N/A')}")
            
            if page.get("headings"):
                print(f"Headings: {', '.join(page['headings'][:10])}")
            
            # Extract security info if requested
            if args.extract:
                findings = extract_security_info(page.get("title", "") + " " + 
                                                  " ".join(page.get("headings", [])))
                if findings:
                    print(f"\n[Security Findings]:")
                    for finding in findings:
                        print(f"  - {finding['keyword']}: {finding['context'][:80]}...")
            
            # Show some links
            links = page.get("links", [])
            if links:
                print(f"Links found: {len(links)}")
                for link in links[:5]:
                    print(f"  - {link}")
    
    else:
        for error in results["errors"]:
            print(f"[ERROR]: {error}")
    
    # Save to output file if specified
    if args.output and results["status"] == "success":
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\n[SHARK Crawler] Results saved to {args.output}")
        except Exception as e:
            print(f"[ERROR] Could not save results: {e}")
    
    return 0 if results["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())