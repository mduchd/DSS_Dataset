"""Build a transparent first-pass mapping from academic majors to VietJobs categories.

Mappings are based only on explicit Vietnamese keywords in the major name or
the source major group. They express topical relevance, not an employment
guarantee. Unmapped majors are exported for a human review pass.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ADMISSION_PATH = ROOT / "data" / "processed" / "admission" / "admission_cutoffs_2018_2024.csv"
JOB_SUMMARY_PATH = ROOT / "data" / "processed" / "jobs" / "job_market_summary_by_category.csv"
MASTER_DIR = ROOT / "data" / "master"

CATEGORY_KEYS = {
    "business": "kinh_doanh_bán_hàng_chăm_sóc_khách_hàng",
    "production": "sản_xuất_lao_động_phổ_thông_cơ_khí",
    "marketing": "marketing_truyền_thông_quảng_cáo_nội_dung",
    "finance": "tài_chính_kế_toán_ngân_hàng_bảo_hiểm",
    "tourism": "du_lịch_nhà_hàng_khách_sạn_dịch_vụ",
    "design": "thiết_kế_nghệ_thuật_giải_trí_truyền_hình_báo_chí",
    "legal_hr": "nhân_sự_hành_chính_pháp_chế_tư_vấn",
    "construction": "xây_dựng_kiến_trúc_bất_động_sản",
    "it": "công_nghệ_thông_tin_kỹ_thuật_số",
    "logistics": "logistics_vận_tải_chuỗi_cung_ứng",
    "electrical": "kỹ_thuật_điện_điện_tử_viễn_thông",
    "education": "giáo_dục_đào_tạo_nghiên_cứu",
    "health": "y_tế_dược_chăm_sóc_sức_khỏe_công_nghệ_sinh_học",
    "language": "ngôn_ngữ_dịch_thuật",
    "other": "nhóm_nghề_khác",
    "agriculture": "nông_nghiệp_năng_lượng_môi_trường",
}

# Rules are intentionally narrow: a direct term in the major name earns high
# confidence. A broad group-level relationship is a fallback only.
NAME_RULES = (
    ("it", r"cong nghe thong tin|tin hoc|ky thuat du lieu|tri tue nhan tao|an toan thong tin|he thong thong tin|ky thuat may tinh|phan mem|mang may tinh|internet van vat", "high"),
    ("logistics", r"logistics|chuoi cung ung|van tai|hang hai|cang bien|xuat nhap khau", "high"),
    ("finance", r"ke toan|kiem toan|tai chinh|ngan hang|bao hiem", "high"),
    ("marketing", r"marketing|truyen thong|quan he cong chung|bao chi|quang cao|noi dung", "high"),
    ("language", r"ngon ngu|tieng anh|tieng trung|tieng nhat|tieng han|tieng phap|tieng nga|tieng duc|han nom|trung quoc hoc|nhat ban hoc|han quoc hoc|bien phien dich", "high"),
    ("legal_hr", r"luat|phap ly|tu phap|hanh chinh nhan su|quan tri nhan luc|quan l[yi] nha nuoc|thanh tra|van thu|luu tru", "high"),
    ("education", r"su pham|giao duc|dao tao giao vien|quan ly giao duc", "high"),
    ("health", r"y khoa|y hoc|dieu duong|duoc hoc|rang ham mat|ky thuat y hoc|phuc hoi chuc nang|dinh duong|ho sinh", "high"),
    ("construction", r"kien truc|xay dung|bat dong san|quy hoach|do thi|cau duong", "high"),
    ("electrical", r"dien tu|dien dien|vien thong|tu dong hoa|ky thuat dien", "high"),
    ("production", r"co khi|o to|che tao|ky thuat vat lieu|cong nghe vat lieu|det may|cong nghe may|cong nghe thuc pham|in|giay", "high"),
    ("agriculture", r"nong nghiep|lam nghiep|thuy san|thu y|moi truong|nang luong|dia chat", "high"),
    ("tourism", r"du lich|khach san|nha hang|am thuc|quan tri dich vu", "high"),
    ("design", r"thiet ke|my thuat|am nhac|thanh nhac|dien anh|san khau|thoi trang|nhiep anh|mua", "high"),
    ("business", r"quan tri kinh doanh|thuong mai|kinh doanh quoc te|kinh te|quan ly cong nghiep|dau tu", "medium"),
    ("legal_hr", r"tam ly|cong tac xa hoi|quan ly nha nuoc|quan he quoc te", "medium"),
)

GROUP_RULES = {
    "kinh doanh va quan ly": ("business", "medium"),
    "kinh te quan tri kinh doanh thuong mai": ("business", "medium"),
    "may tinh va cong nghe thong tin": ("it", "high"),
    "cong nghe thong tin tin hoc": ("it", "high"),
    "cong nghe ky thuat": ("production", "medium"),
    "ky thuat": ("production", "medium"),
    "kien truc va xay dung": ("construction", "high"),
    "xay dung kien truc giao thong": ("construction", "high"),
    "du lich khach san the thao va dich vu ca nhan": ("tourism", "high"),
    "du lich khach san": ("tourism", "high"),
    "suc khoe": ("health", "high"),
    "y duoc": ("health", "high"),
    "khoa hoc su song": ("health", "medium"),
    "phap luat": ("legal_hr", "high"),
    "luat toa an": ("legal_hr", "high"),
    "nhan su hanh chinh": ("legal_hr", "high"),
    "nong lam nghiep va thuy san": ("agriculture", "high"),
    "thuy san lam nghiep nong nghiep": ("agriculture", "high"),
    "tai nguyen moi truong": ("agriculture", "high"),
    "moi truong va bao ve moi truong": ("agriculture", "high"),
    "bao chi va thong tin": ("marketing", "high"),
    "bao chi marketing quang cao pr": ("marketing", "high"),
    "nghe thuat": ("design", "high"),
    "my thuat am nhac nghe thuat": ("design", "high"),
    "thiet ke do hoa game da phuong tien": ("design", "high"),
    "khoa hoc giao duc va dao tao giao vien": ("education", "high"),
    "su pham giao duc": ("education", "high"),
    "dich vu van tai": ("logistics", "high"),
    "ngoai giao ngoai ngu": ("language", "medium"),
    "san xuat va che bien": ("production", "medium"),
    "o to co khi che tao": ("production", "high"),
    "dien lanh dien tu dien tu dong hoa": ("electrical", "high"),
    "cong nghe sinh hoa": ("health", "medium"),
    "cong nghe che bien thuc pham": ("production", "high"),
    "ke toan kiem toan": ("finance", "high"),
    "tai chinh ngan hang bao hiem": ("finance", "high"),
    "ngoai thuong xuat nhap khau kinh te quoc te": ("logistics", "medium"),
    "hang hai thuy loi thoi tiet": ("logistics", "medium"),
    "cong nghe vat lieu": ("production", "high"),
    "mo dia chat": ("agriculture", "medium"),
    "thoi trang may mac": ("design", "high"),
    "toan va thong ke": ("it", "low"),
    "toan hoc va thong ke": ("it", "low"),
    "dich vu xa hoi": ("other", "low"),
    "cong an quan doi": ("other", "low"),
    "an ninh quoc phong": ("other", "low"),
}


def normalize_key(value: object) -> str:
    if pd.isna(value):
        return ""
    value = unicodedata.normalize("NFKD", str(value))
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.replace("đ", "d").replace("Đ", "D").casefold()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def major_catalog(admission: pd.DataFrame) -> pd.DataFrame:
    fields = ["major_code", "major_name", "major_group_name", "year"]
    majors = admission.loc[:, fields].copy()
    majors["major_code"] = majors["major_code"].replace("", pd.NA)
    majors["major_name"] = majors["major_name"].replace("", pd.NA)
    majors = majors.dropna(subset=["major_code", "major_name"])
    grouped = majors.groupby(["major_code", "major_name", "major_group_name"], dropna=False)
    catalog = grouped.agg(
        admission_record_count=("year", "size"),
        first_year=("year", "min"),
        last_year=("year", "max"),
    ).reset_index()
    return catalog.sort_values(["major_code", "major_name", "major_group_name"], kind="stable")


def match_major(major_name: str, major_group: str) -> tuple[str, str, str] | None:
    name_key = normalize_key(major_name)
    group_key = normalize_key(major_group)
    for category_id, pattern, confidence in NAME_RULES:
        if re.search(pattern, name_key):
            return CATEGORY_KEYS[category_id], "major_name_keyword", confidence
    if group_key in GROUP_RULES:
        category_id, confidence = GROUP_RULES[group_key]
        return CATEGORY_KEYS[category_id], "major_group_rule", confidence
    return None


def main() -> None:
    MASTER_DIR.mkdir(parents=True, exist_ok=True)
    admission = pd.read_csv(ADMISSION_PATH, dtype="string", keep_default_na=False)
    job_summary = pd.read_csv(JOB_SUMMARY_PATH, dtype="string", keep_default_na=False)
    category_names = set(job_summary["job_category"])

    catalog = major_catalog(admission)
    catalog_path = MASTER_DIR / "major_catalog.csv"
    catalog.to_csv(catalog_path, index=False, encoding="utf-8", lineterminator="\n")

    mapped_rows = []
    unmapped_rows = []
    for row in catalog.itertuples(index=False):
        match = match_major(row.major_name, row.major_group_name)
        if match is None:
            unmapped_rows.append(row._asdict())
            continue
        category, basis, confidence = match
        if category not in category_names:
            raise ValueError(f"Mapping references a missing VietJobs category: {category}")
        mapped_rows.append(
            {
                **row._asdict(),
                "job_category": category,
                "mapping_basis": basis,
                "mapping_confidence": confidence,
                "mapping_note": "Topical relationship for exploration; verify before making a final recommendation.",
            }
        )

    mapping_columns = [
        "major_code", "major_name", "major_group_name", "job_category", "mapping_basis",
        "mapping_confidence", "mapping_note", "admission_record_count", "first_year", "last_year",
    ]
    mapping = pd.DataFrame(mapped_rows, columns=mapping_columns)
    mapping = mapping.sort_values(["major_code", "major_name"], kind="stable")
    mapping_path = MASTER_DIR / "major_job_mapping.csv"
    mapping.to_csv(mapping_path, index=False, encoding="utf-8", lineterminator="\n")

    unmapped = pd.DataFrame(unmapped_rows, columns=catalog.columns)
    unmapped_path = MASTER_DIR / "unmapped_majors.csv"
    unmapped.to_csv(unmapped_path, index=False, encoding="utf-8", lineterminator="\n")

    confidence_counts = Counter(mapping["mapping_confidence"])
    report = {
        "mapping_version": 1,
        "catalog_majors": len(catalog),
        "mapped_majors": len(mapping),
        "unmapped_majors": len(unmapped),
        "coverage_percent": round(len(mapping) / len(catalog) * 100, 2) if len(catalog) else 0,
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "rule_policy": "Explicit major-name rules take priority over broad major-group rules.",
        "outputs": {
            "catalog": str(catalog_path.relative_to(ROOT)).replace("\\", "/"),
            "mapping": str(mapping_path.relative_to(ROOT)).replace("\\", "/"),
            "unmapped": str(unmapped_path.relative_to(ROOT)).replace("\\", "/"),
        },
    }
    report_path = MASTER_DIR / "major_job_mapping_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
