# DSS Dataset — Hỗ trợ lựa chọn ngành học và trường đại học

Kho dữ liệu cho đề tài **“Xây dựng hệ thống hỗ trợ ra quyết định trong lựa chọn ngành học và trường đại học cho học sinh THPT.”**

Mục tiêu của bộ dữ liệu là hỗ trợ phân tích và gợi ý tham khảo dựa trên ba góc nhìn:

- **Năng lực đầu vào:** điểm thi tốt nghiệp THPT.
- **Khả năng trúng tuyển:** điểm chuẩn theo trường, ngành và tổ hợp xét tuyển.
- **Thị trường lao động:** tin tuyển dụng, kỹ năng, địa điểm và thông tin lương (nếu có).

> Hệ thống chỉ nhằm cung cấp gợi ý tham khảo, không thay thế quyết định cá nhân hoặc tư vấn tuyển sinh chính thức.

## Cấu trúc repository

```text
data/
├── raw/                         # Dữ liệu gốc, không chỉnh sửa trực tiếp
│   ├── admission/
│   │   ├── diemchuan_2018_2023.xlsx
│   │   └── diemchuan_2024.csv
│   ├── exam/
│   │   ├── diemthi_2021.csv
│   │   ├── diemthi_2022.csv
│   │   ├── diemthi_2023.csv
│   │   ├── diemthi_2024.csv
│   │   ├── diemthi_2025_ct2006.csv
│   │   └── diemthi_2025_ct2018.csv
│   ├── jobs/
│   │   └── VietJobs/
│   │       └── VietJobs.csv
│   └── master/                  # Dành cho bảng danh mục tham chiếu
├── cleaned/                     # Dữ liệu sau làm sạch và chuẩn hóa
└── processed/                   # Dữ liệu đã tổng hợp, sẵn sàng phân tích
```

`raw/` luôn được giữ nguyên so với dữ liệu đã tải. Toàn bộ thao tác loại trùng, đổi kiểu dữ liệu, chuẩn hóa tên cột hoặc mapping phải tạo kết quả mới trong `cleaned/` hoặc `processed/`.

## Nguồn dữ liệu

| Nhóm dữ liệu | Phạm vi | Nguồn |
| --- | --- | --- |
| Điểm chuẩn đại học | 2018–2024 | [HTNam1710/ADS_Final](https://github.com/HTNam1710/ADS_Final) |
| Điểm thi tốt nghiệp THPT | 2021–2025 | [sdgedfegw/du-lieu-diem-thi](https://github.com/sdgedfegw/du-lieu-diem-thi) |
| Tin tuyển dụng Việt Nam | VietJobs | [dinhieufam/VietJobs](https://huggingface.co/datasets/dinhieufam/VietJobs) |

Các file được lấy riêng theo năm thay vì dùng một file điểm thi tổng hợp để quá trình kiểm tra schema, làm sạch và chuẩn hóa có thể được tái lập rõ ràng.

## Lưu ý dữ liệu

- Hai file điểm thi năm 2025 được tách theo **chương trình 2006** và **chương trình 2018**. Không nên so sánh trực tiếp phân phối điểm 2025 với các năm trước mà không nêu rõ sự khác biệt chương trình và môn thi.
- Dữ liệu điểm thi có cột `SBD`. Không công bố lại bản ghi cá nhân, kết quả truy vấn theo số báo danh hoặc dashboard có thể nhận diện cá nhân.
- Việc liên kết ngành học với thị trường việc làm cần một bảng mapping rõ ràng, ví dụ `major_code`, `major_name`, `major_group`, `job_category`, `mapping_confidence`.
- Một số file CSV lớn hơn 50 MB. GitHub đã chấp nhận chúng, nhưng Git LFS nên được cân nhắc nếu dữ liệu tiếp tục tăng.

## Quy trình đề xuất

```text
raw
  → kiểm tra schema, giá trị thiếu, trùng lặp và kiểu dữ liệu
  → cleaned
  → chuẩn hóa mã/tên trường, ngành, tổ hợp, tỉnh/thành và nhóm nghề
  → processed
  → phân tích, dashboard hoặc mô hình gợi ý
```

## Trạng thái

- [x] Tải dữ liệu gốc về `data/raw/`
- [ ] Bổ sung danh mục ngành và bảng mapping ngành–nghề
- [ ] Làm sạch, chuẩn hóa schema giữa các năm
- [ ] Tạo bảng tổng hợp phục vụ phân tích và hệ thống gợi ý

## Làm sạch điểm chuẩn 2018–2023

Chạy script sau để tạo một bản dữ liệu clean. File gốc trong `data/raw/` không bị thay đổi.

```bash
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python scripts\clean_diemchuan_2018_2023.py
```

Kết quả: `data/cleaned/admission/diemchuan_2018_2023_cleaned.csv`.

## Chạy giao diện web

Giao diện MVP dùng **HTML, CSS, JavaScript** và **Flask**. Nó hiện đối chiếu điểm người dùng với dữ liệu điểm chuẩn 2024, theo các tổ hợp `A00`, `A01`, `B00`, `C00` và `D01`.

```bash
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python app.py
```

Sau đó mở `http://127.0.0.1:5000` trên trình duyệt.

Các phần VietJobs và xu hướng nhiều năm đã có vị trí trong giao diện, nhưng chỉ được cá nhân hóa sau khi hoàn tất cleaning và bảng mapping ngành–nghề.
