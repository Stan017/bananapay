"""
qr_generator.py — Generador de QR con branding BananaPay.
Produce imágenes PNG en memoria (sin tocar disco).

Requiere: qrcode[pil] y Pillow
"""

import io
import os


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_font(size: int):
    """
    Carga una fuente TrueType del sistema con fallback al bitmap default de Pillow.
    Prueba rutas comunes en Windows, Linux y macOS.
    """
    from PIL import ImageFont

    candidates = [
        # Windows
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        # macOS
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
        "/Library/Fonts/Arial.ttf",
    ]

    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    # Último recurso: fuente bitmap de Pillow (fea pero funcional)
    return ImageFont.load_default()


def _draw_text_centered(draw, y: int, text: str, font, color: str, canvas_w: int) -> int:
    """
    Dibuja texto centrado horizontalmente.
    Retorna el Y final (útil para apilar líneas).
    Compatible con fuentes TrueType y bitmap.
    """
    try:
        # TrueType: usa anchor "mt" (middle-top)
        draw.text((canvas_w // 2, y), text, font=font, fill=color, anchor="mt")
        bbox = draw.textbbox((canvas_w // 2, y), text, font=font, anchor="mt")
        return bbox[3]  # y_bottom
    except (TypeError, AttributeError):
        # Bitmap font: calcula posición manual
        try:
            bbox = font.getbbox(text)
            text_w = bbox[2] - bbox[0]
        except Exception:
            text_w = len(text) * 7  # estimación
        x = max(0, (canvas_w - text_w) // 2)
        draw.text((x, y), text, font=font, fill=color)
        return y + 14


# ─── Función principal ────────────────────────────────────────────────────────

def generate_payment_qr(
    data: str,
    title: str = "BananaPay",
    subtitle: str = "",
    username: str = "",
) -> bytes:
    """
    Genera un QR de cobro con branding BananaPay y lo retorna como PNG en bytes.

    Args:
        data:     Contenido del QR (dirección TRC-20, URI bananapay://, etc.)
        title:    Título encima del QR (ej. "🍌 Cobrar con BananaPay").
        subtitle: Texto informativo debajo del QR (ej. "Red TRC-20 · USDT").
        username: Nombre completo del usuario — se muestra en gris bajo el título.

    Returns:
        PNG como bytes listo para subir a Meta Cloud API.

    Raises:
        ImportError: Si qrcode o Pillow no están instalados.
    """
    import qrcode
    import qrcode.constants
    from PIL import Image, ImageDraw

    # ── Paleta ────────────────────────────────────────────────────────────────
    YELLOW = "#facc15"
    BG     = "#ffffff"
    DARK   = "#1c1c1e"
    GRAY   = "#6e6e73"

    # ── Módulo QR ─────────────────────────────────────────────────────────────
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)

    qr_pil = qr.make_image(fill_color=DARK, back_color=BG).convert("RGB")
    qr_w, qr_h = qr_pil.size   # siempre cuadrado

    # ── Dimensiones del canvas ────────────────────────────────────────────────
    SIDE_PAD = 28
    TOP_BAR  = 10      # barra amarilla superior
    BOT_BAR  = 10      # barra amarilla inferior
    TITLE_H  = 32      # espacio para el título
    USER_H   = 24      # espacio para el nombre de usuario (0 si no hay)
    QR_PAD   = 16      # padding vertical entre header y QR
    SUB_H    = 32      # espacio para subtítulo (0 si no hay)
    INNER_PAD = 12     # padding interior del marco del QR

    # Marco del QR (fondo gris muy claro)
    frame_w = qr_w + INNER_PAD * 2
    frame_h = qr_h + INNER_PAD * 2

    header_h = TOP_BAR + TITLE_H + (USER_H if username else 0) + QR_PAD
    footer_h = (SUB_H if subtitle else 16) + BOT_BAR

    canvas_w = frame_w + SIDE_PAD * 2
    canvas_h = header_h + frame_h + footer_h

    canvas = Image.new("RGB", (canvas_w, canvas_h), BG)
    draw   = ImageDraw.Draw(canvas)

    # ── Barras decorativas ────────────────────────────────────────────────────
    draw.rectangle([0, 0, canvas_w, TOP_BAR], fill=YELLOW)
    draw.rectangle([0, canvas_h - BOT_BAR, canvas_w, canvas_h], fill=YELLOW)

    # ── Fonts ─────────────────────────────────────────────────────────────────
    font_title = _load_font(18)
    font_user  = _load_font(14)
    font_sub   = _load_font(13)

    # ── Título ────────────────────────────────────────────────────────────────
    cursor_y = TOP_BAR + 8
    cursor_y = _draw_text_centered(draw, cursor_y, title, font_title, DARK, canvas_w)

    # Nombre de usuario
    if username:
        cursor_y += 4
        _draw_text_centered(draw, cursor_y, username, font_user, GRAY, canvas_w)

    # ── Marco del QR ─────────────────────────────────────────────────────────
    frame_x = SIDE_PAD
    frame_y = header_h
    draw.rectangle(
        [frame_x, frame_y, frame_x + frame_w, frame_y + frame_h],
        fill="#f2f2f7",
        outline="#e5e5ea",
        width=1,
    )

    # ── QR pegado dentro del marco ────────────────────────────────────────────
    qr_x = frame_x + INNER_PAD
    qr_y = frame_y + INNER_PAD
    canvas.paste(qr_pil, (qr_x, qr_y))

    # ── Subtítulo ─────────────────────────────────────────────────────────────
    if subtitle:
        sub_y = frame_y + frame_h + 10
        _draw_text_centered(draw, sub_y, subtitle, font_sub, GRAY, canvas_w)

    # ── Serializar ────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()
