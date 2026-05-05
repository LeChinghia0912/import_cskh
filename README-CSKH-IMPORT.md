# CSKH Excel Import (Python)

Script: `cskh_import_excel.py` (thư mục gốc dự án)

## Chuẩn bị

- Python 3.10+
- `.env` có đủ biến `DB3_*` và `DB4_*` (host, port, database, username; password có thể để trống)

Cài thư viện:

```bash
pip install -r requirements-cskh-import.txt
```

## Định dạng file Excel

Script tự chọn một trong hai chế độ (in ra dòng `Excel column mode:` khi chạy):

### 1) Định dạng mới (khuyến nghị) — dòng 1 là tiêu đề `bảng.cột`

Khi dòng đầu có đủ các cột nhận diện được (tối thiểu: `cskh_tickets.created_at`, `cskh_customers.name`, `cskh_tickets.issue_content`), script map **theo tên cột**, không còn phụ thuộc vị trí A/B/C cố định.

| Tiêu đề cột Excel (không phân biệt hoa thường, khoảng trắng thừa được chuẩn hoá) | Ý nghĩa |
|---|---|
| `cskh_tickets.created_at` hoặc `tickets.created_at` | Ngày/giờ tạo ticket (ô merge theo ngày → script `ffill` trên đúng cột này) |
| `cskh_status.code` | Trạng thái: có thể là mã workflow (`completed`, `received`, …) hoặc nhãn tiếng Việt (vd `Hoàn thành`, `Chờ`, …) → map sang `workflow_status` |
| `cskh_customers.name` | Tên khách hàng |
| `cskh_customer_phones.phone` | Số điện thoại |
| `cskh_tickets.issue_content` | Nội dung vấn đề / yêu cầu |
| `cskh_tickets.handling` | Tình trạng xử lý → ghi `cskh_tickets.handling` |
| `cskh_solutions.resolution_text` | Kết quả xử lý → insert `cskh_solutions` |
| `users.full_name` | Người tiếp nhận → `created_by` (map user; nếu `Kỹ thuật` thì dùng `--fallback-created-by` và tạo transfer) |
| `cskh_tickets.source` | Nguồn (tối đa 32 ký tự trên DB) |
| `cskh_receiving_departments.id` | ID phòng tiếp nhận (số); nếu có thì ưu tiên gán `receiving_department_id` / `current_department_id` |
| `cskh_tickets.notes` | Ghi chú ticket (giữ nguyên nội dung ô; có thể ghép thêm dòng `Tỉnh/Thành`) |
| `Tỉnh/Thành` (hoặc tiêu đề có cả hai từ *tỉnh* và *thành*) | Thêm dòng `Tỉnh/Thành: …` vào `notes` |
| `cskh_tickets.product_text` *(tuỳ chọn)* | Tên sản phẩm để fuzzy match `mysql3.products` (nếu không có cột này thì không gán `product_id`) |

### 2) Định dạng cũ — đúng 9 cột A..I

Nếu dòng 1 **không** được nhận là header DB, script dùng vị trí cố định:

- A: ngày  
- B: trạng thái sheet (tiếng Việt / mã)  
- C: tên KH  
- D: SĐT  
- E: sản phẩm (fuzzy match `products`)  
- F: `issue_content`  
- G: nội dung ghi vào **`cskh_solutions.resolution_text`** (legacy: không ghi `cskh_tickets.handling`)  
- H: nhân viên tiếp nhận  
- I: nguồn  

Cột `notes` legacy: chỉ thêm dòng `Trạng thái sheet: …` khi B có giá trị.

## Chạy thử (không ghi DB)

```bash
python cskh_import_excel.py --excel "D:\path\to\file.xlsx" --dry-run
```

## Chạy thật

Nên có `--fallback-created-by` khi cột nhân viên trống hoặc là `Kỹ thuật`:

```bash
python cskh_import_excel.py --excel "D:\path\to\file.xlsx" --fallback-created-by 1
```

Một sheet cụ thể:

```bash
python cskh_import_excel.py --excel "D:\path\to\file.xlsx" --sheet "T12026" --fallback-created-by 1
```

## Ghi chú kỹ thuật

- Script tự tạo `cskh_receiving_departments` nếu chưa có phòng `--tech-department-name` (mặc định `Kỹ thuật`).
- Script tự tạo `users` nếu không tìm thấy `full_name` tương ứng (introspect bảng `users`).
- Tên sheet dạng `T{tháng}{năm}` (vd `T12026`) dùng để bù ngày khi ô ngày chỉ có số ngày hoặc định dạng ngắn.

### Chuẩn hóa ô tên khách (cột C / `cskh_customers.name`) trước khi import

Import và chế độ `--normalize-excel-out` đều tách/gom SĐT trong cùng một ô theo các kiểu sau (không đổi vị trí cột legacy):

- SĐT cuối ô sau khoảng trắng/gạch; SĐT có khoảng trắng giữa các số (`091 8070836`).
- Ngoặc quanh SĐT cuối ô: `Tên ( 0365… )`.
- `+84…` / `084…` → quy về dạng `0xxxxxxxxx`.
- 9 số di động thiếu số `0` đầu (vd `948283559` → `0948283559`), không áp dụng cho chuỗi nằm sau chữ `0` của SĐT 10 số.
- Nhiều SĐT trong một ô (`/`, `-` giữa các khối) → cột SĐT ghi `số1; số2` (DB vẫn dùng số đầu để match); phần mô tả sau SĐT cuối (vd “Hỗ trợ máy lọc…”) → ghép vào `notes` nếu không nhận là tên phụ.
- Tên phụ sau SĐT cuối (vd `… - Phan Thị Lệ`, `… / Nguyễn Thị Huế`) → gộp vào chuỗi tên (`Tên1 / Tên2`).

Ghi file Excel đã tách **và** gộp ô cột ngày trên **cùng file** (không cần DB):

```bash
python cskh_import_excel.py --excel "file.xlsx" --normalize-excel-out "file_da_tach.xlsx"
```

Chỉ tách tên/SĐT, **không** gộp cột ngày:

```bash
python cskh_import_excel.py --excel "file.xlsx" --normalize-excel-out "file_da_tach.xlsx" --no-merge-created-at
```

### Gộp ô cột ngày (`created_at`) theo từng ngày (giống merge trên Excel)

Ô đầu mỗi block có ngày, các dòng phía dưới để trống cột ngày = cùng ngày (giống `ffill` khi import). Lệnh sau **merge dọc** các ô đó trên đúng cột tiêu đề `cskh_tickets.created_at` / `tickets.created_at`; file legacy (9 cột A..I) thì gộp **cột A**.

```bash
python cskh_import_excel.py --excel "file.xlsx" --merge-created-at-out "file_da_gop_ngay.xlsx"
```

Không dùng chung một lúc với `--normalize-excel-out` (vì bước gộp ngày đã nằm trong `--normalize-excel-out` trừ khi có `--no-merge-created-at`). Ghi file mới (nên khác tên file nguồn để tránh lỗi khi file đang mở trên Windows).



python cskh_import_excel.py --excel "TIẾP NHẬN CSKH 2026.xlsx" --normalize-excel-out "da_tach.xlsx"