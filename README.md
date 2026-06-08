# EasyApplyBot

A configurable Selenium helper for LinkedIn Easy Apply jobs.

The bot now defaults to **dry-run mode**. In dry-run mode it can search, open Easy Apply forms, fill known fields, and stop at the final submit button without sending the application. Use live mode only after you have watched a dry-run work correctly.

## What changed

- Uses Selenium Manager instead of a hard-coded `CHROMEDRIVER_PATH`.
- Reads credentials and preferences from environment variables instead of source code.
- Searches most-recent jobs first with `sortBy=DD`.
- Rotates through job titles, checks the newest jobs first, then expands up to the last month if needed.
- Tracks seen jobs in `seen_jobs.json` so it does not keep retrying the same postings.
- Writes application outcomes to `applications_log.jsonl`.
- Has safer form handling for text inputs, selects, radio buttons, and certification checkboxes.

## Install

```powershell
python -m pip install -r requirements.txt
```

## Configure

Set these in PowerShell before running:

```powershell
$env:LINKEDIN_EMAIL="your-email@example.com"
$env:LINKEDIN_PASSWORD="your-password"
$env:LINKEDIN_PHONE="5555555555"
$env:LINKEDIN_SEARCH_TERMS="analyst,manager,intern"
$env:LINKEDIN_LOCATION="Fort Lauderdale, Florida"
$env:LINKEDIN_MAX_APPLICATIONS="25"
$env:LINKEDIN_PAGES_PER_SEARCH="2"
$env:LINKEDIN_DRY_RUN="true"
```

Optional answers:

```powershell
$env:LINKEDIN_DEFAULT_YEARS="1"
$env:LINKEDIN_WORK_AUTHORIZED="Yes"
$env:LINKEDIN_SPONSORSHIP="No"
$env:LINKEDIN_NOTICE_PERIOD="2 weeks"
$env:LINKEDIN_CUSTOM_ANSWERS='{"leetcode":"Yes","clearance":"No"}'
```

## Run a dry-run

```powershell
python EasyApplyBot.py
```

## Run live

Only do this after a dry-run behaves correctly:

```powershell
$env:LINKEDIN_DRY_RUN="false"
python EasyApplyBot.py
```

## Notes

LinkedIn may show MFA, captcha, or change its HTML. If the bot stops, run without headless mode and watch where Chrome gets stuck. Automating LinkedIn may violate LinkedIn's terms, so use this carefully and at your own risk.
