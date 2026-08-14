# Streamlit Secrets Setup

Use `.streamlit/secrets.toml` as your local working file only. It is ignored by git and should not be pushed to GitHub.

The values in `google_token.json` and `google_credentials.json` are for the local OAuth desktop flow. Streamlit Community Cloud should use a Google service account key instead.

If Gopuff policy blocks sharing Sheets with the service account, use the optional `[google_oauth]` block instead. That lets Streamlit refresh with the authorized Google user that already has access to the files.

## Where the Values Come From

In Google Cloud Console, open:

`IAM & Admin` > `Service Accounts` > `dc1health-board-streamlit-app`

Then use `Keys` > `Add key` > `Create new key` > `JSON`.

If Google Cloud does not offer JSON download, key creation may be blocked by an organization policy. In that case, use the Streamlit Cloud Secrets box with a service account key provided by an admin, or ask the Google Workspace / Cloud admin to allow key creation for this project/service account.

## Required Fields

Paste the service account JSON fields into Streamlit TOML like this:

```toml
[gcp_service_account]
type = "service_account"
project_id = "dc1-health-board-app"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "dc1health-board-streamlit-app@dc1-health-board-app.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/dc1health-board-streamlit-app%40dc1-health-board-app.iam.gserviceaccount.com"
universe_domain = "googleapis.com"
```

Then add the `[[google_sheets]]` blocks from `.streamlit/secrets.toml`.

## Optional Work-Account OAuth Fallback

Use this only when the hosted app shows `403 caller does not have permission` for org-owned Google Sheets that cannot be shared with the service account.

Copy the values from the local `data/google_token.json` authorized by the work account:

```toml
[google_oauth]
client_id = "..."
client_secret = "..."
refresh_token = "..."
token_uri = "https://oauth2.googleapis.com/token"
account = "your.work.account@example.com"
scopes = [
  "https://www.googleapis.com/auth/spreadsheets.readonly",
  "https://www.googleapis.com/auth/drive.metadata.readonly",
  "https://www.googleapis.com/auth/drive.activity.readonly",
]
```

When `[google_oauth]` is present, the app uses it before `[gcp_service_account]`.

## Decision Support Chat (Anthropic)

Required for the Home > Decision Support Chat page. Create a key at [console.anthropic.com](https://console.anthropic.com/), then add:

```toml
[anthropic]
api_key = "sk-ant-..."
```

Without this block, the page shows a "not configured" message instead of the chat.

## Final Checklist

1. Fill `.streamlit/secrets.toml` locally.
2. Share every connected Google Sheet with the service account email.
3. If service account sharing is blocked, add `[google_oauth]` from a work-account token instead.
4. Add `[anthropic]` if you want Decision Support Chat enabled.
5. Paste the full TOML into Streamlit Community Cloud > App settings > Secrets.
6. Deploy or reboot the Streamlit app.

Never commit `.streamlit/secrets.toml`.
