# Railway Deployment

This repo is ready to deploy from GitHub to Railway.

## 1. Push To GitHub

Upload the contents of this folder to a new GitHub repository.

Do not upload private env files. `.gitignore` blocks `.env`, `.env.*`, and private backup files while allowing the safe examples.

## 2. Create Railway Project

1. New Project
2. Deploy from GitHub repo
3. Add PostgreSQL
4. Open Variables
5. Paste the variables from your private Railway env backup

Railway provides `DATABASE_URL` from Postgres. Keep that variable as Railway gives it; the bot converts `postgres://...` into the async SQLAlchemy URL internally.

## 3. Required Variables

```env
BOT_TOKEN=
ADMIN_IDS=
ADMIN_REVIEW_CHAT_ID=
ADS_CHANNEL_ID=
ADS_GROUP_ID=
DATABASE_URL=
```

## 4. Wallet Addresses

You can either use direct variables:

```env
TRX_ADDRESS=
BNB_ADDRESS=
ETH_ADDRESS=
```

or one JSON variable:

```env
DEPOSIT_ADDRESSES_JSON={"USDT":{"TRC20":"...","BEP20":"...","ERC20":"..."},"ETH":{"BEP20":"...","ERC20":"..."}}
```

Direct variables are merged automatically:

- `TRX_ADDRESS` -> `USDT/TRC20`
- `BNB_ADDRESS` -> `USDT/BEP20` and `ETH/BEP20`
- `ETH_ADDRESS` -> `USDT/ERC20` and `ETH/ERC20`

## 5. Optional API Variables

These are stored in config for future payment auto-checking features:

```env
ETHERSCAN_API_KEY=
INFURA_URL=
INFURA_API_KEY=
TRONGRID_API_KEY=
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=
```

The 12-word wallet phrase is not required and should not be deployed.

## 6. Start Command

Railway uses `railway.json`:

```bash
python -m marco_bot.main
```

The bot uses Telegram long polling, so no web port is required.
