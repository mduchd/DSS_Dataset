# -*- coding: utf-8 -*-
"""Làm sạch dữ liệu điểm chuẩn 2018-2023 cho đồ án DSS.

Input : data/raw/admission/diemchuan_2018_2023.xlsx
Output: data/cleaned/admission/diemchuan_2018_2023_cleaned.csv

Raw luôn được giữ nguyên. Script thực hiện 9 bước tương tự file clean 2024:
đọc XLSX, chuẩn hóa text, bỏ dòng trùng, xử lý thang điểm, tách Ghi chú,
chuẩn hóa mã ngành, gắn cờ outlier, nhóm tổ hợp và kiểm tra mã trường.
"""

import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data" / "raw" / "admission" / "diemchuan_2018_2023.xlsx"
OUTPUT_PATH = ROOT / "data" / "cleaned" / "admission" / "diemchuan_2018_2023_cleaned.csv"


def clean_text(value):
    """Chuẩn hóa Unicode và khoảng trắng, không đổi ý nghĩa dữ liệu."""
    if pd.isna(value):
        return pd.NA
    value = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", " ", value).strip()


def clean_code(value):
    value = clean_text(value)
    if pd.isna(value):
        return pd.NA
    return re.sub(r"^(\d+)\.0+$", r"\1", value).upper()


# ---------------------------------------------------------------------------
# BƯỚC 1: Đọc XLSX
# ---------------------------------------------------------------------------
def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, dtype=object)
    df.columns = [clean_text(column) for column in df.columns]
    print(f"[1] Đã đọc {len(df)} dòng, {len(df.columns)} cột.")
    return df


# ---------------------------------------------------------------------------
# BƯỚC 2: Chuẩn hóa text/mã và loại bỏ dòng trùng hoàn toàn
# ---------------------------------------------------------------------------
def normalize_and_remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    text_columns = [
        "Khu vực", "Tỉnh/ Thành phố", "Tên Trường", "Loại đơn vị",
        "Nhóm ngành", "Phân ngành", "Tên Ngành", "Loại điểm", "Ghi chú",
    ]
    code_columns = [
        "Mã trường xét tuyển", "Mã Trường", "Mã nhóm ngành", "Mã phân ngành",
        "Mã xét tuyển", "Tổ hợp",
    ]
    for column in text_columns:
        df[column] = df[column].map(clean_text).astype("string")
    for column in code_columns:
        df[column] = df[column].map(clean_code).astype("string")

    df["Năm"] = pd.to_numeric(df["Năm"], errors="coerce").astype("Int64")
    df["Điểm chuẩn"] = pd.to_numeric(df["Điểm chuẩn"], errors="coerce").astype("Float64")
    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    print(f"[2] Đã loại bỏ {before - len(df)} dòng trùng hoàn toàn.")
    return df


# ---------------------------------------------------------------------------
# BƯỚC 3: Ghi nhận thang điểm và tạo giá trị quy đổi tỷ lệ cho THPT thang 40
# ---------------------------------------------------------------------------
def normalize_score_scale(df: pd.DataFrame) -> pd.DataFrame:
    df["Thang_diem_goc"] = "Khác"
    df.loc[df["Loại điểm"].eq("THPTQG"), "Thang_diem_goc"] = "30"
    df.loc[df["Loại điểm"].eq("THPTQG - Thang 40"), "Thang_diem_goc"] = "40"
    df.loc[df["Loại điểm"].eq("DGNLHCM"), "Thang_diem_goc"] = "1200"
    df.loc[df["Loại điểm"].eq("DGNLQGHN"), "Thang_diem_goc"] = "150"
    df.loc[df["Loại điểm"].eq("DGTD"), "Thang_diem_goc"] = "100"
    df.loc[df["Loại điểm"].eq("Học bạ"), "Thang_diem_goc"] = "Biến thiên"

    # Chỉ quy đổi tỷ lệ cho hai phương thức THPT. Các loại DGNL/học bạ giữ
    # nguyên điểm nguồn vì không có công thức chung để so sánh với thang 30.
    df["Diem_chuan_quy_doi_30"] = pd.Series(pd.NA, index=df.index, dtype="Float64")
    direct = df["Loại điểm"].eq("THPTQG")
    weighted = df["Loại điểm"].eq("THPTQG - Thang 40")
    df.loc[direct, "Diem_chuan_quy_doi_30"] = df.loc[direct, "Điểm chuẩn"]
    df.loc[weighted, "Diem_chuan_quy_doi_30"] = (df.loc[weighted, "Điểm chuẩn"] * 0.75).round(2)
    print(f"[3] Đã tạo Diem_chuan_quy_doi_30 cho {int((direct | weighted).sum())} dòng THPT.")
    return df


# ---------------------------------------------------------------------------
# BƯỚC 4: Tách vài thông tin có cấu trúc từ Ghi chú
# ---------------------------------------------------------------------------
def extract_note_features(df: pd.DataFrame) -> pd.DataFrame:
    notes = df["Ghi chú"].fillna("")
    lower = notes.str.casefold()

    subject = r"Tiếng Anh|Toán|Ngữ văn|Vật lý|Hóa học|Sinh học|Lịch sử|Địa lý|Ngoại ngữ|Năng khiếu|Vẽ mỹ thuật|Vẽ"
    result = notes.str.extract(rf"(?P<mon>{subject})\s*(?:hệ số|nhân)\s*(?P<he_so>\d+(?:[.,]\d+)?)", flags=re.IGNORECASE)
    df["Mon_he_so"] = result["mon"].astype("string")
    df["He_so_mon"] = pd.to_numeric(result["he_so"].str.replace(",", ".", regex=False), errors="coerce").astype("Float64")

    df["Dieu_kien_gioi_tinh"] = pd.Series(pd.NA, index=df.index, dtype="string")
    female = lower.str.contains(r"thí\s+sinh\s+nữ|chỉ\s+tuyển\s+nữ", regex=True)
    male = lower.str.contains(r"thí\s+sinh\s+nam|chỉ\s+tuyển\s+nam", regex=True)
    df.loc[female & ~male, "Dieu_kien_gioi_tinh"] = "Nữ"
    df.loc[male & ~female, "Dieu_kien_gioi_tinh"] = "Nam"
    df.loc[female & male, "Dieu_kien_gioi_tinh"] = "Cả hai"

    df["Chuong_trinh_CLC"] = lower.str.contains(r"chất\s+lượng\s+cao|\bclc\b", regex=True)
    parsed = df[["Mon_he_so", "He_so_mon", "Dieu_kien_gioi_tinh"]].notna().any(axis=1) | df["Chuong_trinh_CLC"]
    df["Ghi_chu_can_review"] = notes.ne("") & ~parsed
    print(f"[4] Đã tách Ghi chú; {int(df['Ghi_chu_can_review'].sum())} dòng còn cần đọc thủ công nếu cần.")
    return df


# ---------------------------------------------------------------------------
# BƯỚC 5: Chuẩn hóa Mã xét tuyển thành mã ngành gốc và hậu tố biến thể
# ---------------------------------------------------------------------------
def normalize_major_code(df: pd.DataFrame) -> pd.DataFrame:
    parts = df["Mã xét tuyển"].str.extract(r"^(?P<core>\d{7})(?P<suffix>.+)?$")
    df["Ma_nganh_goc"] = parts["core"].fillna(df["Mã xét tuyển"]).astype("string")
    df["Ma_nganh_bien_the"] = parts["suffix"].replace("", pd.NA).astype("string")
    print(f"[5] Đã tách mã ngành biến thể cho {int(df['Ma_nganh_bien_the'].notna().sum())} dòng.")
    return df


# ---------------------------------------------------------------------------
# BƯỚC 6: Gắn cờ outlier theo từng loại điểm, không tự xóa
# ---------------------------------------------------------------------------
def flag_outliers(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby("Loại điểm")["Điểm chuẩn"]
    q1 = grouped.transform(lambda values: values.quantile(0.25))
    q3 = grouped.transform(lambda values: values.quantile(0.75))
    iqr = q3 - q1
    df["Outlier_diem"] = (df["Điểm chuẩn"] < q1 - 1.5 * iqr) | (df["Điểm chuẩn"] > q3 + 1.5 * iqr)
    print(f"[6] Đã gắn cờ {int(df['Outlier_diem'].sum())} outlier theo Loại điểm (không xóa).")
    return df


# ---------------------------------------------------------------------------
# BƯỚC 7: Nhóm tổ hợp môn
# ---------------------------------------------------------------------------
def group_subject_combination(df: pd.DataFrame) -> pd.DataFrame:
    df["Khoi_to_hop"] = df["Tổ hợp"].str.extract(r"^([A-Z]+)")[0].fillna("Khác")
    print(f"[7] Đã tạo Khoi_to_hop từ {df['Tổ hợp'].nunique()} tổ hợp chi tiết.")
    return df


# ---------------------------------------------------------------------------
# BƯỚC 8: Kiểm tra mã trường và tên trường
# ---------------------------------------------------------------------------
def check_school_consistency(df: pd.DataFrame) -> None:
    conflicts = df.groupby(["Năm", "Mã trường xét tuyển"])["Tên Trường"].nunique().gt(1).sum()
    print(f"[8] Có {int(conflicts)} cặp Năm + Mã trường xét tuyển gắn nhiều Tên Trường (chỉ cảnh báo).")


# ---------------------------------------------------------------------------
# BƯỚC 9: Xuất file clean
# ---------------------------------------------------------------------------
def finalize_and_save(df: pd.DataFrame) -> None:
    for column in ["Mã trường xét tuyển", "Mã Trường", "Mã xét tuyển", "Tổ hợp", "Ma_nganh_goc", "Ma_nganh_bien_the"]:
        df[column] = df[column].astype("string")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(f"[9] Hoàn tất: {OUTPUT_PATH} ({len(df)} dòng, {len(df.columns)} cột).")


def main():
    df = load_data(INPUT_PATH)
    df = normalize_and_remove_duplicates(df)
    df = normalize_score_scale(df)
    df = extract_note_features(df)
    df = normalize_major_code(df)
    df = flag_outliers(df)
    df = group_subject_combination(df)
    check_school_consistency(df)
    finalize_and_save(df)


if __name__ == "__main__":
    main()
