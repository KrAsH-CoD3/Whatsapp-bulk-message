# CONTEXT.md — WhatsApp Bulk Messenger

## Glossary

| Term | Definition |
|------|------------|
| Contact | A person receiving a message, identified by name and phone number (CSV) |
| Message Template | External `message.txt` with `{{name}}` placeholder for personalization |
| Invitation Image | Single static image sent as attachment with every message |
| Session Profile | Saved Playwright browser state for persistent WhatsApp Web login |
| Sent Log | `sent.csv` tracking who already received a message (enables resume) |
| Failed Log | `failed.csv` tracking contacts that could not be delivered, retried on next run |
| Pending List | Contacts after filtering: excludes sent, includes failed for retry, deduplicated |

## Decisions

- **Python async Playwright** — user preference, Python 3.10+
- **Single script** — one-off wedding task, not a long-lived product
- **Session persistence** — scan QR once, reuse across runs via `whatsapp_session/`
- **Random delay (8-15s default)** — configurable, mimics human behavior
- **Resume support** — tracks sent contacts, skips on restart; retries failed
- **Dry run + limit flags** — `--dry-run` for preview, `--limit N` for small test
- **Phone validation** — auto-format with default country code +234 (Nigeria), warn on invalid
- **Error handling** — skip & log to `failed.csv`, retry once on transient failures
- **Progress** — console output + log file
- **Search-based flow** — uses WhatsApp Web search bar (no page reloads per message)
- **Cross-platform** — pathlib for paths, utf-8 encoding, works on macOS/Windows/Linux
- **Image size limit** — 16 MB max, validated before sending
- **Deduplication** — duplicate phone numbers in CSV are skipped
- **Graceful shutdown** — Ctrl+C closes browser, logs progress
