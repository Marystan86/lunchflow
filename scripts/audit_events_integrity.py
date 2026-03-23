import sqlite3
import sys
import os
from pathlib import Path


def _ensure_project_root_on_path() -> None:
    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


def main() -> int:
    _ensure_project_root_on_path()
    db_path = os.getenv("DB_PATH", "./db.sqlite3")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    checks = {
        "A_missing_creator": """
            SELECT e.*
            FROM events e
            LEFT JOIN users u ON u.id = e.created_by_user_id
            WHERE e.created_by_user_id IS NOT NULL AND u.id IS NULL
        """,
        "B_role_flag_mismatch": """
            SELECT *
            FROM events
            WHERE (created_by_role = 'club' AND is_club_event != 1)
               OR (created_by_role = 'member' AND is_club_event != 0)
        """,
        "C_club_without_admin_creator": """
            SELECT e.*
            FROM events e
            JOIN users u ON u.id = e.created_by_user_id
            WHERE e.created_by_role = 'club'
              AND (u.is_admin IS NULL OR u.is_admin = 0)
        """,
    }

    failed = False
    for label, sql in checks.items():
        rows = cur.execute(sql).fetchall()
        count = len(rows)
        print(f"{label}: {count}")
        if count > 0:
            failed = True

    conn.close()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
