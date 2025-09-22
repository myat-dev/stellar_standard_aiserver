# LINE RichMenu 作成手順 (LINE Messaging API)

龍泉寺様のLINE　channel からリアルタイムモード操作の為使います。

RichMenu 作成の方法は二つあります。

1. LINE Official Account Manager Console (version1.1 まで使った, リアルタイムモード表示不可)
2. LINE Messaging API  (version2.0 から使用)

## 1. LINE RichMenu 登録
三つのモード　「在宅、半在宅、不在」の為　三つのRichMenu を作ります。
`create_richmenu.ps1`を確認してください。

``` Powershell
curl -v -X POST https://api.line.me/v2/bot/richmenu `
-H 'Authorization: Bearer {CHANNEL_ACCESS_TOKEN}' `
-H 'Content-Type: application/json' `
-d '{
  "size": {
    "width": 2500,
    "height": 843
  },
  "selected": false,
  "name": "hanzaitakuMenu",
  "chatBarText": "モード選択",
```
- {CHANNEL_ACCESS_TOKEN} をLINE channel access token に切り替える(.env file に確認)
- `"name" : "hanzaitakuMenu"　`のところを作るモードの名前と切り替える

### Script 実行
- Powershell で　`line_richmenu `フォルダー下まで行って `.\create_richmenu.ps1` command を実行
- 実行の後以下のように　richmenuid が出たら成功
`{"richMenuId":"richmenu-8ac865401850a1c136452d5bcab748cb"}`
- richmenuid を `src\configs\server_conf.yaml`に記入する
(例：hanzaitaku_menu:　richmenu-8ac865401850a1c136452d5bcab748cb)

"name" を作成したいモードの名前に変更しながら在宅と不在のためもrichmenu を作成してください。

## 2. RichMenu 画像登録

作成した　RichMenu に画像を付ける。
三つのモード選択に対して各モードをハイライトする画像が必要です。
1. zaitaku_menu.png
2. hanzaitaku_menu.png
3. fuzai_menu.png

- 同じPowershell で以下のcommand を実行
```
curl -v -X POST https://api-data.line.me/v2/bot/richmenu/{richmenuid}/content `
-H "Authorization: Bearer {CHANNEL_ACCESS_TOKEN}" `
-H "Content-Type: image/png" `
-T hanzaitaku_menu.png
```
- {richmenuid} を作成した半在宅のrichmenuidと切り替える
- `hanzaitaku_menu.png`も切り替える
{richmenuid}を作成したモードのrichmenuidに変更しながら在宅と不在のためも画像を付けてください。

## 3. RichMenu List 確認

- 以下のcommand を実行すると登録したRichMenu一覧が表示されます。RichMenu が三つあるはずです。
```
curl -v -X GET https://api.line.me/v2/bot/richmenu/list `
-H 'Authorization: Bearer {CHANNEL_ACCESS_TOKEN}'
```