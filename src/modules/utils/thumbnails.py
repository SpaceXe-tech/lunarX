#  Copyright (c) 2025 AshokShau
#  Licensed under the GNU AGPL v3.0: https://www.gnu.org/licenses/agpl-3.0.html
#  Part of the TgMusicBot project. All rights reserved where applicable.

import asyncio
from io import BytesIO
import os

import httpx
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from aiofiles.os import path as aiopath
import aiofiles.os

from src.helpers import CachedTrack
from src.logger import LOGGER

FONTS = {
    "cfont": ImageFont.truetype("src/modules/utils/cfont.ttf", 15),
    "dfont": ImageFont.truetype("src/modules/utils/font2.otf", 12),
    "nfont": ImageFont.truetype("src/modules/utils/font.ttf", 10),
    "tfont": ImageFont.truetype("src/modules/utils/font.ttf", 20),
}


def resize_youtube_thumbnail(img: Image.Image) -> Image.Image:
    """
    Resize a YouTube thumbnail to 640x640 while keeping important content.

    It crops the center of the image after resizing.
    """
    try:
        target_size = 640
        aspect_ratio = img.width / img.height

        if aspect_ratio > 1:
            new_width = int(target_size * aspect_ratio)
            new_height = target_size
        else:
            new_width = target_size
            new_height = int(target_size / aspect_ratio)

        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Crop to 640x640 (center crop)
        left = (img.width - target_size) // 2
        top = (img.height - target_size) // 2
        right = left + target_size
        bottom = top + target_size

        return img.crop((left, top, right, bottom))
    except Exception as e:
        LOGGER.error("YouTube thumbnail resize error: %s", e)
        raise


def resize_jiosaavn_thumbnail(img: Image.Image) -> Image.Image:
    """
    Resize a JioSaavn thumbnail from 500x500 to 600x600.

    It upscales the image while preserving quality.
    """
    try:
        target_size = 600
        img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
        return img
    except Exception as e:
        LOGGER.error("JioSaavn thumbnail resize error: %s", e)
        raise


async def fetch_image(url: str) -> Image.Image | None:
    """
    Fetches an image from the given URL, resizes it if necessary for JioSaavn and
    YouTube thumbnails, and returns the loaded image as a PIL Image object, or None on
    failure.

    Args:
        url (str): URL of the image to fetch.

    Returns:
        Image.Image | None: The fetched and possibly resized image, or None if the fetch fails.
    """
    if not url:
        LOGGER.warning("No URL provided for image fetch")
        return None

    LOGGER.debug("Fetching image from URL: %s", url)
    async with httpx.AsyncClient() as client:
        for attempt in range(3):  # Retry up to 3 times
            try:
                if url.startswith("https://is1-ssl.mzstatic.com"):
                    url = url.replace("500x500bb.jpg", "600x600bb.jpg")
                response = await client.get(url, timeout=10)  # Increased timeout
                response.raise_for_status()
                img = Image.open(BytesIO(response.content)).convert("RGBA")
                if url.startswith("https://i.ytimg.com"):
                    img = resize_youtube_thumbnail(img)
                elif url.startswith("http://c.saavncdn.com") or url.startswith(
                    "https://i1.sndcdn"
                ):
                    img = resize_jiosaavn_thumbnail(img)
                LOGGER.debug("Image fetched successfully from %s", url)
                return img
            except Exception as e:
                LOGGER.error("Image loading error (attempt %d): %s", attempt + 1, e)
                if attempt < 2:
                    await asyncio.sleep(1)  # Wait before retry
                continue
        LOGGER.error("Failed to fetch image after 3 attempts: %s", url)
        return None


def clean_text(text: str, limit: int = 17) -> str:
    """
    Sanitizes and truncates text to fit within the limit.
    """
    try:
        text = text.strip()
        return f"{text[:limit - 3]}..." if len(text) > limit else text
    except Exception as e:
        LOGGER.error("Text cleaning error: %s", e)
        return "Unknown"


def add_controls(img: Image.Image) -> Image.Image:
    """
    Adds blurred background effect and overlay controls.
    """
    try:
        img = img.filter(ImageFilter.GaussianBlur(13))
        box = (120, 120, 520, 480)

        region = img.crop(box)
        if not os.path.exists("src/modules/utils/controls.png"):
            LOGGER.error("Controls image not found: src/modules/utils/controls.png")
            raise FileNotFoundError("Controls image not found")
        controls = Image.open("src/modules/utils/controls.png").convert("RGBA")
        dark_region = ImageEnhance.Brightness(region).enhance(0.5)

        mask = Image.new("L", dark_region.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, box[2] - box[0], box[3] - box[1]), 40, fill=255
        )

        img.paste(dark_region, box, mask)
        img.paste(controls, (135, 305), controls)
        return img
    except Exception as e:
        LOGGER.error("Error in add_controls: %s", e)
        raise


def make_sq(image: Image.Image, size: int = 125) -> Image.Image:
    """
    Crops an image into a rounded square.
    """
    try:
        width, height = image.size
        side_length = min(width, height)
        crop = image.crop(
            (
                (width - side_length) // 2,
                (height - side_length) // 2,
                (width + side_length) // 2,
                (height + side_length) // 2,
            )
        )
        resize = crop.resize((size, size), Image.Resampling.LANCZOS)

        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, size, size), radius=30, fill=255)

        rounded = ImageOps.fit(resize, (size, size))
        rounded.putalpha(mask)
        return rounded
    except Exception as e:
        LOGGER.error("Error in make_sq: %s", e)
        raise


def get_duration(duration: int, time: str = "0:24") -> str:
    """
    Calculates remaining duration.
    """
    try:
        m1, s1 = divmod(duration, 60)
        m2, s2 = map(int, time.split(":"))
        sec = (m1 * 60 + s1) - (m2 * 60 + s2)
        _min, sec = divmod(sec, 60)
        return f"{_min}:{sec:02d}"
    except Exception as e:
        LOGGER.error("Duration calculation error: %s", e)
        return "0:00"


async def gen_thumb(song: CachedTrack) -> str:
    """
    Generates and saves a thumbnail for the song.
    """
    LOGGER.debug("Starting gen_thumb for track_id: %s", song.track_id)
    save_dir = f"database/photos/{song.track_id}.png"
    
    # Check if thumbnail already exists
    if await aiopath.exists(save_dir):
        LOGGER.debug("Thumbnail already exists at %s", save_dir)
        return save_dir

    try:
        # Ensure save directory exists
        os.makedirs("database/photos", exist_ok=True)
        
        title, artist = clean_text(song.name), clean_text(song.artist or "Spotify")
        duration = song.duration or 0

        # Fetch thumbnail
        thumb = await fetch_image(song.thumbnail)
        if not thumb:
            LOGGER.error("Failed to fetch thumbnail for track_id: %s", song.track_id)
            return ""

        # Process Image
        bg = add_controls(thumb)
        image = make_sq(thumb)

        # Positions
        paste_x, paste_y = 145, 155
        bg.paste(image, (paste_x, paste_y), image)

        draw = ImageDraw.Draw(bg)
        
        # Engraved effect for "⎚ Bɪʟʟ∆ Mᴜsɪᴄ" on the right upward side
        text = "⎚ Bɪʟʟ∆ Mᴜsɪᴄ"
        text_x, text_y = 450, 100  # Right upward side
        shadow_offset = 2  # Offset for engraved effect
        shadow_color = (50, 50, 50)  # Darker color for shadow
        main_color = (255, 255, 255)  # White for main text
        bold_font = ImageFont.truetype("src/modules/utils/font.ttf", 20)  # tfont for bold effect

        # Draw shadow text for engraved effect
        draw.text((text_x + shadow_offset, text_y + shadow_offset), text, shadow_color, font=bold_font)
        # Draw main text
        draw.text((text_x, text_y), text, main_color, font=bold_font)
        
        draw.text((285, 200), title, (255, 255, 255), font=FONTS["tfont"])
        draw.text((287, 235), artist, (255, 255, 255), font=FONTS["cfont"])
        draw.text((478, 321), get_duration(duration), (192, 192, 192), font=FONTS["dfont"])

        # Save the image
        await asyncio.to_thread(bg.save, save_dir, format="PNG")
        if await aiopath.exists(save_dir):
            LOGGER.debug("Thumbnail saved successfully at %s", save_dir)
            return save_dir
        else:
            LOGGER.error("Failed to save thumbnail at %s", save_dir)
            return ""
    except Exception as e:
        LOGGER.error("Error in gen_thumb for track_id %s: %s", song.track_id, e)
        return ""
    finally:
        LOGGER.debug("Completed gen_thumb for track_id: %s", song.track_id)
