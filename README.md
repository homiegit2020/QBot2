# MARCO P2P Bot

Telegram bot rebuild for the MARCO P2P flow: P2P ad posting, captcha/group gate, SAFE SELL Express, wallet deposits/withdrawals, per-user stats, global stats, cooldowns, and admin approval.

## What Is Included

- aiogram v3 polling bot
- SQLite by default, with SQLAlchemy async models
- Persistent DB-backed user sessions so flows survive restarts
- MARCO-branded `/start` cards with generated banner image
- Persistent reply keyboard:
  - `POST AD`
  - `SAFE SELL [EXPRESS]`
  - `WALLET💰`
  - `📊 My Stats`
  - `📈 Global Stats`
- POST AD group gate, captcha, ad builder, preview, publish, public channel/group posting, and 3-hour cooldown
- SAFE SELL Express amount/rate calculation, token/network selection, deposit address display, screenshot proof upload, and admin review
- Wallet add funds, withdraw queue, account lock while pending, and admin approval/rejection
- Admin commands for pending queue, stats, payment-mode availability, rates, and broadcasts

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:

- `BOT_TOKEN`: BotFather token
- `ADMIN_IDS`: comma-separated numeric Telegram user IDs
- `ADMIN_REVIEW_CHAT_ID`: admin group/channel for payment proof review
- `ADS_CHANNEL_ID`: public ads channel, such as `@MARCO_P2P`
- `ADS_GROUP_ID`: public ads group numeric ID
- `REQUIRED_GROUP_1_ID` / `REQUIRED_GROUP_2_ID`: groups users must join before posting ads
- `DEPOSIT_ADDRESSES_JSON`: token/network deposit address map

The bot must be admin in any channel/group where it checks membership, posts ads, or sends admin-review messages.

## Run

```bash
python -m marco_bot.main
```

By default the bot creates `marco_bot.sqlite3` in the working directory.

## Deploy On Railway

1. Push this folder to a GitHub repository.
2. Create a new Railway project from the GitHub repo.
3. Add a Railway Postgres database.
4. Set the environment variables from `.env.railway.example` in Railway, using your real private values.
5. Keep Railway's `DATABASE_URL` variable from Postgres; the app converts it to the async SQLAlchemy driver automatically.
6. Deploy. `railway.json` starts the bot with `python -m marco_bot.main`.

This is a polling Telegram bot, so it does not need an HTTP port.

See `RAILWAY_DEPLOY.md` for the full GitHub/Railway checklist.

## Deposit Address Format

Example:

```env
DEPOSIT_ADDRESSES_JSON={"USDT":{"BEP20":"0x...","TRC20":"T..."},"BTC":{"BTC":"bc1..."},"ETH":{"ERC20":"0x..."}}
```

If an address is missing, users will see a visible `CONFIGURE_TOKEN_CHAIN_ADDRESS` placeholder so misconfiguration is obvious.

## Admin Commands

```text
/admin
/pending
/stats
/mode UPI on
/mode CDM off
/rates
/setrate UPI 10 600 94.0
/setrate UPI 5001 + 97.0
/broadcast message text
/emojiids
```

Use `/emojiids` (or `/emojiiids`) as a reply to a message that contains premium/custom emojis, or include premium emojis in the same command message, to print the Telegram custom emoji IDs needed for `<tg-emoji emoji-id="...">` rendering.

Admin approval buttons are attached to every pending screenshot/withdrawal submission:

- Approve unlocks the user.
- Approve for `express_sell` increments user and global SAFE-SOLD stats.
- Approve for `wallet_deposit` credits wallet balance and increments user/global SAFE-SOLD stats.
- Approve for `withdrawal` debits wallet balance.
- Reject unlocks the user and sends retry/support instructions.

## Branding Assets

The bot generates a MARCO banner image automatically for `/start` cards. To use a custom astronaut/shield banner, set:

```env
BANNER_IMAGE_PATH=C:\absolute\path\to\banner.png
```

## Notes

- Message copy and button labels are centralized in `marco_bot/messages.py` and `marco_bot/constants.py`.
- The reply-keyboard cooldown label is computed from `users.post_ad_cooldown_until`.
- Today's global total resets by the configured `TIMEZONE` date.
- Long polling is used for simple hosting. For production, run it behind a process manager and make sure your Telegram bot/channel/group permissions are correct.
