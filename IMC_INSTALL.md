# Insight Map Creator（IMC）の導入

このツールはWindows版Insight Map Creator（IMC）を起動してAT5を生成します。IMCのプログラムはライセンスや配布条件が本ツールと異なるため、リポジトリには含めていません。

## 入手と展開

プロジェクト確認時に使われた配布元は、Navicoの mapcreator.zip です。

- Navico配布ZIP: https://s3-eu-west-1.amazonaws.com/navicodigitalassets/AMER/GoFree/mapcreator.zip
- 配布リンクを案内したReefMasterフォーラム: https://reefmaster.com.au/index.php/forum/support/2242-direct-imc-download-link

リンクは変更・停止される可能性があります。ダウンロードページの提供元とファイルを確認してください。出所不明の実行ファイルは使わないでください。

1. DocumentsフォルダーにAT5MapBuilder\IMCフォルダーを作ります（例：ユーザーのDocuments\AT5MapBuilder\IMC）。
2. mapcreator.zipをそのフォルダーに展開します。中には、IMC本体やサンプルなど複数のZIPファイルが入っています。
3. IMC_0_7_4_0_Application_x64.zipを展開します。IMC_Application_x64フォルダーが作成されます。
4. **IMC_0_7_4_0_Sample.zipも同じ場所に展開します。** IMC_Sampleフォルダーができたことを確認してください。IMC_Application_x64とIMC_Sampleは同じ親フォルダーに置きます。
5. ツールを起動し、初回に表示される「IMCの場所を設定」へIMC_Application_x64内のInsightMapCreator.exeを指定します。エクスプローラーでファイルを右クリックして「パスのコピー」を選び、入力欄へ貼り付けて保存できます。

IMCはフォルダーから起動する形式として使えます。Windowsへの別途インストーラー実行は、配布パッケージに含まれる説明に従ってください。

## 設定ファイルの自動利用

IMCはコマンドラインから地図変換を実行しますが、実行時にはIMCの設定ファイルも読み込みます。本ツールはIMCの場所から配布物に含まれる「IMC_Sample」フォルダーを探し、Raster Mode用の設定を自動で選びます。利用者が設定ファイルを探して登録する必要はありません。

IMC_0_7_4_0_Sample.zipはIMC本体のZIPとは別です。mapcreator.zipを展開しただけでは、Raster Mode設定を含むIMC_Sampleフォルダーはできません。IMC_Application_x64フォルダーの隣にIMC_Sampleフォルダーがある状態にしてください。ツールは登録時にこの近くのサンプルだけを確認し、PC全体の検索は行いません。見つからない場合は、IMC_0_7_4_0_Sample.zipを展開したか確認してください。

保存したパスを直す場合やIMCを別の場所へ移した場合も、画面の「IMC設定」から再登録できます。IMCのバージョンや設定画面が異なる場合は、同梱されるIMCドキュメントも確認してください。
