import bpy, re, subprocess, codecs
from bpy.types import Operator
from bpy.props import *
from .utils import *
from .translation import *
from bpy_extras.io_utils import (
		ImportHelper,
		ExportHelper
		)

class USERTRANSLATE_OT_paste_clipboard_to_tlanslate_text(Operator):
	bl_idname = 'usertranslate.paste_clipboard_to_tlanslate_text'
	bl_label = "Paste translated text from clipboard"
	bl_description = "Paste the clipboard text translated by an automatic translation site etc. as translated text"
	items = [
	("translate","translate",""),
	("source","source",""),
	]
	type : EnumProperty(default="translate",name="Type",items= items)

	# items = [
	# ("FILE","File",""),
	# ("CLIPBOARD","Clipboard",""),
	# ]
	# type : EnumProperty(default="translate",name="Type",items= items)

	# def invoke(self, context, event):
	# 	bpy.context.window_manager.fileselect_add(self)
	# 	return {'RUNNING_MODAL'}

	def execute(self, context):
		prefs = preference()

		if self.type == "source":
			prefs.clipboard_source = bpy.context.window_manager.clipboard.replace("\n","|")
		elif self.type == "translate":
			prefs.clipboard_translate = bpy.context.window_manager.clipboard.replace("\n","|")

		self.report({'INFO'}, "Pasted")
		return{'FINISHED'}


#
class USERTRANSLATE_OT_open_folder(Operator):
	bl_idname = 'usertranslate.open_folder'
	bl_label = "Open Folder"
	bl_description = ""

	def execute(self, context):
		path = dict_dir(create=True)
		if os.name == 'nt':
			subprocess.Popen(["start", "", path], shell=True)
		else:
			subprocess.Popen(["open", "", path], shell=True)

		return{'FINISHED'}


class USERTRANSLATE_OT_copy_bundled_dicts(Operator):
	bl_idname = 'usertranslate.copy_bundled_dicts'
	bl_label = "复制随包词典到自定义目录"
	bl_description = "把插件自带的词典复制到上面指定的词典目录（已存在的文件不覆盖）"

	def execute(self, context):
		import shutil

		src = bundled_dict_dir()
		dst = dict_dir(create=True)
		if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dst)):
			self.report({'WARNING'}, "当前用的就是插件自带目录，无需复制")
			return {'CANCELLED'}

		copied = 0
		for path in glob.glob(os.path.join(src, "*.csv")):
			target = os.path.join(dst, os.path.basename(path))
			if os.path.exists(target):
				continue
			try:
				shutil.copy2(path, target)
				copied += 1
			except Exception as exc:
				print("[user_translate] copy failed:", path, exc)

		re_register_files(None, context)
		self.report({'INFO'}, "已复制 %d 份词典到 %s" % (copied, dst))
		return{'FINISHED'}


#
class USERTRANSLATE_OT_combine_src_and_tras_text(Operator):
	bl_idname = 'usertranslate.combine_src_and_tras_text'
	bl_label = "Combine source & translation to create file"
	bl_description = "Combine the source text and the translated text and save it as a .csv file in the user_files folder"

	def execute(self, context):
		prefs = preference()
		# テキスト内改行は仮に ^^ とし、実際の改行は | にする
		# |だとGoogle翻訳が、翻訳時に勝手に|を除去してしまう
		# "hoge\nhoge\nhuga\nmoga\n"
		# "hoge^^hoge|\nhuga\nmoga|\n"
		# "hoge^^hoge, huga, moga"

		# with open(prefs.translated_text_file) as f:
		# 	source_l = f.readlines()
		source_l = prefs.clipboard_source.replace("|\n","|").split("|")
		translated_l = prefs.clipboard_translate.replace("|\n","|").split("|")

		conv_l = []
		for i,line in enumerate(source_l):
			if len(translated_l)-1 < i:
				break
			conv_l += [
				"\"%s\",\"%s\"" % (translated_l[i].replace("^^","\n"),
				line.replace("^^","\n"))
				]


		save_path = os.path.join(os.path.dirname(__file__),"user_files", prefs.target_filename)
		with codecs.open(save_path, mode='w', encoding='utf-8') as f:
			f.write('\n'.join(conv_l))

		re_register_files(None,context)
		self.report({'INFO'}, "Save [%s] lines to user_file/[%s]" % (str(len(conv_l)),prefs.target_filename))

		return{'FINISHED'}


# class USERTRANSLATE_OT_file_extract_text(Operator, ImportHelper):
class USERTRANSLATE_OT_file_extract_text(Operator):
	bl_idname = 'usertranslate.file_extract_text'
	bl_label = "Extract text from .py file"
	bl_description = "Extract all text elements from the add-on's .py file\n(search for bl_label, bl_description, name, description, text)\nIn the case of a folder, search the .py file to a deeper folder"

	# filename_ext = ".py"
	# filter_glob : StringProperty( default="*.py", options={'HIDDEN'}, )
	process_text : BoolProperty(name="Process for translated text",default=True)
	create_csv_file : BoolProperty(name="Create File(Overwrite)",default=True)
	# use_filter_folder = True
	# dirpath :  StringProperty(type='DIR_PATH')
	is_dir : BoolProperty()
	filepath : StringProperty()
	directory : StringProperty(
		name="Outdir Path",
		description="Where I will save my stuff"
		# subtype='DIR_PATH' is not needed to specify the selection mode.
		# But this will be anyway a directory path.
		)
	#
	# items = [
	# ("NO_EXPORT_FILE","No Export File",""),
	# ("CSV","csv",""),
	# ("TXT","txt",""),
	# ]
	# ext_type : EnumProperty(default="TXT",name="Ext Type",items= items)


	def invoke(self, context, event):
		bpy.context.window_manager.fileselect_add(self)
		return {'RUNNING_MODAL'}


	def execute(self, context):
		prefs = preference()
		# if self.ext_type == "CSV":
		#     tgt_ext = ".csv"
		# elif self.ext_type == "TXT":
		#     tgt_ext = ".txt"

		if self.is_dir:
			# print(self.directory)
			# self.directory = "C:\\Program Files\\blender-3.00\\3.0\\scripts\\addons\\amaranth\\"
			path_l = glob.glob(os.path.join(self.directory,"**","*.py"), recursive=True)
			# print(path_l)
			filename = os.path.basename(os.path.dirname(self.directory)) + ".csv"

		else:
			# print(self.filepath)
			# print(os.path.splitext(os.path.basename(self.filepath)))
			# self.filepath = r"C:\Program Files\blender-3.00\3.0\scripts\addons\node_wrangler.py"
			if not os.path.splitext(os.path.basename(self.filepath))[1] == ".py":
				self.report({'INFO'}, "No .py file")
				return {'CANCELLED'}

			path_l = [self.filepath]
			filename = os.path.splitext(os.path.basename(self.filepath))[0] + ".csv"


		# 検索パターンを作成
		text_l = ["bl_label","bl_description","name", "description", "text"]
		# pat = "\"\"\"(.*)\"\"\"|^(?!.*bl_idname).*$|"
		pat = "\"\"\"(.*)\"\"\"|"
		for t in text_l:
			pat += r"%s(\s|)=(\s|)(\"|')(.*?)(\"|')|" % t
			# pat += "%s=\"(.+)\"|" % t
			# pat += "%s='(.+)'|" % t
			# pat += "%s = '(.+)'|" % t
			# pat += "%s = \"(.+)\"|" % t


		pat = pat[:-1]
		get_text_l = []
		clip_l = []

		# ファイル内を検索
		for path in path_l:
			print(os.path.basename(path))
			with open(path) as f:
				# Hard Opsアドオンのように""" """ で囲われたテキストを取得しようとしてみたが、コメントアウトでも使っているので却下
				# find_l = re.findall("\"\"\"(.*)\"\"\"",f.read(),flags=re.DOTALL)
				# for get_t in find_l:
				#     # for get_t in i:
				#     if not get_t:
				#         continue
				#     clip_l += [get_t.replace("\"","\\\"").replace("\n","^^")]
				#     if self.process_text:
				#         get_text_l += ["\"\",\"%s\"" % get_t.replace("\"","\\\"")]
				#     else:
				#         get_text_l += [get_t.replace("\"","\\\"")]
				try:
					for line in f.readlines():
						if [i for i in ["    bl_idname","\tbl_idname","    bl_idname"] if i in line]:
							continue
						if re.findall("^#.*$",line):
							continue
						find_l = re.findall(pat,line)
						for i in find_l:
							for get_t in i:
								if not get_t:
									continue
								# 改行は内部的な代用文字として^^にする
								clip_l += [get_t.replace("\"","\\\"").replace("\n","^^")]
								if self.process_text:
									get_text_l += ["\"\",\"%s\"" % get_t.replace("\"","\\\"")]
								else:
									get_text_l += [get_t.replace("\"","\\\"")]

				except UnicodeDecodeError:
					pass

		if not get_text_l:
			self.report({'WARNING'}, "No Target Text")
			return {'CANCELLED'}



		# 保存
		if self.create_csv_file:
			get_text_l = [i for i in  get_text_l if not i in {"","\n"," ","'","\\\""}]
			get_text_l = sorted(set(get_text_l), key=get_text_l.index)

		clip_l = [i for i in  clip_l if not i in {"","\n"," ","'","\\\""}]
		clip_l = sorted(set(clip_l), key=clip_l.index)


		clip_text_sep = "|\n".join(clip_l)
		prefs.target_filename = filename
		prefs.clipboard_source = clip_text_sep
		bpy.context.window_manager.clipboard = "\n".join(clip_l)

		if self.create_csv_file:
			save_path = os.path.join(os.path.dirname(__file__),"user_files", filename)
			with codecs.open(save_path, mode='w', encoding='utf-8') as f:
				f.write('\n'.join(get_text_l))

			self.report({'INFO'}, "Save [%s] lines to user_file/[%s] and Clipboard" % (str(len(get_text_l)),filename))
		else:
			self.report({'INFO'}, "Save [%s] lines to Clipboard" % (str(len(get_text_l))))

		return{'FINISHED'}
