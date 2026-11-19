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

## Raster Mode SAPテンプレート

ツールには、利用者のIMC設定やファイルパスを含むSAPファイルを同梱していません。IMCでRaster Modeの設定ファイル（.sap）を作成・保存し、その場所をツールの「Raster Mode SAPテンプレート」欄へ指定してください。

テンプレートはRaster Modeで保存したSAPを指定します。処理のたびにツールが入力フォルダー、作業フォルダー、解像度、Raster Filter Alpha、Atlas Descriptionを更新します。テンプレートそのものは変更せず、Buildごとに新しいSAPを作成します。

## 導入確認

- InsightMapCreator.exe が起動する
- IMCでRaster Modeを選び、設定をSAPファイルとして保存できる
- ツール画面でIMC実行ファイルとSAPテンプレートの両方を指定できる

IMCのバージョンや設定画面が異なる場合は、同梱されるIMCドキュメントも確認してください。
