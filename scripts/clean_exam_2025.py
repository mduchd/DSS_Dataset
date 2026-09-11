"""Clean the two 2025 exam CSV files without modifying raw inputs."""

from __future__ import annotations

import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "exam"
OUT_DIR = ROOT / "data" / "cleaned" / "exam"
FILES = ("diemthi_2025_ct2006.csv", "diemthi_2025_ct2018.csv")
ID_COLUMNS = {"Nam", "Tinh", "SBD_New"}
TEXT_COLUMNS = {"SBD", "MaMonNgoaiNgu"}
SUBJECT_COLUMNS = {
    "Toan", "NguVan", "VatLy", "HoaHoc", "SinhHoc", "LichSu", "DiaLy",
    "GDCD", "KinhTePhapLuat", "TinHoc", "CongNgheCongNghiep",
    "CongNgheNongNghiep", "NgoaiNgu",
}


def normalize_number(value: str, *, integer: bool = False) -> str:
    value = value.strip()
    if not value:
        return ""
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"invalid numeric value: {value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"non-finite numeric value: {value!r}")
    if integer:
        if number != number.to_integral_value():
            raise ValueError(f"expected integer: {value!r}")
        return str(int(number))
    normalized = format(number.normalize(), "f")
    return "0" if normalized in {"-0", ""} else normalized


def clean_file(source: Path, target: Path) -> dict[str, int | str]:
    stats: dict[str, int | str] = {
        "source": str(source), "output": str(target), "input_rows": 0,
        "output_rows": 0, "blank_rows_removed": 0,
        "malformed_rows_removed": 0, "duplicate_sbd_removed": 0,
    }
    seen_sbd: set[str] = set()
    target.parent.mkdir(parents=True, exist_ok=True)

    with source.open("r", encoding="utf-8-sig", newline="") as src, target.open(
        "w", encoding="utf-8", newline=""
    ) as dst:
        reader = csv.DictReader(src)
        if not reader.fieldnames:
            raise ValueError(f"missing header: {source}")
        headers = [h.strip() for h in reader.fieldnames]
        writer = csv.DictWriter(dst, fieldnames=headers, lineterminator="\n")
        writer.writeheader()

        for raw in reader:
            stats["input_rows"] += 1
            if None in raw or any(key is None for key in raw):
                stats["malformed_rows_removed"] += 1
                continue
            row = {key.strip(): (value or "").strip() for key, value in raw.items()}
            if not any(row.values()):
                stats["blank_rows_removed"] += 1
                continue

            sbd = row.get("SBD", "")
            if not sbd.isdigit():
                stats["malformed_rows_removed"] += 1
                continue
            sbd = sbd.zfill(8)
            if sbd in seen_sbd:
                stats["duplicate_sbd_removed"] += 1
                continue
            seen_sbd.add(sbd)
            row["SBD"] = sbd

            try:
                for column in headers:
                    if column in TEXT_COLUMNS or not row[column]:
                        continue
                    row[column] = normalize_number(row[column], integer=column in ID_COLUMNS)
                    if column in SUBJECT_COLUMNS:
                        score = Decimal(row[column])
                        if not Decimal("0") <= score <= Decimal("10"):
                            raise ValueError(f"{column} outside 0..10: {score}")
            except ValueError:
                stats["malformed_rows_removed"] += 1
                seen_sbd.remove(sbd)
                continue

            if "MaMonNgoaiNgu" in row:
                row["MaMonNgoaiNgu"] = row["MaMonNgoaiNgu"].upper()
            writer.writerow(row)
            stats["output_rows"] += 1
    return stats


def main() -> None:
    results = [clean_file(RAW_DIR / name, OUT_DIR / name) for name in FILES]
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
