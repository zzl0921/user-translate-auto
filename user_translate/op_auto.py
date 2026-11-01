# -*- coding: utf-8 -*-
"""Operators, menus and lists for the auto translate feature.

Design notes:

* The add-on picker is a Menu, not a dynamic EnumProperty: dynamic enums do not
  render reliably inside AddonPreferences (Blender reports zero enum_items, so
  the widget draws as an empty icon), while menu rows are plain operator
  buttons and always show their label.
* The on/off list is a real UIList so it gets a scrollbar; one row per
  installed add-on with a checkbox that turns that add-on's UI translation on
  or off.
"""

import os

import bpy
from bpy.types import Menu, Operator, PropertyGroup, UIList
from bpy.props import BoolProperty, StringProperty

from .utils import preference
from .translation import (
    re_register_files,
    reload_translation_file,
    csv_path_for_module,
    disabled_dict_names,
    set_disabled_dict_names,
    translations_enabled,
)
from .auto_translate import (
    translate_addon,
    missing_to_clipboard,
    list_addons,
    filter_addons,
)


def _redraw_areas():
    screen = getattr(bpy.context, "screen", None)
    if screen is None:
        return
    for area in screen.areas:
        area.tag_redraw()


def _find_addon(module_name):
    for module_id, label, _module, path, has_csv, enabled in list_addons():
        if module_id == module_name:
            return module_id, label, path
    return None, None, None


# --------------------------------------------------------------------------- #
# list model: one row per installed add-on
# --------------------------------------------------------------------------- #

class USERTRANSLATE_PG_addon_row(PropertyGroup):
    module: StringProperty(default="")
    label: StringProperty(default="")
    has_csv: BoolProperty(default=False)
    enabled: BoolProperty(default=False)


def addon_row_state(module_id):
    """(csv_exists, translation_active) for one add-on."""
    csv_path = csv_path_for_module(module_id)
    exists = os.path.exists(csv_path)
    active = (
        exists
        and translations_enabled()
        and os.path.basename(csv_path) not in disabled_dict_names()
    )
    return exists, active


def sync_addon_rows(prefs=None):
    """Rebuild the visible rows from the search text + 全部/翻译中/未翻译 filter."""
    prefs = prefs or preference()
    needle = (getattr(prefs, "auto_filter", "") or "").strip().lower()
    mode = getattr(prefs, "addon_filter", "ALL")

    try:
        prefs.addon_rows.clear()
    except Exception:
        return

    for module_id, label, _module, _path, _has_csv, _enabled in list_addons():
        if needle and needle not in ("%s %s" % (label, module_id)).lower():
            continue
        exists, active = addon_row_state(module_id)
        if mode == "ON" and not active:
            continue
        if mode == "OFF" and active:
            continue
        item = prefs.addon_rows.add()
        item.module = module_id
        item.label = label
        item.has_csv = exists
        item.enabled = active

    if prefs.addon_index >= len(prefs.addon_rows):
        prefs.addon_index = max(0, len(prefs.addon_rows) - 1)


class USERTRANSLATE_UL_addons(UIList):
    bl_idname = "USERTRANSLATE_UL_addons"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        op = row.operator(
            "usertranslate.toggle_addon_translation",
            text="",
            icon="CHECKBOX_HLT" if item.enabled else "CHECKBOX_DEHLT",
            emboss=False,
        )
        op.module = item.module
        row.label(text=item.label)
        row.label(text="已翻译" if item.has_csv else "未翻译")
        # per-row "translate again": rebuild this add-on's dictionary on the spot
        op = row.operator(
            "usertranslate.auto_translate_addon", text="", icon="FILE_REFRESH", emboss=False
        )
        op.module = item.module


class USERTRANSLATE_MT_auto_addons(Menu):
    bl_idname = "USERTRANSLATE_MT_auto_addons"
    bl_label = "选择插件并翻译"

    def draw(self, context):
        layout = self.layout
        prefs = preference()
        matches = filter_addons(getattr(prefs, "auto_filter", ""))
        if not matches:
            layout.label(text="没有匹配的插件，改一下搜索词", icon="ERROR")
            return
        for module_id, label, _module, _path, has_csv, enabled in matches:
            op = layout.operator(
                "usertranslate.auto_translate_addon",
                text="%s  [%s]" % (label, _state_text(has_csv, enabled)),
                icon="CHECKMARK" if has_csv else "DOT",
            )
            op.module = module_id


class USERTRANSLATE_MT_auto_missing(Menu):
    bl_idname = "USERTRANSLATE_MT_auto_missing"
    bl_label = "复制待补文字"

    def draw(self, context):
        layout = self.layout
        prefs = preference()
        matches = filter_addons(getattr(prefs, "auto_filter", ""))
        if not matches:
            layout.label(text="没有匹配的插件，改一下搜索词", icon="ERROR")
            return
        for module_id, label, _module, _path, has_csv, enabled in matches:
            op = layout.operator(
                "usertranslate.auto_translate_missing_to_clipboard",
                text="%s  [%s]" % (label, _state_text(has_csv, enabled)),
                icon="PASTEDOWN",
            )
            op.module = module_id


def _state_text(has_csv, enabled):
    state = "已翻译" if has_csv else "未翻译"
    if not enabled:
        state += "·未启用"
    return state


# --------------------------------------------------------------------------- #
# operators
# --------------------------------------------------------------------------- #

class USERTRANSLATE_OT_toggle_addon_translation(Operator):
    bl_idname = "usertranslate.toggle_addon_translation"
    bl_label = "翻译 / 不翻译这个插件"
    bl_description = (
        "勾选：为这个插件生成（或启用）中文词典，界面立即变中文\n"
        "取消：停用它的词典，界面恢复原文"
    )

    module: StringProperty()

    def execute(self, context):
        prefs = preference()
        module_id, label, path = _find_addon(self.module)
        if not module_id:
            self.report({'WARNING'}, "找不到插件：%s" % self.module)
            return {'CANCELLED'}

        csv_path = csv_path_for_module(module_id)
        base = os.path.basename(csv_path)
        exists, active = addon_row_state(module_id)
        disabled = disabled_dict_names()

        if active:
            disabled.add(base)
            set_disabled_dict_names(disabled)
            reload_translation_file(csv_path)
            state = "已停用（界面恢复原文）"
        else:
            if not exists:
                result = translate_addon(
                    module_id, path, target_name=module_id,
                    overwrite=getattr(prefs, "auto_overwrite", False),
                )
                if result["extracted"] == 0:
                    self.report({'WARNING'}, "没有从 %s 里提取到界面文字" % label)
                    return {'CANCELLED'}
                if result["csv"]:
                    csv_path = result["csv"]
                    base = os.path.basename(csv_path)
                if hasattr(prefs, "auto_last_result"):
                    prefs.auto_last_result = "%s：提取 %d 条 / 已翻译 %d 条 / 待补 %d 条" % (
                        label, result["extracted"], result["hit"], result["missing"])
            disabled.discard(base)
            set_disabled_dict_names(disabled)
            reload_translation_file(csv_path)
            state = "已启用（界面已翻译）"

        sync_addon_rows(prefs)
        _redraw_areas()
        self.report({'INFO'}, "%s：%s" % (label, state))
        return {'FINISHED'}


class USERTRANSLATE_OT_translate_selected_addon(Operator):
    bl_idname = "usertranslate.translate_selected_addon"
    bl_label = "重新翻译选中的插件"
    bl_description = "对列表里选中的插件重新执行一次翻译（覆盖其词典）"

    def execute(self, context):
        prefs = preference()
        if prefs.addon_index < 0 or prefs.addon_index >= len(prefs.addon_rows):
            self.report({'WARNING'}, "请先在列表里点选一个插件")
            return {'CANCELLED'}
        module_id = prefs.addon_rows[prefs.addon_index].module
        module_id, label, path = _find_addon(module_id)
        if not module_id:
            return {'CANCELLED'}
        result = translate_addon(
            module_id, path, target_name=module_id,
            overwrite=getattr(prefs, "auto_overwrite", False),
        )
        if result["extracted"] == 0:
            self.report({'WARNING'}, "没有从 %s 里提取到界面文字" % label)
            return {'CANCELLED'}
        if result["csv"]:
            disabled = disabled_dict_names()
            disabled.discard(os.path.basename(result["csv"]))
            set_disabled_dict_names(disabled)
            reload_translation_file(result["csv"])
        sync_addon_rows(prefs)
        _redraw_areas()
        self.report({'INFO'}, "%s：提取 %d 条 / 已翻译 %d 条 / 待补 %d 条"
                    % (label, result["extracted"], result["hit"], result["missing"]))
        return {'FINISHED'}


class USERTRANSLATE_OT_auto_translate_addon(Operator):
    bl_idname = "usertranslate.auto_translate_addon"
    bl_label = "自动翻译选中插件"
    bl_description = (
        "用本地词典翻译选中插件里可识别的界面文字，写入 user_files/<插件>.csv\n"
        "只替换显示文字，不修改插件本身"
    )

    module: StringProperty()

    def execute(self, context):
        prefs = preference()
        module_id, label, path = _find_addon(self.module) if self.module else (None, None, None)
        if not module_id:
            self.report({'WARNING'}, "请在菜单里选择一个插件")
            return {'CANCELLED'}

        result = translate_addon(
            module_id, path, target_name=module_id,
            overwrite=getattr(prefs, "auto_overwrite", False),
        )
        if result["extracted"] == 0:
            self.report({'WARNING'}, "没有从 %s 里提取到界面文字" % label)
            return {'CANCELLED'}

        if result["csv"]:
            disabled = disabled_dict_names()
            disabled.discard(os.path.basename(result["csv"]))
            set_disabled_dict_names(disabled)
            reload_translation_file(result["csv"])
        sync_addon_rows(prefs)
        _redraw_areas()

        message = "%s：提取 %d 条 / 已翻译 %d 条 / 待补 %d 条" % (
            label, result["extracted"], result["hit"], result["missing"])
        if result["csv"]:
            message += " → user_files/%s" % os.path.basename(result["csv"])
        if hasattr(prefs, "auto_last_result"):
            prefs.auto_last_result = message
        self.report({'INFO'}, message)
        return {'FINISHED'}


class USERTRANSLATE_OT_auto_translate_missing_to_clipboard(Operator):
    bl_idname = "usertranslate.auto_translate_missing_to_clipboard"
    bl_label = "复制待补文字到剪贴板"
    bl_description = "把选中插件里还没有翻译的界面文字复制到剪贴板，方便外部翻译后再粘回来"

    module: StringProperty()

    def execute(self, context):
        module_id, label, path = _find_addon(self.module) if self.module else (None, None, None)
        if not module_id:
            self.report({'WARNING'}, "请在菜单里选择一个插件")
            return {'CANCELLED'}

        missing = missing_to_clipboard(module_id, path)
        if not missing:
            self.report({'INFO'}, "%s：没有待补的文字（全部已在词典里）" % label)
            return {'FINISHED'}

        self.report({'INFO'}, "%s：已把 %d 条待补文字复制到剪贴板" % (label, len(missing)))
        return {'FINISHED'}


class USERTRANSLATE_OT_set_all_addons(Operator):
    bl_idname = "usertranslate.set_all_addons"
    bl_label = "全部启用/停用"

    enable: BoolProperty(default=True)

    def execute(self, context):
        from .translation import get_csv_file_list, register_translation_dict

        prefs = preference()
        if self.enable:
            set_disabled_dict_names(set())
        else:
            set_disabled_dict_names({os.path.basename(p) for p in get_csv_file_list()})
        register_translation_dict()
        sync_addon_rows(prefs)
        _redraw_areas()
        self.report({'INFO'}, "已全部%s" % ("启用" if self.enable else "停用"))
        return {'FINISHED'}


def detect_new_addons(prefs=None):
    """Add-ons that appeared since the last time we looked (empty on first run)."""
    prefs = prefs or preference()
    current = [item[0] for item in list_addons()]
    known = {
        line.strip() for line in (getattr(prefs, "known_addons", "") or "").split("\n") if line.strip()
    }

    if not getattr(prefs, "addons_seeded", False):
        # first run: remember what is installed so we do not nag about all of it
        prefs.known_addons = "\n".join(current)
        prefs.addons_seeded = True
        return []

    if not getattr(prefs, "prompt_new_addons", True):
        return []
    return [module_id for module_id in current if module_id not in known]


def mark_addons_known(modules=None):
    prefs = preference()
    current = [item[0] for item in list_addons()]
    known = {
        line.strip() for line in (getattr(prefs, "known_addons", "") or "").split("\n") if line.strip()
    }
    known.update(modules or current)
    prefs.known_addons = "\n".join(sorted(known))


class USERTRANSLATE_OT_translate_new_addons(Operator):
    bl_idname = "usertranslate.translate_new_addons"
    bl_label = "翻译新检测到的插件"
    bl_description = "为新安装的插件批量生成词典并启用"

    modules: StringProperty()

    def execute(self, context):
        prefs = preference()
        wanted = [line.strip() for line in (self.modules or "").split("\n") if line.strip()]
        done = 0
        hits = 0
        for module_id in wanted:
            _mid, label, path = _find_addon(module_id)
            if not _mid:
                continue
            result = translate_addon(
                module_id, path, target_name=module_id,
                overwrite=getattr(prefs, "auto_overwrite", False),
            )
            if result["extracted"] == 0:
                continue
            if result["csv"]:
                disabled = disabled_dict_names()
                disabled.discard(os.path.basename(result["csv"]))
                set_disabled_dict_names(disabled)
                reload_translation_file(result["csv"])
            done += 1
            hits += result["hit"]

        mark_addons_known(wanted)
        sync_addon_rows(prefs)
        _redraw_areas()
        self.report({'INFO'}, "已翻译 %d 个新插件（共 %d 条词条）" % (done, hits))
        return {'FINISHED'}


class USERTRANSLATE_OT_dismiss_new_addons(Operator):
    bl_idname = "usertranslate.dismiss_new_addons"
    bl_label = "忽略新插件提示"
    bl_description = "不再提示这些插件（之后仍可在列表里手动勾选翻译）"

    def execute(self, context):
        mark_addons_known()
        _redraw_areas()
        self.report({'INFO'}, "已忽略本次新插件提示")
        return {'FINISHED'}


class USERTRANSLATE_OT_refresh_auto_addon_list(Operator):
    bl_idname = "usertranslate.refresh_auto_addon_list"
    bl_label = "刷新插件列表"
    bl_description = "重新扫描已安装插件（安装/删除插件后点一下）"

    def execute(self, context):
        items = list_addons(refresh=True)
        sync_addon_rows(preference())
        _redraw_areas()
        self.report({'INFO'}, "已扫描到 %d 个插件" % len(items))
        return {'FINISHED'}
