# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import logging
import os

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

def clean_diemthi(year):
    input_path = f'data/raw/exam/diemthi_{year}.csv'
    output_path = f'data/cleaned/exam/diemthi_{year}_cleaned.csv'
    
    print(f"\n--- THỰC THI 9 TIÊU CHÍ CLEAN: ĐIỂM THI {year} ---")
    
    # ==========================================
    # 1. Đọc đúng encoding (xử lý BOM)
    # ==========================================
    df = pd.read_csv(input_path, encoding='utf-8-sig', dtype={'SBD': str})
    df.columns = df.columns.str.strip()
    print("1. Đã đọc encoding utf-8-sig.")

    # ==========================================
    # 2. Loại bỏ dòng trùng lặp
    # ==========================================
    initial_rows = len(df)
    df.drop_duplicates(inplace=True)
    df.dropna(subset=['SBD'], inplace=True)
    print(f"2. Đã loại bỏ {initial_rows - len(df)} dòng trùng/rỗng.")

    # ==========================================
    # 3. Chuẩn hóa thang điểm (Đảm bảo thang 10)
    # ==========================================
    score_cols = ['Toan', 'NguVan', 'VatLy', 'HoaHoc', 'SinhHoc', 'LichSu', 'DiaLy', 'GDCD', 'NgoaiNgu']
    for col in score_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(-1.0)
            # Ép các điểm vô lý > 10 về -1.0
            df[col] = np.where(df[col] > 10.0, -1.0, df[col])
    print("3. Đã chuẩn hóa thang điểm (Max 10).")

    # ==========================================
    # 4. Tách thông tin có cấu trúc (Lấy Mã tỉnh từ SBD)
    # SBD của Bộ GDĐT luôn có 2 số đầu là mã Cụm thi/Tỉnh
    # ==========================================
    df['SBD'] = df['SBD'].str.zfill(8) # Đảm bảo SBD luôn đủ 8 số
    df['Ma_tinh_extract'] = df['SBD'].str[:2]
    print("4. Đã bóc tách Mã tỉnh từ SBD.")

    # ==========================================
    # 5. Chuẩn hóa Mã (Làm sạch format Mã tỉnh)
    # ==========================================
    df['Ma_tinh_extract'] = df['Ma_tinh_extract'].apply(lambda x: x if x.isdigit() else '99')
    print("5. Đã chuẩn hóa Mã tỉnh gốc.")

    # ==========================================
    # 6. Kiểm tra & gán cờ outlier điểm số
    # ==========================================
    # Nếu thí sinh có điểm dưới 0 (nhưng khác -1.0), đó là outlier
    df['Is_Outlier'] = False
    for col in score_cols:
        if col in df.columns:
            df['Is_Outlier'] = df['Is_Outlier'] | ((df[col] < 0) & (df[col] != -1.0))
    print(f"6. Phát hiện {df['Is_Outlier'].sum()} outlier điểm số.")

    # ==========================================
    # 7. Tạo cột nhóm tổ hợp môn (Khoi_to_hop)
    # Tính mẫu tổng điểm A00 để giảm tải cho bước Processed
    # ==========================================
    if all(c in df.columns for c in ['Toan', 'VatLy', 'HoaHoc']):
        # Chỉ tính tổng nếu thi đủ 3 môn (không có môn nào = -1)
        valid_A00 = (df['Toan'] != -1) & (df['VatLy'] != -1) & (df['HoaHoc'] != -1)
        df['Tong_A00'] = np.where(valid_A00, df['Toan'] + df['VatLy'] + df['HoaHoc'], -1.0)
        print("7. Đã tạo nhóm tổ hợp điểm (Tong_A00).")

    # ==========================================
    # 8. Kiểm tra tính nhất quán (SBD duy nhất)
    # ==========================================
    inconsistent = df.groupby('SBD').size()
    errors = inconsistent[inconsistent > 1].index.tolist()
    if errors:
        logging.warning(f"BƯỚC 8: Phát hiện SBD xuất hiện nhiều lần (chấm đè/lỗi sinh format): {len(errors)} ca.")
    else:
        print("8. Dữ liệu SBD hoàn toàn nhất quán.")

    # ==========================================
    # 9. Chuẩn hóa kiểu dữ liệu cuối cùng
    # ==========================================
    type_mapping = {'SBD': str, 'Ma_tinh_extract': str, 'Is_Outlier': bool}
    for col, dtype in type_mapping.items():
        if col in df.columns:
            df[col] = df[col].astype(dtype)
    print("9. Đã ép kiểu dữ liệu chuẩn xác.")

    # XUẤT FILE
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"=> XONG! Đã lưu: {output_path}")

if __name__ == "__main__":
    clean_diemthi('2021')
    clean_diemthi('2022')