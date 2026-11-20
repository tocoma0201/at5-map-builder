# Insight Map Creator（IMC）の導入

このツールはWindows版Insight Map Creator（IMC）を起動してAT5を生成します。IMCのプログラムはライセンスや配布条件が本ツールと異なるため、リポジトリには含めていません。

## 入手と展開

プロジェクト確認時に使われた配布元は、Navicoの mapcreator.zip です。

- Navico配布ZIP: https://s3-eu-west-1.amazonaws.com/navicodigitalassets/AMER/GoFree/mapcreator.zip
- 配布リンクを案内したReefMasterフォーラム: https://reefmaster.com.au/index.php/forum/support/2242-direct-imc-download-link

リンクは変更・停止される可能性があります。ダウンロードページの提供元とファイルを確認してください。出所不明の実行ファイルは使わないでください。

1. DocumentsフォルダーにAT5MapBuilder\IMCフォルダーを作ります（例：ユーザーのDocuments\AT5MapBuilder\IMC）。
2. ZIPを展開し、内側にある64-bit ApplicationのZIPも同じIMCフォルダー内へ展開します。IMC_Sampleフォルダーを含め、配布物のフォルダー構成を保ってください。
3. 展開したフォルダー内にあるInsightMapCreator.exeを確認します。ZIPの構成により、IMC直下ではなくサブフォルダー内にある場合があります。
4. ツールを起動し、初回に表示される「IMCの場所を設定」へInsightMapCreator.exeのフルパスを入力して保存します。

IMCはフォルダーから起動する形式として使えます。Windowsへの別途インストーラー実行は、配布パッケージに含まれる説明に従ってください。

## 設定ファイルの自動利用

IMCはコマンドラインから地図変換を実行しますが、実行時にはIMCの設定ファイルも読み込みます。本ツールはIMCの場所から配布物に含まれる「IMC_Sample」フォルダーを探し、Raster Mode用の設定を自動で選びます。利用者が設定ファイルを探して登録する必要はありません。

IMCを展開する際は、InsightMapCreator.exeだけでなく、配布ZIPに含まれるIMC_Sampleフォルダーも残してください。ツールは登録時に、指定したIMC実行ファイルの近くにあるIMC_Sampleだけを確認してRaster Mode設定を見つけます。PC全体の検索は行いません。見つからない場合は、展開先とIMC_Sampleの配置を見直して、「IMC設定」から登録し直してください。

保存したパスを直す場合やIMCを別の場所へ移した場合も、画面の「IMC設定」から再登録できます。IMCのバージョンや設定画面が異なる場合は、同梱されるIMCドキュメントも確認してください。
