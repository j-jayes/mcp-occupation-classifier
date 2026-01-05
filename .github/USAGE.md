# Usage Example

This file demonstrates how to use the docs-scraper-template in your own repository.

## Example 1: Scraping Google ADK Documentation

1. Edit `.github/config.yaml`:

```yaml
docs_to_scrape:
  - url: "https://google.github.io/adk-docs/"
    name: "adk-docs"
```

2. Run the scraper:
   - Via GitHub Actions: Go to Actions → Scrape Documentation → Run workflow
   - Or locally: `python .github/scraper.py`

3. The scraped documentation will be saved to `.github/adk-docs/`

## Example 2: Scraping Multiple Documentation Sites

```yaml
docs_to_scrape:
  - url: "https://google.github.io/adk-docs/"
    name: "adk-docs"
  
  - url: "https://docs.python.org/3/"
    name: "python-docs"
  
  - url: "https://developer.mozilla.org/en-US/docs/Web/JavaScript/"
    name: "mdn-javascript"
```

Each site will be scraped into its own directory:
- `.github/adk-docs/`
- `.github/python-docs/`
- `.github/mdn-javascript/`

## Running Locally

```bash
# Install PyYAML (only dependency)
pip install pyyaml

# Run the scraper
cd your-repository
python .github/scraper.py
```

## Testing with a Small Site

For testing, you can use a small documentation site:

```yaml
docs_to_scrape:
  - url: "https://httpbin.org/"
    name: "test-httpbin"
```

## Important Notes

1. **Base URL Path**: The scraper only follows links that start with the same base URL path
   - ✅ Good: `https://example.com/docs/` will scrape all pages under `/docs/`
   - ❌ Won't work: It won't follow links to `https://example.com/blog/`

2. **Large Sites**: By default, limited to 1000 pages. Edit `scraper.py` to increase:
   ```python
   self._scrape_recursive(url, url, output_dir, max_pages=2000)
   ```

3. **JavaScript Content**: This scraper downloads static HTML only. Sites that load content via JavaScript won't be fully scraped.

4. **Rate Limiting**: The scraper doesn't include delays. For large sites, consider adding `time.sleep()` between requests.
