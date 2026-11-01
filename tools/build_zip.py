#!/usr/bin/env python3
"""把 user_translate/ 打包成可安装的 Blender 插件 zip。

用法：
    python tools/build_zip.py
产物：
    dist/user_translate_auto-<version>.zip

版本号取自 user_translate/__init__.py 的 bl_info["version"]，
发版前先改那里，再跑本脚本。
"""

import os
import re
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG_NAME = "user_translate"
PKG_DIR = os.path.join(ROOT, PKG_NAME)
DIST_DIR = os.path.join(ROOT, "dist")

EXCLUDE_DIRS = {"__pycache__", ".git"}
EXCLUDE_SUFFIX = (".pyc", ".pyo", ".bak")


def read_version():
    init = os.path.join(PKG_DIR, "__init__.py")
    with open(init, encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(r'"version"\s*:\s*\(([^)]+)\)', text)
    if not match:
        raise SystemExit("cannot find bl_info version")
    return ".".join(part.strip() for part in match.group(1).split(","))


def main():
    version = read_version()
    os.makedirs(DIST_DIR, exist_ok=True)
    target = os.path.join(DIST_DIR, "%s_auto-%s.zip" % (PKG_NAME, version))

    count = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for root, dirs, files in os.walk(PKG_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for name in files:
                if name.endswith(EXCLUDE_SUFFIX):
                    continue
                full = os.path.join(root, name)
                arc = os.path.join(PKG_NAME, os.path.relpath(full, PKG_DIR)).replace(os.sep, "/")
                archive.write(full, arc)
                count += 1

    size_mb = os.path.getsize(target) / 1024 / 1024
    print("built %s (%d files, %.2f MB)" % (target, count, size_mb))


if __name__ == "__main__":
    main()
