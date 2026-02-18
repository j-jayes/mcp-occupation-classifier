from __future__ import annotations

from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field


class IncomePercentiles(BaseModel):
    p10: Optional[int] = None
    p25: Optional[int] = None
    median: Optional[int] = None
    p75: Optional[int] = None
    p90: Optional[int] = None


class IncomeStatisticsSuccess(BaseModel):
    ok: bool = True
    ssyk_code: str
    year: str
    unit: str = "SEK/month"
    percentiles: IncomePercentiles
    raw: Dict[str, Any] = Field(default_factory=dict)


class IncomeStatisticsError(BaseModel):
    ok: bool = False
    error: str
    ssyk_code: Optional[str] = None


IncomeStatisticsResult = Union[IncomeStatisticsSuccess, IncomeStatisticsError]


def _get_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        v = value.strip()
        if v == "" or v == "..":
            return None
        try:
            return int(float(v))
        except Exception:
            return None
    return None


def normalize_income_statistics(*, ssyk_code: str, stats: Dict[str, Any]) -> IncomeStatisticsResult:
    """Normalize the raw income stats dict into a stable schema.

    The raw input comes from data/processed/income_stats.json and uses Swedish
    human-readable metric labels (e.g. "Medianlön", "10:e percentilen").
    """
    year = stats.get("year")
    if not isinstance(year, str) or not year.strip():
        # Keep this strict to avoid rendering misleading graphs.
        return IncomeStatisticsError(
            error="Income statistics missing 'year'",
            ssyk_code=ssyk_code,
        )

    percentiles = IncomePercentiles(
        p10=_get_int(stats.get("10:e percentilen")),
        p25=_get_int(stats.get("25:e percentilen")),
        median=_get_int(stats.get("Medianlön")),
        p75=_get_int(stats.get("75:e percentilen")),
        p90=_get_int(stats.get("90:e percentilen")),
    )

    return IncomeStatisticsSuccess(
        ssyk_code=ssyk_code,
        year=year.strip(),
        percentiles=percentiles,
        raw=dict(stats),
    )
