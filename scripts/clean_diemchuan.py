# -*- coding: utf-8 -*-
"""
Script làm sạch dữ liệu điểm chuẩn 2024 cho đồ án DSS
(Hệ thống hỗ trợ chọn ngành học / trường đại học cho học sinh THPT)

Input : diemchuan_2024.csv
Output: diemchuan_2024_cleaned.csv

Thực hiện đủ 9 bước:
 1. Đọc đúng encoding (xử lý BOM)
 2. Loại bỏ dòng trùng lặp
 3. Chuẩn hóa thang điểm (30 vs 40) -> cột Diem_chuan_quy_doi
 4. Tách thông tin có cấu trúc từ cột Ghi chú (hệ số môn, TTNV, phân hiệu, giới tính...)
 5. Chuẩn hóa Mã ngành -> tách Ma_nganh_goc
 6. Kiểm tra & gắn cờ outlier điểm số
 7. Tạo cột nhóm tổ hợp môn (Khoi_to_hop) để giảm cardinality khi encode
 8. Kiểm tra tính nhất quán Mã trường <-> Tên trường (log cảnh báo nếu có)
 9. Chuẩn hóa kiểu dữ liệu cuối cùng
"""

import re
import pandas as pd
import numpy as np

INPUT_PATH = "diemchuan_2024.csv"
OUTPUT_PATH = "diemchuan_2024_cleaned.csv"


# ---------------------------------------------------------------------------
# BƯỚC 1: Đọc file, xử lý BOM
# ---------------------------------------------------------------------------
def load_data(path: str) -> pd.DataFrame:
    # utf-8-sig tự động loại bỏ BOM (﻿) ở đầu file nếu có
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    print(f"[1] Đã đọc {len(df)} dòng, {len(df.columns)} cột.")
    return df


# ---------------------------------------------------------------------------
# BƯỚC 2: Loại bỏ trùng lặp
# ---------------------------------------------------------------------------
def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    n_before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    n_removed = n_before - len(df)
    print(f"[2] Đã loại bỏ {n_removed} dòng trùng lặp.")
    return df


# ---------------------------------------------------------------------------
# BƯỚC 3: Chuẩn hóa thang điểm về thang 30
# ---------------------------------------------------------------------------
def normalize_score_scale(df: pd.DataFrame) -> pd.DataFrame:
    """
    Loại điểm 'THPTQG - Thang 40' => quy đổi về thang 30 theo công thức
    tuyến tính chính thức của Bộ GD&ĐT: diem_30 = diem_40 * 30 / 40.
    LƯU Ý: đây là công thức quy đổi TUYẾN TÍNH đơn giản. Một số trường có thể
    công bố công thức riêng (ví dụ chỉ nhân hệ số môn Ngoại ngữ x2 rồi lấy
    tổng, không hẳn là thang 40 tuyến tính đều). Nhóm nên đối chiếu lại với
    đề án tuyển sinh chính thức của từng trường nếu cần độ chính xác cao hơn
    cho những trường có điểm chuẩn ở thang 40.
    """
    df["Thang_diem_goc"] = np.where(
        df["Loại điểm"].str.contains("Thang 40", na=False), 40, 30
    )

    df["Diem_chuan_quy_doi"] = np.where(
        df["Thang_diem_goc"] == 40,
        (df["Điểm chuẩn"] * 30 / 40).round(2),
        df["Điểm chuẩn"],
    )
    n_converted = (df["Thang_diem_goc"] == 40).sum()
    print(f"[3] Đã quy đổi {n_converted} dòng từ thang 40 về thang 30 "
          f"(cột mới: Diem_chuan_quy_doi).")
    return df


# ---------------------------------------------------------------------------
# BƯỚC 4: Tách thông tin có cấu trúc từ Ghi chú
# ---------------------------------------------------------------------------
SUBJECTS = [
    "Tiếng Anh", "Toán", "Ngữ văn", "Vật lý", "Hóa học", "Sinh học",
    "Lịch sử", "Địa lý", "Ngoại ngữ", "Năng khiếu", "Vẽ mỹ thuật", "Vẽ",
]

def extract_note_features(df: pd.DataFrame) -> pd.DataFrame:
    ghi_chu = df["Ghi chú"].fillna("")

    # 4.1 Môn được nhân hệ số 2 (nếu có nêu tên môn cụ thể)
    def find_subject_x2(text: str):
        if "hệ số 2" in text or "nhân 2" in text or "nhân hệ số 2" in text or "x2" in text:
            for subj in SUBJECTS:
                if subj.lower() in text.lower():
                    return subj
            return "Không_xác_định_môn"
        return None

    df["Mon_he_so_2"] = ghi_chu.apply(find_subject_x2)

    # 4.2 Giới hạn số thứ tự nguyện vọng tối đa (TTNV <= N)
    def find_ttnv(text: str):
        m = re.search(r"TTNV\s*[<=]+\s*(\d+)", text)
        return int(m.group(1)) if m else np.nan

    df["TTNV_max"] = ghi_chu.apply(find_ttnv)

    # 4.3 Phân hiệu / cơ sở đào tạo
    def find_campus(text: str):
        m = re.search(r"(Phân hiệu|Cơ sở)\s+([^\,;]+)", text, flags=re.IGNORECASE)
        return m.group(2).strip() if m else None

    df["Phan_hieu_co_so"] = ghi_chu.apply(find_campus)

    # 4.4 Điều kiện giới tính (một số ngành đặc thù: an ninh, quân đội...)
    def find_gender(text: str):
        low = text.lower()
        if "nam" in low and "nữ" not in low:
            return "Nam"
        if "nữ" in low and "nam" not in low:
            return "Nữ"
        return None

    df["Dieu_kien_gioi_tinh"] = ghi_chu.apply(find_gender)

    # 4.5 Cờ đánh dấu "còn ghi chú chưa được phân tích cấu trúc"
    #     (giữ lại để nhóm review thủ công nếu cần, không xóa thông tin gốc)
    df["Ghi_chu_can_review"] = (
        (ghi_chu != "")
        & df["Mon_he_so_2"].isna()
        & df["TTNV_max"].isna()
        & df["Phan_hieu_co_so"].isna()
        & df["Dieu_kien_gioi_tinh"].isna()
    )

    print(f"[4] Đã tách đặc trưng từ Ghi chú: "
          f"{df['Mon_he_so_2'].notna().sum()} dòng có môn hệ số 2, "
          f"{df['TTNV_max'].notna().sum()} dòng có giới hạn TTNV, "
          f"{df['Phan_hieu_co_so'].notna().sum()} dòng có phân hiệu/cơ sở, "
          f"{df['Ghi_chu_can_review'].sum()} dòng ghi chú còn lại cần review thủ công.")
    return df


# ---------------------------------------------------------------------------
# BƯỚC 5: Chuẩn hóa Mã ngành
# ---------------------------------------------------------------------------
def normalize_major_code(df: pd.DataFrame) -> pd.DataFrame:
    df["Ma_nganh_goc"] = df["Mã ngành"].astype(str).str.split("_").str[0]
    n_split = df["Mã ngành"].astype(str).str.contains("_").sum()
    print(f"[5] Đã tách Ma_nganh_goc cho {n_split} dòng có hậu tố '_' "
          f"(chuyên ngành hẹp trong 1 mã ngành gốc).")
    return df


# ---------------------------------------------------------------------------
# BƯỚC 6: Gắn cờ outlier điểm số (sau khi đã quy đổi thang điểm ở bước 3)
# ---------------------------------------------------------------------------
def flag_outliers(df: pd.DataFrame) -> pd.DataFrame:
    q1 = df["Diem_chuan_quy_doi"].quantile(0.25)
    q3 = df["Diem_chuan_quy_doi"].quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    df["Outlier_diem"] = (
        (df["Diem_chuan_quy_doi"] < lower) | (df["Diem_chuan_quy_doi"] > upper)
    )
    print(f"[6] Đã gắn cờ {df['Outlier_diem'].sum()} dòng nằm ngoài khoảng "
          f"IQR [{lower:.2f}, {upper:.2f}] để nhóm review "
          f"(KHÔNG tự xóa vì có thể là ngành đặc thù hợp lệ).")
    return df


# ---------------------------------------------------------------------------
# BƯỚC 7: Nhóm tổ hợp môn theo khối truyền thống để giảm cardinality
# ---------------------------------------------------------------------------
def group_subject_combination(df: pd.DataFrame) -> pd.DataFrame:
    # Lấy ký tự đầu của mã tổ hợp (A, B, C, D, M, N, H, T, DD...) làm nhóm khối lớn
    df["Khoi_to_hop"] = df["Tổ hợp môn"].astype(str).str.extract(r"^([A-Za-z]+)")
    n_groups = df["Khoi_to_hop"].nunique()
    print(f"[7] Đã tạo Khoi_to_hop ({n_groups} nhóm) từ {df['Tổ hợp môn'].nunique()} "
          f"tổ hợp môn chi tiết -> dùng cho encoding thay vì one-hot 182 chiều.")
    return df


# ---------------------------------------------------------------------------
# BƯỚC 8: Kiểm tra tính nhất quán Mã trường <-> Tên trường
# ---------------------------------------------------------------------------
def check_school_consistency(df: pd.DataFrame) -> None:
    map1 = df.groupby("Mã trường")["Trường đào tạo"].nunique()
    map2 = df.groupby("Trường đào tạo")["Mã trường"].nunique()
    n_bad1 = (map1 > 1).sum()
    n_bad2 = (map2 > 1).sum()
    if n_bad1 == 0 and n_bad2 == 0:
        print("[8] Kiểm tra nhất quán Mã trường <-> Tên trường: OK, không có xung đột.")
    else:
        print(f"[8] CẢNH BÁO: {n_bad1} mã trường ứng với nhiều tên, "
              f"{n_bad2} tên trường ứng với nhiều mã. Cần rà soát thủ công.")


# ---------------------------------------------------------------------------
# BƯỚC 9: Chuẩn hóa kiểu dữ liệu cuối cùng
# ---------------------------------------------------------------------------
def finalize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    df["Mã ngành"] = df["Mã ngành"].astype(str)
    df["Ma_nganh_goc"] = df["Ma_nganh_goc"].astype(str)
    df["Diem_chuan_quy_doi"] = df["Diem_chuan_quy_doi"].astype(float)
    df["TTNV_max"] = df["TTNV_max"].astype("float")  # giữ NaN cho dòng không có
    text_cols = ["Mã trường", "Trường đào tạo", "Ngành", "Nhóm ngành",
                 "Tên ngành", "Tổ hợp môn", "Khoi_to_hop"]
    for c in text_cols:
        df[c] = df[c].astype(str).str.strip()
    print("[9] Đã chuẩn hóa lại kiểu dữ liệu cho các cột chính.")
    return df


# ---------------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------------
def main():
    df = load_data(INPUT_PATH)
    df = remove_duplicates(df)
    df = normalize_score_scale(df)
    df = extract_note_features(df)
    df = normalize_major_code(df)
    df = flag_outliers(df)
    df = group_subject_combination(df)
    check_school_consistency(df)
    df = finalize_dtypes(df)

    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(f"\n✅ Hoàn tất. Đã xuất file sạch: {OUTPUT_PATH} ({len(df)} dòng, "
          f"{len(df.columns)} cột).")
    print("\nCác cột mới được thêm vào so với file gốc:")
    new_cols = [
        "Thang_diem_goc", "Diem_chuan_quy_doi", "Mon_he_so_2", "TTNV_max",
        "Phan_hieu_co_so", "Dieu_kien_gioi_tinh", "Ghi_chu_can_review",
        "Ma_nganh_goc", "Outlier_diem", "Khoi_to_hop",
    ]
    for c in new_cols:
        print(f"  - {c}")


if __name__ == "__main__":
    main()
