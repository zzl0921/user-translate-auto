# User Translate Addon (C) 2022-2024 Bookyakuno
# Created by Bookyakuno
# License : GNU General Public License version3 (http://www.gnu.org/licenses/)
# Modified by zzl0921 (2026): auto translate, per add-on switches,
#   new add-on prompt, incremental dictionary registration and bug fixes.

bl_info = {
    "name": "User Translate (Auto Translate)",
    "author": "zzl0921",
    "version": (1, 0, 0),
    "blender": (4, 1, 0),
    "location": "Addon Preferences",
    "description": "Dictionary based UI translation, plus auto-translate from the bundled glossary",
    "warning": "",
    "category": "Preferences"
}


if "bpy" in locals():
    import importlib
    reloadable_modules = [
    "utils",
    "translation",
    "op_other",
    "auto_translate",
    "op_auto",
    ]
    for module in reloadable_modules:
        if module in locals():
            importlib.reload(locals()[module])

import bpy
from .utils import *
from .utils import language_items_old, language_items_V400
from .translation import *
from .op_other import *
from .op_other import re_register_files
from .auto_translate import *
from .op_auto import *

# Only preview a few rows per dictionary in the preferences panel: some files
# contain tens of thousands of rows and drawing them all froze Blender.
FILE_DATA_PREVIEW_ROWS = 20


def _sync_addon_list(self, context):
    """Keep the scrollable add-on list in sync with search + filter."""
    try:
        sync_addon_rows(self)
    except Exception as exc:
        print("[user_translate] sync_addon_rows failed:", exc)


from bpy.props import *
from bpy.types import AddonPreferences


#
class USERTRANSLATE_MT_AddonPreferences(AddonPreferences):
    bl_idname = __name__

    tab_addon_menu : EnumProperty(name="Tab", description="", items=[('Option', "Option", "","DOT",0), ('Link', "Link", "","URL",2)], default='Option')
    ui_toggle_file_data : BoolProperty(name="File Data")
    ui_opened_files : StringProperty()

    target_filename : StringProperty(name="File Name")
    clipboard_source : StringProperty(name="Source")
    clipboard_translate : StringProperty(name="Translated")
    # target_dirpath :  StringProperty(type='DIR_PATH')
    translated_text_file : StringProperty(name="Translated Text File",subtype="FILE_PATH")

    # Auto translate: pick an add-on from a menu, then fill its UI strings
    # from the dictionaries already present in user_files/*.csv.
    auto_filter : StringProperty(
        name="搜索",
        description="按插件名或模块名过滤下面的列表（例如输入 node）",
        default="",
        update=_sync_addon_list,
    )
    auto_overwrite : BoolProperty(
        name="覆盖已有 CSV",
        description="重新生成该插件自己的 csv（旧文件备份为 .csv.bak），用于修复列错位的坏文件",
        default=False,
    )
    auto_last_result : StringProperty(name="", default="")

    # 翻译总开关 + 逐份词典启停：默认全部启用（和原版行为一致），
    # 关掉总开关或取消某份词典后，对应插件界面保持原文。
    translate_enabled : BoolProperty(
        name="启用界面翻译",
        description="总开关：关闭后所有词典都不生效，其它插件界面保持原文",
        default=True,
        update=re_register_files,
    )
    disabled_dicts : StringProperty(default="")

    # 可滚动的插件列表：每行一个已安装插件 + 翻译开关
    addon_filter : EnumProperty(
        name="显示",
        items=[('ALL', "全部", ""), ('ON', "翻译中", ""), ('OFF', "未翻译", "")],
        default='ALL',
        update=_sync_addon_list,
    )
    addon_rows : CollectionProperty(type=USERTRANSLATE_PG_addon_row)
    addon_index : IntProperty()

    # 新装插件提示
    prompt_new_addons : BoolProperty(
        name="新装插件时提示",
        description="检测到新安装的插件时，在面板顶部提示「要翻译吗」",
        default=True,
    )
    known_addons : StringProperty(default="")
    addons_seeded : BoolProperty(default=False)

    # 词典目录：留空 = 插件自带 user_files；指到外部目录后，更新插件不会动词典
    user_dict_dir : StringProperty(
        name="词典目录",
        description="留空则用插件自带的 user_files；选外部文件夹可让词典独立于插件更新",
        subtype="DIR_PATH",
        default="",
        update=re_register_files,
    )

    # 增量注册：只写界面真正会查询的 "*" 上下文（快 10 倍以上）
    register_all_contexts : BoolProperty(
        name="注册全部上下文（慢）",
        description="默认只用 \"*\" 上下文注册；若发现个别文字仍是英文，勾选此项恢复完整注册",
        default=False,
        update=re_register_files,
    )


    if bpy.app.version >= (4,0,0):
        language : EnumProperty(default="ja_JP",name="Language",items= language_items_V400, update=re_register_files)
    else:
        language : EnumProperty(default="ja_JP",name="Language",items= language_items_old, update=re_register_files)

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.prop(self, "tab_addon_menu",expand=True)

        # 自動翻訳 (auto translate) — kept at the very top so it is visible
        # without scrolling and the add-on picker gets the full panel width.
        box = layout.box()
        col = box.column()
        col.label(text="自动翻译（选一个英文插件，只替换它的界面文字）", icon="FONTPREVIEW")
        col.prop(self, "auto_filter", text="搜索", icon="VIEWZOOM")
        matches = filter_addons(self.auto_filter)
        total = len(list_addons())
        if self.auto_filter.strip():
            col.label(
                text="搜索「%s」匹配 %d / %d 个插件%s" % (
                    self.auto_filter.strip(), len(matches), total,
                    "" if matches else "（无匹配，清空搜索框恢复全部）"),
                icon="INFO",
            )
        else:
            col.label(text="共 %d 个插件（输入关键词可过滤）" % total, icon="INFO")

        new_mods = detect_new_addons(self)
        if new_mods:
            names = [item[1] for item in list_addons() if item[0] in new_mods]
            nbox = col.box()
            nbox.label(
                text="检测到 %d 个新插件：%s　要翻译吗？" % (
                    len(new_mods),
                    "、".join(names[:3]) + ("…" if len(names) > 3 else ""),
                ),
                icon="INFO",
            )
            nrow = nbox.row(align=True)
            op = nrow.operator("usertranslate.translate_new_addons", text="全部翻译", icon="CHECKMARK")
            op.modules = "\n".join(new_mods)
            nrow.operator("usertranslate.dismiss_new_addons", text="忽略", icon="X")

        col.separator()
        col.prop(self, "translate_enabled", text="启用界面翻译（总开关）")
        col.label(
            text="生效词典：%d / %d 份" % (active_dict_count(), len(get_csv_file_list())),
            icon="INFO",
        )
        row = col.row(align=True)
        row.prop(self, "addon_filter", expand=True)
        if len(self.addon_rows) == 0:
            sync_addon_rows(self)
        listbox = col.box()
        listbox.template_list(
            "USERTRANSLATE_UL_addons", "", self, "addon_rows", self, "addon_index", rows=10
        )
        row = col.row(align=True)
        row.operator("usertranslate.translate_selected_addon", text="重翻选中", icon="FILE_REFRESH")
        op = row.operator("usertranslate.set_all_addons", text="全部启用", icon="CHECKMARK")
        op.enable = True
        op = row.operator("usertranslate.set_all_addons", text="全部停用", icon="X")
        op.enable = False
        col.separator()

        col.scale_y = 1.0
        col.menu("USERTRANSLATE_MT_auto_missing", text="复制该插件的待补文字", icon="PASTEDOWN")
        col.operator("usertranslate.refresh_auto_addon_list", text="刷新插件列表（新装插件后点一下）", icon="FILE_REFRESH")
        col.prop(self, "auto_overwrite")
        col.prop(self, "prompt_new_addons")
        col.prop(self, "register_all_contexts")
        col.prop(self, "user_dict_dir", text="词典目录")
        if self.user_dict_dir.strip():
            row = col.row(align=True)
            row.operator("usertranslate.copy_bundled_dicts", text="复制随包词典到此目录", icon="COPYDOWN")
            row.operator("usertranslate.open_folder", text="", icon="FILE_FOLDER")
            col.label(text="已使用外部词典目录：更新插件时这里不会被覆盖", icon="INFO")
        if self.auto_last_result:
            col.label(text=self.auto_last_result, icon="INFO")
        col.label(text="勾选列表里的插件 = 自动翻译它；右侧 ↻ = 重新翻译；取消勾选 = 恢复原文", icon="NONE")
        layout.separator()

        layout.prop(context.preferences.view, "use_translate_interface",icon="FONTPREVIEW")

        layout.separator()
        layout.prop(self,"language")
        layout.separator()
        box = layout.box()
        col = box.column()
        row_main = col.row(align=True)
        col = row_main.column()
        col.scale_x = .3
        col.label(text="1.",icon="NONE")
        col.label(text="2.",icon="NONE")
        col.label(text="3.",icon="NONE")
        col = row_main.column()
        row = col.row(align=True)
        op = row.operator("usertranslate.file_extract_text",icon="FILE")
        op.is_dir = False
        op = row.operator("usertranslate.file_extract_text",text="Extract text from .py in a folder",icon="FILE_FOLDER")
        op.is_dir = True
        op = col.operator("usertranslate.paste_clipboard_to_tlanslate_text",icon="PASTEDOWN")
        op.type = "translate"
        # col.prop(self,"translated_text_file")
        box = col.box()
        box.operator("usertranslate.combine_src_and_tras_text",icon="EXPORT")
        box.prop(self,"target_filename")
        row = box.row(align=True)
        op = row.operator("usertranslate.paste_clipboard_to_tlanslate_text",text="",icon="PASTEDOWN")
        op.type = "source"
        row.prop(self,"clipboard_source")
        row.separator()

        op = row.operator("usertranslate.paste_clipboard_to_tlanslate_text",text="",icon="PASTEDOWN")
        op.type = "translate"
        row.prop(self,"clipboard_translate")

        layout.separator()


        # ファイルデータ
        sp = layout.split(align=True,factor=0.7)
        row = sp.row(align=True)
        row.alignment="LEFT"
        row.prop(self,"ui_toggle_file_data",icon="TRIA_DOWN" if self.ui_toggle_file_data else "TRIA_RIGHT", emboss=False)
        row = sp.row(align=True)
        row.alignment="RIGHT"
        row.operator("usertranslate.open_folder",icon="FILE_FOLDER")
        if self.ui_toggle_file_data:
            list = get_csv_file_list()
            box = layout.box()
            col_main = box.column(align=True)

            for path in list:
                col_main.separator()
                rows = read_csv_rows(path)
                col_main.label(text="%s  (%d 条)" % (os.path.basename(path), len(rows)), icon="DOT")
                for line in rows[:FILE_DATA_PREVIEW_ROWS]:
                    if not line or line[0] == "":
                        continue
                    try:
                        row = col_main.row(align=True)
                        row.label(text=line[1].replace('\\n', '\n'), icon="BLANK1")
                    except IndexError:
                        pass
                if len(rows) > FILE_DATA_PREVIEW_ROWS:
                    row = col_main.row(align=True)
                    row.label(
                        text="… 还有 %d 条（点右上「Open Folder」看完整文件）" % (len(rows) - FILE_DATA_PREVIEW_ROWS),
                        icon="INFO",
                    )






classes = (
USERTRANSLATE_PG_addon_row,
USERTRANSLATE_UL_addons,
USERTRANSLATE_OT_open_folder,
USERTRANSLATE_OT_copy_bundled_dicts,
USERTRANSLATE_OT_file_extract_text,
USERTRANSLATE_OT_paste_clipboard_to_tlanslate_text,
USERTRANSLATE_OT_combine_src_and_tras_text,
USERTRANSLATE_OT_auto_translate_addon,
USERTRANSLATE_OT_auto_translate_missing_to_clipboard,
USERTRANSLATE_OT_toggle_addon_translation,
USERTRANSLATE_OT_translate_selected_addon,
USERTRANSLATE_OT_translate_new_addons,
USERTRANSLATE_OT_dismiss_new_addons,
USERTRANSLATE_OT_set_all_addons,
USERTRANSLATE_OT_refresh_auto_addon_list,
USERTRANSLATE_MT_auto_addons,
USERTRANSLATE_MT_auto_missing,
USERTRANSLATE_MT_AddonPreferences,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # translation
    register_translation_dict()




def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    # translation
    unregister_translation_dict()


if __name__ == "__main__":
    register()
