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
  "areas": [
    {
      "bounds": {
        "x": 0,
        "y": 0,
        "width": 833,
        "height": 843
      },
      "action": {
        "type": "message",
        "label": "在宅",
        "text": "在宅モード"
      }
    },
    {
      "bounds": {
        "x": 834,
        "y": 0,
        "width": 833,
        "height": 843
      },
      "action": {
        "type": "message",
        "label": "半在宅",
        "text": "半在宅モード"
      }
    },
    {
      "bounds": {
        "x": 1667,
        "y": 0,
        "width": 833,
        "height": 843
      },
      "action": {
        "type": "message",
        "label": "不在",
        "text": "不在モード"
      }
    }
  ]
}'
