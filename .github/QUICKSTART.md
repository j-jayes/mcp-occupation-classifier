# Quick Start Guide

Get started with the docs scraper in 3 simple steps!

## Step 1: Copy the Template

Copy the entire `.github/` folder to your repository:

```bash
# From your repository root
cp -r /path/to/docs-scraper-template/.github .
```

## Step 2: Configure Your Docs

Edit `.github/config.yaml` and add your documentation URLs:

```yaml
docs_to_scrape:
  - url: "https://google.github.io/adk-docs/"
    name: "adk-docs"
```

## Step 3: Run the Scraper

### Option A: GitHub Actions (Recommended)
1. Commit and push the `.github/` folder
2. Go to **Actions** tab → **Scrape Documentation** → **Run workflow**

### Option B: Run Locally
```bash
pip install pyyaml
python .github/scraper.py
```

## That's It!

Your docs will be saved to `.github/<name>/` and kept up-to-date automatically.

---

For more details, see:
- [README.md](../README.md) - Full documentation
- [USAGE.md](USAGE.md) - Advanced usage examples
