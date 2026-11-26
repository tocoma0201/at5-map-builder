# 地図データの権利・安全に関する案内

この案内は、データの利用許諾や法令上の手続きが不要であることを保証するものではありません。地図ソース、地域、タイル、利用方法によって適用条件が異なります。生成地図を配布・公開する前に、利用者自身で最新の公式条件を確認してください。

## 出典と利用条件

### 米国：USGS航空写真

本ツールのUSGS航空写真は、USGS The National Map の **USGS Imagery Only** タイルサービスを利用します。サービスの出典表示は「USDA, USGS The National Map: Orthoimagery」です。The National Mapのサービス・データはパブリックドメインで利用でき、USGSは派生製品やデータにも出典を記載するよう求めています。ただし、タイルサービスは複数の画像ソースを含みます。公式説明では、米国本土の大部分はNAIP画像、アラスカはSPOT画像とされ、アラスカ画像にはライセンス上の制約が記載されています。したがって、本ツールの出典表示だけで、全地域・全タイルの条件確認が完了したとはみなせません。

- [USGS Imagery Only サービス情報・出典表示](https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer)
- [The National Map の利用条件・ライセンス](https://www.usgs.gov/faqs/what-are-terms-uselicensing-map-services-and-data-national-map)
- [USGSによる画像ソースの説明](https://www.usgs.gov/faqs/what-sources-were-used-imagery-national-map-services)
- [USGSの出典表記案内](https://www.usgs.gov/information-policies-and-instructions/acknowledging-or-crediting-usgs)

### 日本：国土地理院タイル

標準地図、全国最新写真（シームレス）、湖沼図は、タイルごとに利用条件が異なる場合があります。基本測量成果に該当するタイルでは測量法上の申請が必要な場合があり、第三者が権利を持つタイルには個別の条件が適用されることがあります。

- [地理院タイル一覧・個別の出典と利用条件](https://maps.gsi.go.jp/development/ichiran.html)
- [地理院タイル利用上の注意](https://maps.gsi.go.jp/help/use.html)
- [国土地理院・地図の利用手続](https://www.gsi.go.jp/LAW/2930-index.html)

## 生成地図に同梱する出典記録

ビルドでコピーしたAT5と同じフォルダーに、`<地図名>_SOURCE_NOTICES.txt`（地図名を指定しない場合は背景地図・ズーム・範囲を含む名前）を保存します。ファイルには、選択した背景地図と重ねた湖沼図の出典、公式情報へのリンク、範囲、出力ズーム、ビルド日時を記録します。ビルド日時は画像の撮影日やデータ更新日を示すものではありません。これは出典の記録であって、利用許諾や法令上の手続きが完了した証明ではありません。地図名を変えて複数の地図を作る場合は、それぞれの記録ファイルも保持してください。

データ提供元の規約、出典表示要件、測量法その他の法令は変更されることがあります。出典記録にあるリンク先を、生成地図を使う時点でも確認してください。本ツールのソース表示は、出典表示の要件を満たす保証ではありません。

## 安全性と責任

生成地図は正式な航海用海図ではありません。位置、海岸線、水深、障害物、網羅性、最新性、魚探機器との適合性を保証しません。利用者は生成地図と機器上の表示を自ら確認し、現地情報・正式な海図・機器の説明書を参照したうえで利用方法や航行を判断してください。

本ツールおよび生成地図は現状有姿で提供され、正確性・完全性・特定目的への適合性を保証しません。適用法令で認められる範囲で、提供者は生成地図の利用または利用不能から生じる損害について責任を負いません。この記載は、適用法令により制限できない責任を除外するものではありません。免責文だけで、すべての法域における法的責任を排除できるとは限りません。

---

# Map data, rights, and safety notice

This notice does not grant permission or establish that no legal procedure is required. Terms may vary by source, geographic area, individual tile, and use. Before distributing or publishing a generated map, users must check the current official terms themselves.

## Sources and terms

### United States: USGS aerial imagery

This tool uses the **USGS Imagery Only** tile service from USGS The National Map. Its service credit is “USDA, USGS The National Map: Orthoimagery.” The National Map states that its services and data are in the public domain and asks users to credit the source in derived products and data. However, the imagery service combines multiple sources. USGS describes NAIP as the primary source for most of the conterminous United States and SPOT imagery for Alaska; it notes licensing restrictions for Alaska imagery. The tool's attribution alone does not establish that every tile or region has been cleared for every use.

- [USGS Imagery Only service information and credit](https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer)
- [The National Map terms and licensing](https://www.usgs.gov/faqs/what-are-terms-uselicensing-map-services-and-data-national-map)
- [USGS explanation of imagery sources](https://www.usgs.gov/faqs/what-sources-were-used-imagery-national-map-services)
- [USGS credit guidance](https://www.usgs.gov/information-policies-and-instructions/acknowledging-or-crediting-usgs)

### Japan: Geospatial Information Authority of Japan (GSI) tiles

Terms may differ among standard maps, seamless aerial imagery, and lake maps. Some tiles may require procedures under Japan's Survey Act, and tiles containing third-party material may have additional terms.

- [GSI tile list, individual credits, and terms](https://maps.gsi.go.jp/development/ichiran.html)
- [GSI tile usage notes](https://maps.gsi.go.jp/help/use.html)
- [GSI map use procedures](https://www.gsi.go.jp/LAW/2930-index.html)

## Source record included with generated maps

The build copies a `<map-name>_SOURCE_NOTICES.txt` file alongside the AT5 files. If no map name is set, the filename includes the source, zoom, and bounds. The file records the selected base map and any lake-map overlay, links to official source information, the requested bounds, output zoom, and build time. The build timestamp is not the imagery capture date or source-data update date. The file is a source record, not proof of permission or legal compliance. Keep the corresponding notice file with each map set.

Provider terms, attribution requirements, and laws can change. Recheck the linked official sources when using a generated map. The tool's source labels do not guarantee that all attribution requirements have been met.

## Safety and responsibility

Generated maps are not official navigational charts. Accuracy, completeness, currency, or compatibility with a fish finder is not guaranteed for positions, shorelines, depths, hazards, or other content. Users must check the generated map and its display on their device, consult current local information, official charts, and the device manual, and decide how to use the map and whether to navigate with it.

The tool and generated maps are provided “as is,” without warranties of accuracy, completeness, or fitness for a particular purpose. To the extent permitted by applicable law, the providers disclaim liability for damages arising from use or inability to use generated maps. This notice does not exclude liability that cannot be limited under applicable law. A disclaimer alone may not eliminate legal liability in every jurisdiction.
