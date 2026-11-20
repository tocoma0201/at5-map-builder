# Insight Map Creator（IMC）の導入

このツールはWindows版Insight Map Creator（IMC）を起動してAT5を生成します。IMCのプログラムはライセンスや配布条件が本ツールと異なるため、リポジトリには含めていません。

## 入手と展開

プロジェクト確認時に使われた配布元は、Navicoの mapcreator.zip です。

- Navico配布ZIP: https://s3-eu-west-1.amazonaws.com/navicodigitalassets/AMER/GoFree/mapcreator.zip
- 配布リンクを案内したReefMasterフォーラム: https://reefmaster.com.au/index.php/forum/support/2242-direct-imc-download-link

リンクは変更・停止される可能性があります。ダウンロードページの提供元とファイルを確認してください。出所不明の実行ファイルは使わないでください。

1. DocumentsフォルダーにAT5MapBuilder\IMCフォルダーを作ります（例：ユーザーのDocuments\AT5MapBuilder\IMC）。
2. mapcreator.zipをそのフォルダーに展開します。中には、IMC本体とサンプルなど複数のZIPファイルが入っています。
3. IMC_0_7_4_0_Application_x64.zipを展開します。IMC_Application_x64フォルダーが作成されます。
4. IMC_0_7_4_0_Sample.zipは展開せず、そのまま残してください。ツールがZIP内のRaster Mode設定を自動で読み取ります。
5. ツールを起動し、初回に表示される「IMCの場所を設定」へIMC_Application_x64内のInsightMapCreator.exeを指定します。エクスプローラーでファイルを右クリックして「パスのコピー」を選び、入力欄へ貼り付けて保存できます。

IMCはフォルダーから起動する形式として使えます。Windowsへの別途インストーラー実行は、配布パッケージに含まれる説明に従ってください。

## 設定ファイルの自動利用

IMCはコマンドラインから地図変換を実行し、その実行にRaster Mode設定を使います。本ツールはSample ZIP内のSAPからRaster Mode用を自動で選ぶため、利用者が設定ファイルを探して登録する必要はありません。

IMC_0_7_4_0_Sample.zipは、展開したmapcreator.zipと同じフォルダーに置いてください。ツールはIMC実行ファイルの近くにあるSample ZIPからRaster Mode設定だけを読み取り、必要な設定をこのPCのアプリ用フォルダーへ保存します。ZIPの手動展開やPC全体の検索は行いません。

保存したパスを直す場合やIMCを別の場所へ移した場合も、画面の「IMC設定」から再登録できます。IMCのバージョンや設定画面が異なる場合は、同梱されるIMCドキュメントも確認してください。
