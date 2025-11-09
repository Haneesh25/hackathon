
import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/meetings.space.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(
    port=0,
    prompt="consent",
    access_type="offline",
    include_granted_scopes="true"
)

# Print to console
print("\n✅ ACCESS TOKEN:\n", creds.token)
print("\n🔁 REFRESH TOKEN:\n", creds.refresh_token)
print("\n📅 EXPIRES AT:\n", creds.expiry)

# Save to token.json for later scripts
data = {
    "token": creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri": creds.token_uri,
    "client_id": creds.client_id,
    "client_secret": creds.client_secret,
    "scopes": SCOPES,
}
with open("token.json", "w") as f:
    json.dump(data, f, indent=2)

print("\n💾 Saved token.json — you can now use this token in your fetch scripts!")
