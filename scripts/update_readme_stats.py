from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
IGNORED_TOP_LEVEL = {"_rules", ".github", "scripts", ".git"}
TEXT_EXTENSIONS = {".md", ".txt"}

CATEGORY_MARKERS = {
    "课堂笔记": "_课堂笔记_",
    "录音转文字稿": "_课堂录音转文字稿_",
    "课后整理": "_课后整理_",
    "错题": "_错题_",
    "必背": "_必背_",
}


def count_words(text: str) -> int:
    """按中文单字、英文单词、数字序列统计学习资料字数。"""
    tokens = re.findall(
        r"[\u3400-\u4dbf\u4e00-\u9fff]|[A-Za-z]+(?:['’-][A-Za-z]+)*|\d+(?:\.\d+)?",
        text,
    )
    return len(tokens)


def learning_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        rel = path.relative_to(ROOT)
        if not rel.parts:
            continue
        top = rel.parts[0]
        if top in IGNORED_TOP_LEVEL or top.startswith(".") or top.startswith("_"):
            continue
        if rel == Path("README.md"):
            continue
        files.append(path)
    return sorted(files)


def lesson_key(path: Path) -> tuple[str, ...] | None:
    parts = path.relative_to(ROOT).parts
    try:
        index = parts.index("课堂")
    except ValueError:
        return None
    if index + 1 >= len(parts) - 0:
        return None
    # 课堂目录后的第一个目录即一个课次目录；文件若直接放在“课堂”下则不计为课次。
    if index + 1 >= len(parts) - 1:
        return None
    return tuple(parts[: index + 2])


def category_counts(files: list[Path]) -> dict[str, int]:
    counts = {name: 0 for name in CATEGORY_MARKERS}
    for path in files:
        name = path.name
        for category, marker in CATEGORY_MARKERS.items():
            if marker in name:
                counts[category] += 1
    return counts


def build_stats() -> str:
    files = learning_files()
    word_cache: dict[Path, int] = {}
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
        word_cache[path] = count_words(text)

    subjects: dict[str, list[Path]] = defaultdict(list)
    for path in files:
        subjects[path.relative_to(ROOT).parts[0]].append(path)

    lessons = {key for path in files if (key := lesson_key(path)) is not None}
    categories = category_counts(files)
    total_words = sum(word_cache.values())

    lines = [
        "<!-- STATS:START -->",
        "### 总览",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| 学科数 | {len(subjects):,} |",
        f"| 课次数 | {len(lessons):,} |",
        f"| 学习资料文件数 | {len(files):,} |",
        f"| 学习资料总字数 | {total_words:,} |",
        f"| 课堂笔记文件数 | {categories['课堂笔记']:,} |",
        f"| 录音转文字稿文件数 | {categories['录音转文字稿']:,} |",
        f"| 课后整理文件数 | {categories['课后整理']:,} |",
        f"| 错题文件数 | {categories['错题']:,} |",
        f"| 必背文件数 | {categories['必背']:,} |",
        "",
        "### 各科统计",
        "",
    ]

    if subjects:
        lines.extend(
            [
                "| 科目 | 课次 | 文件数 | 字数 | 课堂笔记 | 录音转写 | 课后整理 | 错题 | 必背 |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for subject in sorted(subjects):
            subject_files = subjects[subject]
            subject_lessons = {
                key for path in subject_files if (key := lesson_key(path)) is not None
            }
            subject_categories = category_counts(subject_files)
            subject_words = sum(word_cache[path] for path in subject_files)
            lines.append(
                f"| {subject} | {len(subject_lessons):,} | {len(subject_files):,} | {subject_words:,} | "
                f"{subject_categories['课堂笔记']:,} | {subject_categories['录音转文字稿']:,} | "
                f"{subject_categories['课后整理']:,} | {subject_categories['错题']:,} | {subject_categories['必背']:,} |"
            )
    else:
        lines.append("暂无课程资料。")

    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")
    lines.extend(
        [
            "",
            "**统计口径：** 仅统计各学科目录内的 `.md`、`.txt` 学习资料；排除 `README.md`、`_rules/`、`.github/`、`scripts/` 等管理与自动化文件。“字数”按中文字符、英文单词和数字序列统计。",
            f"**最后自动统计：** {now}（北京时间）",
            "<!-- STATS:END -->",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    readme = README.read_text(encoding="utf-8")
    stats = build_stats()
    pattern = r"<!-- STATS:START -->.*?<!-- STATS:END -->"
    if not re.search(pattern, readme, flags=re.S):
        raise RuntimeError("README 中缺少统计区域标记")
    updated = re.sub(pattern, stats, readme, count=1, flags=re.S)
    README.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
