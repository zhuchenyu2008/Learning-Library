from __future__ import annotations

import math
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
    # “课堂”后的第一个目录代表一个课次；直接放在“课堂”下的文件不计课次。
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


def mermaid_label(value: str) -> str:
    return value.replace("\\", "／").replace('"', "'").replace("\n", " ")


def mermaid_bar_chart(title: str, y_label: str, labels: list[str], values: list[int]) -> list[str]:
    """生成 GitHub README 可渲染的 Mermaid xychart，不创建图片文件。"""
    if not labels or not values or max(values, default=0) <= 0:
        return ["暂无数据。"]

    max_value = max(values)
    if max_value <= 10:
        y_max = max_value + 1
    else:
        magnitude = 10 ** max(0, len(str(max_value)) - 2)
        y_max = int(math.ceil((max_value * 1.1) / magnitude) * magnitude)
        if y_max <= max_value:
            y_max = max_value + magnitude

    safe_labels = ", ".join(f'"{mermaid_label(label)}"' for label in labels)
    data = ", ".join(str(value) for value in values)
    return [
        "```mermaid",
        "xychart-beta",
        f'    title "{mermaid_label(title)}"',
        f"    x-axis [{safe_labels}]",
        f'    y-axis "{mermaid_label(y_label)}" 0 --> {y_max}',
        f"    bar [{data}]",
        "```",
    ]


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

    subject_rows: list[tuple[str, int, int, int, dict[str, int]]] = []
    for subject in sorted(subjects):
        subject_files = subjects[subject]
        subject_lessons = {
            key for path in subject_files if (key := lesson_key(path)) is not None
        }
        subject_categories = category_counts(subject_files)
        subject_words = sum(word_cache[path] for path in subject_files)
        subject_rows.append(
            (subject, len(subject_lessons), len(subject_files), subject_words, subject_categories)
        )

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

    if subject_rows:
        lines.extend(
            [
                "| 科目 | 课次 | 文件数 | 字数 | 课堂笔记 | 录音转写 | 课后整理 | 错题 | 必背 |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for subject, lesson_count, file_count, subject_words, subject_categories in subject_rows:
            lines.append(
                f"| {subject} | {lesson_count:,} | {file_count:,} | {subject_words:,} | "
                f"{subject_categories['课堂笔记']:,} | {subject_categories['录音转文字稿']:,} | "
                f"{subject_categories['课后整理']:,} | {subject_categories['错题']:,} | "
                f"{subject_categories['必背']:,} |"
            )
    else:
        lines.append("暂无课程资料。")

    lines.extend(["", "### 自动图表", ""])

    if subject_rows:
        subject_names = [row[0] for row in subject_rows]
        subject_lesson_counts = [row[1] for row in subject_rows]
        subject_word_counts = [row[3] for row in subject_rows]

        lines.extend(["#### 各科字数", ""])
        lines.extend(mermaid_bar_chart("各科学习资料字数", "字数", subject_names, subject_word_counts))
        lines.extend(["", "#### 各科课次数", ""])
        lines.extend(mermaid_bar_chart("各科课次数", "课次", subject_names, subject_lesson_counts))
        lines.extend(["", "#### 资料类型文件数", ""])
        category_names = list(CATEGORY_MARKERS.keys())
        category_values = [categories[name] for name in category_names]
        lines.extend(mermaid_bar_chart("各类学习资料文件数", "文件数", category_names, category_values))
    else:
        lines.append("暂无课程资料，添加课程后将自动生成图表。")

    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")
    lines.extend(
        [
            "",
            "**统计口径：** 仅统计各学科目录内的 `.md`、`.txt` 学习资料；排除 `README.md`、`_rules/`、`.github/`、`scripts/` 等管理与自动化文件。“字数”按中文字符、英文单词和数字序列统计。不统计任何文件内部的错题数、必背条目数、知识点数等条目数量。",
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
