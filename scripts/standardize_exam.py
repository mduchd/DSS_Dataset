"""Create a canonical, privacy-aware exam dataset from cleaned source files.

The cleaned source files remain unchanged. This script writes two outputs:

* record-level, partitioned CSV files in ``data/processed/exam`` for analysis;
* a province/year summary that does not include candidate identifiers and can be
  used by the application.

Run with:
    ./.venv/Scripts/python scripts/standardize_exam.py
"""

from __future__ import annotations

import csv
import json
import argparse
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CLEANED_DIR = ROOT / "data" / "cleaned" / "exam"
OUTPUT_DIR = ROOT / "data" / "processed" / "exam"
CHUNK_SIZE = 100_000


@dataclass(frozen=True)
class SourceSpec:
    filename: str
    year: int
    exam_program: str
    output_name: str


SOURCES = (
    SourceSpec("diemthi_2021_cleaned.csv", 2021, "pre_2025", "scores_2021.csv"),
    SourceSpec("diemthi_2022_cleaned.csv", 2022, "pre_2025", "scores_2022.csv"),
    SourceSpec("diemthi_2023.csv", 2023, "pre_2025", "scores_2023.csv"),
    SourceSpec("diemthi_2024.csv", 2024, "pre_2025", "scores_2024.csv"),
    SourceSpec("diemthi_2025_ct2006.csv", 2025, "ct_2006", "scores_2025_ct2006.csv"),
    SourceSpec("diemthi_2025_ct2018.csv", 2025, "ct_2018", "scores_2025_ct2018.csv"),
)

SCORE_FIELDS = (
    "math_score",
    "literature_score",
    "physics_score",
    "chemistry_score",
    "biology_score",
    "history_score",
    "geography_score",
    "civics_score",
    "economics_law_score",
    "informatics_score",
    "industrial_technology_score",
    "agricultural_technology_score",
    "foreign_language_score",
)

SOURCE_FIELDS = {
    "candidate_id": ("SBD", "sbd"),
    "source_year": ("Nam", "nam"),
    "province_code": ("Tinh", "ma_tinh"),
    "candidate_number": ("SBD_New", "sbd_noi_tinh"),
    "foreign_language_code": ("MaMonNgoaiNgu", "ma_mon_ngoai_ngu"),
    "reported_total_score": ("TongDiem", "tong_diem"),
    "math_score": ("Toan", "toan"),
    "literature_score": ("NguVan", "ngu_van"),
    "physics_score": ("VatLy", "vat_ly"),
    "chemistry_score": ("HoaHoc", "hoa_hoc"),
    "biology_score": ("SinhHoc", "sinh_hoc"),
    "history_score": ("LichSu", "lich_su"),
    "geography_score": ("DiaLy", "dia_ly"),
    "civics_score": ("GDCD", "gdcd"),
    "economics_law_score": ("KinhTePhapLuat", "kinh_te_phap_luat"),
    "informatics_score": ("TinHoc", "tin_hoc"),
    "industrial_technology_score": ("CongNgheCongNghiep", "cong_nghe_cong_nghiep"),
    "agricultural_technology_score": ("CongNgheNongNghiep", "cong_nghe_nong_nghiep"),
    "foreign_language_score": ("NgoaiNgu", "ngoai_ngu"),
}

COMBINATIONS = {
    "a00_score": ("math_score", "physics_score", "chemistry_score"),
    "a01_score": ("math_score", "physics_score", "foreign_language_score"),
    "a02_score": ("math_score", "physics_score", "biology_score"),
    "b00_score": ("math_score", "chemistry_score", "biology_score"),
    "c00_score": ("literature_score", "history_score", "geography_score"),
    "c01_score": ("literature_score", "math_score", "physics_score"),
    "c02_score": ("literature_score", "math_score", "chemistry_score"),
    "d01_score": ("math_score", "literature_score", "foreign_language_score"),
    "d07_score": ("math_score", "chemistry_score", "foreign_language_score"),
}

CANONICAL_COLUMNS = (
    "year",
    "exam_program",
    "candidate_id",
    "province_code",
    "candidate_number",
    "foreign_language_code",
    "reported_total_score",
    *SCORE_FIELDS,
    *COMBINATIONS.keys(),
)


class DataValidationError(ValueError):
    """Raised when a source violates the processed-data contract."""


def source_column(frame: pd.DataFrame, field: str) -> pd.Series:
    for name in SOURCE_FIELDS[field]:
        if name in frame.columns:
            return frame[name].astype("string").str.strip()
    return pd.Series(pd.NA, index=frame.index, dtype="string")


def examples(values: pd.Series, limit: int = 5) -> list[str]:
    return [str(value) for value in values.dropna().head(limit).tolist()]


def parse_score(values: pd.Series, field: str, source_name: str) -> pd.Series:
    values = values.replace("", pd.NA)
    numeric = pd.to_numeric(values, errors="coerce").astype("Float64")
    non_numeric = values.notna() & numeric.isna()
    invalid_range = numeric.notna() & numeric.ne(-1) & ((numeric < 0) | (numeric > 10))
    if non_numeric.any() or invalid_range.any():
        bad = values[non_numeric | invalid_range]
        raise DataValidationError(
            f"{source_name}: {field} has invalid score values {examples(bad)}"
        )
    # 2021–2022 clean files use -1 as their missing-score marker.
    return numeric.mask(numeric.eq(-1))


def parse_number(values: pd.Series, field: str, source_name: str) -> pd.Series:
    values = values.replace("", pd.NA)
    numeric = pd.to_numeric(values, errors="coerce").astype("Float64")
    invalid = values.notna() & numeric.isna()
    if invalid.any():
        raise DataValidationError(
            f"{source_name}: {field} has non-numeric values {examples(values[invalid])}"
        )
    return numeric


def validate_year(values: pd.Series, expected_year: int, source_name: str) -> None:
    values = values.replace("", pd.NA)
    parsed = pd.to_numeric(values, errors="coerce").astype("Int64")
    valid = parsed.isin((expected_year, expected_year % 100))
    invalid = values.notna() & ~valid
    if invalid.any():
        raise DataValidationError(
            f"{source_name}: unexpected year values {examples(values[invalid])}"
        )


def canonicalize(frame: pd.DataFrame, spec: SourceSpec) -> pd.DataFrame:
    candidate_id = source_column(frame, "candidate_id").replace("", pd.NA)
    invalid_id = candidate_id.isna() | ~candidate_id.str.fullmatch(r"\d+")
    if invalid_id.any():
        raise DataValidationError(
            f"{spec.filename}: candidate_id is missing or invalid {examples(candidate_id[invalid_id])}"
        )
    candidate_id = candidate_id.str.zfill(8)

    source_year = source_column(frame, "source_year")
    validate_year(source_year, spec.year, spec.filename)

    province = source_column(frame, "province_code").replace("", pd.NA)
    province = province.str.replace(r"\.0$", "", regex=True)
    invalid_province = province.isna() | ~province.str.fullmatch(r"\d{1,2}")
    if invalid_province.any():
        raise DataValidationError(
            f"{spec.filename}: province_code is missing or invalid {examples(province[invalid_province])}"
        )

    standardized = pd.DataFrame(index=frame.index)
    standardized["year"] = spec.year
    standardized["exam_program"] = spec.exam_program
    standardized["candidate_id"] = candidate_id
    standardized["province_code"] = province.str.zfill(2)
    standardized["candidate_number"] = source_column(frame, "candidate_number").replace("", pd.NA)
    standardized["foreign_language_code"] = (
        source_column(frame, "foreign_language_code").replace("", pd.NA).str.upper()
    )
    standardized["reported_total_score"] = parse_number(
        source_column(frame, "reported_total_score"), "reported_total_score", spec.filename
    )

    for field in SCORE_FIELDS:
        standardized[field] = parse_score(source_column(frame, field), field, spec.filename)

    for field, subject_fields in COMBINATIONS.items():
        standardized[field] = standardized.loc[:, list(subject_fields)].sum(axis=1, min_count=3)

    duplicated = standardized["candidate_id"].duplicated(keep=False)
    if duplicated.any():
        raise DataValidationError(
            f"{spec.filename}: duplicated candidate_id values {examples(standardized.loc[duplicated, 'candidate_id'])}"
        )
    return standardized.loc[:, CANONICAL_COLUMNS]


def update_summary(summary: dict[tuple[int, str, str], dict[str, float]], frame: pd.DataFrame) -> None:
    group_columns = ["year", "exam_program", "province_code"]
    for key, group in frame.groupby(group_columns, dropna=False, sort=False):
        row = summary[key]
        row["candidate_count"] += len(group)
        for field in SCORE_FIELDS + tuple(COMBINATIONS):
            values = group[field].dropna()
            row[f"{field}_count"] += len(values)
            row[f"{field}_sum"] += float(values.sum())


def write_summary(summary: dict[tuple[int, str, str], dict[str, float]]) -> Path:
    target = OUTPUT_DIR / "exam_score_summary_by_year_province.csv"
    score_columns = SCORE_FIELDS + tuple(COMBINATIONS)
    columns = ["year", "exam_program", "province_code", "candidate_count"]
    columns.extend(f"mean_{field}" for field in score_columns)
    columns.extend(f"count_{field}" for field in score_columns)

    with target.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for (year, exam_program, province_code), values in sorted(summary.items()):
            row: dict[str, object] = {
                "year": year,
                "exam_program": exam_program,
                "province_code": province_code,
                "candidate_count": int(values["candidate_count"]),
            }
            for field in score_columns:
                count = int(values[f"{field}_count"])
                row[f"count_{field}"] = count
                row[f"mean_{field}"] = round(values[f"{field}_sum"] / count, 4) if count else ""
            writer.writerow(row)
    return target


def process_source(spec: SourceSpec, summary: dict[tuple[int, str, str], dict[str, float]]) -> dict[str, object]:
    source = CLEANED_DIR / spec.filename
    if not source.exists():
        raise FileNotFoundError(f"Missing cleaned input: {source}")

    target = OUTPUT_DIR / spec.output_name
    temporary = target.with_suffix(".csv.tmp")
    rows_written = 0
    chunks = 0
    with temporary.open("w", encoding="utf-8", newline="") as output:
        for chunk in pd.read_csv(
            source,
            dtype="string",
            keep_default_na=False,
            encoding="utf-8-sig",
            chunksize=CHUNK_SIZE,
        ):
            standardized = canonicalize(chunk, spec)
            standardized.to_csv(output, index=False, header=chunks == 0, lineterminator="\n")
            update_summary(summary, standardized)
            rows_written += len(standardized)
            chunks += 1

    if not chunks:
        raise DataValidationError(f"{spec.filename}: source has no records")
    temporary.replace(target)
    return {
        "input": str(source.relative_to(ROOT)).replace("\\", "/"),
        "output": str(target.relative_to(ROOT)).replace("\\", "/"),
        "year": spec.year,
        "exam_program": spec.exam_program,
        "rows_written": rows_written,
    }


def summarize_processed_files() -> tuple[dict[tuple[int, str, str], dict[str, float]], list[dict[str, object]]]:
    summary: dict[tuple[int, str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    reports = []
    for spec in SOURCES:
        source = OUTPUT_DIR / spec.output_name
        if not source.exists():
            raise FileNotFoundError(f"Missing processed output: {source}")
        rows_read = 0
        for chunk in pd.read_csv(source, dtype="string", keep_default_na=False, chunksize=CHUNK_SIZE):
            for field in SCORE_FIELDS + tuple(COMBINATIONS):
                chunk[field] = pd.to_numeric(chunk[field], errors="coerce").astype("Float64")
            chunk["year"] = pd.to_numeric(chunk["year"], errors="raise").astype("int64")
            update_summary(summary, chunk)
            rows_read += len(chunk)
        reports.append(
            {
                "output": str(source.relative_to(ROOT)).replace("\\", "/"),
                "year": spec.year,
                "exam_program": spec.exam_program,
                "rows_written": rows_read,
            }
        )
    return summary, reports


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        action="append",
        choices=[spec.output_name for spec in SOURCES],
        help="Process only one named output. Use --summary-only after processing sources individually.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Rebuild the aggregate and report from all processed record files.",
    )
    args = parser.parse_args()
    if args.summary_only and args.source:
        parser.error("--summary-only cannot be combined with --source")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.summary_only:
        summary, reports = summarize_processed_files()
    else:
        selected = set(args.source or [spec.output_name for spec in SOURCES])
        summary = defaultdict(lambda: defaultdict(float))
        reports = []
        for spec in SOURCES:
            if spec.output_name not in selected:
                continue
            source_report = process_source(spec, summary)
            reports.append(source_report)
            print(
                f"Completed {spec.filename}: {source_report['rows_written']:,} rows",
                flush=True,
            )
    summary_path = write_summary(summary)

    report = {
        "contract_version": 1,
        "record_schema": list(CANONICAL_COLUMNS),
        "sources": reports,
        "summary": str(summary_path.relative_to(ROOT)).replace("\\", "/"),
        "privacy": "Do not expose candidate_id or candidate_number in the application.",
    }
    report_path = OUTPUT_DIR / "standardization_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
