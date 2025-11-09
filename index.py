# index.py  (Slack-only testing)
import requests, time, os

# --- your filler bot token (for testing only) ---
SLACK_BOT_TOKEN = os.getenv(
    "SLACK_BOT_TOKEN",
    "xoxb-9878042867524-9902813950496-JhbHUM6W2oJ6s20hNE6ToOvJ"
)
SLACK_API = "https://slack.com/api"

def _bearer():
    return {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}

def list_channels(types="public_channel,private_channel", limit=200):
    chans, cursor = [], None
    while True:
        params = {"limit": limit, "types": types}
        if cursor: params["cursor"] = cursor
        r = requests.get(f"{SLACK_API}/conversations.list", headers=_bearer(), params=params).json()
        if not r.get("ok"):
            raise RuntimeError(r)
        chans += r.get("channels", [])
        cursor = (r.get("response_metadata") or {}).get("next_cursor")
        if not cursor: break
    return chans

def try_join(channel_id):
    # needs channels:join scope
    resp = requests.post(f"{SLACK_API}/conversations.join",
                         headers=_bearer(),
                         data={"channel": channel_id}).json()
    return resp.get("ok"), resp.get("error")

def channel_history(channel_id, oldest=None, limit=200):
    msgs, cursor = [], None
    tried_join = False
    while True:
        params = {"channel": channel_id, "limit": limit}
        if cursor: params["cursor"] = cursor
        if oldest: params["oldest"] = oldest
        r = requests.get(f"{SLACK_API}/conversations.history", headers=_bearer(), params=params).json()
        if not r.get("ok"):
            err = r.get("error")
            if err == "not_in_channel" and not tried_join:
                ok, jerr = try_join(channel_id)
                tried_join = True
                if ok:
                    time.sleep(0.3)
                    continue
                else:
                    print(f"skip {channel_id}: cannot join ({jerr})")
                    return msgs
            raise RuntimeError(r)
        msgs += r.get("messages", [])
        cursor = (r.get("response_metadata") or {}).get("next_cursor")
        if not cursor: break
        time.sleep(0.2)
    return msgs

if __name__ == "__main__":
    chans = list_channels()
    print("channels:", len(chans))
    if chans:
        msgs = channel_history(chans[0]["id"])
        for i in range(len(msgs)):
            print("first channel msgs:", msgs[i]["text"])
