# -*- coding: utf-8 -*-
"""
Auto translate helper for User Translate.

It does NOT touch any add-on code: it only extracts the UI strings an add-on
declares (bl_label / bl_description / bl_category / description / name / text),
looks them up in the dictionary that already ships in ``user_files/*.csv`` and
writes a normal ``<module>.csv`` file for the current target language.

The result is applied by the existing ``translation.py`` machinery through
``bpy.app.translations.register`` - exactly the same replacement principle as
the rest of this add-on.
"""

import os
import re
import csv
import codecs
import glob
import addon_utils

from .utils import read_csv_rows

try:
    import bpy
except ImportError:  # allow importing this module without Blender
    bpy = None


# --------------------------------------------------------------------------- #
# paths / glossary
# --------------------------------------------------------------------------- #

def user_files_dir():
    """Dictionary folder (bundled by default, or the user's custom folder)."""
    from .translation import dict_dir
    return dict_dir(create=True)


def _csv_paths():
    return sorted(glob.glob(os.path.join(user_files_dir(), "*.csv")))


_glossary_cache_sig = None
_glossary_cache_map = {}
_addons_cache = None
_addons_signature = None


def _addon_dirs():
    dirs = []
    try:
        import bpy as _bpy
        for base in _bpy.utils.script_paths():
            for sub in ("addons", "extensions"):
                candidate = os.path.join(base, sub)
                if os.path.isdir(candidate):
                    dirs.append(candidate)
    except Exception:
        pass
    return dirs


def _addon_dirs_signature():
    signature = []
    for directory in _addon_dirs():
        try:
            if os.path.basename(directory) == "extensions":
                # extensions live two levels deeper (repo / package)
                entries = []
                for root, dirs, _files in os.walk(directory):
                    depth = root[len(directory):].count(os.sep)
                    if depth >= 3:
                        dirs[:] = []
                        continue
                    for name in dirs:
                        entries.append(os.path.join(root, name)[len(directory):])
                signature.append((directory, tuple(sorted(entries))))
            else:
                signature.append((directory, tuple(sorted(os.listdir(directory)))))
        except OSError:
            continue
    return tuple(signature)

_CJK = re.compile("[\u4e00-\u9fff]")
_LATIN = re.compile("[A-Za-z]")

# A row is only trusted when the source looks English, the translation looks
# Chinese and the two are not a concatenated blob (a few hand-made CSVs in the
# wild have shifted columns, which otherwise poisons the merged glossary).
_FILE_MAX_BAD_RATIO = 0.25


def pair_is_sane(translated, source):
    if not translated or not source:
        return False
    if translated.strip() == source.strip():
        return False
    if _CJK.search(source) or not _LATIN.search(source):
        return False
    if not _CJK.search(translated):
        return False
    if len(translated) > max(40, len(source) * 3 + 30):
        return False
    return True


def _csv_signature():
    signature = []
    for path in _csv_paths():
        try:
            stat = os.stat(path)
            signature.append((path, int(stat.st_mtime), stat.st_size))
        except OSError:
            continue
    return tuple(signature)


def build_glossary(refresh=False, exclude=None):
    """Return {english_source_string: translated_string} merged from all CSVs.

    ``exclude`` skips one file (the add-on's own CSV) so a corrupted file can
    never poison its own regeneration. Results are cached per exclude path and
    invalidated as soon as any CSV changes, so a second click is instant.
    """
    global _glossary_cache_sig, _glossary_cache_map

    signature = _csv_signature()
    if refresh or signature != _glossary_cache_sig:
        _glossary_cache_sig = signature
        _glossary_cache_map = {}

    exclude = os.path.normcase(os.path.abspath(exclude)) if exclude else None
    cache_key = exclude or ""
    if cache_key in _glossary_cache_map:
        return _glossary_cache_map[cache_key]

    glossary = {}
    for path in _csv_paths():
        if exclude and os.path.normcase(os.path.abspath(path)) == exclude:
            continue
        rows = read_csv_rows(path)
        if not rows:
            continue
        valid_rows = []
        good = bad = 0
        for row in rows:
            if len(row) < 2:
                continue
            translated = row[0].replace("\\n", "\n").strip()
            source = row[1].replace("\\n", "\n").strip()
            if not translated or not source:
                continue
            if pair_is_sane(translated, source):
                valid_rows.append((source, translated))
                good += 1
            else:
                bad += 1

        # A file whose rows are mostly unusable is usually column-shifted.
        if bad and (bad > good * _FILE_MAX_BAD_RATIO) and bad > 5:
            continue

        for source, translated in valid_rows:
            glossary.setdefault(source, translated)

    _glossary_cache_map[cache_key] = glossary
    return glossary


def known_csv_keys():
    """Lower-cased file names (without extension) that already have a CSV."""
    return {
        os.path.splitext(os.path.basename(path))[0].strip().lower()
        for path in _csv_paths()
    }


# --------------------------------------------------------------------------- #
# add-on discovery
# --------------------------------------------------------------------------- #

def list_addons(refresh=False):
    """[(module_id, label, module_name, file_path, has_csv, enabled)] sorted by label.

    The list is cached, but the cache is invalidated automatically as soon as
    the on-disk add-on folders change, so a freshly installed add-on shows up
    without pressing anything.
    """
    global _addons_cache, _addons_signature

    signature = _addon_dirs_signature()
    if signature != _addons_signature:
        refresh = True

    if _addons_cache is not None and not refresh:
        return _addons_cache

    if refresh:
        try:
            addon_utils.modules_refresh()
        except Exception:
            pass
    _addons_signature = signature

    known = known_csv_keys()
    result = []

    for module in addon_utils.modules():
        module_name = getattr(module, "__name__", "")
        if not module_name or module_name.startswith("_"):
            continue

        path = getattr(module, "__file__", "") or ""
        info = getattr(module, "bl_info", {}) or {}
        label = info.get("name") or module_name
        key = os.path.splitext(os.path.basename(path))[0].strip().lower()
        has_csv = (key in known) or (module_name.lower() in known)

        try:
            enabled = bool(addon_utils.check(module_name)[0])
        except Exception:
            enabled = False

        result.append((module_name, label, module_name, path, has_csv, enabled))

    result.sort(key=lambda item: item[1].lower())
    _addons_cache = result
    return result


def filter_addons(needle):
    """Installed add-ons whose name / module id contains ``needle``."""
    needle = (needle or "").strip().lower()
    result = []
    for item in list_addons():
        haystack = ("%s %s" % (item[1], item[0])).lower()
        if not needle or needle in haystack:
            result.append(item)
    return result


def addon_items(self, context):
    """Dynamic EnumProperty items: one entry per installed add-on."""
    items = []
    for index, (module_name, label, _module, _path, has_csv, enabled) in enumerate(list_addons()):
        state = "已翻译" if has_csv else "未翻译"
        if not enabled:
            state += "·未启用"
        items.append((module_name, "%s  [%s]" % (label, state), state,
                      "CHECKMARK" if has_csv else "DOT", index))
    if not items:
        items.append(("__none__", "（没有找到插件）", "", "ERROR", 0))
    return items


# --------------------------------------------------------------------------- #
# string extraction
# --------------------------------------------------------------------------- #

_STRING_PATTERN = re.compile(
    r"""(?P<key>\bbl_label|\bbl_description|\bbl_category|\bdescription|\bname|\btext)"""
    r"""\s*=\s*(?P<quote>['"])(?P<value>(?:\\.|(?!\2).)*)(?P=quote)"""
)

_SKIP_LINE_PATTERN = re.compile(r"^\s*#")
_LONG_STRING = 300

# Strings that are clearly not UI text: identifiers, file names, URLs, format
# specifiers and pure numbers. They used to inflate the "extracted" count and
# made the hit rate look worse than what the user actually sees.
_NON_UI_PATTERNS = (
    re.compile(r"^https?://", re.I),
    re.compile(
        r"^[\w.\-]+\.(py|json|blend|blend1|png|jpe?g|exr|hdr|fbx|glb|gltf|obj|abc|usd\w*|ttf|otf|wav|mp3|mp4|zip|toml|ya?ml)$",
        re.I,
    ),
    re.compile(r"^\d[\d\s.,%:+\-*/()]*$"),
    re.compile(r"%[sdfr]"),
    re.compile(r"\{[a-zA-Z_][^}]*\}"),
    re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)+$"),  # snake_case identifiers
    re.compile(r"^bpy\."),
)


def is_ui_string(text):
    if not text or not re.search(r"[A-Za-z\u4e00-\u9fff]", text):
        return False
    for pattern in _NON_UI_PATTERNS:
        if pattern.search(text):
            return False
    return True


_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")


def is_already_localized(text):
    """Chinese (or mixed Chinese) labels need no translation at all."""
    return bool(_CJK_PATTERN.search(text))


def _normalize_key(text):
    """Lower-case, drop trailing ellipsis / colon, collapse whitespace."""
    text = text.strip().lower()
    text = re.sub(r"[\.\u2026]+$", "", text)
    text = re.sub(r"[:：\s]+$", "", text)
    return re.sub(r"\s+", " ", text)


_index_cache = {}


def glossary_index(exclude=None):
    """(glossary, lower-cased index, normalized index) for one exclude set."""
    key = os.path.normcase(os.path.abspath(exclude)) if exclude else ""
    glossary = build_glossary(exclude=exclude)

    cached = _index_cache.get(key)
    if cached and cached[0] is glossary:
        return cached

    lower = {}
    normalized = {}
    for source, translated in glossary.items():
        lower.setdefault(source.lower(), translated)
        normalized.setdefault(_normalize_key(source), translated)

    entry = (glossary, lower, normalized)
    _index_cache[key] = entry
    return entry


def lookup_translation(index, source):
    """Exact → case-insensitive → punctuation-insensitive dictionary lookup."""
    glossary, lower, normalized = index
    translated = glossary.get(source) or glossary.get(source.strip())
    if translated:
        return translated
    translated = lower.get(source.lower()) or lower.get(source.strip().lower())
    if translated:
        return translated
    return normalized.get(_normalize_key(source))


def module_py_files(module_name, module_path):
    """All .py files that belong to that add-on.

    A packaged add-on reports ``.../<pkg>/__init__.py`` as its file, but its UI
    strings usually live in sibling modules - so walk the whole package folder
    instead of stopping at that one file.
    """
    if not module_path or not os.path.exists(module_path):
        return []
    if os.path.isdir(module_path):
        base = module_path
    elif os.path.basename(module_path).lower() == "__init__.py":
        base = os.path.dirname(module_path)
    else:
        return [module_path]
    return glob.glob(os.path.join(base, "**", "*.py"), recursive=True)


def extract_strings(module_name, module_path, limit=4000):
    """Ordered, unique UI strings declared by the add-on's Python sources."""
    found = []
    seen = set()

    for path in module_py_files(module_name, module_path):
        try:
            with codecs.open(path, "r", "utf-8") as handle:
                lines = handle.readlines()
        except Exception:
            try:
                with codecs.open(path, "r", "utf-8", errors="ignore") as handle:
                    lines = handle.readlines()
            except Exception:
                continue

        for line in lines:
            if _SKIP_LINE_PATTERN.match(line) or "bl_idname" in line:
                continue
            for match in _STRING_PATTERN.finditer(line):
                value = match.group("value")
                value = value.strip()
                if not value or len(value) > _LONG_STRING:
                    continue
                if value in seen:
                    continue
                if not is_ui_string(value):
                    continue
                seen.add(value)
                found.append(value)
                if len(found) >= limit:
                    return found

    return found


# --------------------------------------------------------------------------- #
# writing the CSV / applying it
# --------------------------------------------------------------------------- #

def _existing_pairs(csv_path):
    """Trusted pairs already present in that add-on's own CSV."""
    pairs = {}
    if not os.path.exists(csv_path):
        return pairs
    for row in read_csv_rows(csv_path):
        if len(row) < 2:
            continue
        translated = row[0].replace("\\n", "\n").strip()
        source = row[1].replace("\\n", "\n").strip()
        if pair_is_sane(translated, source):
            pairs.setdefault(source, translated)
    return pairs


def _csv_escape(text):
    return '"%s"' % text.replace('"', '""').replace("\n", "\\n")


def translate_addon(module_name, module_path, target_name=None, dry_run=False, overwrite=False):
    """Extract + translate one add-on. Returns a small result dict."""
    strings = extract_strings(module_name, module_path)

    if not strings:
        return {"module": module_name, "extracted": 0, "hit": 0, "missing": 0,
                "csv": None, "samples": []}

    csv_name = (target_name or module_name).strip() + ".csv"
    csv_path = os.path.join(user_files_dir(), csv_name)

    # Never let the add-on's own file feed its own translation: a few CSVs out
    # there have shifted columns and would otherwise reproduce the same damage.
    index = glossary_index(exclude=csv_path)

    if overwrite:
        if os.path.exists(csv_path):
            try:
                import shutil
                shutil.copy2(csv_path, csv_path + ".bak")
            except Exception:
                pass
        pairs = {}
        existing_pairs = {}
    else:
        existing_pairs = _existing_pairs(csv_path)
        pairs = dict(existing_pairs)

    hit = 0
    blender_strings = set()
    localized = 0
    for source in strings:
        if is_already_localized(source):
            # Chinese add-on: nothing to translate, do not count it as a miss
            localized += 1
            continue
        if source in pairs and pairs[source]:
            hit += 1
            continue
        translated = lookup_translation(index, source)
        if translated:
            pairs[source] = translated
            hit += 1
            continue
        # Blender itself already translates this one (built-in UI translation),
        # so the user sees Chinese even without a dictionary entry.
        try:
            if bpy is not None and bpy.app.translations.pgettext_iface(source) != source:
                blender_strings.add(source)
        except Exception:
            pass

    if not dry_run:
        rows = []
        written = set()
        for source in strings:
            rows.append("%s,%s" % (_csv_escape(pairs.get(source, "")), _csv_escape(source)))
            written.add(source)
        # Never delete a translation that was already there: keep every trusted
        # existing pair even when this extraction pass did not come across it.
        for source, translated in existing_pairs.items():
            if source in written:
                continue
            rows.append("%s,%s" % (_csv_escape(translated), _csv_escape(source)))
            written.add(source)

        os.makedirs(user_files_dir(), exist_ok=True)
        with codecs.open(csv_path, "w", "utf-8") as handle:
            handle.write("\n".join(rows))

    missing = [
        source for source in strings
        if not pairs.get(source) and source not in blender_strings
        and not is_already_localized(source)
    ]
    return {
        "module": module_name,
        "extracted": len(strings),
        "hit": hit,
        "blender": len(blender_strings),
        "localized": localized,
        "missing": len(missing),
        "csv": csv_path if not dry_run else None,
        "samples": missing[:8],
    }


def existing_pairs(csv_path):
    """Public wrapper: trusted pairs already stored for one add-on."""
    return _existing_pairs(csv_path)


def pending_strings(module_name, module_path, csv_path=None):
    """Strings that still have no Chinese: not in the dictionary, not Chinese,
    not already handled by Blender's own translation."""
    index = glossary_index()
    existing = _existing_pairs(csv_path) if csv_path else {}
    pending = []
    for source in extract_strings(module_name, module_path):
        if is_already_localized(source):
            continue
        if existing.get(source):
            continue
        if lookup_translation(index, source):
            continue
        try:
            if bpy is not None and bpy.app.translations.pgettext_iface(source) != source:
                continue
        except Exception:
            pass
        pending.append(source)
    return pending


def write_pairs(csv_path, pairs):
    """Rewrite one dictionary file from a {english: chinese} mapping."""
    rows = []
    for source in sorted(pairs):
        translated = (pairs[source] or "").strip()
        if not translated:
            continue
        rows.append("%s,%s" % (_csv_escape(translated), _csv_escape(source)))
    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
    with codecs.open(csv_path, "w", "utf-8") as handle:
        handle.write("\n".join(rows))
    return len(rows)


def audit_dicts():
    """Quick health summary of every dictionary file."""
    report = {
        "files": 0,
        "rows": 0,
        "valid": 0,
        "invalid": 0,
        "duplicates": 0,
        "suspect_files": [],
    }
    seen = set()
    for path in _csv_paths():
        report["files"] += 1
        good = bad = 0
        for row in read_csv_rows(path):
            if len(row) < 2:
                continue
            report["rows"] += 1
            translated = row[0].replace("\\n", "\n").strip()
            source = row[1].replace("\\n", "\n").strip()
            if not translated or not source:
                continue
            pair = (source, translated)
            if pair in seen:
                report["duplicates"] += 1
            seen.add(pair)
            if pair_is_sane(translated, source):
                good += 1
            else:
                bad += 1
        report["valid"] += good
        report["invalid"] += bad
        if bad and (bad > good * _FILE_MAX_BAD_RATIO) and bad > 5:
            report["suspect_files"].append(os.path.basename(path))
    return report


def missing_to_clipboard(module_name, module_path):
    """Put the not-yet-translated strings on the clipboard (one per line)."""
    index = glossary_index()
    strings = extract_strings(module_name, module_path)
    missing = [source for source in strings if not lookup_translation(index, source)]
    if bpy is not None and missing:
        bpy.context.window_manager.clipboard = "\n".join(missing)
    return missing
