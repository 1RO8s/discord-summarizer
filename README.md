# ChatGPT を使って Discord の Public channel をまとめて要約するスクリプト

by [1RO8s](https://twitter.com/kizzo168) 2023-[APACHE LICENSE, 2.0](https://www.apache.org/licenses/LICENSE-2.0)




SERVER_ID

#### SUMMARY_CHANNEL_ID
- ユーザー設定を開き、詳細設定 -> 開発者モードをONにする
![message-content-intent](images/developer-mode.png)
- 対象のサーバーに移動後、サーバー名を右クリックして、メニューから「IDをコピー」を選択

### botの作成

[Botアカウント作成](https://discordpy.readthedocs.io/ja/latest/discord.html)


### 権限設定
Developer Portal
- Bot -> MESSAGE CONTENT INTENTを有効化する
![message-content-intent](images/message-content-setting.png)

### botの招待
YOUR_CLIENT_IDにはbotのclient idを設定

以下のURLを開いて、対象のサーバーにbotを招待してください
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=67584&scope=bot
```