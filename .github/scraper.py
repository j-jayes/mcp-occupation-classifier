#!/usr/bin/env python3
"""
Documentation Scraper
This script scrapes documentation websites and saves them locally.
It reads URLs from config.yaml and saves content to .github/<name>/ directories.
"""

import os
import sys
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
import yaml


class LinkExtractor(HTMLParser):
    """Extract all links from HTML content."""
    
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.links = set()
    
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr, value in attrs:
                if attr == 'href':
                    # Resolve relative URLs
                    absolute_url = urllib.parse.urljoin(self.base_url, value)
                    self.links.add(absolute_url)


class DocsScraper:
    """Main scraper class to download documentation."""
    
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self._load_config()
        self.visited_urls = set()
    
    def _load_config(self):
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                if config is None:
                    return []
                return config.get('docs_to_scrape', []) or []
        except FileNotFoundError:
            print(f"Error: Config file not found at {self.config_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Error parsing YAML config: {e}")
            sys.exit(1)
    
    def _is_same_domain(self, url, base_url):
        """Check if URL is from the same domain as base URL."""
        url_parts = urllib.parse.urlparse(url)
        base_parts = urllib.parse.urlparse(base_url)
        
        # Check if scheme, netloc, and path prefix match
        return (url_parts.scheme == base_parts.scheme and 
                url_parts.netloc == base_parts.netloc and
                url_parts.path.startswith(base_parts.path))
    
    def _get_local_path(self, url, base_url, output_dir):
        """Convert URL to local file path."""
        # Parse both URLs
        url_parsed = urllib.parse.urlparse(url)
        base_parsed = urllib.parse.urlparse(base_url)
        
        # Get the relative path by removing the base path
        url_path = url_parsed.path
        base_path = base_parsed.path
        
        # Remove base path from URL path
        if url_path.startswith(base_path):
            relative_path = url_path[len(base_path):]
        else:
            relative_path = url_path
        
        # Remove leading slash
        if relative_path.startswith('/'):
            relative_path = relative_path[1:]
        
        # If path is empty or ends with /, add index.html
        if not relative_path or relative_path.endswith('/'):
            relative_path = os.path.join(relative_path, 'index.html')
        
        # If path has no extension, assume it's HTML
        if not os.path.splitext(relative_path)[1]:
            relative_path = relative_path + '.html'
        
        return os.path.join(output_dir, relative_path)
    
    def _download_page(self, url):
        """Download a single page and return its content."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=10) as response:
                content = response.read()
                return content
        except Exception as e:
            print(f"Error downloading {url}: {e}")
            return None
    
    def _extract_links(self, html_content, base_url):
        """Extract all links from HTML content."""
        try:
            parser = LinkExtractor(base_url)
            parser.feed(html_content.decode('utf-8', errors='ignore'))
            return parser.links
        except Exception as e:
            print(f"Error extracting links: {e}")
            return set()
    
    def _scrape_recursive(self, url, base_url, output_dir, max_pages=1000):
        """Recursively scrape pages starting from a URL."""
        # Check if already visited
        if url in self.visited_urls:
            return
        
        # Check if we've hit the max pages limit
        if len(self.visited_urls) >= max_pages:
            print(f"Reached maximum page limit ({max_pages})")
            return
        
        # Check if URL is from the same domain
        if not self._is_same_domain(url, base_url):
            return
        
        # Mark as visited
        self.visited_urls.add(url)
        print(f"Scraping [{len(self.visited_urls)}]: {url}")
        
        # Download the page
        content = self._download_page(url)
        if not content:
            return
        
        # Save the page
        local_path = self._get_local_path(url, base_url, output_dir)
        local_dir = os.path.dirname(local_path)
        if local_dir:  # Only create directories if dirname is not empty
            os.makedirs(local_dir, exist_ok=True)
        
        try:
            with open(local_path, 'wb') as f:
                f.write(content)
            print(f"  Saved to: {local_path}")
        except Exception as e:
            print(f"  Error saving file: {e}")
            return
        
        # Extract and follow links (only for HTML pages)
        # Check if this is likely an HTML page based on URL extension or lack thereof
        url_path = urllib.parse.urlparse(url).path
        file_ext = os.path.splitext(url_path)[1].lower()
        is_html = (file_ext in ['', '.html', '.htm'] or url_path.endswith('/'))
        
        if is_html:
            links = self._extract_links(content, url)
            for link in links:
                # Remove fragments and query parameters for comparison
                clean_link = link.split('#')[0].split('?')[0]
                if clean_link and self._is_same_domain(clean_link, base_url):
                    self._scrape_recursive(clean_link, base_url, output_dir, max_pages)
    
    def scrape_all(self):
        """Scrape all configured documentation sites."""
        if not self.config:
            print("No documentation sites configured in config.yaml")
            return
        
        for doc_config in self.config:
            if not doc_config:
                continue
                
            url = doc_config.get('url')
            name = doc_config.get('name')
            
            if not url or not name:
                print("Skipping invalid config entry (missing url or name)")
                continue
            
            print(f"\n{'='*60}")
            print(f"Scraping: {name}")
            print(f"URL: {url}")
            print(f"{'='*60}\n")
            
            # Create output directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(script_dir, name)
            
            # Reset visited URLs for each site
            self.visited_urls = set()
            
            # Start scraping
            self._scrape_recursive(url, url, output_dir)
            
            print(f"\nCompleted scraping {name}")
            print(f"Total pages downloaded: {len(self.visited_urls)}")
            print(f"Output directory: {output_dir}\n")


def main():
    """Main entry point."""
    # Get the script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'config.yaml')
    
    print("Documentation Scraper")
    print("=" * 60)
    print(f"Config file: {config_path}\n")
    
    # Create scraper and run
    scraper = DocsScraper(config_path)
    scraper.scrape_all()
    
    print("\nScraping completed!")


if __name__ == '__main__':
    main()
