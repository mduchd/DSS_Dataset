# -*- coding: utf-8 -*-
"""Làm sạch dữ liệu tin tuyển dụng VietJobs cho đồ án DSS.

Input : data/raw/jobs/VietJobs/VietJobs.csv
Output: data/cleaned/jobs/VietJobs_cleaned.csv

Raw luôn được giữ nguyên. Script chỉ chuẩn hóa text, bỏ dòng trùng,
chuẩn hóa lương/kinh nghiệm và đưa các cột danh sách về dạng dễ dùng.
"""

import ast
import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data" / "raw" / "jobs" / "VietJobs" / "VietJobs.csv"
OUTPUT_PATH = ROOT / "data" / "cleaned" / "jobs" / "VietJobs_cleaned.csv"

LIST_COLUMNS = ["qualifications", "technical_skills", "soft_skills", "benefits"]


def clean_text(value):
    """Chuẩn hóa Unicode và khoảng trắng, không thay đổi nội dung chính."""
    if pd.isna(value) or not str(value).strip():
        return ""
    value = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", " ", value).strip()


def clean_list(value):
    """Đưa chuỗi list của nguồn về JSON list để dùng lại ổn định."""
    value = clean_text(value)
    if not value:
        return "", False
    try:
        items = ast.literal_eval(value)
        if not isinstance(items, list):
            return value, True
        items = [clean_text(item) for item in items if clean_text(item)]
        return json.dumps(items, ensure_ascii=False), False
    except (SyntaxError, ValueError):
        return value, True


def experience_to_months(value):
    """Quy đổi '1 năm', '6 tháng' về số tháng; không đoán giá trị lạ."""
    value = clean_text(value).casefold()
    if value == "không yêu cầu":
        return 0
    match = re.fullmatch(r"(\d+)\s*(năm|tháng)", value)
    if not match:
        return pd.NA
    amount = int(match.group(1))
    return amount * 12 if match.group(2) == "năm" else amount


def main():
    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    print(f"[1] Đã đọc {len(df)} dòng, {len(df.columns)} cột.")

    # Chuẩn hóa toàn bộ cột text trước khi xử lý tiếp.
    for column in df.columns:
        df[column] = df[column].map(clean_text)

    # Các cột list giữ nguyên tên nhưng dùng JSON hợp lệ thay vì Python repr.
    list_errors = pd.Series(False, index=df.index)
    for column in LIST_COLUMNS:
        cleaned = df[column].map(clean_list)
        df[column] = cleaned.map(lambda item: item[0])
        list_errors |= cleaned.map(lambda item: item[1])

    df["_list_parse_error"] = list_errors
    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    list_errors = df.pop("_list_parse_error")
    print(f"[2] Đã loại bỏ {before - len(df)} dòng trùng hoàn toàn sau chuẩn hóa.")

    # Lương gốc giữ nguyên; cột mới có kiểu số, đơn vị triệu đồng/tháng.
    df["salary_min_trieu"] = pd.to_numeric(df["salary_min"], errors="coerce").astype("Float64")
    df["salary_max_trieu"] = pd.to_numeric(df["salary_max"], errors="coerce").astype("Float64")
    df["salary_thoa_thuan"] = df["salary_min_trieu"].le(0) | df["salary_max_trieu"].le(0)
    df["salary_bat_thuong"] = df["salary_min_trieu"].gt(df["salary_max_trieu"])
    df["salary_avg_trieu"] = ((df["salary_min_trieu"] + df["salary_max_trieu"]) / 2).round(2)
    df.loc[df["salary_thoa_thuan"] | df["salary_bat_thuong"], "salary_avg_trieu"] = pd.NA
    print(f"[3] Đã chuẩn hóa lương; {int(df['salary_thoa_thuan'].sum())} dòng lương thỏa thuận.")

    df["experience_months"] = df["experience_required"].map(experience_to_months).astype("Int64")
    df["experience_can_review"] = df["experience_months"].isna()
    print(f"[4] Đã quy đổi kinh nghiệm; {int(df['experience_can_review'].sum())} dòng cần review.")

    # Chuẩn hóa khóa text đơn giản phục vụ lọc/matching, không mapping địa danh.
    df["job_title_normalized"] = df["job_title"].str.casefold()
    df["location_normalized"] = df["location"].str.casefold()
    df["can_review"] = list_errors | df["salary_bat_thuong"] | df["experience_can_review"]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(f"[5] Hoàn tất: {OUTPUT_PATH} ({len(df)} dòng, {len(df.columns)} cột).")


if __name__ == "__main__":
    main()
