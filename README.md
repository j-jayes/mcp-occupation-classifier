

---

### 2. Prompt for Coding Agent

**Role:** You are an expert Python AI Engineer specializing in the **Model Context Protocol (MCP)** and **Data Science** workflows.

**Goal:** Create a new GitHub repository structure and the foundational code for an MCP server that performs Swedish occupational classification and income lookups.

**Constraints & Tech Stack:**

1. **Package Management:** Use `uv` strictly. Initialize the project with `uv init` and manage dependencies with `uv add`.
2. **MCP SDK:** Use the `mcp` python package. Specifically, use the high-level `FastMCP` class (`from mcp.server.fastmcp import FastMCP`) for the server implementation.
3. **Project Structure:** Follow the **Cookiecutter Data Science** convention (folders for `data/raw`, `data/processed`, `models`, `src`, `notebooks`).
4. **Language:** Python 3.12+.

**Core Functionality (Primitives):**
The server must expose **two Tools**:

1. **`classify_occupation(title: str, description: str) -> list[dict]`**
* **Logic:** A hybrid search engine.
* **Step 1 (BM25):** Perform a keyword search on the SSYK taxonomy using `rank_bm25`.
* **Step 2 (Vector):** Encode the input `"{title}: {description}"` using `sentence-transformers` (e.g., `all-MiniLM-L6-v2`) and calculate cosine similarity against pre-computed SSYK embeddings.
* **Step 3 (Hybrid Merge):** Normalize scores from both steps using Reciprocal Rank Fusion (RRF) or a weighted average to return the top N matches.
* **Output:** A list of SSYK codes, titles, and similarity scores.


2. **`get_income_statistics(ssyk_code: str) -> dict`**
* **Logic:** A fast dictionary lookup.
* **Data:** Loads a processed dataset (CSV/Parquet) derived from Statistics Sweden (SCB) data containing income percentiles (10th, 25th, 50th, 75th, 90th) for each SSYK code.
* **Output:** A dictionary with the income distribution for that code.



**Implementation Plan for the Agent:**

**Step 1: Project Initialization**

* Create the folder structure as defined in Cookiecutter Data Science.
* Generate a `pyproject.toml` using `uv`.
* Add dependencies: `mcp`, `pandas`, `numpy`, `scikit-learn`, `sentence-transformers`, `rank_bm25`, `httpx` (for fetching SCB data).

**Step 2: Data Ingestion Module (`src/ssyk_mcp/ingestion.py`)**

* Write a script to mock/download the SSYK taxonomy. *Note: Since we don't have the live API right now, create a dummy CSV generator that creates a file `data/raw/ssyk_structure.csv` with columns `[ssyk_code, occupation_title, definition]`.*
* Write a script to generate dummy SCB income data `data/raw/income_stats.csv` with columns `[ssyk_code, median_salary, percentile_25, percentile_75]`.
* Create a processing function that cleans this data and saves it to `data/processed/` for the server to load efficiently on startup.

**Step 3: The Search Engine (`src/ssyk_mcp/search.py`)**

* Create a `SearchEngine` class.
* On `__init__`, it should load the processed data, fit the BM25 index on the occupational titles, and load/compute the vector embeddings for the SSYK definitions.
* Implement a `search(query, n=3)` method that performs the hybrid ranking.

**Step 4: The MCP Server (`src/ssyk_mcp/server.py`)**

* Initialize `mcp = FastMCP("SSYK Agent")`.
* Load the `SearchEngine` and the Income Data DataFrame into global variables (or a state class) at startup.
* Decorate the two primitives with `@mcp.tool()`.
* Ensure the tool docstrings are detailed (as these serve as the prompt for the LLM).

**Step 5: Execution**

* Provide a `dev.py` or instruction to run the server using `uv run mcp run src/ssyk_mcp/server.py`.

**Output Required:**
Please generate the file commands to create the structure, the content of `pyproject.toml`, and the Python code for `ingestion.py`, `search.py`, and `server.py`.


# SSYK-hierarki + yrkesbenämningar – JSON
curl -L -o the-ssyk-hierarchy-with-occupations.json \
  "https://data.jobtechdev.se/taxonomy/version/latest/query/the-ssyk-hierarchy-with-occupations/the-ssyk-hierarchy-with-occupations.json"



# Genomsnittlig månadslön och lönespridning efter sektor, yrke (SSYK 2012) och kön. År 2023 - 2024

https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__AM__AM0110__AM0110A/LoneSpridSektYrk4AN/

https://www.statistikdatabasen.scb.se/Resources/PX/bulk/ssd/sv/TAB5932_sv.zip 

### Repository Structure & Design

This is a sophisticated project combining **Data Engineering** (ingesting SCB/SSYK data), **Machine Learning** (hybrid semantic search), and **System Engineering** (MCP server architecture).

Below is the recommended structure following **Cookiecutter Data Science** adapted for an MCP server.

```text
ssyk-mcp-server/
├── .python-version      # Managed by uv
├── pyproject.toml       # Dependencies and project config
├── uv.lock              # Lockfile for reproducible builds
├── README.md
├── .env                 # Secrets (if any)
├── data/
│   ├── raw/             # Original CSVs/JSONs from SCB (immutable)
│   ├── processed/       # Cleaned parquet files for the server (fast load)
│   └── external/        # SSYK taxonomy reference files
├── notebooks/           # Jupyter notebooks for testing search logic
│   └── 01_search_prototyping.ipynb
├── src/
│   ├── ssyk_mcp/        # Main package
│   │   ├── __init__.py
│   │   ├── server.py    # Entry point: FastMCP Server instance
│   │   ├── config.py    # Configuration (paths, constants)
│   │   ├── ingestion.py # Scripts to fetch/clean SCB data
│   │   ├── search.py    # Hybrid Search Engine (BM25 + Vectors)
│   │   └── scb_api.py   # Module for fetching live income stats
│   └── utils/           # Helper functions
└── tests/               # Pytest folder

```

---

### Prompt for Your Coding Agent

Copy and paste the text below into your coding agent (Cursor, Windsurf, GitHub Copilot, etc.). It contains the specific SCB API endpoints and the `uv`/`FastMCP` syntax instructions.

---

**Role:** You are an expert Python AI Engineer specializing in **Model Context Protocol (MCP)** and **Data Science**.

**Goal:** Create a GitHub repository structure and the foundational code for an MCP server that performs Swedish occupational classification (SSYK) and income lookups.

**Tech Stack:**

* **Package Manager:** `uv` (strict requirement: use `uv init`, `uv add`).
* **MCP SDK:** `mcp` (specifically the high-level `FastMCP` interface).
* **Search:** `rank_bm25`, `sentence-transformers`, `numpy`.
* **Data:** `pandas`, `httpx`.

**Core Functionality (2 Primitives):**

1. **`classify_occupation(title: str, description: str) -> list[dict]`**
* **Logic:** Hybrid search.
* *Step 1:* Keyword search (BM25) on SSYK job titles.
* *Step 2:* Semantic search (Vector embeddings) on `"{title}: {description}"`.
* *Step 3:* Merge scores (Reciprocal Rank Fusion) to return top N SSYK codes.


* **Data:** Load SSYK taxonomy from `data/processed/` on startup.


2. **`get_income_statistics(ssyk_code: str) -> dict`**
* **Logic:** Fetch real-time salary data from Statistics Sweden (SCB).
* **API Details:**
* **Endpoint:** `https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0110/AM0110A/LoneSpridSektYrk4AN`
* **Method:** `POST`
* **Payload Strategy:**
1. First, perform a `GET` on the endpoint to fetch metadata and map the human-readable labels (e.g., "Medianlön", "25:e percentilen") to their internal `valueTexts` or codes.
2. Construct a JSON payload filtering by:
* `Yrke2012`: [The input ssyk_code]
* `Sektor`: "0" (Samtliga sektorer)
* `Kon`: "1+2" (Totalt)
* `Tid`: The latest available year (dynamically determined or hardcoded to "2023"/"2024").






* **Output:** A dictionary containing the 25th percentile, Median, and 75th percentile monthly salaries.



**Implementation Plan:**

**Step 1: Project Setup**

* Initialize `pyproject.toml` with `uv`.
* Add dependencies: `mcp`, `pandas`, `numpy`, `scikit-learn`, `sentence-transformers`, `rank_bm25`, `httpx`, `python-dotenv`.

**Step 2: Data Ingestion (`src/ssyk_mcp/ingestion.py`)**

* Create a script to download/mock the SSYK taxonomy CSV (columns: `ssyk_code`, `title`, `description`).
* *Note:* Since we don't have the full SSYK vector database yet, create a dummy generator for `data/processed/ssyk_vectors.parquet` so the server can boot.

**Step 3: SCB Client (`src/ssyk_mcp/scb_api.py`)**

* Implement a `fetch_salary_stats(ssyk_code)` function.
* Use `httpx` to POST to the SCB API.
* **Crucial:** Handle the SCB JSON-stat response format which can be nested.

**Step 4: The Server (`src/ssyk_mcp/server.py`)**

* Use `from mcp.server.fastmcp import FastMCP`.
* Instantiate `mcp = FastMCP("SSYK Agent")`.
* Load the search index into global state on startup.
* Decorate the two functions with `@mcp.tool()`.

**Output Required:**
Generate the file tree creation commands, `pyproject.toml`, and the Python code for `server.py`, `search.py`, and `scb_api.py`.

---

### SCB API Reference (for your Context)

If you need to test the API yourself, here is the `curl` request for the table `LoneSpridSektYrk4AN` (Salary dispersion by sector and occupation).

**Endpoint:**
`POST https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0110/AM0110A/LoneSpridSektYrk4AN`

**JSON Payload (Example):**

```json
{
  "query": [
    {
      "code": "Yrke2012",
      "selection": {
        "filter": "item",
        "values": ["2511"]
      }
    },
    {
      "code": "Sektor",
      "selection": {
        "filter": "item",
        "values": ["0"]
      }
    },
    {
      "code": "Kon",
      "selection": {
        "filter": "item",
        "values": ["1+2"]
      }
    },
    {
      "code": "ContentsCode",
      "selection": {
        "filter": "item",
        "values": [
          "000002V5",  // Average salary (check metadata for exact code)
          "000007CD"   // Percentiles (check metadata for exact code)
        ]
      }
    }
  ],
  "response": {
    "format": "json"
  }
}

```

*Note: The specific codes for `ContentsCode` (e.g., Median vs Average) change occasionally. The code should inspect the metadata first.*