#  Copyright (c) 2025 AshokShau
#  Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
#  Part of the TgMusicBot project. All rights reserved where applicable.

import inspect
import io
import os
import platform
import re
import socket
import sys
import traceback
import uuid
from datetime import datetime, timedelta
from html import escape
from sys import version as pyver
from typing import Any, Optional, Tuple, Union

import psutil
from meval import meval
from ntgcalls import __version__ as ntgver
from pyrogram import __version__ as pyrover
from pytdbot import Client, types
from pytdbot import __version__ as py_td_ver
from pytgcalls import __version__ as pytgver

from src import StartTime
from src.config import OWNER_ID, DEVS, LOGGER_ID
from src.helpers import call
from src.helpers import chat_cache, get_string
from src.helpers import db
from src.modules.utils import Filter
from src.modules.utils.play_helpers import del_msg, extract_argument


def format_exception(
    exp: BaseException, tb: Optional[list[traceback.FrameSummary]] = None
) -> str:
    """
    Formats an exception traceback as a string, similar to the Python interpreter.
    """

    if tb is None:
        tb = traceback.extract_tb(exp.__traceback__)

    # Replace absolute paths with relative paths
    cwd = os.getcwd()
    for frame in tb:
        if cwd in frame.filename:
            frame.filename = os.path.relpath(frame.filename)

    stack = "".join(traceback.format_list(tb))
    msg = str(exp)
    if msg:
        msg = f": {msg}"

    return f"Traceback (most recent call last):\n{stack}{type(exp).__name__}{msg}"


@Client.on_message(filters=Filter.command("eval"))
async def exec_eval(c: Client, m: types.Message) -> None:
    """
    Run python code.
    """
    if int(m.from_id) != OWNER_ID:
        return None

    text = m.text.split(None, 1)
    if len(text) <= 1:
        reply = await m.reply_text("Usage: /eval &lt code &gt")
        if isinstance(reply, types.Error):
            c.logger.warning(reply.message)
        return None

    code = text[1]
    out_buf = io.StringIO()

    async def _eval() -> Tuple[str, Optional[str]]:
        async def send(
            *args: Any, **kwargs: Any
        ) -> Union["types.Error", "types.Message"]:
            return await m.reply_text(*args, **kwargs)

        def _print(*args: Any, **kwargs: Any) -> None:
            if "file" not in kwargs:
                kwargs["file"] = out_buf
                return print(*args, **kwargs)
            return None

        eval_vars = {
            "loop": c.loop,
            "client": c,
            "stdout": out_buf,
            "c": c,
            "m": m,
            "msg": m,
            "types": types,
            "send": send,
            "print": _print,
            "inspect": inspect,
            "os": os,
            "re": re,
            "sys": sys,
            "traceback": traceback,
            "uuid": uuid,
            "io": io,
            "db": db,
            "call": call,
        }

        try:
            return "", await meval(code, globals(), **eval_vars)
        except Exception as e:
            first_snip_idx = -1
            tb = traceback.extract_tb(e.__traceback__)
            for i, frame in enumerate(tb):
                if frame.filename == "<string>" or frame.filename.endswith("ast.py"):
                    first_snip_idx = i
                    break

            # Re-raise exception if it wasn't caused by the snippet
            if first_snip_idx == -1:
                raise e

            # Return formatted stripped traceback
            stripped_tb = tb[first_snip_idx:]
            formatted_tb = format_exception(e, tb=stripped_tb)
            return "⚠️ Error:\n\n", formatted_tb

    prefix, result = await _eval()

    if not out_buf.getvalue() or result is not None:
        print(result, file=out_buf)

    out = out_buf.getvalue()
    if out.endswith("\n"):
        out = out[:-1]

    result = f"""{prefix}<b>In:</b>
<pre language="python">{escape(code)}</pre>
<b>ᴏᴜᴛ:</b>
<pre language="python">{escape(out)}</pre>"""

    if len(result) > 2000:
        filename = f"database/{uuid.uuid4().hex}.txt"
        with open(filename, "w", encoding="utf-8") as file:
            file.write(out)

        caption = f"""{prefix}<b>ᴇᴠᴀʟ:</b>
    <pre language="python">{escape(code)}</pre>
    """
        reply = await m.reply_document(
            document=types.InputFileLocal(filename),
            caption=caption,
            disable_notification=True,
            parse_mode="html",
        )
        if isinstance(reply, types.Error):
            c.logger.warning(reply.message)

        if os.path.exists(filename):
            os.remove(filename)

        return None

    reply = await m.reply_text(str(result), parse_mode="html")
    if isinstance(reply, types.Error):
        c.logger.warning(reply.message)
    return None


@Client.on_message(filters=Filter.command(["activevc", "av"]))
async def active_vc(c: Client, message: types.Message) -> None:
    """
    Get active voice chats.
    """
    if message.from_id not in DEVS:
        await del_msg(message)
        return None

    active_chats = chat_cache.get_active_chats()
    if not active_chats:
        reply = await message.reply_text("No active voice chats.")
        if isinstance(reply, types.Error):
            c.logger.warning(reply.message)

        return None

    text = f"🎵 <b>Active Voice Chats</b> ({len(active_chats)}):\n\n"

    for chat_id in active_chats:
        queue_length = chat_cache.count(chat_id)
        if current_song := chat_cache.get_current_song(chat_id):
            song_info = f"🎶 <b>Now Playing:</b> <a href='{current_song.url}'>{current_song.name}</a> - {current_song.artist} ({current_song.duration}s)"
        else:
            song_info = "🔇 No song playing."

        text += (
            f"➤ <b>Chat ID:</b> <code>{chat_id}</code>\n"
            f"📌 <b>Queue Size:</b> {queue_length}\n"
            f"{song_info}\n\n"
        )

    if len(text) > 4096:
        text = f"🎵 <b>Active Voice Chats</b> ({len(active_chats)})"

    reply = await message.reply_text(text, disable_web_page_preview=True)
    if isinstance(reply, types.Error):
        c.logger.warning(reply.message)
        await message.reply_text(reply.message)
    return None


@Client.on_message(filters=Filter.command("logger"))
async def logger(c: Client, message: types.Message) -> None:
    """
    Enable or disable logging.
    """
    if message.from_id not in DEVS:
        await del_msg(message)
        return

    if not LOGGER_ID or LOGGER_ID == 0:
        reply = await message.reply_text("Please set LOGGER_ID in .env first.")
        if isinstance(reply, types.Error):
            c.logger.warning(reply.message)
        return

    lang = await db.get_lang(message.chat_id)
    args = extract_argument(message.text)
    enabled = await db.get_logger_status(c.me.id)

    if not args:
        status = (
            get_string("enabled", lang) if enabled else get_string("disabled", lang)
        )
        reply = await message.reply_text(
            get_string("logger_usage_status", lang).format(status=status)
        )
        if isinstance(reply, types.Error):
            c.logger.warning(reply.message)
        return

    arg = args.lower()
    if arg in ["on", "enable"]:
        await db.set_logger_status(c.me.id, True)
        reply = await message.reply_text(get_string("logger_enabled", lang))
        if isinstance(reply, types.Error):
            c.logger.warning(reply.message)
        return
    if arg in ["off", "disable"]:
        await db.set_logger_status(c.me.id, False)
        reply = await message.reply_text(get_string("logger_disabled", lang))
        if isinstance(reply, types.Error):
            c.logger.warning(reply.message)
        return

    await message.reply_text(get_string("logger_invalid_usage", lang).format(arg=args))


@Client.on_message(filters=Filter.command(["autoend", "auto_end"]))
async def auto_end(c: Client, message: types.Message) -> None:
    if message.from_id not in DEVS:
        await del_msg(message)
        return

    args = extract_argument(message.text)

    if not args:
        status = await db.get_auto_end(c.me.id)
        status_text = "enabled ✅" if status else "disabled ❌"
        reply = await message.reply_text(
            f"<b>Auto End</b> is currently <b>{status_text}</b>.\n\n"
            "When enabled, the bot will automatically end group voice chats "
            "if no users are listening. Useful for saving resources and keeping chats clean.",
            disable_web_page_preview=True,
        )
        if isinstance(reply, types.Error):
            c.logger.warning(reply.message)
        return

    args = args.lower()
    if args in ["on", "enabled"]:
        await db.set_auto_end(c.me.id, True)
        reply = await message.reply_text("✅ <b>Auto End</b> has been <b>enabled</b>.")
    elif args in ["off", "disabled"]:
        await db.set_auto_end(c.me.id, False)
        reply = await message.reply_text("❌ <b>Auto End</b> has been <b>disabled</b>.")
    else:
        reply = await message.reply_text(
            f"⚠️ Unknown argument: <b>{args}</b>\nUse <code>/autoend on</code> or <code>/autoend off</code>.",
            disable_web_page_preview=True,
        )
    if isinstance(reply, types.Error):
        c.logger.warning(reply.message)


@Client.on_message(filters=Filter.command(["clearass", "clearallassistants"]))
async def clear_all_assistants(c: Client, message: types.Message) -> None:
    if message.from_id not in DEVS:
        await del_msg(message)
        return

    count = await db.clear_all_assistants()
    c.logger.info(
        "Cleared assistants from %s chats by command from %s", count, message.from_id
    )
    reply = await message.reply_text(f"♻️ Cleared assistants from {count} chats")
    if isinstance(reply, types.Error):
        c.logger.warning(reply.message)
    return


@Client.on_message(filters=Filter.command("logs"))
async def logs(c: Client, message: types.Message) -> None:
    if message.from_id not in DEVS:
        await del_msg(message)
        return

    reply = await message.reply_document(
        document=types.InputFileLocal("bot.log"),
        disable_notification=True,
    )
    if isinstance(reply, types.Error):
        c.logger.warning(reply.message)
