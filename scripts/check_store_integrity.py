import os
import sqlite3


def main() -> int:
    db_path = os.getenv("DB_PATH", "./db.sqlite3")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    checks = {
        "A_orders_missing_user": """
            SELECT o.*
            FROM store_orders o
            LEFT JOIN users u ON u.id=o.user_id
            WHERE u.id IS NULL
        """,
        "B_orders_missing_product": """
            SELECT o.*
            FROM store_orders o
            LEFT JOIN store_products p ON p.id=o.product_id
            WHERE p.id IS NULL
        """,
        "C_ledger_duplicates_by_order": """
            SELECT user_id, entity_id, COUNT(*) AS cnt
            FROM points_ledger
            WHERE entity_type='store_order'
            GROUP BY user_id, entity_id
            HAVING COUNT(*) > 1
        """,
        "D_paid_without_ledger": """
            SELECT o.*
            FROM store_orders o
            LEFT JOIN points_ledger l
              ON l.entity_type='store_order' AND l.entity_id=o.id AND l.user_id=o.user_id
            WHERE o.status IN ('paid','fulfilled') AND l.id IS NULL
        """,
    }

    has_errors = False
    for label, sql in checks.items():
        rows = cur.execute(sql).fetchall()
        count = len(rows)
        print(f"{label}: {count}")
        if count > 0:
            has_errors = True

    conn.close()
    return 1 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

