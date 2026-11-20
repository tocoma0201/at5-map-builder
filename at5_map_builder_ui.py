#!/usr/bin/env python3
"""Local browser UI for selecting a raster map bbox and running the AT5 builder.

Uses only the Python standard library. The background map loads GSI tiles in the
user's browser; a network connection is needed to see the background.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from configure_imc_raster_sap import find_raster_template

ROOT = Path(__file__).resolve().parent
BUILDER = ROOT / "build_at5_map.py"
DEFAULT_BBOX = [35.140, 139.130, 35.330, 139.590]
STATE_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AT5MapBuilder"
STATE_FILE = STATE_DIR / "range-ui-state.json"
DEFAULT_COPY_TO = ""
DEFAULT_IMC_EXE = os.environ.get("AT5_IMC_EXE", "")

HTML = r"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lowrance魚群探知機用 AT5日本地図作成ツール</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
*{box-sizing:border-box} body{margin:0;font:15px system-ui,sans-serif;color:#18212b}
header{padding:10px 16px;background:#173c58;color:white} h1{font-size:19px;margin:0}
main{display:grid;grid-template-columns:minmax(330px,390px) 1fr;min-height:calc(100vh - 48px)}
aside{padding:14px;border-right:1px solid #ccd4da;overflow:auto}
#map{height:calc(100vh - 48px);min-height:520px}
label{display:block;font-weight:600;margin:11px 0 4px}
input,textarea,button{font:inherit;padding:8px;border:1px solid #aab6bf;border-radius:5px;width:100%}
textarea{height:62px;resize:vertical} button{cursor:pointer;background:#eef4f7}
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
<header><h1>Lowrance魚群探知機用 AT5日本地図作成ツール</h1></header>
<main>
<aside>
<p class="note">地図は通常ドラッグで移動できます。「範囲選択」をONにした間だけドラッグで範囲を囲めます。座標は「南 西 北 東」の順で入力します。最後に使った範囲は次回も保持されます。</p>
<button id="selectMode">範囲選択: OFF（ドラッグで地図移動）</button>
<label for="bbox">範囲（南, 西, 北, 東）</label>
<textarea id="bbox" spellcheck="false" placeholder="35.140, 139.130, 35.330, 139.590"></textarea>
<div class="actions"><button id="apply">入力した範囲を反映</button><button id="useMap">地図の表示範囲を入力へ反映</button></div>
<div id="estimate" class="note"></div>
<label for="mapName">Ti2で選ぶ地図名／AT5先頭文字（任意）</label>
<input id="mapName" placeholder="例: Map01" maxlength="32">
<label for="copyTo">出力先フォルダー</label>
<input id="copyTo" placeholder="例: F:\ShadedRelief" title="SDカードに保存する場合は、カード直下の ShadedRelief フォルダーを指定してください。例：F:\ShadedRelief。PCに保存する場合は任意のフォルダーを指定できます。">
<div class="actions"><button id="imcSettings" type="button">IMC設定</button><span id="imcStatus" class="note">確認中…</span></div>
<dialog id="imcDialog">
<h2>IMCの場所を設定</h2>
<p class="note">エクスプローラーでInsightMapCreator.exeを右クリックして「パスのコピー」を選び、ここに貼り付けてください。Raster Mode設定はmapcreator.zip内のSample ZIPから自動取得するため、追加展開は不要です。設定はこのPCに保存され、「IMC設定」からいつでも変更できます。</p>
<label for="imcPath">InsightMapCreator.exeのパス</label>
<input id="imcPath" placeholder="例: C:\Users\名前\Documents\AT5MapBuilder\IMC\InsightMapCreator.exe">
<p id="imcPathError" class="note warning"></p>
<div class="actions"><button id="cancelImc" type="button">キャンセル</button><button id="saveImc" type="button" class="primary">保存</button></div>
</dialog>


<p class="note">生成条件：Min 1〜Max 8192 / Filter Alpha 0。容量の1,000 MBは推奨目安で、超えても警告のみで作成を続けます。タイル数が目安1,000枚を超えた場合も警告のみです。名前を入力すると、AT5ファイル名の先頭に付けると同時にAtlas Descriptionを「M=名前」に設定します。Ti2で地図を選ぶ際の識別名として使います。別の地図セットとは異なる名前にしてください。AT5容量は過去の試験結果を面積比で換算した概算です。</p>
<div class="actions"><button id="save">範囲を保存</button><button id="build" class="primary">AT5を作成して出力先へ保存</button></div>
<button id="runPowerShell">PowerShellで実行</button>
<div id="status">起動しています…</div>
<p class="note">本ツールはWindows専用です。実行状況と詳細はPowerShellで確認できます。</p>
</aside>
<div id="map"></div>
</main>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const pythonExecutable = __PYTHON_EXECUTABLE_JSON__;
const map=L.map('map').setView([35.24,139.36],10);
L.tileLayer('https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png',{
 maxZoom:18, attribution:'地理院タイル（標準地図） | 国土地理院'
}).addTo(map);
let rect=null, dragStart=null, bbox=null, running=false, selectMode=false;
const box=document.getElementById('bbox'), copyTo=document.getElementById('copyTo'), mapName=document.getElementById('mapName');
const imcDialog=document.getElementById('imcDialog'), imcPath=document.getElementById('imcPath');
const imcStatus=document.getElementById('imcStatus'), imcPathError=document.getElementById('imcPathError');
let imcExePath='', imcTemplatePath='';
imcPath.addEventListener('paste',e=>{
 const pasted=e.clipboardData?.getData('text/plain');
 if(!pasted)return;
 const trimmed=pasted.trim();
 const clean=trimmed.length>=2&&trimmed.startsWith('"')&&trimmed.endsWith('"')?trimmed.slice(1,-1):pasted;
 if(clean!==pasted){e.preventDefault();document.execCommand('insertText',false,clean)}
});

function valid(a){return a.length===4&&a.every(Number.isFinite)&&a[0]<a[2]&&a[1]<a[3]&&a[0]>=-90&&a[2]<=90&&a[1]>=-180&&a[3]<=180}
function setBox(a,save=true){
 if(!valid(a)){status('範囲の数値が不正です。南 西 北 東の順に入力してください。');return}
 bbox=a.map(Number); box.value=bbox.map(x=>x.toFixed(6)).join(', ');
 const bounds=[[bbox[0],bbox[1]],[bbox[2],bbox[3]]];
 if(rect)rect.setBounds(bounds);else rect=L.rectangle(bounds,{color:'#d23636',weight:2,fillOpacity:.10}).addTo(map);
 map.fitBounds(bounds,{padding:[12,12]}); updateCommand(); updateEstimate();
 if(save) persist();
}
function parseBox(s){const parts=s.trim().split(/[\s,，]+/).filter(Boolean);if(parts.length!==4)return [];return parts.map(Number)}
function status(s){document.getElementById('status').textContent=s}
function outputTag(a){return a.map(x=>(x<0?'m':'p')+String(Math.round(Math.abs(x)*1000000)).padStart(9,'0')).join('-')}
function areaKm2(a){const r=6371,rad=Math.PI/180;return r*r*(a[3]-a[1])*rad*(Math.sin(a[2]*rad)-Math.sin(a[0]*rad))}
function updateEstimate(){
 if(!bbox)return;
 const reference=areaKm2([35.140,139.130,35.330,139.590]);
 const mib=Math.round(870*areaKm2(bbox)/reference), mb=Math.round(mib*1.048576);
 const el=document.getElementById('estimate');el.className='note '+(mb<=1000?'good':'warning');
 el.textContent=`範囲面積 約${Math.round(areaKm2(bbox))} km² / AT5概算 約${mib} MiB（${mb} MB）。目安は1,000 MB以内。地図の内容や分割で実サイズは変わります。`;
}
function updateCommand(){}
async function persist(){
 try{await fetch('/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({bbox,copyTo:copyTo.value.trim(),at5Prefix:mapName.value.trim(),imcExe:imcExePath,templateSap:imcTemplatePath})})}catch(e){}
}
document.getElementById('apply').onclick=()=>setBox(parseBox(box.value));
document.getElementById('useMap').onclick=()=>{const b=map.getBounds();setBox([b.getSouth(),b.getWest(),b.getNorth(),b.getEast()])};
document.getElementById('save').onclick=async()=>{await persist();status('範囲と出力先を保存しました。次回起動時に復元します。')};
copyTo.onchange=()=>{updateCommand();persist()};
mapName.oninput=()=>{updateCommand();persist()};
document.getElementById('imcSettings').onclick=()=>{imcPath.value=imcExePath;imcPathError.textContent='';imcDialog.showModal()};
document.getElementById('cancelImc').onclick=()=>imcDialog.close();
document.getElementById('saveImc').onclick=async()=>{
 const path=imcPath.value.trim();
 if(!path){imcPathError.textContent='InsightMapCreator.exeのパスを入力してください。';return}
 const button=document.getElementById('saveImc');button.disabled=true;imcPathError.textContent='IMCと付属設定を確認しています…';
 try{
  const r=await fetch('/imc-settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({imcExe:path})});
  const j=await r.json();if(!r.ok)throw Error(j.error||'IMCを設定できません');
  imcExePath=j.imcExe;imcTemplatePath=j.templateSap||'';imcStatus.textContent='IMC設定済み';imcDialog.close();await persist();status('IMCの場所を保存しました。');
 }catch(e){imcPathError.textContent=String(e)}
 finally{button.disabled=false}
};
document.getElementById('selectMode').onclick=e=>{selectMode=!selectMode;e.currentTarget.textContent=selectMode?'範囲選択: ON（ドラッグで範囲指定）':'範囲選択: OFF（ドラッグで地図移動）';e.currentTarget.classList.toggle('primary',selectMode);map.dragging[selectMode?'disable':'enable']()};
map.on('mousedown',e=>{if(!selectMode||e.originalEvent.button!==0)return;dragStart=e.latlng;if(rect)map.removeLayer(rect);rect=L.rectangle([dragStart,dragStart],{color:'#d23636',weight:2,fillOpacity:.10}).addTo(map)});
map.on('mousemove',e=>{if(dragStart&&rect)rect.setBounds(L.latLngBounds(dragStart,e.latlng))});
document.addEventListener('mouseup',e=>{if(!dragStart)return;const end=map.mouseEventToLatLng(e);const bounds=L.latLngBounds(dragStart,end),sw=bounds.getSouthWest(),ne=bounds.getNorthEast();dragStart=null;if(sw.lat===ne.lat||sw.lng===ne.lng)return;setBox([sw.lat,sw.lng,ne.lat,ne.lng])});
document.getElementById('build').onclick=async()=>{
 if(running)return;
 const a=parseBox(box.value),dest=copyTo.value.trim(),name=mapName.value.trim(),imc=imcExePath;
 if(!valid(a)){status('先に正しいbboxを指定してください。');return}
 if(!dest){status('出力先パスを入力してください。');return}
 if(!imc){imcDialog.showModal();return}
 if(name&&!/^[A-Za-z0-9-]{1,32}$/.test(name)){status('AT5名の先頭文字は半角英数字とハイフンで入力してください。');return}
 await persist();running=true;document.getElementById('build').disabled=true;status('Buildを開始しました。完了までこの画面を開いたままにしてください。');
 
 try{const r=await fetch('/build',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({bbox:a,copyTo:dest,at5Prefix:name,imcExe:imc})});const j=await r.json();if(!r.ok)throw Error(j.error||'Build開始に失敗');poll()}catch(e){running=false;document.getElementById('build').disabled=false;status(String(e))}
};
document.getElementById('runPowerShell').onclick=async()=>{
 if(running)return;
 const a=parseBox(box.value),dest=copyTo.value.trim(),name=mapName.value.trim(),imc=imcExePath;
 if(!valid(a)){status('先に正しいbboxを指定してください。');return}
 if(!dest){status('出力先パスを入力してください。');return}
 if(!imc){imcDialog.showModal();return}
 if(name&&!/^[A-Za-z0-9-]{1,32}$/.test(name)){status('AT5名の先頭文字は半角英数字とハイフンで入力してください。');return}
 try{const r=await fetch('/powershell',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({bbox:a,copyTo:dest,at5Prefix:name,imcExe:imc})});const j=await r.json();if(!r.ok)throw Error(j.error||'PowerShellを起動できません');await persist();running=true;document.getElementById('build').disabled=true;status(j.message);poll()}catch(e){status(String(e))}
};
async function poll(){
 try{const r=await fetch('/log');const j=await r.json();
 if(j.running){setTimeout(poll,1200)}else{running=false;document.getElementById('build').disabled=false;status(j.result||'処理が終了しました。ログを確認してください。')}
 }catch(e){setTimeout(poll,2000)}
}
(async()=>{try{const s=await (await fetch('/state')).json();copyTo.value=s.copyTo||copyTo.value;mapName.value=s.at5Prefix||'';imcExePath=s.imcExe||'';imcTemplatePath=s.templateSap||'';imcStatus.textContent=s.imcValid?'IMC設定済み':'IMC設定を確認してください';setBox(s.bbox||[35.140,139.130,35.330,139.590],false);status('範囲を読み込みました。地図はドラッグで移動できます。');if(!s.imcValid)imcDialog.showModal()}catch(e){setBox([35.140,139.130,35.330,139.590],false);imcStatus.textContent='IMC未設定';imcDialog.showModal();status('既定の範囲を表示しています。')}})();
</script>
</body>
</html>
"""

class AppState:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.log = ""
        self.result = ""

    def read_saved(self):
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            result = {"bbox": data.get("bbox", DEFAULT_BBOX),
                      "copyTo": data.get("copyTo", DEFAULT_COPY_TO),
                      "at5Prefix": data.get("at5Prefix", ""),
                      "imcExe": data.get("imcExe", DEFAULT_IMC_EXE),
                      "templateSap": data.get("templateSap", "")}
            exe = Path(str(result["imcExe"]).strip()) if result["imcExe"] else None
            template = Path(str(result["templateSap"]).strip()) if result["templateSap"] else None
            result["imcValid"] = bool(exe and exe.is_file() and template and template.is_file())
            return result
        except (OSError, ValueError, TypeError):
            return {"bbox": DEFAULT_BBOX, "copyTo": DEFAULT_COPY_TO, "at5Prefix": "", "imcExe": DEFAULT_IMC_EXE, "templateSap": ""}

    def save(self, data):
        bbox = validate_bbox(data.get("bbox"))
        copy_to = str(data.get("copyTo", DEFAULT_COPY_TO)).strip()
        at5_prefix = validate_at5_prefix(data.get("at5Prefix", ""))
        previous = self.read_saved()
        imc_exe = str(data.get("imcExe", previous.get("imcExe", DEFAULT_IMC_EXE))).strip()
        template_sap = str(data.get("templateSap", previous.get("templateSap", ""))).strip()
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        saved = {"bbox": bbox, "copyTo": copy_to, "at5Prefix": at5_prefix,
                 "imcExe": imc_exe, "templateSap": template_sap}
        STATE_FILE.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
        return saved

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

    def start_build(self, data):
        with self.lock:
            if self.running:
                raise RuntimeError("Buildはすでに実行中です")
            bbox = validate_bbox(data.get("bbox"))
            copy_to = str(data.get("copyTo", "")).strip()
            at5_prefix = validate_at5_prefix(data.get("at5Prefix", ""))
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
                       "imcExe": str(imc_exe), "templateSap": str(template_sap)})
            self.running = True
            self.log = ""
            self.result = "Buildを実行中です"

        def worker():
            command = [
                sys.executable, str(BUILDER),
                "--bbox", *[str(v) for v in bbox],
                "--imc-exe", str(imc_exe),
                "--template-sap", str(template_sap),
                "--output-dir", output_dir_for_bbox(bbox),
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
                    self.result = "AT5作成と出力先への保存が完了しました。" if code == 0 else f"Buildが終了コード {code} で停止しました。"
            except Exception as exc:
                with self.lock:
                    self.log += f"\n{exc}\n"
                    self.result = f"Build起動エラー: {exc}"
            finally:
                with self.lock:
                    self.running = False

        threading.Thread(target=worker, daemon=True).start()

    def launch_powershell(self, data):
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
        self.save({"bbox": bbox, "copyTo": copy_to, "at5Prefix": at5_prefix,
                   "imcExe": str(imc_exe), "templateSap": str(template_sap)})
        args = [
            sys.executable, str(BUILDER),
            "--bbox", *[str(v) for v in bbox],
            "--imc-exe", str(imc_exe),
            "--template-sap", str(template_sap),
            "--output-dir", output_dir_for_bbox(bbox),
            "--min-resolution", "1", "--max-resolution", "8192",
            "--filter-alpha", "0", "--copy-to", copy_to,
        ]
        if at5_prefix:
            args.extend(["--at5-prefix", at5_prefix])
        def ps_quote(value):
            return "'" + str(value).replace("'", "''") + "'"
        ps_command = "& " + " ".join(ps_quote(x) for x in args) + "; if ($LASTEXITCODE -ne 0) { Write-Host ('Build failed: ' + $LASTEXITCODE) -ForegroundColor Red }"
        proc = subprocess.Popen(
            ["powershell.exe", "-NoExit", "-Command", ps_command],
            cwd=ROOT, creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        with self.lock:
            self.running = True
            self.log = ""
            self.result = "別ウィンドウのPowerShellで実行中です"
        def wait_for_powershell():
            code = proc.wait()
            with self.lock:
                self.running = False
                self.result = "PowerShellを閉じました。実行結果はPowerShell側で確認してください。"
        threading.Thread(target=wait_for_powershell, daemon=True).start()

state = AppState()

def output_dir_for_bbox(bbox):
    tag = "-".join(("m" if value < 0 else "p") + f"{round(abs(value) * 1_000_000):09d}" for value in bbox)
    return f"map-ui-{tag}"

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

def validate_at5_prefix(value):
    prefix = str(value or "").strip()
    if prefix and not all(char.isascii() and (char.isalnum() or char == "-") for char in prefix):
        raise ValueError("AT5名の先頭文字は半角英数字とハイフンで指定してください")
    if len(prefix) > 32:
        raise ValueError("AT5名の先頭文字は32文字以内で指定してください")
    return prefix

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            body = HTML.replace("__PYTHON_EXECUTABLE_JSON__", json.dumps(sys.executable)).encode("utf-8")
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
                                     "result": state.result})
        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if path == "/imc-settings":
                self.send_json(200, state.set_imc(data))
            elif path == "/state":
                self.send_json(200, state.save(data))
            elif path == "/build":
                state.start_build(data)
                self.send_json(202, {"started": True})
            elif path == "/powershell":
                state.launch_powershell(data)
                self.send_json(202, {"started": True, "message": "PowerShellを別ウィンドウで開きました。実行結果はPowerShell側で確認できます。"})
            else:
                self.send_error(404)
        except Exception as exc:
            self.send_json(400, {"error": str(exc)})

    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass

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
