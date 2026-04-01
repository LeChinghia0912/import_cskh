# CSKH Excel Import (Python)

Script: `scripts/cskh_import_excel.py`

## Chuẩn bị

- Python 3.10+
- `.env` đã có các biến `DB3_*` và `DB4_*` đúng (theo `config/database.php`)

Cài thư viện:

```bash
pip install -r scripts/requirements-cskh-import.txt
```

## Mapping cột Excel

Script đọc theo vị trí cột (A..I):

- A: Ngày tháng → `cskh_tickets.created_at`
- B: Trạng thái sheet (Chờ/Đang xử lý/Chưa LL/Xử lý sau/...) → lưu vào `cskh_tickets.notes` (workflow sẽ set `received`)
- C: Tên KH → `cskh_customers.name`
- D: SĐT → `cskh_customer_phones.phone` + `phone_normalized`
- E: Sản phẩm (gần đúng) → fuzzy match sang `mysql3.products` (các cột `product_name/name/model`), ghi tên chuẩn vào `cskh_tickets.product_text` và ghi lại `id/score` vào `notes`
- F: Vấn đề hỗ trợ → `cskh_tickets.issue_content`
- G: Tình trạng xử lý → `cskh_tickets.handling`
- H: Nhân viên tiếp nhận → map `users.full_name` → `cskh_tickets.created_by`
  - Nếu H = `Kỹ thuật`: ticket sẽ được tạo và auto tạo bản ghi `cskh_ticket_transfers` (chuyển đến phòng ban “Kỹ thuật”)
- I: Nguồn → `cskh_tickets.source` (cắt tối đa 32 ký tự)

## Chạy thử (không ghi DB)

```bash
python scripts/cskh_import_excel.py --excel "D:\path\to\file.xlsx" --dry-run
```

## Chạy thật

Bạn nên truyền `--fallback-created-by` để dùng trong trường hợp:
- Cột H trống
- hoặc cột H = `Kỹ thuật`

```bash
python scripts/cskh_import_excel.py --excel "D:\path\to\file.xlsx" --fallback-created-by 1
```

## Ghi chú kỹ thuật

- Script tự tạo `cskh_receiving_departments` nếu chưa có “Kỹ thuật”.
- Script tự tạo `users` nếu không tìm thấy `full_name` tương ứng. Nó sẽ introspect schema `users` để insert đúng các cột đang tồn tại.

