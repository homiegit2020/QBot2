from __future__ import annotations

import io
import json
import random
import string
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import BufferedInputFile, FSInputFile, Message, User as TelegramUser
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import states
from .config import Settings
from .models import CaptchaAttempt, GlobalStats, RateTier, RequiredGroup, User, UserSession, utcnow


def parse_decimal(value: str) -> Decimal | None:
    try:
        parsed = Decimal(value.strip().replace(",", ""))
    except (InvalidOperation, AttributeError):
        return None
    return parsed if parsed.is_finite() else None


def as_money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def format_remaining(until: datetime) -> str:
    remaining = until - datetime.utcnow()
    total_seconds = max(0, int(remaining.total_seconds()))
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    return f"{hours}h {minutes}m"


def random_code(length: int = 4) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def random_captcha() -> str:
    return "".join(random.choice(string.ascii_uppercase) for _ in range(random.randint(4, 5)))


async def get_or_create_user(session: AsyncSession, tg_user: TelegramUser) -> tuple[User, bool]:
    user = await session.get(User, tg_user.id)
    created = False
    if not user:
        created = True
        user = User(
            user_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
        )
        session.add(user)
        await session.flush()
    else:
        user.username = tg_user.username
        user.first_name = tg_user.first_name
    return user, created


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_or_create_session(session: AsyncSession, user_id: int) -> UserSession:
    bot_session = await session.get(UserSession, user_id)
    if not bot_session:
        bot_session = UserSession(user_id=user_id, state=states.IDLE)
        session.add(bot_session)
        await session.flush()
    return bot_session


def session_data(bot_session: UserSession) -> dict:
    return json.loads(bot_session.data_json or "{}")


def session_stack(bot_session: UserSession) -> list[str]:
    return json.loads(bot_session.stack_json or "[]")


async def set_state(
    session: AsyncSession,
    user_id: int,
    state: str,
    data: dict | None = None,
    stack: list[str] | None = None,
) -> UserSession:
    bot_session = await get_or_create_session(session, user_id)
    bot_session.state = state
    if data is not None:
        bot_session.data_json = json.dumps(data)
    if stack is not None:
        bot_session.stack_json = json.dumps(stack)
    return bot_session


async def transition(
    session: AsyncSession,
    user_id: int,
    new_state: str,
    data_updates: dict | None = None,
    push: bool = True,
) -> UserSession:
    bot_session = await get_or_create_session(session, user_id)
    data = session_data(bot_session)
    if data_updates:
        data.update(data_updates)
    stack = session_stack(bot_session)
    if push and bot_session.state != new_state:
        stack.append(bot_session.state)
    bot_session.state = new_state
    bot_session.data_json = json.dumps(data)
    bot_session.stack_json = json.dumps(stack)
    return bot_session


async def clear_flow(session: AsyncSession, user_id: int) -> UserSession:
    return await set_state(session, user_id, states.IDLE, data={}, stack=[])


async def pop_state(session: AsyncSession, user_id: int) -> UserSession:
    bot_session = await get_or_create_session(session, user_id)
    stack = session_stack(bot_session)
    previous = stack.pop() if stack else states.IDLE
    bot_session.state = previous
    bot_session.stack_json = json.dumps(stack)
    return bot_session


def generate_captcha_image(code: str) -> bytes:
    width, height = 260, 96
    image = Image.new("RGB", (width, height), (245, 248, 255))
    draw = ImageDraw.Draw(image)
    for _ in range(18):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        draw.line((x1, y1, x2, y2), fill=(random.randint(120, 210), random.randint(120, 210), random.randint(120, 210)), width=1)
    font = _captcha_font(44)
    x = 28
    for letter in code:
        y = random.randint(18, 34)
        color = (random.randint(20, 90), random.randint(40, 110), random.randint(90, 180))
        draw.text((x, y), letter, font=font, fill=color)
        x += random.randint(38, 46)
    image = image.filter(ImageFilter.SMOOTH_MORE)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _captcha_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


async def save_captcha(session: AsyncSession, user_id: int, code: str, reset_attempts: bool = True) -> CaptchaAttempt:
    attempt = await session.get(CaptchaAttempt, user_id)
    if not attempt:
        attempt = CaptchaAttempt(user_id=user_id, captcha_code=code, attempts=0, expires_at=utcnow() + timedelta(minutes=10))
        session.add(attempt)
    else:
        attempt.captcha_code = code
        if reset_attempts:
            attempt.attempts = 0
        attempt.expires_at = utcnow() + timedelta(minutes=10)
    return attempt


async def required_groups(session: AsyncSession) -> list[RequiredGroup]:
    result = await session.execute(select(RequiredGroup).order_by(RequiredGroup.label))
    return list(result.scalars().all())


async def user_is_in_required_groups(bot: Bot, session: AsyncSession, user_id: int) -> bool:
    groups = await required_groups(session)
    if not groups:
        return True
    for group in groups:
        try:
            member = await bot.get_chat_member(group.group_id, user_id)
        except (TelegramBadRequest, TelegramForbiddenError):
            continue
        if member.status in {"left", "kicked"}:
            return False
    return True


async def get_rate_tiers(session: AsyncSession, payment_mode: str) -> list[tuple[Decimal, Decimal | None, Decimal]]:
    result = await session.execute(
        select(RateTier)
        .where(RateTier.payment_mode == payment_mode)
        .order_by(RateTier.min_usd)
    )
    tiers = result.scalars().all()
    return [(tier.min_usd, tier.max_usd, tier.rate_inr) for tier in tiers]


async def rate_for_amount(session: AsyncSession, payment_mode: str, amount: Decimal) -> Decimal | None:
    for min_usd, max_usd, rate in await get_rate_tiers(session, payment_mode):
        if amount >= min_usd and (max_usd is None or amount <= max_usd):
            return rate
    return None


def deposit_address(settings: Settings, token: str, chain: str) -> str:
    configured = settings.deposit_addresses.get(token, {}).get(chain)
    if configured:
        return configured
    safe_chain = chain.replace(" ", "_").upper()
    return f"CONFIGURE_{token}_{safe_chain}_ADDRESS"


async def reset_today_if_needed(session: AsyncSession, stats: GlobalStats, timezone_name: str) -> None:
    tz = ZoneInfo(timezone_name)
    now_local = datetime.now(tz)
    if not stats.today_reset_at:
        stats.today_reset_at = utcnow()
        return
    reset_local_date = stats.today_reset_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz).date()
    if reset_local_date < now_local.date():
        stats.today_safe_sold_amount = Decimal("0.00")
        stats.today_reset_at = utcnow()
        await session.flush()


async def add_safe_sell_stats(session: AsyncSession, user: User, amount_usd: Decimal, timezone_name: str) -> None:
    stats = await session.get(GlobalStats, 1)
    if not stats:
        stats = GlobalStats(id=1)
        session.add(stats)
        await session.flush()
    await reset_today_if_needed(session, stats, timezone_name)
    user.safe_sells_completed += 1
    user.safe_sell_volume = as_money(user.safe_sell_volume + amount_usd)
    stats.total_safe_sold_amount = as_money(stats.total_safe_sold_amount + amount_usd)
    stats.today_safe_sold_amount = as_money(stats.today_safe_sold_amount + amount_usd)
    stats.total_deals_completed += 1


async def send_brand_message(
    bot: Bot,
    chat_id: int | str,
    text: str,
    settings: Settings,
    reply_markup=None,
) -> Message:
    if settings.banner_image_path:
        return await bot.send_photo(
            chat_id=chat_id,
            photo=FSInputFile(settings.banner_image_path),
            caption=text,
            reply_markup=reply_markup,
        )
    return await bot.send_photo(
        chat_id=chat_id,
        photo=brand_banner_file(),
        caption=text,
        reply_markup=reply_markup,
    )


def captcha_file(code: str) -> BufferedInputFile:
    return BufferedInputFile(generate_captcha_image(code), filename="captcha.png")


def brand_banner_file() -> BufferedInputFile:
    width, height = 1100, 520
    image = Image.new("RGB", (width, height), (9, 21, 35))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        shade = int(35 + (y / height) * 26)
        draw.line((0, y, width, y), fill=(9, shade, 45))

    title_font = _captcha_font(72)
    label_font = _captcha_font(34)
    small_font = _captcha_font(28)

    draw.rounded_rectangle((68, 64, width - 68, height - 64), radius=34, outline=(80, 220, 190), width=4)
    draw.ellipse((120, 110, 330, 320), fill=(232, 244, 255), outline=(80, 220, 190), width=8)
    draw.ellipse((160, 155, 290, 245), fill=(16, 38, 60), outline=(120, 230, 255), width=5)
    draw.rounded_rectangle((192, 304, 262, 410), radius=20, fill=(238, 246, 255), outline=(80, 220, 190), width=5)
    draw.polygon([(330, 250), (420, 290), (402, 405), (330, 448), (258, 405), (240, 290)], fill=(20, 165, 135), outline=(236, 255, 250))
    draw.text((306, 326), "✓", font=title_font, fill=(245, 255, 250))
    draw.rounded_rectangle((316, 98, 456, 154), radius=20, fill=(245, 255, 250))
    draw.text((342, 110), "Hello", font=small_font, fill=(9, 35, 45))

    draw.text((500, 128), "MARCO P2P BOT", font=title_font, fill=(245, 255, 250))
    draw.text((520, 244), "FAST        SAFE        SECURE", font=label_font, fill=(122, 235, 209))
    draw.text((580, 336), "Safe • Secure • Fast", font=label_font, fill=(255, 215, 120))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return BufferedInputFile(output.getvalue(), filename="marco-p2p-banner.png")


def safe_sell_banner_file() -> BufferedInputFile:
    width, height = 1100, 430
    image = Image.new("RGB", (width, height), (8, 25, 18))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        green = int(40 + (y / height) * 115)
        draw.line((0, y, width, y), fill=(10, green, 34))

    title_font = _captcha_font(70)
    label_font = _captcha_font(34)
    small_font = _captcha_font(28)

    draw.rounded_rectangle((50, 42, width - 50, height - 42), radius=28, outline=(142, 255, 125), width=4)
    draw.text((78, 82), "MARCO SAFE SELL", font=title_font, fill=(222, 255, 215))
    draw.text((82, 178), "Instant Payments  •  Verified Funds  •  UPI | IMPS | CDM", font=label_font, fill=(255, 245, 185))
    draw.text((82, 252), "Fund Purity & Safety - Guaranteed by MARCO", font=label_font, fill=(235, 255, 235))
    draw.text((82, 318), "Each penny you receive is 100% authentic & Guaranteed!", font=small_font, fill=(205, 240, 215))
    draw.ellipse((865, 102, 1015, 252), fill=(235, 255, 240), outline=(120, 250, 145), width=8)
    draw.rounded_rectangle((905, 235, 976, 342), radius=18, fill=(235, 255, 240), outline=(120, 250, 145), width=5)
    draw.text((900, 128), "₹", font=title_font, fill=(12, 110, 44))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return BufferedInputFile(output.getvalue(), filename="marco-safe-sell-banner.png")


def public_username(user: User) -> str:
    return user.username or str(user.user_id)


def telegram_username(tg_user: TelegramUser) -> str:
    return tg_user.username or str(tg_user.id)
