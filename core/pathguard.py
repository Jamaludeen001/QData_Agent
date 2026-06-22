from pathlib import Path


def safe_path(folder: Path, schema: str, filename: str) -> tuple[Path | None, str]:
    resolved = (folder / schema / filename).resolve()
    if not str(resolved).startswith(str(folder.resolve())):
        return None, "Access denied: path traversal detected."
    if not resolved.exists():
        return None, f"File '{schema}/{filename}' not found.\n{list_available(folder)}"
    return resolved, "ok"


def list_available(folder: Path) -> str:
    lines = ["Available schemas and tables:"]
    for schema_dir in sorted(folder.iterdir()):
        if schema_dir.is_dir():
            lines.append(f"  schema: {schema_dir.name}")
            for csv_file in sorted(schema_dir.glob("*.csv")):
                lines.append(f"    - {csv_file.stem}  → {schema_dir.name}.{csv_file.stem}")
    if len(lines) == 1:
        return "No schemas or tables found in source folder."
    return "\n".join(lines)
