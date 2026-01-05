import json
from typing import Dict, Any, Optional
from .config import PROCESSED_DATA_DIR

INCOME_STATS_PATH = PROCESSED_DATA_DIR / "income_stats.json"

class SCBClient:
    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.is_loaded = False

    def load_data(self):
        """Loads the pre-fetched income statistics from JSON."""
        if not INCOME_STATS_PATH.exists():
            print(f"Warning: Income stats file not found at {INCOME_STATS_PATH}")
            return

        try:
            with open(INCOME_STATS_PATH, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            self.is_loaded = True
            print(f"Loaded income stats for {len(self.data)} occupations.")
        except Exception as e:
            print(f"Error loading income stats: {e}")

    def get_income_statistics(self, ssyk_code: str) -> Dict[str, Any]:
        """
        Retrieves income statistics from the local cache.
        """
        if not self.is_loaded:
            self.load_data()
            
        stats = self.data.get(ssyk_code)
        if not stats:
            return {"error": f"No income data found for SSYK code {ssyk_code}"}
            
        return {
            "ssyk_code": ssyk_code,
            **stats
        }
