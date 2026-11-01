import bpy
import glob
import os
import csv
import codecs  # 辞書
from .utils import *

DICT_LIST_NAME = "dist_name_l"
dist_name_l = []

BASE_DICT_NAME = "__user_translate_base"


# --------------------------------------------------------------------------- #
# which dictionaries are active
# --------------------------------------------------------------------------- #

def disabled_dict_names():
    raw = getattr(preference(), "disabled_dicts", "") or ""
    return {line.strip() for line in raw.split("\n") if line.strip()}


def set_disabled_dict_names(names):
    preference().disabled_dicts = "\n".join(sorted(names))


def translations_enabled():
    """Master switch: when off nothing at all is registered."""
    return bool(getattr(preference(), "translate_enabled", True))


def file_enabled(path):
    return translations_enabled() and os.path.basename(path) not in disabled_dict_names()


def active_contexts():
    """Contexts written into the registered tables.

    Blender looks interface strings up in the "*" context; the other ~54
    contexts are only consulted by explicit ``pgettext_ctxt`` calls. Writing
    every entry into every context multiplied the table by ~55 (10.9M entries,
    ~5 s start-up), so "*" alone is the default. Users can switch the full
    matrix back on if some label ever stays English.
    """
    if getattr(preference(), "register_all_contexts", False):
        return tuple(bpy.app.translations.contexts)
    return ("*",)


# --------------------------------------------------------------------------- #
# register / unregister
# --------------------------------------------------------------------------- #

def dict_dir(create=False):
    """Where dictionaries live.

    Default is the bundled ``user_files`` folder. Users can point this to a
    folder outside the add-on (preference ``user_dict_dir``) so that updating
    the add-on never touches their dictionaries.
    """
    custom = ""
    try:
        custom = (getattr(preference(), "user_dict_dir", "") or "").strip()
    except Exception:
        custom = ""

    if custom:
        path = bpy.path.abspath(custom)
    else:
        path = os.path.join(os.path.dirname(__file__), "user_files")

    if create:
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as exc:
            print("[user_translate] cannot create dictionary folder:", path, exc)
    return path


def bundled_dict_dir():
    return os.path.join(os.path.dirname(__file__), "user_files")


def get_csv_file_list():
    directory = dict_dir()
    if not os.path.isdir(directory):
        return []
    return glob.glob(os.path.join(directory, "*.csv"))


def csv_path_for_module(module_name):
    """Path of that add-on's dictionary (existing file, or the one we would write)."""
    target = module_name + ".csv"
    for path in get_csv_file_list():
        if os.path.basename(path) == target:
            return path
    return os.path.join(dict_dir(create=True), target)


def _dist_name(path):
    return __name__ + os.path.basename(path)


def _build_file_dict(path, language, seen=None):
    """[(context, source)] -> target for one CSV.

    ``seen`` is shared across files so a pair already registered by an earlier
    dictionary is not registered again (incremental loading). Later
    registrations never override earlier ones in Blender, so skipping repeats
    changes no visible result.
    """
    rows = read_csv_rows(path)
    if not rows:
        return None
    contexts = active_contexts()
    table = {}
    for row in rows:
        if not row or row[0] == "":
            continue
        try:
            source = row[1].replace('\\n', '\n')
            target = row[0].replace('\\n', '\n')
        except IndexError:
            continue
        if not source or not target:
            continue
        for context in contexts:
            key = (context, source)
            if seen is not None:
                if key in seen:
                    continue
                seen.add(key)
            table[key] = target
    if not table:
        return None
    return {language: table}


def _unregister_one(path):
    global dist_name_l
    name = _dist_name(path)
    if name in dist_name_l:
        try:
            bpy.app.translations.unregister(name)
        except Exception:
            pass
        try:
            dist_name_l.remove(name)
        except ValueError:
            pass


def register_translation_file(path, seen=None):
    """Register exactly one CSV (used when the user re-enables a dictionary)."""
    global dist_name_l
    _unregister_one(path)
    data = _build_file_dict(path, preference().language, seen=seen)
    if not data:
        return False
    try:
        name = _dist_name(path)
        bpy.app.translations.register(name, data)
        dist_name_l.append(name)
        return True
    except Exception as exc:
        print("[user_translate] register failed:", os.path.basename(path), exc)
        return False


def unregister_translation_file(path):
    _unregister_one(path)


def register_translation_dict():
    """Register every enabled dictionary (master switch + per-add-on list)."""
    unregister_translation_dict()
    if not translations_enabled():
        return
    disabled = disabled_dict_names()
    seen = set()
    for path in get_csv_file_list():
        if os.path.basename(path) in disabled:
            continue
        register_translation_file(path, seen=seen)


def unregister_translation_dict():
    global dist_name_l
    for name in list(dist_name_l):
        try:
            bpy.app.translations.unregister(name)
        except Exception:
            pass
    dist_name_l = []


def re_register_files(self, context):
    register_translation_dict()
    screen = getattr(bpy.context, "screen", None)
    if screen is None:
        return
    for area in screen.areas:
        area.tag_redraw()


def reload_translation_file(path):
    """Re-register a single CSV file, or drop it when it has been disabled."""
    if not file_enabled(path):
        _unregister_one(path)
        return
    register_translation_file(path)


def active_dict_count():
    if not translations_enabled():
        return 0
    disabled = disabled_dict_names()
    return sum(1 for path in get_csv_file_list() if os.path.basename(path) not in disabled)
