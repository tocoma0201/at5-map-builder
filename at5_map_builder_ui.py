#!/usr/bin/env python3
"""範囲を選び、AT5地図の作成を実行するローカルブラウザー画面。

Python標準ライブラリーで動作し、背景地図の表示にはブラウザーの通信を使う。
"""
from __future__ import annotations

import ctypes
import json
import locale
import os
import subprocess
import sys
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from configure_imc_raster_sap import find_raster_template

ROOT = Path(__file__).resolve().parent
BUILDER = ROOT / "build_at5_map.py"
DEFAULT_BBOX = [35.140, 139.130, 35.330, 139.590]
US_DEFAULT_BBOX = [38.900, -77.150, 39.100, -76.850]
STATE_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AT5MapBuilder"
STATE_FILE = STATE_DIR / "range-ui-state.json"
DEFAULT_COPY_TO = ""
DEFAULT_IMC_EXE = os.environ.get("AT5_IMC_EXE", "")
DEFAULT_BASE_MAP = "standard"
DEFAULT_ZOOM = 15
DEFAULT_LAKE_CONTOURS = False
# 画面表示の版番号をVERSIONファイルで一元管理する。
TOOL_VERSION = (ROOT / "VERSION").read_text(encoding="ascii").strip()


# 初回起動時だけ使うWindowsの地域と言語設定を取得する。
def windows_country_code():
    if os.name != "nt":
        current_locale = locale.getlocale()[0] or ""
        return current_locale.split("_")[-1].upper() if "_" in current_locale else ""
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_geo_name = kernel32.GetUserDefaultGeoName
        get_geo_name.argtypes = [ctypes.c_wchar_p, ctypes.c_int]
        get_geo_name.restype = ctypes.c_int
        buffer = ctypes.create_unicode_buffer(16)
        if get_geo_name(buffer, len(buffer)):
            return buffer.value.upper()
    except (AttributeError, OSError):
        pass
    return ""


def windows_default_language():
    if os.name != "nt":
        return "ja" if (locale.getlocale()[0] or "").lower().startswith("ja") else "en"
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_ui_language = kernel32.GetUserDefaultUILanguage
        get_ui_language.restype = ctypes.c_ushort
        primary_language = get_ui_language() & 0x03FF
        return "ja" if primary_language == 0x11 else "en"
    except (AttributeError, OSError):
        return "en"


def initial_region_defaults():
    country = windows_country_code()
    if country == "JP":
        return DEFAULT_BBOX, "standard"
    # 米国以外に対応地図がない初回は、USGSと米国内の初期範囲を使う。
    return US_DEFAULT_BBOX, "usgs_imagery"


DEFAULT_LANGUAGE = windows_default_language()

HTML = r"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lowrance魚群探知機用 AT5日本地図作成ツール</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
*{box-sizing:border-box} body{margin:0;font:15px system-ui,sans-serif;color:#18212b}
header{padding:10px 16px;background:#173c58;color:white;display:flex;justify-content:space-between;align-items:center;gap:16px} h1{font-size:19px;margin:0} .version{font-size:13px;color:#d8e7f1}.header-tools{display:flex;align-items:center;gap:12px}.header-tools label{display:inline;margin:0;color:white;font-size:13px}.header-tools select{width:auto;padding:4px 8px;font-size:13px}
main{display:grid;grid-template-columns:minmax(330px,390px) 1fr;min-height:calc(100vh - 48px)}
aside{padding:14px;border-right:1px solid #ccd4da;overflow:auto}
#map{height:calc(100vh - 48px);min-height:520px}
label{display:block;font-weight:600;margin:11px 0 4px}
input,textarea,button,select{font:inherit;padding:8px;border:1px solid #aab6bf;border-radius:5px;width:100%}
input[type=checkbox]{width:auto;vertical-align:middle;margin-right:6px}
textarea{height:62px;resize:vertical} button{cursor:pointer;background:#eef4f7} button:disabled{opacity:.55;cursor:not-allowed;background:#a9b4bb;color:#f7fafb;border-color:#a9b4bb}
.map-option{margin:8px 0}.map-option label{margin-top:8px}.map-option .note{margin:4px 0}
.path-picker{display:flex;gap:6px}.path-picker input{flex:1;min-width:0}.path-picker button{width:auto;white-space:nowrap}
.actions{display:flex;gap:8px;margin-top:8px}.actions button{flex:1}
.primary{background:#176b9b;color:white;border-color:#176b9b}
.good{background:#e8f6ec;color:#175b2b}
.warning{background:#fff0d9;color:#754500}
.note{font-size:13px;color:#52606b;line-height:1.45}
dialog{border:1px solid #aab6bf;border-radius:8px;width:min(480px,calc(100vw - 32px));padding:18px;box-shadow:0 12px 32px #0003}dialog::backdrop{background:#0006}dialog h2{margin:0 0 8px;font-size:19px}dialog .actions{margin-top:12px}
#status{white-space:pre-wrap;background:#f4f6f8;padding:9px;min-height:42px;margin-top:10px}
@media(max-width:800px){main{display:flex;flex-direction:column}aside{border:0}#map{height:55vh;min-height:380px}}
</style>
</head>
<body>
<header><h1 data-i18n="title">Lowrance魚群探知機用 AT5地図作成ツール</h1><div class="header-tools"><label for="language" data-i18n="languageLabel">Language</label><select id="language" aria-label="Language"><option value="en">English</option><option value="ja">日本語</option></select><span class="version">v__TOOL_VERSION__</span></div></header>
<main>
<aside>
<p class="note" data-i18n="mapInstructions">地図は通常ドラッグで移動できます。「範囲選択」をONにした間だけドラッグで範囲を囲めます。座標は「南 西 北 東」の順で入力します。最後に使った範囲は次回も保持されます。</p>
<button id="selectMode" data-i18n="selectOff">範囲選択: OFF（ドラッグで地図移動）</button>
<div class="map-option">
<label for="baseMap" data-i18n="baseMapLabel">背景地図</label>
<select id="baseMap">
<option value="standard" data-i18n="mapStandard">JP: 国土地理院 / 標準地図</option>
<option value="aerial" data-i18n="mapAerial">JP: 国土地理院 / 航空写真</option>
<option value="usgs_imagery" data-i18n="mapUsgs">US: USGS / 航空写真</option>
</select>
<label id="lakeContoursLabel" data-i18n-title="lakeContoursTip" title="オンにすると、国土地理院の湖沼図に収録されている湖の等深線が作成する地図に含まれます。湖沼図の等深線は背景地図に焼き込まれるため、魚探上で湖沼図の等深線だけを個別に表示・非表示にはできません。海や未調査の湖沼の等深線は含まれません。"><input id="lakeContours" type="checkbox"><span data-i18n="lakeContours">湖沼図（湖の等深線）を重ねる</span></label>
<label for="mapZoom" data-i18n="zoomLabel">出力ズームレベル</label>
<select id="mapZoom" data-i18n-title="zoomTip" title="ZLを1段上げると、地図の細かさ（地上解像度）は約2倍になります。同じ範囲で必要なタイル数・画像データ量は約4倍が目安です。完成容量は写真の内容や圧縮率で変わります。ブラウザーの表示倍率は変わりません。">
<option value="15">ZL 15</option>
<option value="16">ZL 16</option>
<option value="17">ZL 17</option>
</select>
<p class="note" data-i18n="mapAvailability">湖沼図は国土地理院が公開する調査済み湖沼の範囲で利用できます。航空写真・湖沼図の取得範囲は地図上で確認してください。</p>
</div>
<label for="bbox" data-i18n="bboxLabel">範囲（南, 西, 北, 東）</label>
<textarea id="bbox" spellcheck="false" placeholder="35.140, 139.130, 35.330, 139.590" data-i18n-title="bboxTip" title="南, 西, 北, 東の順に入力し、Enterで地図上の選択範囲へ反映します。"></textarea>
<div id="estimate" class="note"></div>
<label for="mapName" data-i18n="mapNameLabel">Ti2で選ぶ地図名／AT5先頭文字（任意）</label>
<input id="mapName" placeholder="例: Map01" data-i18n-placeholder="mapNamePlaceholder" maxlength="32">
<label for="copyTo" data-i18n="outputLabel">出力先フォルダー</label>
<div class="path-picker"><input id="copyTo" placeholder="例: F:\ShadedRelief" data-i18n-placeholder="outputPlaceholder" data-i18n-title="outputTip" title="SDカードに保存する場合は、カード直下の ShadedRelief フォルダーを指定してください。例：F:\ShadedRelief。PCに保存する場合は任意のフォルダーを指定できます。"><button id="browseOutput" type="button" data-i18n="browse">参照…</button></div>
<div class="actions"><button id="imcSettings" type="button" data-i18n="imcSettings">IMC設定</button><span id="imcStatus" class="note" data-i18n="checking">確認中…</span></div>
<dialog id="imcDialog">
<h2 data-i18n="imcDialogTitle">IMCの場所を設定</h2>
<p class="note" data-i18n="imcHelp">「参照…」からInsightMapCreator.exeを選ぶか、エクスプローラーでコピーしたパスを貼り付けてください。Raster Mode設定はmapcreator.zip内のSample ZIPから自動取得するため、追加展開は不要です。設定はこのPCに保存され、「IMC設定」からいつでも変更できます。</p>
<label for="imcPath" data-i18n="imcPathLabel">InsightMapCreator.exeのパス</label>
<div class="path-picker"><input id="imcPath" placeholder="例: C:\Users\名前\Documents\AT5MapBuilder\IMC\InsightMapCreator.exe" data-i18n-placeholder="imcPathPlaceholder"><button id="browseImc" type="button" data-i18n="browse">参照…</button></div>
<p id="imcPathError" class="note warning"></p>
<div class="actions"><button id="cancelImc" type="button" data-i18n="cancel">キャンセル</button><button id="saveImc" type="button" class="primary" data-i18n="save">保存</button></div>
</dialog>


<p class="note" data-i18n="buildNotes">生成条件：Min 1〜Max 8192 / Filter Alpha 0。容量1,000 MB・タイル数1,000枚は目安です。超えても警告のみで作成を続けます。名前を入力すると、AT5ファイル名の先頭とTi2のChart sourceに使われます。</p>
<label for="command" data-i18n="commandLabel">PowerShellコマンド（編集できます）</label>
<textarea id="command" rows="4" spellcheck="false"></textarea>
<button id="runPowerShell" class="primary" data-i18n="runPowerShell">PowerShellで実行</button>
<div id="status" data-i18n="starting">起動しています…</div>
<p class="note" data-i18n="windowsOnly">本ツールはWindows専用です。実行状況と詳細はPowerShellで確認できます。</p>
</aside>
<div id="map"></div>
</main>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
// 範囲入力と地図描画の連携を行うクライアント側処理。
// 翻訳を言語ごとに集約し、対応言語を増やす場合はここへ辞書を追加する。
const messages={
 ja:{title:'Lowrance魚群探知機用 AT5地図作成ツール',languageLabel:'Language',mapInstructions:'地図は通常ドラッグで移動できます。「範囲選択」をONにした間だけドラッグで範囲を囲めます。座標は「南 西 北 東」の順で入力します。最後に使った範囲は次回も保持されます。',selectOff:'範囲選択: OFF（ドラッグで地図移動）',selectOn:'範囲選択: ON（ドラッグで範囲指定）',baseMapLabel:'背景地図',mapStandard:'JP: 国土地理院 / 標準地図',mapAerial:'JP: 国土地理院 / 航空写真',mapUsgs:'US: USGS / 航空写真',lakeContours:'湖沼図（湖の等深線）を重ねる',lakeContoursTip:'このチェックボックスを入れると、湖沼図の等深線が作成する地図に含まれます。魚探上で湖沼図の等深線だけを個別に表示・非表示にはできません。海や未調査の湖沼の等深線は含まれません。',zoomLabel:'出力ズームレベル',zoomTip:'ZLを1段上げると、地図の細かさ（地上解像度）は約2倍になります。同じ範囲で必要なタイル数・画像データ量は約4倍が目安です。完成容量は写真の内容や圧縮率で変わります。ブラウザーの表示倍率は変わりません。',mapAvailability:'湖沼図は国土地理院が公開する調査済み湖沼の範囲で利用できます。航空写真・湖沼図の取得範囲は地図上で確認してください。',bboxLabel:'範囲（南, 西, 北, 東）',bboxTip:'南, 西, 北, 東の順に入力し、Enterで地図上の選択範囲へ反映します。',mapNameLabel:'Ti2で選ぶ地図名／AT5先頭文字（任意）',outputLabel:'出力先フォルダー',outputTip:'SDカードに保存する場合は、カード直下の ShadedRelief フォルダーを指定してください。PCに保存する場合は任意のフォルダーを指定できます。',browse:'参照…',imcSettings:'IMC設定',checking:'確認中…',imcDialogTitle:'IMCの場所を設定',imcHelp:'「参照…」からInsightMapCreator.exeを選ぶか、エクスプローラーでコピーしたパスを貼り付けてください。Raster Mode設定はmapcreator.zip内のSample ZIPから自動取得します。設定はこのPCに保存され、「IMC設定」からいつでも変更できます。',imcPathLabel:'InsightMapCreator.exeのパス',cancel:'キャンセル',save:'保存',buildNotes:'生成条件：Min 1〜Max 8192 / Filter Alpha 0。容量1,000 MB・タイル数1,000枚は目安です。超えても警告のみで作成を続けます。名前を入力すると、AT5ファイル名の先頭とTi2のChart sourceに使われます。',commandLabel:'PowerShellコマンド（編集できます）',runPowerShell:'PowerShellで実行',starting:'起動しています…',windowsOnly:'本ツールはWindows専用です。画面表示は日本語・英語を選べます。ビルドスクリプトのターミナル出力は日本語です。',rangeInvalid:'範囲の数値が不正です。南 西 北 東の順に入力してください。',rangeUpdated:'範囲を更新しました。',estimate:(a,z,m,b,w)=>`範囲面積 約${a} km² / ZL${z}のAT5概算 約${m} MiB（${b} MB）。目安は1,000 MB以内。実サイズは地図の内容や圧縮率で変わります。${w?' 米国本土以外を含む範囲です。USGS航空写真は地域によって高解像度タイルがなく、Buildが失敗する場合があります。':''}`,zoomUsgsTip:' USGS航空写真はZL16までです。ZL17のタイルを取得できない地域があるため選択できません。',outsideUsWarning:'米国本土以外を含む範囲です。USGS航空写真は地域によって高解像度タイルがなく、Buildが失敗する場合があります。',imcValid:'IMC設定済み',imcMissing:'IMC設定を確認してください',imcUnset:'IMC未設定',rangeLoaded:'範囲を読み込みました。地図はドラッグで移動できます。',defaultRange:'既定の範囲を表示しています。',bboxError:'先に正しい範囲を指定してください。',outputMissing:'出力先パスを入力してください。',nameError:'AT5名の先頭文字は半角英数字とハイフンで入力してください。',commandError:'PowerShellコマンドを確認してください。',buildRunning:'Buildを実行中です。詳細はPowerShellで確認できます。',buildDone:'Buildが完了しました。PowerShellで結果を確認できます。',buildFailed:'Buildに失敗しました。PowerShellで詳細を確認してください。',buildEnded:'処理が終了しました。ログを確認してください。',imcPathRequired:'InsightMapCreator.exeのパスを入力してください。',imcChecking:'IMCと付属設定を確認しています…',imcSaved:'IMCの場所を保存しました。',rangeBad:'bboxは南・西・北・東の4数値で指定してください。'},
 en:{title:'AT5 Map Builder for Lowrance Fish Finders',languageLabel:'Language',mapInstructions:'Drag the map to move it. Turn on “Select area” to draw a map area by dragging. Enter coordinates in south, west, north, east order. The last area is restored next time.',selectOff:'Select area: OFF (drag to move map)',selectOn:'Select area: ON (drag to select area)',baseMapLabel:'Base map',mapStandard:'JP: GSI / Standard map',mapAerial:'JP: GSI / Aerial imagery',mapUsgs:'US: USGS / Aerial imagery',lakeContours:'Overlay lake depth contours',lakeContoursTip:'When checked, lake depth contours from GSI lake maps are included in the generated map. They are baked into the map and cannot be toggled independently on the fish finder. Sea contours and unsurveyed lakes are not included.',zoomLabel:'Output zoom level',zoomTip:'Increasing ZL by one doubles ground detail (resolution). For the same area, tile count and image data are roughly four times larger. Final size depends on image content and compression. This does not change the browser zoom.',mapAvailability:'GSI lake maps are available only for surveyed lakes published by GSI. Check the map to see aerial imagery and lake-map coverage.',bboxLabel:'Area (south, west, north, east)',bboxTip:'Enter coordinates in south, west, north, east order. Press Enter to update the selected map area.',mapNameLabel:'Map name on Ti2 / AT5 filename prefix (optional)',outputLabel:'Output folder',outputTip:'For an SD card, select the ShadedRelief folder at the card root. You can choose any folder on your PC.',browse:'Browse...',imcSettings:'IMC settings',checking:'Checking...',imcDialogTitle:'Set IMC location',imcHelp:'Select InsightMapCreator.exe with Browse... or paste its path from File Explorer. Raster Mode settings are found automatically in the Sample ZIP inside mapcreator.zip. The setting is saved on this PC and can be changed here at any time.',imcPathLabel:'InsightMapCreator.exe path',cancel:'Cancel',save:'Save',buildNotes:'Build settings: Min 1 to Max 8192 / Filter Alpha 0. The 1,000 MB and 1,000 tile figures are guidelines; exceeding them shows a warning but does not stop the build. The name is used as the AT5 filename prefix and Ti2 Chart source.',commandLabel:'PowerShell command (editable)',runPowerShell:'Run in PowerShell',starting:'Starting...',windowsOnly:'This tool runs on Windows only. The UI is available in Japanese and English. Build script output in the terminal remains Japanese.',rangeInvalid:'Invalid area coordinates. Enter south, west, north, east.',rangeUpdated:'Area updated.',estimate:(a,z,m,b,w)=>`Area: about ${a} km² / Estimated AT5 size at ZL${z}: about ${m} MiB (${b} MB). Aim for 1,000 MB or less. Actual size varies with map content and compression.${w?' This area includes locations outside the contiguous United States. High-resolution USGS imagery may be unavailable and the build may fail.':''}`,zoomUsgsTip:' USGS imagery supports up to ZL16. ZL17 is unavailable because tiles may not exist in some areas.',outsideUsWarning:'This area includes locations outside the contiguous United States. High-resolution USGS imagery may be unavailable and the build may fail.',imcValid:'IMC configured',imcMissing:'Check IMC settings',imcUnset:'IMC not configured',rangeLoaded:'Area loaded. Drag the map to move it.',defaultRange:'Showing the default area.',bboxError:'Enter a valid area first.',outputMissing:'Enter an output folder.',nameError:'Use ASCII letters, numbers, and hyphens for the AT5 name prefix.',commandError:'Check the PowerShell command.',buildRunning:'Build is running. See PowerShell for details.',buildDone:'Build completed. Check the result in PowerShell.',buildFailed:'Build failed. See PowerShell for details.',buildEnded:'Process ended. Check the log.',imcPathRequired:'Enter the path to InsightMapCreator.exe.',imcChecking:'Checking IMC and its settings...',imcSaved:'IMC location saved.',rangeBad:'Enter four numeric coordinates in south, west, north, east order.'}
};
Object.assign(messages.ja,{folderPickerError:'フォルダー選択画面を開けません',filePickerError:'ファイル選択画面を開けません',outputSaved:'出力先フォルダーを設定しました。',imcSetError:'IMCを設定できません',powershellError:'PowerShellを起動できません',mapNamePlaceholder:'例: Map01',outputPlaceholder:'例: F:\\ShadedRelief',imcPathPlaceholder:'例: C:\\Users\\Name\\Documents\\AT5MapBuilder\\IMC\\InsightMapCreator.exe'});
Object.assign(messages.en,{folderPickerError:'Could not open the folder picker.',filePickerError:'Could not open the file picker.',outputSaved:'Output folder set.',imcSetError:'Could not configure IMC.',powershellError:'Could not start PowerShell.',mapNamePlaceholder:'Example: Map01',outputPlaceholder:'Example: F:\\ShadedRelief',imcPathPlaceholder:'Example: C:\\Users\\Name\\Documents\\AT5MapBuilder\\IMC\\InsightMapCreator.exe'});
let language=__DEFAULT_LANGUAGE_JSON__;
const languageBox=document.getElementById('language');
function t(key,...args){const value=messages[language]?.[key]??messages.en[key]??key;return typeof value==='function'?value(...args):value}
function applyLanguage(){document.documentElement.lang=language;document.querySelectorAll('[data-i18n]').forEach(el=>el.textContent=t(el.dataset.i18n));document.querySelectorAll('[data-i18n-title]').forEach(el=>el.title=t(el.dataset.i18nTitle));document.querySelectorAll('[data-i18n-placeholder]').forEach(el=>el.placeholder=t(el.dataset.i18nPlaceholder));languageBox.value=language;refreshMapLayers();updateEstimate();}
const pythonExecutable = __PYTHON_EXECUTABLE_JSON__;
const toolRoot = __TOOL_ROOT_JSON__;
const commandBox = document.getElementById('command');
const map=L.map('map').setView([35.24,139.36],10);
const baseMapBox=document.getElementById('baseMap');
const lakeContoursBox=document.getElementById('lakeContours');
const mapZoomBox=document.getElementById('mapZoom');
let baseTileLayer=null, aerialTileLayer=null, lakeContourLayer=null;
function refreshMapLayers(){
 if(baseTileLayer)map.removeLayer(baseTileLayer);
 if(aerialTileLayer)map.removeLayer(aerialTileLayer);
 if(lakeContourLayer)map.removeLayer(lakeContourLayer);
 const selected=baseMapBox.value;
 const zoom17Option=mapZoomBox.querySelector('option[value="17"]');
 if(zoom17Option)zoom17Option.disabled=selected==='usgs_imagery';
 if(selected==='usgs_imagery'&&mapZoomBox.value==='17')mapZoomBox.value='16';
 mapZoomBox.title=t('zoomTip')+(selected==='usgs_imagery'?t('zoomUsgsTip'):'');
 if(selected==='usgs_imagery'){
  // USGSキャッシュはArcGISの行・列順で指定し、画像のネイティブ詳細はZL16まで表示する。
  baseTileLayer=L.tileLayer('https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}',{
   minZoom:0,maxZoom:18,maxNativeZoom:16,
   attribution:'USDA, USGS The National Map: Orthoimagery'
  }).addTo(map);
 }else{
  const standardUrl='https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png';
  baseTileLayer=L.tileLayer(standardUrl,{minZoom:5,maxZoom:18,
   attribution:'地理院タイル（標準地図） | 国土地理院'}).addTo(map);
  if(selected==='aerial'){
   aerialTileLayer=L.tileLayer('https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg',{
    minZoom:14,maxZoom:18,
    attribution:'地理院タイル（全国最新写真・シームレス） | 国土地理院'
   }).addTo(map);
  }
 }
 if(lakeContoursBox.checked){
  lakeContourLayer=L.tileLayer('https://cyberjapandata.gsi.go.jp/xyz/lake1/{z}/{x}/{y}.png',{
   minZoom:11,maxZoom:17,opacity:0.9,
   attribution:'地理院タイル（湖沼図） | 国土地理院'
  }).addTo(map);
 }
 if(lakeContoursBox.checked&&map.getZoom()>17)map.setZoom(17);
}
let rect=null, dragStart=null, dragEnd=null, bbox=null, running=false, selectMode=false;
const box=document.getElementById('bbox'), copyTo=document.getElementById('copyTo'), mapName=document.getElementById('mapName');
const imcDialog=document.getElementById('imcDialog'), imcPath=document.getElementById('imcPath');
const imcStatus=document.getElementById('imcStatus'), imcPathError=document.getElementById('imcPathError');
let imcExePath='', imcTemplatePath='';
imcPath.addEventListener('paste',e=>{
 const pasted=e.clipboardData?.getData('text/plain');
 if(!pasted)return;
 const trimmed=pasted.trim();
 const clean=trimmed.length>=2&&trimmed.startsWith('"')&&trimmed.endsWith('"')?trimmed.slice(1,-1):pasted;
 if(clean!==pasted){e.preventDefault();const start=imcPath.selectionStart,end=imcPath.selectionEnd;imcPath.setRangeText(clean,start,end,'end');imcPath.dispatchEvent(new Event('input',{bubbles:true}))}
});

// 緯度経度の順序と大小関係を画面側で先に確認する。
function valid(a){return a.length===4&&a.every(Number.isFinite)&&a[0]<a[2]&&a[1]<a[3]&&a[0]>=-90&&a[2]<=90&&a[1]>=-180&&a[3]<=180}
// 座標欄、赤い矩形、概算値、コマンドを同じ範囲に揃える。
function setBox(a,save=true,fitMap=false){
 if(!valid(a)){status(t('rangeInvalid'));return}
 bbox=a.map(Number); box.value=bbox.map(x=>x.toFixed(6)).join(', ');
 status(t('rangeUpdated'));
 const bounds=[[bbox[0],bbox[1]],[bbox[2],bbox[3]]];
 if(rect)rect.setBounds(bounds);else rect=L.rectangle(bounds,{color:'#d23636',weight:2,fillOpacity:.10}).addTo(map);
 if(fitMap)map.fitBounds(bounds,{padding:[12,12]}); updateCommand(); updateEstimate();
 if(save) persist();
}
function parseBox(s){const parts=s.trim().split(/[\s,，]+/).filter(Boolean);if(parts.length!==4)return [];return parts.map(Number)}
function status(s,force=false){if(running&&!force)return;document.getElementById('status').textContent=s}
function outputTag(a){return a.map(x=>(x<0?'m':'p')+String(Math.round(Math.abs(x)*1000000)).padStart(9,'0')).join('-')}
function outputDirectory(a){
 const source=baseMapBox.value+(lakeContoursBox.checked?'-lake':'')+'-z'+mapZoomBox.value;
 return 'map-ui-'+source+'-'+outputTag(a);
}
function areaKm2(a){const r=6371,rad=Math.PI/180;return r*r*(a[3]-a[1])*rad*(Math.sin(a[2]*rad)-Math.sin(a[0]*rad))}
// 試験済み範囲の実測値を基準に、面積比で容量を概算する。
function updateEstimate(){
 if(!bbox)return;
 const reference=areaKm2([35.140,139.130,35.330,139.590]);
 const zoom=Number(mapZoomBox.value);
 const zoomFactor=4**(zoom-15);
 const mib=Math.round(870*areaKm2(bbox)/reference*zoomFactor), mb=Math.round(mib*1.048576);
 const el=document.getElementById('estimate');
 const outsideUsMainland=baseMapBox.value==='usgs_imagery'&&
  (bbox[0]<24||bbox[2]>50||bbox[1]<-125||bbox[3]>-66);
 el.className='note '+(outsideUsMainland||mb>1000?'warning':'good');
 el.textContent=t('estimate',Math.round(areaKm2(bbox)),zoom,mib,mb,outsideUsMainland);
}
// 現在の入力値からPowerShellコマンド欄を再生成する。
function updateCommand(){
 const a=parseBox(box.value),dest=copyTo.value.trim(),name=mapName.value.trim();
 if(!valid(a)||!dest||!imcExePath||!imcTemplatePath){commandBox.value='';return}
 const q=v=>"'"+String(v).replace(/'/g,"''")+"'";
 const args=[pythonExecutable,toolRoot.replace(/\\/g,'/')+'/build_at5_map.py',
  '--bbox',...a.map(v=>String(Number(v).toFixed(6))),
  '--imc-exe',imcExePath,'--template-sap',imcTemplatePath,
  '--base-map',baseMapBox.value,'--zoom',mapZoomBox.value,
  '--output-dir',outputDirectory(a),
  '--min-resolution','1','--max-resolution','8192','--filter-alpha','0','--copy-to',dest];
 if(lakeContoursBox.checked)args.push('--lake-contours');
 if(name)args.push('--at5-prefix',name);
 commandBox.value="Set-Location -LiteralPath "+q(toolRoot)+"; & "+args.map(q).join(' ')+
  "; if ($LASTEXITCODE -ne 0) { Write-Host ('Build failed: ' + $LASTEXITCODE) -ForegroundColor Red }";
}
async function persist(){
 try{await fetch('/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({bbox,copyTo:copyTo.value.trim(),at5Prefix:mapName.value.trim(),imcExe:imcExePath,templateSap:imcTemplatePath,baseMap:baseMapBox.value,zoom:Number(mapZoomBox.value),lakeContours:lakeContoursBox.checked,language})})}catch(e){}
}
languageBox.onchange=async()=>{language=languageBox.value==='ja'?'ja':'en';applyLanguage();status(t('rangeUpdated'));await persist()};
// Enter確定時に入力範囲を地図へ反映する。Shift+Enterは改行。
box.addEventListener('keydown',e=>{
 if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();setBox(parseBox(box.value),true,true)}
});
copyTo.onchange=()=>{updateCommand();persist()};
document.getElementById('browseOutput').onclick=async()=>{
 try{
  const r=await fetch('/select-output-dir',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({initialDir:copyTo.value.trim()})});
  const j=await r.json();if(!r.ok)throw Error(j.error||t('folderPickerError'));
  if(j.path){copyTo.value=j.path;updateCommand();await persist();status(t('outputSaved'))}
 }catch(e){status(String(e))}
};
mapName.oninput=()=>{updateCommand();persist()};
baseMapBox.onchange=()=>{refreshMapLayers();updateCommand();updateEstimate();persist()};
lakeContoursBox.onchange=()=>{refreshMapLayers();updateCommand();persist()};
mapZoomBox.onchange=()=>{refreshMapLayers();updateCommand();updateEstimate();persist()};
refreshMapLayers();
document.getElementById('imcSettings').onclick=()=>{imcPath.value=imcExePath;imcPathError.textContent='';imcDialog.showModal()};
document.getElementById('browseImc').onclick=async()=>{
 try{
  const r=await fetch('/select-imc-exe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({initialPath:imcPath.value.trim()||imcExePath})});
  const j=await r.json();if(!r.ok)throw Error(j.error||t('filePickerError'));
  if(j.path){imcPath.value=j.path;imcPathError.textContent='';}
 }catch(e){imcPathError.textContent=String(e)}
};
document.getElementById('cancelImc').onclick=()=>imcDialog.close();
document.getElementById('saveImc').onclick=async()=>{
 const path=imcPath.value.trim();
 if(!path){imcPathError.textContent=t('imcPathRequired');return}
 const button=document.getElementById('saveImc');button.disabled=true;imcPathError.textContent=t('imcChecking');
 try{
  const r=await fetch('/imc-settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({imcExe:path})});
  const j=await r.json();if(!r.ok)throw Error(j.error||t('imcSetError'));
  imcExePath=j.imcExe;imcTemplatePath=j.templateSap||'';imcStatus.textContent=t('imcValid');imcDialog.close();await persist();updateCommand();status(t('imcSaved'));
 }catch(e){imcPathError.textContent=String(e)}
 finally{button.disabled=false}
};
document.getElementById('selectMode').onclick=e=>{selectMode=!selectMode;e.currentTarget.textContent=t(selectMode?'selectOn':'selectOff');e.currentTarget.classList.toggle('primary',selectMode);map.dragging[selectMode?'disable':'enable']()};
// 範囲選択中だけ、地図ドラッグを矩形指定として扱う。
map.on('mousedown',e=>{if(!selectMode||e.originalEvent.button!==0)return;dragStart=e.latlng;dragEnd=e.latlng;if(rect)map.removeLayer(rect);rect=L.rectangle([dragStart,dragStart],{color:'#d23636',weight:2,fillOpacity:.10}).addTo(map)});
map.on('mousemove',e=>{if(dragStart&&rect){dragEnd=e.latlng;rect.setBounds(L.latLngBounds(dragStart,dragEnd))}});
function finishRange(end){
 if(!dragStart)return;
 const start=dragStart;dragStart=null;dragEnd=null;
 const bounds=L.latLngBounds(start,end),sw=bounds.getSouthWest(),ne=bounds.getNorthEast();
 if(sw.lat===ne.lat||sw.lng===ne.lng)return;
 setBox([sw.lat,sw.lng,ne.lat,ne.lng]);
}
// 範囲選択はLeafletが変換した座標を使い、画面表示と入力座標のずれを防ぐ。
map.on('mouseup',e=>finishRange(e.latlng));
// 地図の外でマウスを離した場合は、地図内で最後に取得した地点を範囲の終点にする。
document.addEventListener('mouseup',()=>{if(dragStart)finishRange(dragEnd||dragStart)});
// 必須項目を確認してから、ローカルサーバー経由でPowerShellを起動する。
document.getElementById('runPowerShell').onclick=async()=>{
 if(running)return;
 const a=parseBox(box.value),dest=copyTo.value.trim(),name=mapName.value.trim(),imc=imcExePath,command=commandBox.value.trim();
 if(!valid(a)){status(t('bboxError'));return}
 if(!dest){status(t('outputMissing'));return}
 if(!imc){imcDialog.showModal();return}
 if(name&&!/^[A-Za-z0-9-]{1,32}$/.test(name)){status(t('nameError'));return}
 if(!command){status(t('commandError'));return}
 try{const r=await fetch('/powershell',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({bbox:a,copyTo:dest,at5Prefix:name,imcExe:imc,command,baseMap:baseMapBox.value,zoom:Number(mapZoomBox.value),lakeContours:lakeContoursBox.checked,language})});const j=await r.json();if(!r.ok)throw Error(j.error||t('powershellError'));await persist();running=true;document.getElementById('runPowerShell').disabled=true;status(t('buildRunning'));poll()}catch(e){status(String(e))}
};
async function poll(){
 try{const r=await fetch('/log');const j=await r.json();
 if(j.running){setTimeout(poll,1200)}else{running=false;document.getElementById('runPowerShell').disabled=false;status(j.resultKey?t(j.resultKey):t('buildEnded'))}
 }catch(e){setTimeout(poll,2000)}
}
(async()=>{try{const s=await (await fetch('/state')).json();language=s.language==='ja'||s.language==='en'?s.language:__DEFAULT_LANGUAGE_JSON__;applyLanguage();copyTo.value=s.copyTo||copyTo.value;mapName.value=s.at5Prefix||'';baseMapBox.value=s.baseMap||'standard';mapZoomBox.value=String(s.zoom||15);lakeContoursBox.checked=Boolean(s.lakeContours);refreshMapLayers();imcExePath=s.imcExe||'';imcTemplatePath=s.templateSap||'';imcStatus.textContent=s.imcValid?t('imcValid'):t('imcMissing');setBox(s.bbox||[35.140,139.130,35.330,139.590],false,true);status(t('rangeLoaded'));if(!s.imcValid)imcDialog.showModal()}catch(e){language=__DEFAULT_LANGUAGE_JSON__;applyLanguage();setBox([35.140,139.130,35.330,139.590],false,true);imcStatus.textContent=t('imcUnset');imcDialog.showModal();status(t('defaultRange'))}})();
async function restoreBuildStatus(){
 try{
  const j=await (await fetch('/log')).json();
  if(j.running){
   running=true;
   document.getElementById('runPowerShell').disabled=true;
   status(t('buildRunning'),true);
   poll();
  }
 }catch(e){}
}
restoreBuildStatus();
</script>
</body>
</html>
"""

# UIとビルドの状態をまとめて管理する。
class AppState:
    # 実行状態、ログ、排他制御用ロックを初期化する。
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.log = ""
        self.result = ""
        self.run_id = None

    # 前回の入力値を設定ファイルから読み込み、未設定項目は既定値で補う。
    def read_saved(self):
        default_bbox, default_base_map = initial_region_defaults()
        defaults = {"bbox": default_bbox, "copyTo": DEFAULT_COPY_TO, "at5Prefix": "",
                    "imcExe": DEFAULT_IMC_EXE, "templateSap": "",
                    "baseMap": default_base_map, "zoom": DEFAULT_ZOOM,
                    "lakeContours": DEFAULT_LAKE_CONTOURS, "language": DEFAULT_LANGUAGE}
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            result = {key: data.get(key, value) for key, value in defaults.items()}
            if result["language"] not in ("ja", "en"):
                result["language"] = DEFAULT_LANGUAGE
            exe = Path(str(result["imcExe"]).strip()) if result["imcExe"] else None
            template = Path(str(result["templateSap"]).strip()) if result["templateSap"] else None
            result["imcValid"] = bool(exe and exe.is_file() and template and template.is_file())
            return result
        except (OSError, ValueError, TypeError):
            return {**defaults, "imcValid": False}

    # 範囲や出力先、IMCの場所を検証してユーザー設定へ保存する。
    def save(self, data):
        bbox = validate_bbox(data.get("bbox"))
        copy_to = str(data.get("copyTo", DEFAULT_COPY_TO)).strip()
        at5_prefix = validate_at5_prefix(data.get("at5Prefix", ""))
        previous = self.read_saved()
        imc_exe = str(data.get("imcExe", previous.get("imcExe", DEFAULT_IMC_EXE))).strip()
        template_sap = str(data.get("templateSap", previous.get("templateSap", ""))).strip()
        base_map = str(data.get("baseMap", previous.get("baseMap", DEFAULT_BASE_MAP)))
        zoom = int(data.get("zoom", previous.get("zoom", DEFAULT_ZOOM)))
        lake_contours = bool(data.get("lakeContours", previous.get("lakeContours", DEFAULT_LAKE_CONTOURS)))
        language = str(data.get("language", previous.get("language", DEFAULT_LANGUAGE)))
        if language not in ("ja", "en"):
            raise ValueError("Language must be ja or en")
        if base_map not in ("standard", "aerial", "usgs_imagery"):
            raise ValueError("背景地図の指定が不正です")
        if zoom not in (15, 16, 17):
            raise ValueError("ズームレベルは15～17から選択してください")
        if base_map == "usgs_imagery" and zoom > 16:
            raise ValueError("USGS航空写真の出力ズームレベルはZL15またはZL16です")
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        saved = {"bbox": bbox, "copyTo": copy_to, "at5Prefix": at5_prefix,
                 "imcExe": imc_exe, "templateSap": template_sap,
                 "baseMap": base_map, "zoom": zoom, "lakeContours": lake_contours,
                 "language": language}
        STATE_FILE.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
        return saved

    # IMC実行ファイルを確認し、Raster Mode設定を検出して保存する。
    def set_imc(self, data):
        raw_path = str(data.get("imcExe", "")).strip().strip('"')
        if not raw_path:
            raise ValueError("InsightMapCreator.exeのパスを入力してください")
        imc_exe = Path(raw_path).expanduser().resolve()
        if not imc_exe.is_file():
            raise FileNotFoundError(f"InsightMapCreator.exeがありません: {imc_exe}")
        template_sap = find_raster_template(imc_exe)
        saved = self.read_saved()
        saved["imcExe"] = str(imc_exe)
        saved["templateSap"] = str(template_sap)
        result = self.save(saved)
        result["imcConfigured"] = True
        return result

    # ブラウザーから受け取った設定を確認し、ビルドをバックグラウンドで開始する。
    def start_build(self, data):
        with self.lock:
            if self.running:
                raise RuntimeError("Buildはすでに実行中です")
            bbox = validate_bbox(data.get("bbox"))
            copy_to = str(data.get("copyTo", "")).strip()
            at5_prefix = validate_at5_prefix(data.get("at5Prefix", ""))
            base_map = str(data.get("baseMap", DEFAULT_BASE_MAP))
            zoom = int(data.get("zoom", DEFAULT_ZOOM))
            lake_contours = bool(data.get("lakeContours", DEFAULT_LAKE_CONTOURS))
            if base_map not in ("standard", "aerial", "usgs_imagery") or zoom not in (15, 16, 17):
                raise ValueError("背景地図またはズームレベルの指定が不正です")
            if base_map == "usgs_imagery" and zoom > 16:
                raise ValueError("USGS航空写真の出力ズームレベルはZL15またはZL16です")
            saved = self.read_saved()
            imc_exe = Path(str(data.get("imcExe") or saved.get("imcExe", "")).strip()).expanduser()
            template_sap = Path(str(saved.get("templateSap", "")).strip()) if saved.get("templateSap") else None
            if not copy_to:
                raise ValueError("出力先パスを指定してください")
            if not Path(copy_to).is_dir():
                raise ValueError(f"出力先フォルダーがありません: {copy_to}")
            if not imc_exe.is_file():
                raise FileNotFoundError(f"InsightMapCreator.exeがありません: {imc_exe}")
            if template_sap is None or not template_sap.is_file():
                template_sap = find_raster_template(imc_exe)
            if not BUILDER.is_file():
                raise FileNotFoundError(f"Buildスクリプトがありません: {BUILDER}")
            self.save({"bbox": bbox, "copyTo": copy_to, "at5Prefix": at5_prefix,
                       "imcExe": str(imc_exe), "templateSap": str(template_sap),
                       "baseMap": base_map, "zoom": zoom, "lakeContours": lake_contours})
            self.running = True
            self.log = ""
            self.result = "buildRunning"

        # 変換スクリプトを実行し、進行ログと終了結果を状態へ反映する。
        def worker():
            command = [
                sys.executable, str(BUILDER),
                "--bbox", *[str(v) for v in bbox],
                "--zoom", str(zoom), "--base-map", base_map,
                *(["--lake-contours"] if lake_contours else []),
                "--imc-exe", str(imc_exe),
                "--template-sap", str(template_sap),
                "--output-dir", output_dir_for_bbox(bbox, base_map, zoom, lake_contours),
                "--min-resolution", "1",
                "--max-resolution", "8192",
                "--filter-alpha", "0",
                "--copy-to", copy_to,
            ]
            if at5_prefix:
                command.extend(["--at5-prefix", at5_prefix])
            try:
                proc = subprocess.Popen(
                    command, cwd=ROOT, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                    errors="replace", bufsize=1,
                )
                chunks = []
                assert proc.stdout is not None
                for line in proc.stdout:
                    chunks.append(line)
                    with self.lock:
                        self.log = "".join(chunks[-500:])
                code = proc.wait()
                with self.lock:
                    self.result = "buildDone" if code == 0 else "buildFailed"
            except Exception as exc:
                with self.lock:
                    self.log += f"\n{exc}\n"
                    self.result = "buildFailed"
            finally:
                with self.lock:
                    self.running = False

        threading.Thread(target=worker, daemon=True).start()

    # 編集済みのPowerShellコマンドを別ウィンドウで実行する。
    def launch_powershell(self, data, completion_url):
        if os.name != "nt":
            raise RuntimeError("PowerShell実行ボタンはWindows上で起動した場合に使えます")
        with self.lock:
            if self.running:
                raise RuntimeError("Buildはすでに実行中です")
        bbox = validate_bbox(data.get("bbox"))
        copy_to = str(data.get("copyTo", "")).strip()
        at5_prefix = validate_at5_prefix(data.get("at5Prefix", ""))
        saved = self.read_saved()
        imc_exe = Path(str(data.get("imcExe") or saved.get("imcExe", "")).strip()).expanduser()
        template_sap = Path(str(saved.get("templateSap", "").strip())) if saved.get("templateSap") else None
        if not copy_to:
            raise ValueError("出力先パスを指定してください")
        if not Path(copy_to).is_dir():
            raise ValueError(f"出力先フォルダーがありません: {copy_to}")
        if not imc_exe.is_file():
            raise FileNotFoundError(f"InsightMapCreator.exeがありません: {imc_exe}")
        if template_sap is None or not template_sap.is_file():
            template_sap = find_raster_template(imc_exe)
        if not BUILDER.is_file():
            raise FileNotFoundError(f"Buildスクリプトがありません: {BUILDER}")
        base_map = str(data.get("baseMap", DEFAULT_BASE_MAP))
        zoom = int(data.get("zoom", DEFAULT_ZOOM))
        lake_contours = bool(data.get("lakeContours", DEFAULT_LAKE_CONTOURS))
        self.save({"bbox": bbox, "copyTo": copy_to, "at5Prefix": at5_prefix,
                   "imcExe": str(imc_exe), "templateSap": str(template_sap),
                   "baseMap": base_map, "zoom": zoom, "lakeContours": lake_contours,
                   "language": data.get("language", saved.get("language", DEFAULT_LANGUAGE))})
        ps_command = str(data.get("command", "")).strip()
        if not ps_command:
            raise ValueError("PowerShellコマンドが空です")

        # Buildの終了コードにかかわらず、finallyからUIへ完了を通知する。
        run_id = uuid.uuid4().hex
        safe_url = completion_url.replace("'", "''")
        wrapped_command = f"""
$__at5BuildExitCode = 0
try {{
{ps_command}
    if ($null -ne $LASTEXITCODE) {{ $__at5BuildExitCode = [int]$LASTEXITCODE }}
}} catch {{
    $__at5BuildExitCode = 1
    Write-Error $_
}} finally {{
    try {{
        $body = @{{ runId = '{run_id}'; exitCode = $__at5BuildExitCode }} | ConvertTo-Json -Compress
        Invoke-RestMethod -Uri '{safe_url}' -Method Post -ContentType 'application/json' -Body $body | Out-Null
    }} catch {{
        Write-Host 'UIへのBuild完了通知に失敗しました。'
    }}
}}
"""
        with self.lock:
            self.running = True
            self.run_id = run_id
            self.log = ""
            self.result = "buildRunning"
        try:
            proc = subprocess.Popen(
                ["powershell.exe", "-NoExit", "-Command", wrapped_command],
                cwd=ROOT, creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except Exception:
            with self.lock:
                if self.run_id == run_id:
                    self.running = False
                    self.run_id = None
                    self.result = "buildFailed"
            raise

        # 通知が届かずにPowerShellが閉じた場合も、UIの実行中状態を解除する。
        def wait_for_powershell():
            proc.wait()
            with self.lock:
                if self.running and self.run_id == run_id:
                    self.running = False
                    self.run_id = None
                    self.result = "buildEnded"
        threading.Thread(target=wait_for_powershell, daemon=True).start()

    # UIから届いたBuild完了通知を、現在の実行に限って反映する。
    def finish_powershell(self, data):
        run_id = str(data.get("runId", ""))
        try:
            exit_code = int(data.get("exitCode", 1))
        except (TypeError, ValueError):
            exit_code = 1
        with self.lock:
            if not self.running or run_id != self.run_id:
                return False
            self.running = False
            self.run_id = None
            self.result = "buildDone" if exit_code == 0 else "buildFailed"
            return True

state = AppState()

# 地図の種類、ズーム、範囲から再利用時に混ざらない作業フォルダー名を作る。
def output_dir_for_bbox(bbox, base_map=DEFAULT_BASE_MAP, zoom=DEFAULT_ZOOM,
                        lake_contours=DEFAULT_LAKE_CONTOURS):
    tag = "-".join(("m" if value < 0 else "p") + f"{round(abs(value) * 1_000_000):09d}" for value in bbox)
    source = base_map + ("-lake" if lake_contours else "") + f"-z{zoom}"
    return f"map-ui-{source}-{tag}"

# 南・西・北・東の順と緯度経度の範囲を検証する。
def validate_bbox(value):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("bboxは南・西・北・東の4数値で指定してください")
    try:
        bbox = [float(v) for v in value]
    except (TypeError, ValueError):
        raise ValueError("bboxに数値以外が含まれています")
    south, west, north, east = bbox
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("bboxの範囲または南西北東の順を確認してください")
    return bbox

# Windowsのフォルダー選択画面でAT5の保存先を選ぶ。
def select_output_directory(data):
    if os.name != "nt":
        raise RuntimeError("フォルダー選択画面はWindows上で利用できます")
    import tkinter as tk
    from tkinter import filedialog

    initial = str(data.get("initialDir", "")).strip().strip('"')
    initial_path = Path(initial).expanduser() if initial else Path.home()
    if not initial_path.is_dir():
        initial_path = initial_path.parent if initial_path.parent.is_dir() else Path.home()
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            parent=root,
            title="出力先フォルダーを選択",
            initialdir=str(initial_path),
            mustexist=True,
        )
    finally:
        root.destroy()
    return {"path": selected} if selected else {"cancelled": True}


# Windowsのファイル選択画面でInsightMapCreator.exeを選ぶ。
def select_imc_executable(data):
    if os.name != "nt":
        raise RuntimeError("ファイル選択画面はWindows上で利用できます")
    import tkinter as tk
    from tkinter import filedialog

    initial = str(data.get("initialPath", "")).strip().strip('"')
    initial_path = Path(initial).expanduser() if initial else Path.home()
    initial_dir = initial_path.parent if initial_path.is_file() else initial_path
    if not initial_dir.is_dir():
        initial_dir = initial_dir.parent if initial_dir.parent.is_dir() else Path.home()
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askopenfilename(
            parent=root,
            title="InsightMapCreator.exeを選択",
            initialdir=str(initial_dir),
            filetypes=(("InsightMapCreator.exe", "InsightMapCreator.exe"),
                       ("実行ファイル", "*.exe"),
                       ("すべてのファイル", "*.*")),
        )
    finally:
        root.destroy()
    return {"path": selected} if selected else {"cancelled": True}


# AT5名に使う先頭文字を許可文字と長さで検証する。
def validate_at5_prefix(value):
    prefix = str(value or "").strip()
    if prefix and not all(char.isascii() and (char.isalnum() or char == "-") for char in prefix):
        raise ValueError("AT5名の先頭文字は半角英数字とハイフンで指定してください")
    if len(prefix) > 32:
        raise ValueError("AT5名の先頭文字は32文字以内で指定してください")
    return prefix

# ローカルブラウザー画面からのHTTP要求を処理する。
class Handler(BaseHTTPRequestHandler):
    # 画面、保存設定、実行状況のGET要求を返す。
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            body = HTML.replace("__PYTHON_EXECUTABLE_JSON__", json.dumps(sys.executable)).replace("__TOOL_ROOT_JSON__", json.dumps(str(ROOT))).replace("__TOOL_VERSION__", TOOL_VERSION).replace("__DEFAULT_LANGUAGE_JSON__", json.dumps(DEFAULT_LANGUAGE)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/state":
            self.send_json(200, state.read_saved())
        elif path == "/log":
            with state.lock:
                self.send_json(200, {"running": state.running, "log": state.log,
                                     "resultKey": state.result})
        else:
            self.send_error(404)

    # 設定保存、パス選択、変換起動のPOST要求を振り分ける。
    def do_POST(self):
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if path == "/select-output-dir":
                self.send_json(200, select_output_directory(data))
            elif path == "/select-imc-exe":
                self.send_json(200, select_imc_executable(data))
            elif path == "/imc-settings":
                self.send_json(200, state.set_imc(data))
            elif path == "/state":
                self.send_json(200, state.save(data))
            elif path == "/build":
                state.start_build(data)
                self.send_json(202, {"started": True})
            elif path == "/powershell":
                completion_url = f"http://127.0.0.1:{self.server.server_port}/build-finished"
                state.launch_powershell(data, completion_url)
                self.send_json(202, {"started": True, "message": "Buildを実行中です。詳細はPowerShellで確認できます。"})
            elif path == "/build-finished":
                accepted = state.finish_powershell(data)
                self.send_json(200, {"accepted": accepted})
            else:
                self.send_error(404)
        except Exception as exc:
            self.send_json(400, {"error": str(exc)})

    # JSONデータをHTTPレスポンスとして返す。
    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # 標準HTTPサーバーのアクセスログ出力を抑制する。
    def log_message(self, fmt, *args):
        pass

# ローカル専用Webサーバーを起動し、ブラウザーで画面を開く。
def main():
    if sys.version_info < (3, 9):
        raise SystemExit("Python 3.9 or later is required.")
    if not BUILDER.is_file():
        raise SystemExit(f"Buildスクリプトがありません: {BUILDER}")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"AT5範囲設定UI: {url}")
    print(f"範囲設定の保存先: {STATE_FILE}")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n終了します")
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
