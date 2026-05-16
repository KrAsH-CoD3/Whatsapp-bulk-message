#!/usr/bin/env python3
"""WhatsApp Bulk Messenger — Playwright automation for wedding invitations."""

import asyncio
import csv
import logging
import random
import re
import sys
from datetime import datetime
from pathlib import Path

import click
from playwright.async_api import async_playwright

# --- Config ---
SESSION_DIR = Path("./whatsapp_session")
SENT_LOG = Path("sent.csv")
FAILED_LOG = Path("failed.csv")
CONTACTS_CSV = Path("contacts.csv")
MESSAGE_FILE = Path("message.txt")
IMAGE_FILE = Path("invitation.png")
DEFAULT_COUNTRY_CODE = "+234"
MIN_DELAY = 8
MAX_DELAY = 15
MAX_RETRIES = 1

# --- Logging ---
log_file = Path("messages.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file),
    ],
)
logger = logging.getLogger(__name__)


# --- Phone validation ---
def clean_phone(raw: str, default_code: str = DEFAULT_COUNTRY_CODE) -> str:
    """Strip non-digits, add country code if missing, return WhatsApp-safe number."""
    digits = re.sub(r"[^\d+]", "", raw.strip())
    if digits.startswith("+"):
        return digits
    if digits.startswith("00"):
        return "+" + digits[2:]
    if digits.startswith("0"):
        digits = digits[1:]
    if not digits.startswith("+"):
        digits = default_code.lstrip("+") + digits
        digits = "+" + digits
    return digits

def is_valid_phone(phone: str) -> bool:
    """Basic check: + followed by 7-15 digits."""
    return bool(re.match(r"^\+\d{7,15}$", phone))


# --- CSV helpers ---
def load_contacts(path: Path = CONTACTS_CSV) -> list[dict]:
    """Load contacts from CSV. Expects columns: name, phone."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)

def load_sent(path: Path = SENT_LOG) -> set[str]:
    """Load set of already-sent phone numbers."""
    if not path.exists():
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["phone"].strip() for row in reader}

def load_failed(path: Path = FAILED_LOG) -> set[str]:
    """Load set of previously-failed phone numbers."""
    if not path.exists():
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["phone"].strip() for row in reader}

def log_sent(contact: dict, path: Path = SENT_LOG):
    """Append a contact to the sent log."""
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "phone", "timestamp"])
        if path.stat().st_size == 0:
            writer.writeheader()
        writer.writerow({**contact, "timestamp": datetime.now().isoformat()})

def log_failed(contact: dict, reason: str, path: Path = FAILED_LOG):
    """Append a contact to the failed log."""
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "phone", "reason", "timestamp"])
        if path.stat().st_size == 0:
            writer.writeheader()
        writer.writerow({**contact, "reason": reason, "timestamp": datetime.now().isoformat()})


# --- Message template ---
def load_template(path: Path = MESSAGE_FILE) -> str:
    """Load message template from file."""
    return Path(path).read_text(encoding="utf-8")

def render_template(template: str, name: str) -> str:
    """Replace {{name}} placeholder."""
    return template.replace("{{name}}", name).replace("{{Name}}", name)

async def type_message(page, message: str):
    """Type message, converting \\n to Shift+Enter for newlines."""
    for char in message:
        if char == "\n":
            await page.keyboard.down("Shift")
            await page.keyboard.press("Enter")
            await page.keyboard.up("Shift")
        else:
            await page.keyboard.type(char)


# --- WhatsApp Web automation ---
async def send_message(page, phone: str, message: str, image_path: Path | None = None) -> bool:
    """Search contact, open chat, send message + optional image, return to list."""
    BACK_BUTTON = 'span[data-testid="back"]'
    SEARCH_BAR = '*[aria-label="Search or start a new chat"]'
    CLEAR_SEARCH_BUTTON = '*[aria-label="End icon button"]'
    SEARCH_RESULT = 'xpath=//*[@id="pane-side"]//div[@data-testid="list-item-1"]'
    SEND_BUTTON = 'span[data-testid="wds-ic-send-filled"]'
    IMG_MESSAGE_INPUT = '[aria-label*="Type a message"]'
    MESSAGE_INPUT = '[aria-label*="Type a message"]'
    
    # Ensure we're on the chat list
    back = await page.query_selector(BACK_BUTTON)
    if back:
        await back.click()
        await asyncio.sleep(1)

    # Click search bar or clear button, type phone
    selector = await page.wait_for_selector(SEARCH_BAR + ", " + CLEAR_SEARCH_BUTTON, timeout=15_000)
    await selector.click()
    # await page.keyboard.press("Meta+A")
    # await page.keyboard.press("Delete")
    await selector.fill(phone)

    # Wait for search results to populate
    await asyncio.sleep(2)

    # Check for no results
    no_results = await page.query_selector('*[data-testid="search-no-chats-or-contacts"]')
    if no_results:
        return False

    # Click first search result
    result = await page.wait_for_selector(SEARCH_RESULT, timeout=15_000)
    await result.click()

    # Wait for chat panel to open
    await page.wait_for_selector('div[data-testid="conversation-panel-wrapper"]', timeout=15_000)

    if image_path and image_path.exists():
        # Attach image via file chooser
        async with page.expect_file_chooser() as fc_info: 
            attach_btn = await page.wait_for_selector('span[data-testid="plus-rounded"]', timeout=10_000)
            await attach_btn.click()
            await asyncio.sleep(2)
            photo_option = await page.wait_for_selector("text=Photos & videos", timeout=10_000)
            await photo_option.click()
            await asyncio.sleep(2)
        file_chooser = await fc_info.value
        await file_chooser.set_files(str(image_path))

        # Wait for image preview + caption area to appear
        await page.wait_for_selector('[aria-label="Add file"]', timeout=15_000)
        await asyncio.sleep(2)

        # Type caption — use the caption input below the preview
        caption = await page.query_selector(IMG_MESSAGE_INPUT)
        if caption:
            await caption.click()
            await type_message(page, message)
            await asyncio.sleep(1)

        # Send
        send_btn = await page.wait_for_selector(SEND_BUTTON, timeout=15_000)
        await send_btn.click()
    else:
        # Type message
        msg_input = await page.wait_for_selector(MESSAGE_INPUT, timeout=15_000)
        await msg_input.click()
        await type_message(page, message)

        # Send
        send_btn = await page.wait_for_selector(SEND_BUTTON, timeout=15_000)
        await send_btn.click()

    await asyncio.sleep(1)

    # # Return to chat list
    # back = await page.wait_for_selector(BACK_BUTTON, timeout=10000)
    # await back.click()
    # await asyncio.sleep(1)

    return True

async def run(dry_run: bool, limit: int | None, min_delay: int, max_delay: int, country_code: str):
    """Main execution loop."""
    logger.info("=== WhatsApp Bulk Messenger ===")
    logger.info(f"Contacts: {CONTACTS_CSV}")
    logger.info(f"Template: {MESSAGE_FILE}")
    logger.info(f"Image: {IMAGE_FILE}")
    logger.info(f"Session: {SESSION_DIR}")

    # Load data
    contacts = load_contacts()
    sent_phones = load_sent()
    failed_phones = load_failed()
    template = load_template()

    logger.info(f"Total contacts: {len(contacts)}")
    logger.info(f"Already sent: {len(sent_phones)}")
    logger.info(f"Previously failed: {len(failed_phones)}")

    # Filter: sent takes priority, failed gets retried
    pending = []
    for c in contacts:
        phone = clean_phone(c["phone"], country_code)
        if not is_valid_phone(phone):
            logger.warning(f"Invalid phone for {c['name']}: {c['phone']}")
            log_failed({**c, "phone": phone}, "invalid phone format")
            continue
        if phone in sent_phones:
            # Already sent — never retry, even if also in failed.csv
            continue
        if phone in failed_phones:
            logger.info(f"Retrying previously failed: {c['name']} ({phone})")
        c["phone"] = phone
        pending.append(c)

    if limit:
        pending = pending[:limit]

    logger.info(f"Pending: {len(pending)}")

    if not pending:
        logger.info("No contacts to send. All done!")
        return

    if dry_run:
        logger.info("--- DRY RUN ---")
        for c in pending:
            msg = render_template(template, c["name"])
            logger.info(f"Would send to {c['name']} ({c['phone']}):")
            logger.info(f"  {msg[:100]}...")
        logger.info("--- END DRY RUN ---")
        return

    # Launch Playwright
    SESSION_DIR.mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=False,
            viewport={"width": 1080, "height": 720},
        )
        page = browser.pages[0] if browser.pages else await browser.new_page()

        # Check if already logged in
        await page.goto("https://web.whatsapp.com")
        try:
            # After login: default-user (no chats) or chat-list (has conversations)
            await page.wait_for_selector(
                'div[data-testid="default-user"], div[data-testid="chat-list"]',
                timeout=15000
            )
            logger.info("Session active — already logged in.")
        except Exception:
            logger.info("Scan QR code now... waiting for login.")
            await page.wait_for_selector(
                'div[data-testid="default-user"], div[data-testid="chat-list"]',
                timeout=120000
            )
            logger.info("Logged in!")

        sent_count = 0
        failed_count = 0

        for i, contact in enumerate(pending, 1):
            name = contact["name"]
            phone = contact["phone"]
            msg = render_template(template, name)

            logger.info(f"[{i}/{len(pending)}] Sending to {name} ({phone})...")

            success = False
            for attempt in range(1, MAX_RETRIES + 2):
                try:
                    success = await send_message(page, phone, msg, IMAGE_FILE)
                    if success:
                        break
                except Exception as e:
                    logger.warning(f"Attempt {attempt} failed for {name}: {e}")
                    if attempt <= MAX_RETRIES:
                        await asyncio.sleep(5)

            if success:
                log_sent(contact)
                sent_count += 1
                logger.info(f"  ✓ Sent to {name}")
            else:
                log_failed(contact, "send failed")
                failed_count += 1
                logger.error(f"  ✗ Failed to send to {name}")

            # Random delay between messages
            if i < len(pending):
                delay = random.uniform(min_delay, max_delay)
                logger.info(f"  Waiting {delay:.1f}s...")
                await asyncio.sleep(delay)

        logger.info(f"=== Complete: {sent_count} sent, {failed_count} failed ===")

        await browser.close()

@click.command()
@click.option("--dry-run", is_flag=True, help="Preview messages without sending")
@click.option("--limit", type=int, default=None, help="Send to only first N contacts")
@click.option("--min-delay", type=int, default=MIN_DELAY, help="Min delay between messages (seconds)")
@click.option("--max-delay", type=int, default=MAX_DELAY, help="Max delay between messages (seconds)")
@click.option("--country-code", default=DEFAULT_COUNTRY_CODE, help="Default country code for phone numbers")
def main(dry_run, limit, min_delay, max_delay, country_code):
    """WhatsApp Bulk Messenger for wedding invitations."""
    asyncio.run(run(dry_run, limit, min_delay, max_delay, country_code))

if __name__ == "__main__":
    main()
