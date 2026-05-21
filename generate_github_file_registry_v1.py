# generate_github_file_registry_v2.py

import json
import subprocess
from pathlib import Path
from datetime import datetime
from urllib.parse import quote


REPO_ROOT = Path(r"C:\Users\Clarke Towson\melbourne-scats-intelligence")
GITHUB_BASE = "https://github.com/clarketowson/melbourne-scats-intelligence/blob/main"
OUT_FILE = REPO_ROOT / "github_file_registry.json"

INCLUDE_EXTS = {
    ".py", ".ps1", ".sql", ".json", ".csv", ".html", ".css", ".js",
    ".md", ".txt", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".yml", ".yaml"
}

SKIP_EXTS = {
    ".duckdb", ".db", ".sqlite", ".sqlite3", ".parquet", ".zip", ".7z", ".rar",
    ".mp4", ".mov", ".avi", ".mkv", ".mp3", ".wav"
}

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "$WINDOWS.~BT",
    "$WINDOWS.~WS",
    "System Volume Information",
    "Recovery",
    "Recycle.Bin",
    "$RECYCLE.BIN",
}

def git_tracked_files(repo_root: Path):
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=True
        )

        files = [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip()
        ]

        return files

    except Exception as e:
        print("WARNING: git ls-files failed.")
        print(e)
        print("Falling back to strict filesystem scan.")

        files = []
        for p in repo_root.rglob("*"):
            if not p.is_file():
                continue

            rel = p.relative_to(repo_root).as_posix()

            if should_skip_path(rel):
                continue

            files.append(rel)

        return files


def should_skip_path(rel_path: str):
    rel_lower = rel_path.lower()

    # hard exclusions
    BAD_PATTERNS = [
        "$windows",
        "sources/",
        "boot/",
        "efi/",
        "system volume information",
        "$recycle.bin",
        "recovery/",
    ]

    for pattern in BAD_PATTERNS:
        if pattern in rel_lower:
            return True

    parts = Path(rel_path).parts
    parts_lower = {p.lower() for p in parts}

    for skip in SKIP_DIRS:
        if skip.lower() in parts_lower:
            return True

    name = Path(rel_path).name.lower()

    if name.startswith("~") or name.startswith(".~"):
        return True

    ext = Path(rel_path).suffix.lower()

    if ext in SKIP_EXTS:
        return True

    if ext not in INCLUDE_EXTS:
        return True

    return False


def category_for(rel_path: str):
    path = Path(rel_path)
    s = rel_path.lower()
    ext = path.suffix.lower()

    if ext == ".py":
        return "Python script"
    if ext == ".ps1":
        return "PowerShell wrapper"
    if ext == ".sql":
        return "SQL"
    if ext == ".json":
        return "JSON metadata"
    if ext == ".csv":
        return "CSV output"
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".svg"}:
        return "Chart / image asset"
    if ext in {".html", ".css", ".js"}:
        return "Web asset"
    if ext in {".md", ".txt"}:
        return "Documentation"
    if ext in {".yml", ".yaml"}:
        return "Workflow / config"
    return "Other"


def describe(rel_path: str):
    name = Path(rel_path).name.lower()
    s = rel_path.lower()

    if "yearly" in s:
        return "Yearly totals / annual movement analysis"
    if "monthly" in s:
        return "Monthly totals or monthly coverage analysis"
    if "daily" in s:
        return "Daily traffic movement analysis"
    if "time_bin" in s or "time-bin" in s:
        return "15-minute time-bin behavioural analysis"
    if "weekday" in s or "weekend" in s:
        return "Weekday/weekend behavioural analysis"
    if "day_of_week" in s or "day-of-week" in s:
        return "Day-of-week behavioural analysis"
    if "month_of_year" in s or "month-of-year" in s:
        return "Month-of-year seasonality analysis"
    if "site_month" in s or "site-month" in s:
        return "Site-month intelligence"
    if "site" in s:
        return "SCATS site intelligence / rankings"
    if "database_diagnostics" in s or "diagnostics" in s:
        return "Database diagnostics and structural audit output"
    if "data_quality" in s or "dedup" in s:
        return "Data quality, cleaning or deduplication evidence"
    if "performance" in s or "duckdb_performance" in s:
        return "DuckDB performance benchmark output"
    if "kepler" in s:
        return "Kepler.gl map / animation export"
    if "animation" in s:
        return "Traffic animation asset or workflow"
    if "readme" in name:
        return "Repository documentation"

    return "Melbourne SCATS Intelligence repository file"


def github_url_for(rel_path: str):
    # Encode each path component, preserving forward slashes
    encoded = "/".join(quote(part) for part in rel_path.split("/"))
    return f"{GITHUB_BASE}/{encoded}"


def main():
    rows = []
    tracked = git_tracked_files(REPO_ROOT)

    for rel_path in tracked:
        rel_path = rel_path.replace("\\", "/")

        if should_skip_path(rel_path):
            continue

        full_path = REPO_ROOT / rel_path

        if not full_path.exists() or not full_path.is_file():
            continue

        stat = full_path.stat()

        rows.append({
            "filename": full_path.name,
            "path": rel_path,
            "extension": full_path.suffix.lower(),
            "category": category_for(rel_path),
            "description": describe(rel_path),
            "size_bytes": stat.st_size,
            "size_kb": round(stat.st_size / 1024, 2),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "github_url": github_url_for(rel_path),
            "keywords": " ".join([
                full_path.name,
                rel_path,
                category_for(rel_path),
                describe(rel_path)
            ]).lower()
        })

    rows.sort(key=lambda x: (x["category"], x["path"]))

    output = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "repo": "clarketowson/melbourne-scats-intelligence",
        "registry_method": "git ls-files tracked files only",
        "file_count": len(rows),
        "files": rows
    }

    OUT_FILE.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Wrote {OUT_FILE}")
    print(f"Indexed {len(rows):,} Git-tracked files")


if __name__ == "__main__":
    main()