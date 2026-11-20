# Insight Map Creator（IMC）の導入

このツールはWindows版Insight Map Creator（IMC）を起動してAT5を生成します。IMCのプログラムはライセンスや配布条件が本ツールと異なるため、リポジトリには含めていません。

## 入手と展開

プロジェクト確認時に使われた配布元は、Navicoの mapcreator.zip です。

- Navico配布ZIP: https://s3-eu-west-1.amazonaws.com/navicodigitalassets/AMER/GoFree/mapcreator.zip
- 配布リンクを案内したReefMasterフォーラム: https://reefmaster.com.au/index.php/forum/support/2242-direct-imc-download-link

リンクは変更・停止される可能性があります。ダウンロードページの提供元とファイルを確認してください。出所不明の実行ファイルは使わないでください。

1. ZIPを展開します。
2. 内側にある64-bit ApplicationのZIPをさらに展開します。
3. 展開したフォルダーにある InsightMapCreator.exe を起動します。同梱ファイルは同じフォルダーに置いたままにします。
4. 展開先は任意です。プロジェクトの設定画面で InsightMapCreator.exe の場所を指定します。

IMCはフォルダーから起動する形式として使えます。Windowsへの別途インストーラー実行は、配布パッケージに含まれる説明に従ってください。

## 設定ファイルの自動利用

IMCはコマンドラインから地図変換を実行しますが、実行時にはIMCの設定ファイルも読み込みます。本ツールはIMCの場所から配布物に含まれる「IMC_Sample」フォルダーを探し、Raster Mode用の設定を自動で選びます。利用者が設定ファイルを探して登録する必要はありません。

IMCを展開する際は、InsightMapCreator.exeだけでなく、配布ZIPに含まれる「IMC_Sample」フォルダーも残してください。ツール画面ではInsightMapCreator.exeの場所を指定します。

IMCのバージョンや設定画面が異なる場合は、同梱されるIMCドキュメントも確認してください。
