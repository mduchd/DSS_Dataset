"""Standardize cleaned VietJobs postings for analysis and major-to-job mapping.

The source's job category is preserved. This script does not infer academic
majors from a job title or description; that explicit relationship belongs in
the later major-to-job mapping table.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data" / "cleaned" / "jobs" / "VietJobs_cleaned.csv"
OUTPUT_DIR = ROOT / "data" / "processed" / "jobs"

LIST_FIELDS = (
    "languages",
    "qualifications",
    "technical_skills",
    "soft_skills",
    "benefits",
)

CANONICAL_COLUMNS = (
    "job_id",
    "source_name",
    "job_title",
    "job_title_key",
    "job_category",
    "job_category_key",
    "location_text",
    "location_key",
    "country",
    "contract_type",
    "working_hours",
    "salary_min_million_vnd",
    "salary_max_million_vnd",
    "salary_average_million_vnd",
    "salary_is_negotiable",
    "salary_needs_review",
    "experience_months",
    "experience_needs_review",
    "languages",
    "qualifications",
    "technical_skills",
    "soft_skills",
    "benefits",
    "description",
    "requirements_text",
    "list_needs_review",
    "record_needs_review",
)


class DataValidationError(ValueError):
    """Raised when a cleaned VietJobs value cannot satisfy the data contract."""


def text(values: pd.Series) -> pd.Series:
    return values.astype("string").str.strip().replace({"": pd.NA, "<NA>": pd.NA})


def key(values: pd.Series) -> pd.Series:
    def normalize(value: object) -> str | None:
        if pd.isna(value):
            return None
        value = unicodedata.normalize("NFKD", str(value))
        value = "".join(char for char in value if not unicodedata.combining(char))
        value = value.replace("đ", "d").replace("Đ", "D").casefold()
        return re.sub(r"[^a-z0-9]+", " ", value).strip() or None

    return values.map(normalize).astype("string")


def parse_boolean(values: pd.Series, field: str) -> pd.Series:
    normalized = text(values).str.casefold()
    result = pd.Series(pd.NA, index=values.index, dtype="boolean")
    result[normalized.isin(("true", "1", "yes"))] = True
    result[normalized.isin(("false", "0", "no"))] = False
    invalid = normalized.notna() & result.isna()
    if invalid.any():
        raise DataValidationError(f"{field} has invalid values {normalized[invalid].head(5).tolist()}")
    return result


def parse_number(values: pd.Series, field: str) -> pd.Series:
    values = text(values)
    numeric = pd.to_numeric(values, errors="coerce").astype("Float64")
    invalid = values.notna() & numeric.isna()
    if invalid.any():
        raise DataValidationError(f"{field} has non-numeric values {values[invalid].head(5).tolist()}")
    return numeric


def parse_json_list(values: pd.Series) -> tuple[pd.Series, pd.Series]:
    normalized: list[str] = []
    needs_review: list[bool] = []
    for value in text(values).tolist():
        if pd.isna(value):
            normalized.append("[]")
            needs_review.append(False)
            continue
        try:
            parsed = json.loads(str(value))
            if not isinstance(parsed, list):
                raise ValueError("not a list")
            items = [str(item).strip() for item in parsed if str(item).strip()]
            normalized.append(json.dumps(items, ensure_ascii=False, separators=(",", ":")))
            needs_review.append(False)
        except (json.JSONDecodeError, TypeError, ValueError):
            # Keep the source text as one item rather than discarding it.
            normalized.append(json.dumps([str(value)], ensure_ascii=False, separators=(",", ":")))
            needs_review.append(True)
    return (
        pd.Series(normalized, index=values.index, dtype="string"),
        pd.Series(needs_review, index=values.index, dtype="boolean"),
    )


def stable_job_id(frame: pd.DataFrame) -> pd.Series:
    # Every canonical source field participates so distinct postings never
    # collapse merely because title, location and description happen to match.
    payload = frame.astype("string").fillna("").agg("\x1f".join, axis=1)
    return payload.map(lambda value: f"vj_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]}")


def standardize(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    result = pd.DataFrame(index=frame.index)
    result["source_name"] = "VietJobs"
    result["job_title"] = text(frame["job_title"])
    if result["job_title"].isna().any():
        raise DataValidationError("job_title is required")
    result["job_title_key"] = key(result["job_title"])
    result["job_category"] = text(frame["category"])
    result["job_category_key"] = key(result["job_category"])
    result["location_text"] = text(frame["location"])
    result["location_key"] = key(result["location_text"])
    result["country"] = text(frame["country"])
    result["contract_type"] = text(frame["contract_type"])
    result["working_hours"] = text(frame["working_hours"])

    salary_min = parse_number(frame["salary_min_trieu"], "salary_min_trieu")
    salary_max = parse_number(frame["salary_max_trieu"], "salary_max_trieu")
    invalid_salary = (salary_min.notna() & (salary_min < 0)) | (salary_max.notna() & (salary_max < 0))
    if invalid_salary.any():
        raise DataValidationError("salary values cannot be negative")
    result["salary_is_negotiable"] = salary_min.isna() | salary_max.isna() | salary_min.le(0) | salary_max.le(0)
    result["salary_needs_review"] = parse_boolean(frame["salary_bat_thuong"], "salary_bat_thuong")
    result["salary_needs_review"] = result["salary_needs_review"].fillna(False) | salary_min.gt(salary_max)
    valid_salary = ~result["salary_is_negotiable"] & ~result["salary_needs_review"]
    result["salary_min_million_vnd"] = salary_min.where(valid_salary)
    result["salary_max_million_vnd"] = salary_max.where(valid_salary)
    result["salary_average_million_vnd"] = ((salary_min + salary_max) / 2).round(2).where(valid_salary)

    result["experience_months"] = parse_number(frame["experience_months"], "experience_months")
    result["experience_needs_review"] = parse_boolean(
        frame["experience_can_review"], "experience_can_review"
    ).fillna(False)
    result["languages"], language_review = parse_json_list(frame["languages_required"])
    result["qualifications"], qualification_review = parse_json_list(frame["qualifications"])
    result["technical_skills"], technical_review = parse_json_list(frame["technical_skills"])
    result["soft_skills"], soft_review = parse_json_list(frame["soft_skills"])
    result["benefits"], benefit_review = parse_json_list(frame["benefits"])
    result["description"] = text(frame["description"])
    result["requirements_text"] = text(frame["requirements_text"])
    result["list_needs_review"] = (
        language_review | qualification_review | technical_review | soft_review | benefit_review
    )
    result["record_needs_review"] = (
        result["salary_needs_review"]
        | result["experience_needs_review"]
        | result["list_needs_review"]
    )

    result = result.loc[:, [column for column in CANONICAL_COLUMNS if column != "job_id"]]
    before = len(result)
    result = result.drop_duplicates().reset_index(drop=True)
    duplicates_removed = before - len(result)
    result.insert(0, "job_id", stable_job_id(result))
    if result["job_id"].duplicated().any():
        raise DataValidationError("stable job identifiers are not unique")
    return result.loc[:, CANONICAL_COLUMNS], duplicates_removed


def build_summary(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = frame.groupby(["job_category", "job_category_key"], dropna=False)
    summary = grouped.agg(
        posting_count=("job_id", "count"),
        salary_count=("salary_average_million_vnd", "count"),
        average_salary_million_vnd=("salary_average_million_vnd", "mean"),
        median_salary_million_vnd=("salary_average_million_vnd", "median"),
        average_experience_months=("experience_months", "mean"),
        records_needing_review=("record_needs_review", "sum"),
    ).reset_index()
    return summary.sort_values("posting_count", ascending=False, kind="stable")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source = pd.read_csv(INPUT_PATH, encoding="utf-8-sig", dtype="string", keep_default_na=False)
    standardized, duplicates_removed = standardize(source)

    output_path = OUTPUT_DIR / "vietjobs_postings.csv"
    temporary = output_path.with_suffix(".csv.tmp")
    standardized.to_csv(temporary, index=False, encoding="utf-8", lineterminator="\n")
    temporary.replace(output_path)

    summary = build_summary(standardized)
    summary_path = OUTPUT_DIR / "job_market_summary_by_category.csv"
    summary.to_csv(summary_path, index=False, encoding="utf-8", lineterminator="\n")

    report = {
        "contract_version": 1,
        "record_schema": list(CANONICAL_COLUMNS),
        "input": str(INPUT_PATH.relative_to(ROOT)).replace("\\", "/"),
        "input_rows": len(source),
        "records_written": len(standardized),
        "duplicates_removed_after_standardization": duplicates_removed,
        "records_needing_review": int(standardized["record_needs_review"].sum()),
        "summary": str(summary_path.relative_to(ROOT)).replace("\\", "/"),
    }
    report_path = OUTPUT_DIR / "standardization_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
