import argparse
import json
import os
import re
import secrets
import string
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv
from rapidfuzz import fuzz, process
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from unidecode import unidecode


def _env(name: str, default: Optional[str] = None) -> str:
    v = os.getenv(name, default)
    if v is None or v == "":
        raise RuntimeError(f"Missing env var: {name}")
    return v


def _normalize_text(s: Any) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    if not s:
        return ""
    s = unidecode(s)
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_vn_phone(raw: Any) -> str:
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    digits = re.sub(r"\D+", "", s)
    if digits.startswith("84") and len(digits) >= 10:
        digits = "0" + digits[2:]
    return digits


def make_username_from_full_name(full_name: str) -> str:
    base = _normalize_text(full_name).replace(" ", ".")
    base = base[:32] if base else "user"
    return base


def random_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def bcrypt_laravel(password: str) -> str:
    import bcrypt  # lazy import

    salt = bcrypt.gensalt(rounds=10)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
    # Laravel/PHP commonly uses $2y$ prefix; PHP can also accept $2b$ on newer versions,
    # but to be safe we rewrite to $2y$.
    if hashed.startswith("$2b$"):
        hashed = "$2y$" + hashed[4:]
    return hashed


def build_mysql_url(prefix: str) -> str:
    host = _env(f"{prefix}_HOST")
    port = _env(f"{prefix}_PORT")
    db = _env(f"{prefix}_DATABASE")
    user = _env(f"{prefix}_USERNAME")
    pwd = os.getenv(f"{prefix}_PASSWORD", "")
    # pymysql works well on Windows
    return f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}?charset=utf8mb4"


def get_table_columns(engine: Engine, table: str, schema: Optional[str] = None) -> List[str]:
    if schema is None:
        schema = engine.url.database
    q = text(
        """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table
        ORDER BY ORDINAL_POSITION
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(q, {"schema": schema, "table": table}).fetchall()
    return [r[0] for r in rows]


def select_one(engine: Engine, sql: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    with engine.begin() as conn:
        row = conn.execute(text(sql), params).mappings().first()
        return dict(row) if row else None


def ensure_cskh_status_code(engine4: Engine, code: str, expected_id: Optional[int] = None) -> Dict[str, Any]:
    row = select_one(
        engine4,
        "SELECT id, code, description FROM cskh_status WHERE code = :c LIMIT 1",
        {"c": code},
    )
    if not row:
        raise RuntimeError(f"Missing cskh_status.code='{code}'. Please create it before import.")
    if expected_id is not None and int(row.get("id") or 0) != expected_id:
        raise RuntimeError(
            f"cskh_status.code='{code}' exists but id={row.get('id')} (expected id={expected_id}). "
            "Fix the seed/data or remove the expected_id check."
        )
    return row


def upsert_customer_and_phone(
    engine4: Engine,
    customer_name: str,
    phone_raw: Any,
) -> Optional[int]:
    phone_norm = normalize_vn_phone(phone_raw)
    if not customer_name and not phone_norm:
        return None

    if phone_norm:
        existing = select_one(
            engine4,
            "SELECT customer_id FROM cskh_customer_phones WHERE phone_normalized = :p LIMIT 1",
            {"p": phone_norm},
        )
        if existing:
            return int(existing["customer_id"])

    customer_cols = set(get_table_columns(engine4, "cskh_customers"))

    payload: Dict[str, Any] = {}
    if "name" in customer_cols:
        payload["name"] = customer_name or phone_norm or "Khách hàng"
    if "created_at" in customer_cols:
        payload["created_at"] = datetime.now()
    if "updated_at" in customer_cols:
        payload["updated_at"] = datetime.now()

    if "name" not in payload:
        raise RuntimeError("cskh_customers table missing required column: name")

    columns = ", ".join(payload.keys())
    values = ", ".join([f":{k}" for k in payload.keys()])
    sql = f"INSERT INTO cskh_customers ({columns}) VALUES ({values})"

    with engine4.begin() as conn:
        res = conn.execute(text(sql), payload)
        customer_id = int(res.lastrowid)

        if phone_norm:
            # Insert phone; if another process inserted same phone concurrently, ignore.
            conn.execute(
                text(
                    """
                    INSERT IGNORE INTO cskh_customer_phones (customer_id, phone, phone_normalized, is_primary, created_at)
                    VALUES (:cid, :phone, :phone_norm, 1, NOW())
                    """
                ),
                {"cid": customer_id, "phone": str(phone_raw).strip(), "phone_norm": phone_norm},
            )

    return customer_id


def ensure_receiving_department(engine4: Engine, description: str) -> int:
    desc = (description or "").strip()
    if not desc:
        desc = "Kỹ thuật"
    found = select_one(
        engine4,
        "SELECT id FROM cskh_receiving_departments WHERE description = :d LIMIT 1",
        {"d": desc},
    )
    if found:
        return int(found["id"])
    dept_cols = set(get_table_columns(engine4, "cskh_receiving_departments"))
    payload: Dict[str, Any] = {"description": desc}
    if "is_active" in dept_cols:
        payload["is_active"] = 1
    if "created_at" in dept_cols:
        payload["created_at"] = datetime.now()
    if "updated_at" in dept_cols:
        payload["updated_at"] = datetime.now()

    columns = ", ".join(payload.keys())
    values = ", ".join([f":{k}" for k in payload.keys()])
    sql = f"INSERT INTO cskh_receiving_departments ({columns}) VALUES ({values})"

    with engine4.begin() as conn:
        res = conn.execute(text(sql), payload)
        return int(res.lastrowid)


def ensure_user_by_full_name(engine4: Engine, full_name: str) -> int:
    full_name = (full_name or "").strip()
    if not full_name:
        raise RuntimeError("Empty full_name for user")

    row = select_one(
        engine4,
        "SELECT id FROM users WHERE full_name = :n LIMIT 1",
        {"n": full_name},
    )
    if row:
        return int(row["id"])

    cols = set(get_table_columns(engine4, "users"))
    username_base = make_username_from_full_name(full_name)
    username = username_base

    # If username column exists, try to keep it unique.
    if "username" in cols:
        i = 1
        while True:
            exists = select_one(
                engine4,
                "SELECT id FROM users WHERE username = :u LIMIT 1",
                {"u": username},
            )
            if not exists:
                break
            i += 1
            username = f"{username_base}.{i}"[:64]

    pwd_plain = random_password()
    pwd_hash = bcrypt_laravel(pwd_plain)

    payload: Dict[str, Any] = {}
    if "full_name" in cols:
        payload["full_name"] = full_name
    if "name" in cols:
        payload["name"] = full_name
    if "username" in cols:
        payload["username"] = username
    if "email" in cols:
        # create a stable fake email if unique constraint exists
        local = re.sub(r"[^a-z0-9.]+", "", username.lower()) or "user"
        payload["email"] = f"{local}@import.local"
    if "password" in cols:
        payload["password"] = pwd_hash
    if "is_active" in cols:
        payload["is_active"] = 1
    if "created_at" in cols:
        payload["created_at"] = datetime.now()
    if "updated_at" in cols:
        payload["updated_at"] = datetime.now()

    # Minimal required fields fallback
    if not payload:
        raise RuntimeError("Users table columns not compatible with expected schema")

    columns = ", ".join(payload.keys())
    values = ", ".join([f":{k}" for k in payload.keys()])
    sql = f"INSERT INTO users ({columns}) VALUES ({values})"

    with engine4.begin() as conn:
        res = conn.execute(text(sql), payload)
        return int(res.lastrowid)


@dataclass
class ProductIndex:
    choices: List[str]
    meta: Dict[str, Dict[str, Any]]


def build_product_index(engine3: Engine) -> ProductIndex:
    sql = text(
        """
        SELECT id, product_name, name, model
        FROM products
        WHERE status IS NULL OR status != 0
        """
    )
    choices: List[str] = []
    meta: Dict[str, Dict[str, Any]] = {}
    with engine3.begin() as conn:
        rows = conn.execute(sql).mappings().all()
    for r in rows:
        pid = int(r["id"])
        fields = [r.get("product_name"), r.get("name"), r.get("model")]
        labels = [str(x).strip() for x in fields if x is not None and str(x).strip()]
        if not labels:
            continue
        # store a single canonical label for matching
        canonical = labels[0]
        key = f"{pid}:{canonical}"
        choices.append(key)
        meta[key] = {"id": pid, "canonical": canonical, "all_labels": labels}
    return ProductIndex(choices=choices, meta=meta)


def match_product(product_index: ProductIndex, raw_name: str) -> Tuple[Optional[int], Optional[str], int]:
    raw_name = (raw_name or "").strip()
    if not raw_name:
        return None, None, 0

    query = _normalize_text(raw_name)
    if not query:
        return None, None, 0

    # Custom scorer for rapidfuzz.process.extractOne.
    # Signature must be (query, choice, **kwargs), see rapidfuzz docs.
    def scorer(q: str, choice_key: str, **kwargs: Any) -> int:
        labels = product_index.meta[choice_key]["all_labels"]
        best = 0
        for lb in labels:
            lb_n = _normalize_text(lb)
            best = max(best, fuzz.token_set_ratio(q, lb_n))
        return best

    best = process.extractOne(query, product_index.choices, scorer=scorer)
    if not best:
        return None, None, 0
    choice_key, score, _idx = best
    if score < 70:
        return None, None, int(score)
    info = product_index.meta[choice_key]
    return int(info["id"]), str(info["canonical"]), int(score)


def parse_sheet_month_year(sheet_name: str) -> Tuple[int, int]:
    s = str(sheet_name or "").strip().replace(" ", "")
    m = re.match(r"^[Tt](\d{1,2})(\d{4})$", s)
    if not m:
        raise RuntimeError(
            f"Sheet name '{sheet_name}' không đúng định dạng. "
            "Ví dụ hợp lệ: T12025, T22025, T122025"
        )

    month = int(m.group(1))
    year = int(m.group(2))

    if month < 1 or month > 12:
        raise RuntimeError(f"Tháng trong sheet '{sheet_name}' không hợp lệ: {month}")

    return month, year


def parse_created_at(value: Any, sheet_month: int, sheet_year: int) -> Optional[datetime]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()

    if isinstance(value, datetime):
        return value

    # Nếu ô A chỉ là số ngày: 1, 2, 15, 31...
    if isinstance(value, (int, float)) and not pd.isna(value):
        day = int(value)
        if 1 <= day <= 31:
            return datetime(sheet_year, sheet_month, day, 0, 0, 0)

    s = str(value).strip()
    if not s:
        return None

    # Nếu là chuỗi chỉ chứa ngày, ví dụ "1", "15"
    if re.fullmatch(r"\d{1,2}", s):
        day = int(s)
        if 1 <= day <= 31:
            return datetime(sheet_year, sheet_month, day, 0, 0, 0)

    # Nếu là chuỗi kiểu "Ngày 15"
    m_day = re.search(r"(\d{1,2})", s)
    if m_day:
        day = int(m_day.group(1))
        if 1 <= day <= 31:
            return datetime(sheet_year, sheet_month, day, 0, 0, 0)

    # Nếu ô A đã là ngày đầy đủ dd/mm/yyyy thì vẫn parse bình thường
    try:
        ts = pd.to_datetime(s, dayfirst=True, errors="coerce")
        if pd.isna(ts):
            return None
        return ts.to_pydatetime()
    except Exception:
        return None

# Map workflow status from sheet status
def map_workflow_status(sheet_status: str) -> str:
    s = _normalize_text(sheet_status)

    if "ko nghe may" in s or "khong nghe may" in s:
        return "not_answered"

    return "completed" if (sheet_status or "").strip() else "received"


def insert_cskh_solution_from_handling(
    conn: Any,
    solution_cols: set,
    ticket_id: int,
    handling: str,
    created_at: Optional[datetime],
    workflow_status: str,
    completed_status_id: Optional[int],
) -> None:
    """Ghi cột G (tình trạng xử lý) vào cskh_solutions.resolution_text, không dùng cskh_tickets.handling."""
    txt = (handling or "").strip()
    if not txt:
        return
    if "ticket_id" not in solution_cols or "resolution_text" not in solution_cols:
        return

    payload: Dict[str, Any] = {
        "ticket_id": ticket_id,
        "resolution_text": txt,
    }
    if "created_at" in solution_cols:
        payload["created_at"] = created_at if created_at is not None else datetime.now()
    if "latest_reason" in solution_cols:
        payload["latest_reason"] = None
    if "status_id" in solution_cols and workflow_status == "completed" and completed_status_id is not None:
        payload["status_id"] = completed_status_id

    cols_i = list(payload.keys())
    col_sql = ", ".join(cols_i)
    val_sql = ", ".join([f":{c}" for c in cols_i])
    conn.execute(text(f"INSERT INTO cskh_solutions ({col_sql}) VALUES ({val_sql})"), payload)


def insert_ticket_activity_if_possible(
    engine4: Engine,
    ticket_id: int,
    user_id: int,
    action: str,
    type_: str,
    meta: Dict[str, Any],
    created_at: Optional[datetime],
) -> None:
    cols = set(get_table_columns(engine4, "cskh_ticket_activities"))
    payload: Dict[str, Any] = {}

    if "cskh_ticket_id" in cols:
        payload["cskh_ticket_id"] = ticket_id
    elif "ticket_id" in cols:
        payload["ticket_id"] = ticket_id
    else:
        return

    if "user_id" in cols:
        payload["user_id"] = user_id
    if "action" in cols:
        payload["action"] = action
    if "type" in cols:
        payload["type"] = type_
    if "meta" in cols:
        # Some MySQL drivers can't bind a Python dict directly.
        # Store as JSON string (compatible with JSON/TEXT columns).
        payload["meta"] = json.dumps(meta, ensure_ascii=False, default=str)
    if "created_at" in cols and created_at is not None:
        payload["created_at"] = created_at

    if not payload:
        return

    with engine4.begin() as conn:
        cols_i = list(payload.keys())
        col_sql = ", ".join(cols_i)
        val_sql = ", ".join([f":{c}" for c in cols_i])
        conn.execute(text(f"INSERT INTO cskh_ticket_activities ({col_sql}) VALUES ({val_sql})"), payload)


def import_excel(
    engine3: Engine,
    engine4: Engine,
    excel_path: str,
    sheet_name: Optional[str],
    start_row: int,
    dry_run: bool,
    fallback_created_by: Optional[int],
    tech_department_name: str,
) -> None:
    xls = pd.ExcelFile(excel_path)
    actual_sheet_name = sheet_name or xls.sheet_names[0]

    df = pd.read_excel(xls, sheet_name=actual_sheet_name, header=0)

    # Lấy tháng/năm từ tên sheet, ví dụ T12025 => tháng 1, năm 2025
    sheet_month, sheet_year = parse_sheet_month_year(actual_sheet_name)

    # Cột A bị merge trong Excel:
    # pandas chỉ đọc giá trị ở dòng đầu tiên, các dòng dưới sẽ là NaN
    # => dùng ffill để đổ ngày xuống các dòng trống bên dưới
    df.iloc[:, 0] = df.iloc[:, 0].ffill()

    # Normalize column names like Excel: A,B,C... but user uses positions
    # Expect at least columns A..I
    needed = 9
    if df.shape[1] < needed:
        raise RuntimeError(f"Excel needs at least {needed} columns (A..I). Found: {df.shape[1]}")

    product_index = build_product_index(engine3)

    imported = 0
    skipped = 0
    errors: List[str] = []

    # Validate workflow statuses exist in DB.
    ensure_cskh_status_code(engine4, "received", expected_id=1)
    ensure_cskh_status_code(engine4, "completed")
    ensure_cskh_status_code(engine4, "not_answered")

    ticket_cols = set(get_table_columns(engine4, "cskh_tickets"))
    transfer_cols = set(get_table_columns(engine4, "cskh_ticket_transfers"))
    solution_cols = set(get_table_columns(engine4, "cskh_solutions"))
    tech_dept_id = ensure_receiving_department(engine4, tech_department_name)

    completed_row = select_one(
        engine4,
        "SELECT id FROM cskh_status WHERE code = 'completed' LIMIT 1",
        {},
    )
    completed_status_id = int(completed_row["id"]) if completed_row else None

    for i in range(start_row, len(df)):
        row = df.iloc[i]

        created_at = parse_created_at(row.iloc[0], sheet_month, sheet_year)  # A
        sheet_status = str(row.iloc[1]).strip() if row.iloc[1] is not None else ""  # B
        customer_name = str(row.iloc[2]).strip() if row.iloc[2] is not None else ""  # C
        phone_raw = row.iloc[3]  # D
        # E: sản phẩm — NaN / trống coi như không có (product_text & product_id = NULL)
        _pr = row.iloc[4]
        if _pr is None or (isinstance(_pr, float) and pd.isna(_pr)):
            product_raw = ""
        else:
            product_raw = str(_pr).strip()
            if product_raw.lower() == "nan":
                product_raw = ""
        issue_content = str(row.iloc[5]).strip() if row.iloc[5] is not None else ""  # F
        handling = str(row.iloc[6]).strip() if row.iloc[6] is not None else ""  # G
        receiver_name = str(row.iloc[7]).strip() if row.iloc[7] is not None else ""  # H
        source = str(row.iloc[8]).strip() if row.iloc[8] is not None else ""  # I

        # Skip empty lines
        if not any([customer_name, normalize_vn_phone(phone_raw), product_raw, issue_content, handling, receiver_name, source, created_at]):
            skipped += 1
            continue

        try:
            customer_id = upsert_customer_and_phone(engine4, customer_name, phone_raw)

            # Status mapping:
            # - Nếu cột B chứa "Ko nghe máy" / "Không nghe máy" => not_answered
            # - Nếu cột B có text khác => completed
            # - Nếu cột B rỗng => received
            workflow_status = map_workflow_status(sheet_status)

            product_id, product_canonical, product_score = match_product(product_index, product_raw)

            notes_parts = []
            if sheet_status:
                notes_parts.append(f"Trạng thái sheet: {sheet_status}")

            notes = "\n".join(notes_parts) if notes_parts else None

            is_tech = _normalize_text(receiver_name) == _normalize_text("Kỹ thuật")

            created_by: Optional[int] = None
            if is_tech:
                created_by = fallback_created_by
            else:
                if receiver_name:
                    created_by = ensure_user_by_full_name(engine4, receiver_name)
                else:
                    created_by = fallback_created_by

            if created_by is None:
                raise RuntimeError("Cannot resolve created_by (receiver missing and no fallback)")

            ticket_payload: Dict[str, Any] = {}
            if "customer_id" in ticket_cols:
                ticket_payload["customer_id"] = customer_id
            if "workflow_status" in ticket_cols:
                ticket_payload["workflow_status"] = workflow_status
            if "product_text" in ticket_cols:
                # Sheet không có sản phẩm → NULL; có sản phẩm + match → tên chuẩn; có nhưng không match → NULL
                if not product_raw:
                    ticket_payload["product_text"] = None
                else:
                    ticket_payload["product_text"] = product_canonical if product_id else None
            if "product_id" in ticket_cols:
                ticket_payload["product_id"] = int(product_id) if product_id is not None else None
            if "issue_content" in ticket_cols:
                ticket_payload["issue_content"] = issue_content or None
            # Cột G → cskh_solutions.resolution_text (không lưu handling trên ticket)
            if "handling" in ticket_cols:
                ticket_payload["handling"] = None
            if "source" in ticket_cols:
                ticket_payload["source"] = (source[:32] if source else None)
            if "notes" in ticket_cols:
                ticket_payload["notes"] = notes
            if "created_by" in ticket_cols:
                ticket_payload["created_by"] = created_by
            if "receiving_department_id" in ticket_cols:
                ticket_payload["receiving_department_id"] = (tech_dept_id if is_tech else None)
            if "current_department_id" in ticket_cols:
                ticket_payload["current_department_id"] = (tech_dept_id if is_tech else None)
            if "created_at" in ticket_cols:
                ticket_payload["created_at"] = created_at
            if "updated_at" in ticket_cols:
                ticket_payload["updated_at"] = created_at or datetime.now()

            # Ensure minimal required columns exist
            if "created_by" in ticket_cols and "created_by" not in ticket_payload:
                raise RuntimeError("cskh_tickets requires created_by but script couldn't set it")
            if "workflow_status" in ticket_cols and "workflow_status" not in ticket_payload:
                raise RuntimeError("cskh_tickets requires workflow_status but script couldn't set it")

            if dry_run:
                imported += 1
                continue

            with engine4.begin() as conn:
                cols = list(ticket_payload.keys())
                col_sql = ", ".join(cols)
                val_sql = ", ".join([f":{c}" for c in cols])
                res = conn.execute(text(f"INSERT INTO cskh_tickets ({col_sql}) VALUES ({val_sql})"), ticket_payload)
                ticket_id = int(res.lastrowid)

                insert_cskh_solution_from_handling(
                    conn,
                    solution_cols,
                    ticket_id,
                    handling,
                    created_at,
                    workflow_status,
                    completed_status_id,
                )

                activity_meta: Dict[str, Any] = {
                    "import": "excel",
                    "sheet_status": sheet_status or None,
                    "product_raw": product_raw or None,
                    "product_id": product_id,
                    "product_name": product_canonical,
                    "product_score": product_score,
                    "source": source or None,
                }
                insert_ticket_activity_if_possible(
                    engine4=engine4,
                    ticket_id=ticket_id,
                    user_id=created_by,
                    action="import",
                    type_="excel",
                    meta=activity_meta,
                    created_at=created_at,
                )

                if is_tech:
                    transfer_payload: Dict[str, Any] = {}
                    if "ticket_id" in transfer_cols:
                        transfer_payload["ticket_id"] = ticket_id
                    if "to_department_id" in transfer_cols:
                        transfer_payload["to_department_id"] = tech_dept_id
                    if "error_encountered" in transfer_cols:
                        transfer_payload["error_encountered"] = "Chuyển tiếp từ import Excel"
                    if "descriptions" in transfer_cols:
                        transfer_payload["descriptions"] = (issue_content or "")[:2000]
                    if "note" in transfer_cols:
                        transfer_payload["note"] = "Auto transfer: receiver=Kỹ thuật"
                    if "transferred_by" in transfer_cols:
                        transfer_payload["transferred_by"] = created_by
                    if "created_at" in transfer_cols:
                        transfer_payload["created_at"] = created_at

                    cols_t = list(transfer_payload.keys())
                    col_sql_t = ", ".join(cols_t)
                    val_sql_t = ", ".join([f":{c}" for c in cols_t])
                    conn.execute(text(f"INSERT INTO cskh_ticket_transfers ({col_sql_t}) VALUES ({val_sql_t})"), transfer_payload)

            imported += 1

        except Exception as e:
            errors.append(f"Row {i+2}: {e}")  # +2 because header=0 and 1-indexed Excel rows

    print(f"Imported rows: {imported}")
    print(f"Skipped empty rows: {skipped}")
    if errors:
        print(f"Errors: {len(errors)}")
        for msg in errors[:50]:
            print(msg)
        if len(errors) > 50:
            print(f"... {len(errors)-50} more")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import CSKH tickets from Excel to mysql4.cskh_tickets (map products from mysql3.products).")
    parser.add_argument("--excel", required=True, help="Path to Excel file")
    parser.add_argument("--sheet", default=None, help="Excel sheet name (default: first sheet)")
    parser.add_argument("--start-row", type=int, default=0, help="0-based data row index (excluding header). Default 0.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and validate only; do not write to DB")
    parser.add_argument("--fallback-created-by", type=int, default=None, help="User id to use when receiver is empty or receiver is 'Kỹ thuật'")
    parser.add_argument("--tech-department-name", default="Kỹ thuật", help="cskh_receiving_departments.description to use/create for 'Kỹ thuật'")
    args = parser.parse_args()

    load_dotenv()

    engine3 = create_engine(build_mysql_url("DB3"), pool_pre_ping=True, future=True)
    engine4 = create_engine(build_mysql_url("DB4"), pool_pre_ping=True, future=True)

    import_excel(
        engine3=engine3,
        engine4=engine4,
        excel_path=args.excel,
        sheet_name=args.sheet,
        start_row=args.start_row,
        dry_run=args.dry_run,
        fallback_created_by=args.fallback_created_by,
        tech_department_name=args.tech_department_name,
    )


if __name__ == "__main__":
    main()

