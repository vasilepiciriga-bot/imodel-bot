from __future__ import annotations

import io
import logging
import random
from typing import Optional, List, Tuple

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
)

from bot.config import settings
from prompts import PROMPT_INTERIOR_PRO, NEGATIVE_PROMPT, AUTO_CLEAN_HINT
from providers.replicate_client import run_img2img, run_upscale, detect_small_objects, inpaint
from postprocess.local_ops import fix_verticals, gentle_denoise, micro_contrast, apply_white_balance
from utils.image_io import bytes_to_pil, pil_to_bytes, maybe_downscale
from utils.mask_grid import make_grid_overlay, cells_to_mask
from utils.logging import StageTimer


router = Router()


class St(StatesGroup):
    idle = State()
    awaiting_photo = State()
    awaiting_cells = State()


def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏨 Интерьер PRO", callback_data="interior_pro")]
    ])


def kb_settings(auto_clean: bool, wb: str, seed: int) -> InlineKeyboardMarkup:
    ac_label = "🧹 Авто-очистка: ВКЛ" if auto_clean else "🧹 Авто-очистка: ВЫКЛ"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ac_label, callback_data="toggle_auto")],
        [InlineKeyboardButton(text="🧽 Ручная очистка (выбор областей)", callback_data="manual_clean")],
        [InlineKeyboardButton(text="Тёплый WB", callback_data="wb_warm"),
         InlineKeyboardButton(text="Нейтральный WB", callback_data="wb_neutral"),
         InlineKeyboardButton(text="Холодный WB", callback_data="wb_cool")],
        [InlineKeyboardButton(text=f"🔁 Повторить (seed={seed})", callback_data="rerun_same"),
         InlineKeyboardButton(text="🔁 (seed+1)", callback_data="rerun_plus"),
         InlineKeyboardButton(text="🔁 (seed-1)", callback_data="rerun_minus")],
    ])


def kb_grid_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Применить", callback_data="apply_inpaint")],
        [InlineKeyboardButton(text="↩️ Ещё области", callback_data="more_cells")],
        [InlineKeyboardButton(text="✖️ Отмена", callback_data="cancel_inpaint")],
    ])


@router.message(Command("start"))
async def on_start(m: Message, state: FSMContext):
    await state.set_state(St.idle)
    await m.answer("Добро пожаловать! Нажмите кнопку, чтобы начать:", reply_markup=kb_main())


@router.callback_query(F.data == "interior_pro")
async def cb_interior(c: CallbackQuery, state: FSMContext):
    seed = 123456
    await state.update_data(auto_clean=True, wb="neutral", seed=seed, last=None, last_src=None)
    await c.message.answer("Режим Интерьер PRO. Пришлите фото интерьера.",
                           reply_markup=kb_settings(True, "neutral", seed))
    await state.set_state(St.awaiting_photo)
    await c.answer()


@router.callback_query(F.data == "toggle_auto")
async def cb_toggle_auto(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    auto = not bool(data.get("auto_clean", True))
    await state.update_data(auto_clean=auto)
    await c.message.edit_reply_markup(reply_markup=kb_settings(auto, data.get("wb", "neutral"), int(data.get("seed", 123456))))
    await c.answer()


@router.callback_query(F.data.startswith("wb_"))
async def cb_wb(c: CallbackQuery, state: FSMContext):
    wb = c.data.split("wb_")[-1]
    data = await state.get_data()
    await state.update_data(wb=wb)
    await c.message.edit_reply_markup(reply_markup=kb_settings(bool(data.get("auto_clean", True)), wb, int(data.get("seed", 123456))))
    await c.answer()


@router.callback_query(F.data.startswith("rerun_"))
async def cb_rerun(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    seed = int(data.get("seed", 123456))
    if c.data.endswith("same"):
        pass
    elif c.data.endswith("plus"):
        seed += 1
    elif c.data.endswith("minus"):
        seed -= 1
    await state.update_data(seed=seed)
    await c.message.edit_reply_markup(reply_markup=kb_settings(bool(data.get("auto_clean", True)), data.get("wb", "neutral"), seed))
    await c.answer("Обновлён seed. Пришлите фото ещё раз для повтора.")


@router.message(F.photo, St.awaiting_photo)
async def on_photo(m: Message, state: FSMContext):
    file = await m.bot.get_file(m.photo[-1].file_id)
    b = await m.bot.download_file(file.file_path)
    img_bytes = b.read()
    data = await state.get_data()
    await state.update_data(last_src=img_bytes)

    await m.answer("Этап 1/3: улучшение качества…")
    seed = int(data.get("seed", 123456))
    wb = str(data.get("wb", "neutral"))
    auto_clean = bool(data.get("auto_clean", True))

    # Downscale if huge
    pil_in = maybe_downscale(bytes_to_pil(img_bytes), max_side=3500)
    img_bytes0 = pil_to_bytes(pil_in, quality=95)

    # A) Img2Img
    t = StageTimer("img2img")
    outA = run_img2img(
        prompt=PROMPT_INTERIOR_PRO,
        negative=NEGATIVE_PROMPT,
        image_bytes=img_bytes0,
        strength=0.20,
        guidance=6.0,
        seed=seed,
        scheduler="DPM++ Karras",
        control=None,
    )
    t.done()

    # B) Upscale x2 + local ops
    await m.answer("Этап 2/3: апскейл…")
    t = StageTimer("upscale")
    outB = run_upscale(outA, scale=2)
    t.done()

    imgB = bytes_to_pil(outB)
    await m.answer("Этап 3/3: финальная коррекция…")
    imgB = fix_verticals(imgB)
    imgB = gentle_denoise(imgB)
    imgB = micro_contrast(imgB, amount=0.15)
    imgB = apply_white_balance(imgB, wb if wb in ("warm", "neutral", "cool") else "neutral")

    result_bytes = pil_to_bytes(imgB, quality=92)

    # C1) Auto cleanup (optional)
    if auto_clean:
        await m.answer("Очистка мелочей: авто-детект…")
        polys = detect_small_objects(result_bytes, classes=["cloth", "cable", "bag", "cup", "bottle", "box", "paper"]) or []
        if polys:
            # Build mask from small polygons
            from PIL import Image, ImageDraw
            base = bytes_to_pil(result_bytes)
            w, h = base.size
            mask = Image.new("L", (w, h), 0)
            draw = ImageDraw.Draw(mask)
            total_area = w * h
            for poly in polys:
                if len(poly) < 3:
                    continue
                # area filter via bbox approximation
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                area_box = max(1, (max(xs) - min(xs)) * (max(ys) - min(ys)))
                if (area_box / total_area) <= settings.SMALL_OBJ_MAX_RATIO:
                    draw.polygon(poly, fill=255)
            m_bytes = io.BytesIO()
            mask.convert("RGB").save(m_bytes, format="PNG")
            m_bytes = m_bytes.getvalue()
            if max(mask.getextrema()) > 0:  # any mask
                result_bytes = inpaint(result_bytes, m_bytes)
        else:
            logging.warning("Auto-cleanup: no small objects detected")

    await state.update_data(last=result_bytes)
    await m.answer_photo(photo=result_bytes, caption="Готово ✅", reply_markup=kb_settings(auto_clean, wb, seed))


@router.callback_query(F.data == "manual_clean")
async def cb_manual_clean(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    src = data.get("last") or data.get("last_src")
    if not src:
        await c.answer("Сначала пришлите фото", show_alert=True)
        return
    img = bytes_to_pil(src)
    grid = make_grid_overlay(img, rows=settings.GRID_ROWS, cols=settings.GRID_COLS)
    await c.message.answer_photo(photo=pil_to_bytes(grid), caption="Укажите ячейки для очистки (например: B2, C2, C3)")
    await state.set_state(St.awaiting_cells)
    await c.answer()


@router.message(St.awaiting_cells, F.text)
async def on_cells(m: Message, state: FSMContext):
    data = await state.get_data()
    src = data.get("last") or data.get("last_src")
    if not src:
        await m.answer("Нет изображения в сессии. Пришлите фото.")
        await state.set_state(St.awaiting_photo)
        return
    img = bytes_to_pil(src)
    cells_raw = [t.strip() for t in m.text.split(',') if t.strip()]
    mask_img = cells_to_mask(img, cells_raw, rows=settings.GRID_ROWS, cols=settings.GRID_COLS, feather=8)
    buf = io.BytesIO()
    mask_img.save(buf, format="PNG")
    mask_b = buf.getvalue()

    # Preview
    try:
        preview = inpaint(pil_to_bytes(img), mask_b)
    except Exception as e:
        logging.exception("inpaint error: %s", e)
        await m.answer("Ошибка inpaint. Попробуйте другие ячейки.")
        return
    await state.update_data(pending_mask=mask_b, pending_preview=preview)
    await m.answer_photo(preview, caption="Предпросмотр очистки", reply_markup=kb_grid_actions())


@router.callback_query(F.data == "apply_inpaint")
async def cb_apply(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    preview = data.get("pending_preview")
    if not preview:
        await c.answer("Нет предпросмотра", show_alert=True)
        return
    await state.update_data(last=preview, pending_mask=None, pending_preview=None)
    await c.message.answer_photo(preview, caption="Готово ✅")
    await c.answer("Применено")
    await state.set_state(St.awaiting_photo)


@router.callback_query(F.data == "more_cells")
async def cb_more_cells(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    src = data.get("last") or data.get("last_src")
    if not src:
        await c.answer("Сначала пришлите фото", show_alert=True)
        return
    img = bytes_to_pil(src)
    grid = make_grid_overlay(img, rows=settings.GRID_ROWS, cols=settings.GRID_COLS)
    await c.message.answer_photo(photo=pil_to_bytes(grid), caption="Добавьте ячейки (например: A1, B3)")
    await state.set_state(St.awaiting_cells)
    await c.answer()


@router.callback_query(F.data == "cancel_inpaint")
async def cb_cancel(c: CallbackQuery, state: FSMContext):
    await state.update_data(pending_mask=None, pending_preview=None)
    await c.answer("Отменено")

