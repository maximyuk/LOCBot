#!/usr/bin/env python3
import argparse
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


DEFAULT_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".kt",
    ".go",
    ".rs",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".cs",
    ".php",
    ".rb",
    ".swift",
    ".scala",
    ".sh",
    ".html",
    ".css",
    ".scss",
    ".sql",
}

DEFAULT_IGNORE_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".idea",
    ".vscode",
}


def iter_source_files(root: Path, extensions: set[str], ignore_dirs: set[str]):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignore_dirs for part in path.parts):
            continue
        if extensions and path.suffix.lower() not in extensions:
            continue
        yield path


def count_non_empty_lines(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0
    return sum(1 for line in text.splitlines() if line.strip())


def parse_csv_set(value: str) -> set[str]:
    items = {item.strip() for item in value.split(",") if item.strip()}
    return items


def normalize_extensions(exts: set[str]) -> set[str]:
    return {ext if ext.startswith(".") else f".{ext}" for ext in exts}


def count_project(root: Path, extensions: set[str], ignore_dirs: set[str]):
    per_file = []
    total = 0
    for file_path in iter_source_files(root, extensions, ignore_dirs):
        loc = count_non_empty_lines(file_path)
        if loc == 0:
            continue
        rel = file_path.relative_to(root)
        per_file.append((loc, rel))
        total += loc
    per_file.sort(reverse=True, key=lambda x: x[0])
    return per_file, total


def is_http_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def parse_github_repo_url(url: str):
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise ValueError("Supported only github.com repository links.")
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        raise ValueError("Invalid GitHub repository URL.")
    owner = parts[0]
    repo = parts[1].removesuffix(".git")
    branch = None
    subpath = None
    if len(parts) >= 4 and parts[2] == "tree":
        branch = parts[3]
        if len(parts) > 4:
            subpath = "/".join(parts[4:])
    return owner, repo, branch, subpath


def download_and_extract_repo(url: str, temp_dir: Path) -> Path:
    owner, repo, branch, subpath = parse_github_repo_url(url)
    if branch:
        branch_path = urllib.parse.quote(branch, safe="/")
        archive_url = f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{branch_path}"
    else:
        archive_url = f"https://api.github.com/repos/{owner}/{repo}/zipball"

    zip_path = temp_dir / "repo.zip"
    request = urllib.request.Request(
        archive_url,
        headers={"User-Agent": "loc-counter-script"},
    )
    with urllib.request.urlopen(request) as response, zip_path.open("wb") as out_file:
        out_file.write(response.read())

    extract_dir = temp_dir / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_dir)

    subdirs = [p for p in extract_dir.iterdir() if p.is_dir()]
    root = subdirs[0] if len(subdirs) == 1 else extract_dir

    if subpath:
        target = root.joinpath(*subpath.split("/"))
        if not target.exists():
            raise ValueError(f"Path not found in repository: {subpath}")
        return target

    return root


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Count non-empty lines of code in a local project or GitHub repository."
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Local path or GitHub repository URL.",
    )
    parser.add_argument(
        "--ext",
        default=",".join(sorted(DEFAULT_EXTENSIONS)),
        help="Comma-separated file extensions to include (example: py,js,ts).",
    )
    parser.add_argument(
        "--ignore-dirs",
        default=",".join(sorted(DEFAULT_IGNORE_DIRS)),
        help="Comma-separated directory names to ignore.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="How many top files by LOC to display (default: 20).",
    )
    args = parser.parse_args()
    target = args.target
    if target is None:
        if sys.stdin.isatty():
            try:
                user_input = input(
                    "Paste GitHub URL or local path (Enter = current folder): "
                ).strip()
            except EOFError:
                user_input = ""
            target = user_input or "."
        else:
            target = "."

    extensions = normalize_extensions(parse_csv_set(args.ext)) if args.ext else set()
    ignore_dirs = parse_csv_set(args.ignore_dirs)

    try:
        if is_http_url(target):
            with tempfile.TemporaryDirectory(prefix="loc_counter_") as tmp:
                temp_dir = Path(tmp)
                root = download_and_extract_repo(target, temp_dir)
                per_file, total = count_project(root, extensions, ignore_dirs)
                print(f"Source: {target}")
                print(f"Project (temp): {root}")
        else:
            root = Path(target).resolve()
            per_file, total = count_project(root, extensions, ignore_dirs)
            print(f"Project: {root}")
    except (ValueError, urllib.error.URLError, zipfile.BadZipFile) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Files counted: {len(per_file)}")
    print(f"Total non-empty LOC: {total}")
    print()
    print(f"Top {min(args.top, len(per_file))} files:")
    for loc, rel in per_file[: args.top]:
        print(f"{loc:>8}  {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
