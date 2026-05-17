# WhatsApp Bulk Messenger

Playwright automation for sending bulk WhatsApp messages with personalized text and image attachments.

## Backstory

A friend getting married needed a simple way to send bulk invitations to their contacts. This tool was built to automate that process reliably.

## Requirements

- Python 3.10+
- uv (or pip)
- Chromium browser (installed by Playwright)

## Setup

```bash
# Using uv (recommended)
uv sync
uv run playwright install chromium

# Or using pip
pip install -r requirements.txt
playwright install chromium
```

## Files to prepare

| File | Description |
|------|-------------|
| `contacts.csv` | Guest list with `name,phone` columns |
| `message.txt` | Message template with `{{name}}` placeholder |
| `invitation.png` | Wedding invitation image (max 16 MB) |

### CSV format

```csv
name,phone
John Doe,+2348012345678
Jane Smith,08098765432
```

Phone numbers are auto-formatted. `08012345678` becomes `+2348012345678`.

### Message template

```
Hi {{name}}!

You're invited to our wedding!

Date: Saturday, June 15, 2026
Venue: The Grand Garden

With love,
[Your Names]
```

Use `\n` in the text file for line breaks in the message.

## Usage

```bash
# Preview messages (no sends)
uv run send_messages.py --dry-run

# Test with first 3 contacts
uv run send_messages.py --limit 3

# Full send with custom delays
uv run send_messages.py --min-delay 10 --max-delay 20

# Custom country code
uv run send_messages.py --country-code +44
```

## First run

1. Script opens a browser window
2. Scan the WhatsApp Web QR code with your phone
3. Session is saved — no need to scan again on future runs

## How it works

1. Reads `contacts.csv`, skips already-sent numbers from `sent.csv`
2. Retries contacts from `failed.csv`
3. Searches each contact in WhatsApp Web, sends image + caption
4. Logs progress to console and `messages.log`
5. Failed contacts go to `failed.csv` for retry on next run

## Cross-platform

Works on macOS, Windows, and Linux. File paths use `pathlib` for OS compatibility.
