# Streamlit Deployment

This app can run locally with OAuth, but hosted Streamlit should use a Google Cloud service account stored in Streamlit secrets.

## Deployment Shape

```text
Google Sheets
  -> Streamlit-hosted DC1 Health Board
  -> Google Sites iframe/embed
```

The Streamlit app remains the live engine. Google Sites becomes the presentation shell that embeds the Streamlit URL or specific query-string views.

## 1. Prepare Google Access

1. Create or reuse a Google Cloud project.
2. Enable these APIs:
   - Google Sheets API
   - Google Drive API
   - Google Drive Activity API
3. Create a service account.
4. Create a JSON key for that service account.
5. Share each connected Google Sheet with the service account `client_email` as a viewer.

The deployed app cannot use the local desktop OAuth browser flow, so this service account is the clean hosted path.

## 2. Prepare The Repo

Streamlit Community Cloud deploys from GitHub. The deployed repo should include:

- `app.py`
- `requirements.txt`
- `styles.css`
- `assets/`
- `.streamlit/secrets.example.toml`
- `STREAMLIT_DEPLOYMENT.md`

Do not commit:

- `google_credentials.json`
- `data/google_token.json`
- `data/*.sqlite`
- `.streamlit/secrets.toml`

The `.gitignore` already excludes these.

## 3. Configure Streamlit Secrets

In Streamlit Community Cloud, open the app settings and add secrets using the shape in:

```text
.streamlit/secrets.example.toml
```

Include:

- `[gcp_service_account]` with the service account JSON values.
- `[[google_sheets]]` entries for the live sheets the app should seed on first run.

Supported sheet tags:

- `SDT Schedule`
- `OB TO Tracker`
- `Fill Rate`
- `Carrier Mapping`
- `Core-Mark`
- `Other`

## 4. Deploy

1. Push the `dc1-health-board` folder to GitHub.
2. In Streamlit Community Cloud, create a new app from that GitHub repo.
3. Set the main file path to:

```text
app.py
```

4. Add the secrets.
5. Deploy.

On first run, the app will seed any `[[google_sheets]]` secrets into its local dashboard cache, then refresh those sheets.

## 5. Embed In Google Sites

Use Google Sites `Embed` and paste the deployed Streamlit app URL.

Useful view URLs:

```text
https://YOUR-APP.streamlit.app/?section=Home&view=Live%20Update
https://YOUR-APP.streamlit.app/?section=Home&view=Executive%20Briefs
https://YOUR-APP.streamlit.app/?section=Operations&view=Fill%20Rate%20/%20Pallet%20Ops
https://YOUR-APP.streamlit.app/?section=Operations&view=Market%20Profiles
```

For focused Google Sites modules, use `site_embed` to render only the selected app block:

```text
https://YOUR-APP.streamlit.app/?site_embed=home_live_metrics&embed=true
https://YOUR-APP.streamlit.app/?site_embed=daily_health&embed=true
https://YOUR-APP.streamlit.app/?site_embed=transportation_control&embed=true
https://YOUR-APP.streamlit.app/?site_embed=executive_brief&embed=true
https://YOUR-APP.streamlit.app/?site_embed=market_profiles&embed=true
```

If a full-page embedded app shows Streamlit chrome you do not want, try appending Streamlit's built-in display flag:

```text
?embed=true
```

or for an existing query string:

```text
&embed=true
```

## Scheduled Refresh

The app checks every 15 minutes while the Streamlit process is awake and refreshes connected sheets once after each slot:

- 4:00 AM
- 4:00 PM

If the hosted process is asleep at the exact scheduled time, it refreshes on the next wake/page load after that slot.

## Important Hosting Notes

- Streamlit Community Cloud is good for a live MVP and Google Sites embedding.
- The local SQLite database in cloud is app-local cache, not a durable enterprise database.
- Any permanent app configuration should live in Streamlit secrets or Google Sheets, not in local SQLite.
- Uploaded PDFs/presentations/LEAN files saved to SQLite are fine locally, but should move to Drive or another durable store before heavy multi-user use.
