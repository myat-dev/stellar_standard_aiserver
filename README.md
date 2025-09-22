# 龍泉寺様　AI サーバー 🤖

## 開発者向け
### セットアップ ⚙️

Operation System: Windows 11

1. リポジトリをクローンする
```
>> git clone https://github.com/myat-dev/stellar-chatbot.git
```
2. 環境設定

Virtualenv 
```
>> pip install virtualenv
>> python -m venv chatbotenv
>> .\chatbotenv\Scripts\Activate.ps1

>> cd stellar-chatbot
>> pip install -r requirements.txt
```

3. API keys 設定

set your own api keys in `.env`

API Keys file (.env)は関係者から貰ってください。

----
### 1. サーバー起動

以下コメンドを実行する:
```
>> python runner.py
```
以下の表示が出ったらサーバー起動完了
```
[07/07/25 15:58:24] INFO     サーバー起動 モード: 在宅モード
INFO:     Started server process [14504]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
```

## 2. LINE webhook 実行

以下コメンドを実行する:
```
>> python ngrok_runner.py
```
ngrok_runner.py (security token がある為)関係者から貰ってください。

----

## Unity Avatar でテスト
Unity のアバター　exe を実行してください。

## Command Line　でテスト

AI サーバーと新しいcommand line から直接話できます。
Unity からのUI 入力が必要な機能たちはテストできないです。

You can speak with AI server from command line terminal. \
Open a new terminal with environment activated. \
Some of the UI inputs which required Unity can't be used.

以下コメンドを実行する:
```
>> python unit_test/test_client.py
```

## Customization📝
- To modify AI prompt, rag information, tool usage, update
[src\configs\AI_conf.yaml](src\configs\AI_conf.yaml).

- LINE ID, モード, などの情報は　
[src\configs\server_conf.yaml](src\configs\server_conf.yaml)　に更新してください。

- 電話対応機能の　電話番号は　[src\static\config.yaml](src\static\config.yaml)　に更新してください。


## Exe 作成方 (Command line)
### AI サーバーexe
1. pychcache を削除する
```
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
```

2. PyInstaller でexe を作る
```
pyinstaller --noconfirm --onedir --console --add-data "{C:\PCのパース}\stella-chatbot\src;src/" --add-data "{C:\PCのパース}\stella-chatbot\.env;." --collect-all "torch" --collect-all "torchvision" --collect-all "langchain" --collect-all "langchain_community" --collect-all "langchain_core" --collect-all "langchain_openai" --collect-all "pandas" --collect-all "pydantic" --collect-all "dotenv" --collect-all "openpyxl" --collect-all "fastapi" --collect-all "uvicorn" --collect-all "yaml" --collect-all "rich" --collect-all "twilio" --collect-all "python_multipart" --collect-all "selenium" --hidden-import cv2 --collect-submodules cv2 "{C:\PCのパース}\stella-chatbot\runner.py"
```

3. AI サーバーexe の準備
- PyInstaller から　`dist`と`build`,二つのフォルダーが出てきます。
`dist`フォルダーの中から　`dist/runner/_internal/.env`をコピーして
`dist/runner/` に張り付けてください。
- 電話対応のため　パソコンにインストールされる　Microsoft Edge browser を確認して、version に合うDriverをdownload してください。
- `msedgedriver.exe` を `dist/runner/`に入れてください。
- `runner.exe` を実行して、準備完了

### AI サーバー shutdown exe

1. PyInstaller でexe を作る
```
pyinstaller --noconfirm --onefile --console .\shutdown.py
```
`dist`と`build`フォルダーが出て、`dist`の中にshutdown.exe があれば完了

### ngrok exe

1. PyInstaller でexe を作る
```
pyinstaller --noconfirm --onefile --console .\ngrok_runner.py --collect-all "ngrok"
```
`dist`と`build`フォルダーが出て、`dist`の中にngork_runner.exe があれば完了

----
## 非技術者向け

AI Avatar 起動順番

1. runner.exe  
2. ngrok_runner.exe
3. Unity avatar.exe

AI Avatar 停止順番

1. Unity avatar.exe
2. ngrok_runner.exe
3. shutdown.exe
























