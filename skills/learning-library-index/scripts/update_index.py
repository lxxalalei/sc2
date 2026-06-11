#!/usr/bin/env python3
"""Update external index for organized learning resources."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INDEX_SCHEMA = "learning-library-index/v1"
DUPLICATE_SCHEMA = "learning-library-duplicates/v1"
UPDATE_SCHEMA = "learning-library-index-update/v1"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_path(path: Path) -> Path:
    return path.expanduser().resolve()


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_index_location(index_dir: Path, library_dir: Path | None) -> None:
    if not library_dir:
        return
    resolved_index = resolve_path(index_dir)
    resolved_library = resolve_path(library_dir)
    if resolved_index == resolved_library or is_relative_to(resolved_index, resolved_library):
        raise ValueError("索引目录不能位于最终资料库内部")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_resources(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"index_schema": INDEX_SCHEMA, "updated_at": "", "resources": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    resources = data.get("resources")
    if not isinstance(resources, list):
        raise ValueError("resources.json 格式错误：resources 必须是列表")
    data["index_schema"] = data.get("index_schema") or INDEX_SCHEMA
    return data


def load_duplicates(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"duplicate_schema": DUPLICATE_SCHEMA, "updated_at": "", "duplicates": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    duplicates = data.get("duplicates")
    if not isinstance(duplicates, list):
        raise ValueError("duplicates.json 格式错误：duplicates 必须是列表")
    data["duplicate_schema"] = data.get("duplicate_schema") or DUPLICATE_SCHEMA
    return data


def first_value(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value is not None and not isinstance(value, (dict, list, tuple, set)):
            text = str(value).strip()
            if text:
                return text
    return ""


def resource_key(item: dict[str, Any], library_file: Path) -> tuple[str, str]:
    digest = first_value(item.get("sha256"))
    if digest:
        return digest, "high"
    if library_file.exists() and library_file.is_file():
        return sha256_file(library_file), "high"
    return f"path:{library_file}", "low"


def make_record(item: dict[str, Any], key: str, dedupe_confidence: str, timestamp: str, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    classification = item.get("classification") if isinstance(item.get("classification"), dict) else {}
    return {
        "resource_key": key,
        "title": item.get("title") or existing.get("title") or "",
        "library_file": item.get("library_file") or existing.get("library_file") or "",
        "original_file": item.get("original_file") or existing.get("original_file") or "",
        "format": item.get("format") or existing.get("format") or "",
        "resource_type": item.get("resource_type") or existing.get("resource_type") or "",
        "classification": classification or existing.get("classification") or {},
        "classification_confidence": item.get("classification_confidence", existing.get("classification_confidence", 0.0)),
        "needs_review": bool(item.get("needs_review", existing.get("needs_review", False))),
        "source_url": item.get("source_url") or existing.get("source_url") or "",
        "sha256": first_value(item.get("sha256"), existing.get("sha256")),
        "dedupe_confidence": dedupe_confidence,
        "created_at": existing.get("created_at") or timestamp,
        "updated_at": timestamp,
    }


def update_index(data: dict[str, Any], index_dir: Path, library_dir: Path | None, dry_run: bool) -> tuple[dict[str, Any], int]:
    validate_index_location(index_dir, library_dir)
    resources_file = index_dir / "resources.json"
    duplicates_file = index_dir / "duplicates.json"
    resources_doc = load_resources(resources_file)
    duplicates_doc = load_duplicates(duplicates_file)
    resources = resources_doc["resources"]
    duplicates = duplicates_doc["duplicates"]
    by_key = {str(item.get("resource_key")): item for item in resources if item.get("resource_key")}
    timestamp = now_iso()

    organized_files = data.get("organized_files") or []
    if not isinstance(organized_files, list):
        raise ValueError("organized_files 必须是列表")

    created = 0
    updated = 0
    duplicate_records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for item in organized_files:
        if not isinstance(item, dict):
            failures.append({"title": "", "library_file": "", "error": "归档项不是对象"})
            continue
        library_file = Path(str(item.get("library_file") or ""))
        if not item.get("library_file"):
            failures.append({"title": item.get("title") or "", "library_file": "", "error": "缺少 library_file"})
            continue
        if not library_file.exists() or not library_file.is_file():
            failures.append({"title": item.get("title") or "", "library_file": str(library_file), "error": "资料库文件不存在"})
            continue

        key, dedupe_confidence = resource_key(item, library_file)
        existing = by_key.get(key)
        if existing:
            existing_path = str(existing.get("library_file") or "")
            incoming_path = str(item.get("library_file") or "")
            if existing_path and incoming_path and resolve_path(Path(existing_path)) != resolve_path(Path(incoming_path)):
                duplicate = {
                    "resource_key": key,
                    "existing_file": existing_path,
                    "incoming_file": incoming_path,
                    "title": item.get("title") or existing.get("title") or "",
                    "detected_at": timestamp,
                    "reason": "sha256 相同但资料库路径不同",
                }
                duplicates.append(duplicate)
                duplicate_records.append(duplicate)
                continue
            new_record = make_record(item, key, dedupe_confidence, timestamp, existing)
            existing.clear()
            existing.update(new_record)
            updated += 1
        else:
            record = make_record(item, key, dedupe_confidence, timestamp)
            resources.append(record)
            by_key[key] = record
            created += 1

    resources_doc["updated_at"] = timestamp
    duplicates_doc["updated_at"] = timestamp
    if not dry_run:
        write_json(resources_file, resources_doc)
        write_json(duplicates_file, duplicates_doc)

    if created or updated or duplicate_records:
        status = "completed" if not failures else "partial"
    else:
        status = "failed" if failures else "completed"

    result = {
        "index_schema": UPDATE_SCHEMA,
        "status": status,
        "index_dir": str(index_dir),
        "resources_file": str(resources_file),
        "duplicates_file": str(duplicates_file),
        "dry_run": dry_run,
        "created": created,
        "updated": updated,
        "duplicates": duplicate_records,
        "failures": failures,
        "summary": {
            "input_files": len(organized_files),
            "total_indexed": len(resources),
            "created": created,
            "updated": updated,
            "duplicates": len(duplicate_records),
            "failed": len(failures),
        },
    }
    return result, 0 if status in {"completed", "partial"} else 1


def run(args: argparse.Namespace) -> int:
    try:
        data = load_json(args.input)
        library_dir = Path(args.library_dir) if args.library_dir else None
        result, exit_code = update_index(data, Path(args.index_dir), library_dir, args.dry_run)
    except Exception as exc:
        result = {
            "index_schema": UPDATE_SCHEMA,
            "status": "failed",
            "index_dir": args.index_dir,
            "resources_file": str(Path(args.index_dir) / "resources.json"),
            "duplicates_file": str(Path(args.index_dir) / "duplicates.json"),
            "dry_run": args.dry_run,
            "created": 0,
            "updated": 0,
            "duplicates": [],
            "failures": [{"title": "", "library_file": "", "error": str(exc)}],
            "summary": {"input_files": 0, "total_indexed": 0, "created": 0, "updated": 0, "duplicates": 0, "failed": 1},
        }
        exit_code = 1

    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        if args.library_dir:
            validate_index_location(output_path.parent, Path(args.library_dir))
        write_json(output_path, result)
    else:
        print(output)
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Update external index for organized learning resources")
    parser.add_argument("input", help="Organize result JSON file, or '-' for stdin")
    parser.add_argument("--index-dir", default=".learning-resource-work/index", help="External index directory")
    parser.add_argument("--library-dir", help="Final library directory, used to prevent index pollution")
    parser.add_argument("--dry-run", action="store_true", help="Preview index updates without writing index files")
    parser.add_argument("-o", "--output", help="Write update summary JSON outside the final library")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
