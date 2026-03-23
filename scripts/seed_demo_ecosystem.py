import argparse
import json
import sys
from pathlib import Path


def _ensure_project_root_on_path() -> None:
    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo ecosystem for sample users.")
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Do not clear existing sample data before insert.",
    )
    args = parser.parse_args()

    _ensure_project_root_on_path()
    from backend.app.services.demo_seed_service import run_seed

    stats = run_seed(clear_sample_data=not args.no_clear)
    print("Demo seed completed.")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
