#!/usr/bin/env python3
"""词典体检 / 清理 / 合并工具（不需要 Blender）。

用法：
    python tools/dict_audit.py                       # 只体检，打印报告
    python tools/dict_audit.py --report report.md    # 体检并写 Markdown 报告
    python tools/dict_audit.py --fix                 # 清理有问题的行（自动备份原文件）
    python tools/dict_audit.py --merged merged.csv   # 另外输出一份去重合并版

“有问题的行”指：中文列不是中文、英文列含中文（列错位）、译文等于原文、
译文长度异常（拼接了多行）等。
"""

import argparse
import csv
import io
import os
import re
import shutil
import sys
import time

CJK = re.compile("[\u4e00-\u9fff]")
LATIN = re.compile("[A-Za-z]")
MAX_BAD_RATIO = 0.25


def sanity(translated, source):
    if not translated or not source:
        return False
    if translated.strip() == source.strip():
        return False
    if CJK.search(source) or not LATIN.search(source):
        return False
    if not CJK.search(translated):
        return False
    if len(translated) > max(40, len(source) * 3 + 30):
        return False
    return True


def read_rows(path):
    for encoding in ("utf-8", "gbk"):
        try:
            with io.open(path, encoding=encoding) as handle:
                return list(csv.reader(handle))
        except Exception:
            continue
    return []


def analyze(dict_dir):
    files = []
    seen_pairs = set()
    totals = {"files": 0, "rows": 0, "valid": 0, "invalid": 0, "duplicates": 0}

    for name in sorted(os.listdir(dict_dir)):
        if not name.lower().endswith(".csv"):
            continue
        path = os.path.join(dict_dir, name)
        rows = read_rows(path)
        good, bad, dup = [], [], 0
        for row in rows:
            if len(row) < 2:
                continue
            totals["rows"] += 1
            translated = row[0].replace("\\n", "\n").strip()
            source = row[1].replace("\\n", "\n").strip()
            if not translated or not source:
                continue
            pair = (source, translated)
            if pair in seen_pairs:
                dup += 1
            seen_pairs.add(pair)
            (good if sanity(translated, source) else bad).append((translated, source))

        totals["files"] += 1
        totals["valid"] += len(good)
        totals["invalid"] += len(bad)
        totals["duplicates"] += dup
        ratio = len(bad) / float(max(1, len(good) + len(bad)))
        files.append({
            "name": name,
            "path": path,
            "good": good,
            "bad": bad,
            "dup": dup,
            "ratio": ratio,
            "suspect": len(bad) > 5 and ratio > MAX_BAD_RATIO,
        })
    return totals, files


def print_report(totals, files):
    print("词典目录: %d 个文件" % totals["files"])
    print("总行数  : %d" % totals["rows"])
    print("有效    : %d" % totals["valid"])
    print("异常    : %d (%.1f%%)" % (
        totals["invalid"],
        100.0 * totals["invalid"] / max(1, totals["rows"])))
    print("重复    : %d" % totals["duplicates"])
    suspects = [f for f in files if f["suspect"]]
    if suspects:
        print("\n可疑文件（异常占比 > %.0f%%）：" % (MAX_BAD_RATIO * 100))
        for item in sorted(suspects, key=lambda f: -f["ratio"])[:10]:
            print("  %-40s %d/%d 异常" % (
                item["name"], len(item["bad"]), len(item["bad"]) + len(item["good"])))


def write_markdown(path, totals, files):
    lines = [
        "# 词典体检报告",
        "",
        "| 指标 | 数值 |",
        "| --- | --- |",
        "| 文件数 | %d |" % totals["files"],
        "| 总行数 | %d |" % totals["rows"],
        "| 有效 | %d |" % totals["valid"],
        "| 异常 | %d |" % totals["invalid"],
        "| 重复 | %d |" % totals["duplicates"],
        "",
        "## 异常最多的文件",
        "",
        "| 文件 | 异常 | 总数 |",
        "| --- | --- | --- |",
    ]
    for item in sorted(files, key=lambda f: -len(f["bad"]))[:15]:
        if not item["bad"]:
            continue
        lines.append("| %s | %d | %d |" % (
            item["name"], len(item["bad"]), len(item["bad"]) + len(item["good"])))
    io.open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("报告已写入:", path)


def fix_files(dict_dir, files):
    backup = os.path.join(dict_dir, ".audit-backup-%s" % time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(backup, exist_ok=True)
    fixed = 0
    for item in files:
        if not item["bad"]:
            continue
        shutil.copy2(item["path"], os.path.join(backup, item["name"]))
        rows = []
        for translated, source in item["good"]:
            rows.append('"%s","%s"' % (
                translated.replace('"', '""').replace("\n", "\\n"),
                source.replace('"', '""').replace("\n", "\\n")))
        with io.open(item["path"], "w", encoding="utf-8") as handle:
            handle.write("\n".join(rows))
        fixed += 1
    print("已清理 %d 个文件，原文件备份在: %s" % (fixed, backup))


def write_merged(path, files):
    merged = {}
    for item in files:
        for translated, source in item["good"]:
            merged.setdefault(source, translated)
    with io.open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(
            '"%s","%s"' % (
                tr.replace('"', '""').replace("\n", "\\n"),
                src.replace('"', '""').replace("\n", "\\n"))
            for src, tr in sorted(merged.items())))
    print("合并版已写入: %s（%d 条唯一词条）" % (path, len(merged)))


def main():
    parser = argparse.ArgumentParser(description="Blender 词典体检/清理/合并")
    parser.add_argument("--dir", default=None, help="词典目录，默认 <仓库>/user_translate/user_files")
    parser.add_argument("--report", default=None, help="输出 Markdown 报告路径")
    parser.add_argument("--fix", action="store_true", help="清理异常行（自动备份）")
    parser.add_argument("--merged", default=None, help="输出一份去重合并版 CSV")
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dict_dir = args.dir or os.path.join(root, "user_translate", "user_files")
    if not os.path.isdir(dict_dir):
        sys.exit("找不到词典目录: %s" % dict_dir)

    totals, files = analyze(dict_dir)
    print_report(totals, files)
    if args.report:
        write_markdown(args.report, totals, files)
    if args.fix:
        fix_files(dict_dir, files)
    if args.merged:
        write_merged(args.merged, files)


if __name__ == "__main__":
    main()
