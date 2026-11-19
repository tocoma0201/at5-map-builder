# Lowrance Elite Ti2でのAT5表示

## 地図ソースを選ぶ

1. チャート画面のメニューから **Chart source** を開きます。
2. AT5作成時に指定した地図名（Atlas Description）を選びます。例：KanagawaNanbu。
3. SDカードの ShadedRelief フォルダーに、同じ地図名で作成されたAT5ファイル一式があることを確認します。

同じSDカードに複数の地図セットを置く場合は、作成時にそれぞれ異なる地図名を指定してください。Chart source一覧で表示対象のセットを切り替えます。同じ名前にすると、ファイルが置き換わったり、地図セットの識別が難しくなります。

## 表示設定

- **Photo overlay**：まず **Land only** を選択
- **Overlay**：Genesis Liveの等深線を重ねる場合は **Genesis live**
- **Genesis Live options → Transparency**：地図と等深線の見やすさに合わせて調整

Photo overlayがOffだと、作成したラスター地図が表示されないことを実機で確認しています。Shaded relief項目がグレー表示でも、この地図の表示には影響しませんでした。

## 表示されないとき

- Chart sourceで該当地図名が選択されているか
- Photo overlayがOffになっていないか
- SDカード内の ShadedRelief に同じ地図名のAT5一式があるか
- 現在位置が作成範囲内か
- 前回と異なる地図セットを表示する場合、Chart sourceを選び直したか

表示が確認できても、地図は正式な航海用海図ではありません。水深、浅瀬、障害物、航行可否は正式な海図や最新の航行情報で確認してください。
