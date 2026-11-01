import bpy
import codecs
import csv
from bl_i18n_utils.settings import LANGUAGES


def read_csv_rows(path, limit=None):
    """Read a dictionary CSV, tolerating the legacy GBK files.

    The original tool wrote files with the platform default encoding on some
    systems, so a few dictionaries on disk are not UTF-8. Falling back keeps
    those files usable instead of aborting the whole registration.
    """
    for encoding in ("utf-8", "gbk"):
        try:
            with codecs.open(path, "r", encoding) as handle:
                rows = list(csv.reader(handle))
            return rows[:limit] if limit else rows
        except Exception:
            continue
    return []


def preference():
    preference = bpy.context.preferences.addons[__name__.partition('.')[0]].preferences
    return preference



#
language_items_old = [
('', 'ab', 'description', 'None', 0) ,
("en_US","en_US",""),
("es","es",""),
("ja_JP","ja_JP",""),
("sk_SK","sk_SK",""),
("vi_VN","vi_VN",""),
("zh_CN","zh_CN",""),
("ar_EG","ar_EG",""),
("cs_CZ","cs_CZ",""),
("de_DE","de_DE",""),
("fr_FR","fr_FR",""),
("it_IT","it_IT",""),
("ko_KR","ko_KR",""),
("pt_BR","pt_BR",""),
("pt_PT","pt_PT",""),
("ru_RU","ru_RU",""),
("uk_UA","uk_UA",""),
("zh_TW","zh_TW",""),
("ab","ab",""),
("ca_AD","ca_AD",""),
("eo","eo",""),
("eu_EU","eu_EU",""),
("fa_IR","fa_IR",""),
("ha","ha",""),
("he_IL","he_IL",""),
("hi_IN","hi_IN",""),
("hr_HR","hr_HR",""),
("hu_HU","hu_HU",""),
("id_ID","id_ID",""),
("ky_KG","ky_KG",""),
("nl_NL","nl_NL",""),
("pl_PL","pl_PL",""),
("sr_RS","sr_RS",""),
("sr_RS@latin","sr_RS",""),
("sv_SE","sv_SE",""),
("th_TH","th_TH",""),
("tr_TR","tr_TR",""),
]

language_items_V400 = [
('en_US', 'English (English)', ''),
('ja_JP', 'Japanese (日本語)', ''),
('nl_NL', 'Dutch (Nederlands)', ''),
('it_IT', 'Italian (Italiano)', ''),
('de_DE', 'German (Deutsch)', ''),
('fi_FI', 'Finnish (Suomi)', ''),
('sv_SE', 'Swedish (Svenska)', ''),
('fr_FR', 'French (Français)', ''),
('es', 'Spanish (Español)', ''),
('ca_AD', 'Catalan (Català)', ''),
('cs_CZ', 'Czech (Čeština)', ''),
('pt_PT', 'Portuguese (Português)', ''),
('zh_HANS', 'Simplified Chinese (简体中文)', ''),
('zh_HANT', 'Traditional Chinese (繁體中文)', ''),
('ru_RU', 'Russian (Русский)', ''),
('hr_HR', 'Croatian (Hrvatski)', ''),
('sr_RS', 'Serbian (Српски)', ''),
('uk_UA', 'Ukrainian (Українська)', ''),
('pl_PL', 'Polish (Polski)', ''),
('ro_RO', 'Romanian (Român)', ''),
('ar_EG', 'Arabic (ﺔﻴﺑﺮﻌﻟﺍ)', ''),
('bg_BG', 'Bulgarian (Български)', ''),
('el_GR', 'Greek (Ελληνικά)', ''),
('ko_KR', 'Korean (한국어)', ''),
('ne_NP', 'Nepali (नेपाली)', ''),
('fa_IR', 'Persian (ﯽﺳﺭﺎﻓ)', ''),
('id_ID', 'Indonesian (Bahasa indonesia)', ''),
('sr_RS@latin', 'Serbian Latin (Srpski latinica)', ''),
('ky_KG', 'Kyrgyz (Кыргыз тили)', ''),
('tr_TR', 'Turkish (Türkçe)', ''),
('hu_HU', 'Hungarian (Magyar)', ''),
('pt_BR', 'Brazilian Portuguese (Português do Brasil)', ''),
('he_IL', 'Hebrew (תירִבְעִ)', ''),
('et_EE', 'Estonian (Eesti keel)', ''),
('eo', 'Esperanto (Esperanto)', ''),
('am_ET', 'Amharic (አማርኛ)', ''),
('uz_UZ@latin', 'Uzbek (Oʻzbek)', ''),
('uz_UZ@cyrillic', 'Uzbek Cyrillic (Ўзбек)', ''),
('hi_IN', 'Hindi (हिन्दी)', ''),
('vi_VN', 'Vietnamese (Tiếng Việt)', ''),
('eu_EU', 'Basque (Euskara)', ''),
('ha', 'Hausa (Hausa)', ''),
('kk_KZ', 'Kazakh (Қазақша)', ''),
('ab', 'Abkhaz (Аԥсуа бызшәа)', ''),
('th_TH', 'Thai (ภาษาไทย)', ''),
('sk_SK', 'Slovak (Slovenčina)', ''),
('ka', 'Georgian (ქართული)', ''),
('ta', 'Tamil (தமிழ்)', ''),
('km', 'Khmer (ខ្មែរ)', ''),
('sw', 'Swahili (Kiswahili)', ''),
]


# うまく登録できないので未使用
def get_languages_enum(self,context):
    if bpy.app.version >= (4,0,0):
        # tgt_language_items = []
        # tgt_l = list(LANGUAGES)
        # for item in tgt_l:
        #     if item[2] == "DEFAULT":
        #         continue
        #     tgt_language_items += [(item[2], item[1], "")]
        #
        # tgt_language_items = [tgt_language_items]

        global language_items_V400
        tgt_language_items = language_items_V400

    else:
        global language_items_old
        tgt_language_items = language_items_old


    return tgt_language_items
