# https://default7fb910a1b6dd4dfcb4b7f2f8393b00.24.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/f84a9e052f3344329e1b85f94fd30958/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=i7KVeG5N23_dKBTtNdB4RBmIqxMZ75apanok5PvSjTg
import requests

WEBHOOK_URL = "https://default7fb910a1b6dd4dfcb4b7f2f8393b00.24.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/f84a9e052f3344329e1b85f94fd30958/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=i7KVeG5N23_dKBTtNdB4RBmIqxMZ75apanok5PvSjTg"

payload = {
    "type": "AdaptiveCard",
    "version": "1.4",
    "body": [
        {
            "type": "TextBlock",
            "text": "🚨 Website Alert",
            "weight": "Bolder",
            "size": "Large"
        },
        {
            "type": "TextBlock",
            "text": "Site: example.com\nStatus: DOWN",
            "wrap": True
        }
    ]
}

requests.post(WEBHOOK_URL, json=payload)