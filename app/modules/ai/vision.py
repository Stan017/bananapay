"""
vision.py — Análisis de comprobantes con Claude Vision
═══════════════════════════════════════════════════════
Recibe los bytes de una imagen de comprobante bancario y le pregunta
a Claude qué ve.  Devuelve un VisionResult con:

  verdict   : "approved" | "rejected" | "review_needed"
  confidence: 0.0–1.0
  reason    : texto libre para el log / panel de admin
  amount    : monto detectado en la imagen (o None)
  bank      : banco detectado (o None)
  reference : número de referencia / transacción (o None)
  tx_date   : fecha detectada en el comprobante (o None)
"""

from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass, field
from decimal import Decimal

import anthropic

from app.utils.logger import get_logger

logger = get_logger(__name__)

# ─── Modelo ──────────────────────────────────────────────────────────────────
_MODEL = "claude-haiku-4-5"   # rápido y barato para análisis de imágenes

# ─── Prompt ──────────────────────────────────────────────────────────────────
_SYSTEM = """Eres un auditor financiero experto en verificar comprobantes de transferencia bancaria.
Tu única función es analizar la imagen y responder SIEMPRE con JSON puro, sin texto adicional, sin markdown.

Esquema de respuesta obligatorio:
{
  "verdict":    "approved" | "rejected" | "review_needed",
  "confidence": <float 0.0-1.0>,
  "reason":     "<explicación breve en español>",
  "amount":     <número decimal o null>,
  "bank":       "<nombre del banco o null>",
  "reference":  "<código/número de transacción o null>",
  "tx_date":    "<fecha YYYY-MM-DD o null>"
}

Reglas de veredicto:
- "approved"      → imagen clara, comprobante legítimo, monto y fecha visibles
- "rejected"      → imagen falsa, recortada, de otro depósito, ilegible o no es un comprobante
- "review_needed" → hay dudas razonables, imagen parcial o datos inconsistentes

Devuelve SOLO el JSON. Nada más."""


@dataclass
class VisionResult:
    verdict: str                      # "approved" | "rejected" | "review_needed"
    confidence: float = 0.0
    reason: str = ""
    amount: Decimal | None = None
    bank: str | None = None
    reference: str | None = None
    tx_date: str | None = None
    raw_response: str = field(default="", repr=False)

    @property
    def is_approved(self) -> bool:
        return self.verdict == "approved" and self.confidence >= 0.80

    @property
    def is_rejected(self) -> bool:
        return self.verdict == "rejected" and self.confidence >= 0.75

    @property
    def needs_review(self) -> bool:
        return not self.is_approved and not self.is_rejected


_MAX_ATTEMPTS = 2   # 1 intento + 1 reintento
_RETRY_DELAY  = 2   # segundos entre intentos


def _parse_raw(raw: str) -> dict:
    """Quita markdown si Claude lo agrega y parsea el JSON. Lanza JSONDecodeError si falla."""
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw.strip())
        raw = raw.strip()
    return json.loads(raw)


def analyze_voucher(
    image_bytes: bytes,
    mime_type: str,
    declared_amount: Decimal | None = None,
) -> VisionResult:
    """
    Analiza un comprobante bancario usando Claude Vision.

    Args:
        image_bytes:     Bytes de la imagen.
        mime_type:       MIME type (image/jpeg, image/png, image/webp).
        declared_amount: Monto que el usuario declaró depositar (para validación cruzada).

    Returns:
        VisionResult con el veredicto de Claude.

    Reintentos:
        Hasta 2 intentos ante JSON malformado o errores transitorios de API
        (429, 5xx, red). No reintenta ante errores 4xx del cliente.
    """
    # Claude Vision solo acepta estos tipos
    _ALLOWED = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if mime_type not in _ALLOWED:
        mime_type = "image/jpeg"

    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    user_text = "Analiza este comprobante de depósito bancario."
    if declared_amount is not None:
        user_text += f" El usuario declaró depositar ${declared_amount:.2f} USD."

    from app.config import settings
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    messages_payload = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": b64,
                    },
                },
                {"type": "text", "text": user_text},
            ],
        }
    ]

    last_exc: Exception | None = None
    raw: str = ""

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = client.messages.create(
                model=_MODEL,
                max_tokens=512,
                system=_SYSTEM,
                messages=messages_payload,
            )
            raw = response.content[0].text.strip()
            data = _parse_raw(raw)

            # ── Construcción del resultado ─────────────────────────────────────
            amount = None
            if data.get("amount") is not None:
                try:
                    amount = Decimal(str(data["amount"]))
                except Exception:
                    pass

            result = VisionResult(
                verdict=data.get("verdict", "review_needed"),
                confidence=float(data.get("confidence", 0.5)),
                reason=data.get("reason", ""),
                amount=amount,
                bank=data.get("bank"),
                reference=data.get("reference"),
                tx_date=data.get("tx_date"),
                raw_response=raw,
            )

            # ── Validación cruzada de monto ────────────────────────────────────
            if declared_amount and result.amount:
                diff_pct = abs(result.amount - declared_amount) / declared_amount
                if diff_pct > 0.05 and result.verdict == "approved":
                    result.verdict = "review_needed"
                    result.confidence = min(result.confidence, 0.60)
                    result.reason = (
                        f"Monto en comprobante (${result.amount:.2f}) difiere del declarado "
                        f"(${declared_amount:.2f}) en {diff_pct*100:.1f}%. {result.reason}"
                    )
                    logger.warning(
                        "vision: monto no coincide — declarado=%.2f detectado=%.2f",
                        declared_amount, result.amount,
                    )

            logger.info(
                "vision: verdict=%s confidence=%.2f amount=%s bank=%s reason=%s",
                result.verdict, result.confidence, result.amount, result.bank, result.reason[:80],
            )
            return result

        except json.JSONDecodeError as exc:
            last_exc = exc
            logger.warning(
                "vision: JSON inválido intento %d/%d — %s | raw=%r",
                attempt, _MAX_ATTEMPTS, exc, raw[:120],
            )

        except (anthropic.RateLimitError, anthropic.InternalServerError) as exc:
            last_exc = exc
            logger.warning(
                "vision: API transitoria (%s) intento %d/%d",
                type(exc).__name__, attempt, _MAX_ATTEMPTS,
            )

        except anthropic.APIConnectionError as exc:
            last_exc = exc
            logger.warning(
                "vision: APIConnectionError intento %d/%d — %s",
                attempt, _MAX_ATTEMPTS, exc,
            )

        except anthropic.BadRequestError as exc:
            # 4xx del cliente — imagen inválida, etc. No reintenta.
            logger.error("vision: BadRequestError (no reintentable) — %s", exc)
            return VisionResult(verdict="review_needed", confidence=0.0, reason=f"Imagen inválida: {exc}")

        except anthropic.APIError as exc:
            last_exc = exc
            logger.warning("vision: APIError intento %d/%d — %s", attempt, _MAX_ATTEMPTS, exc)

        except Exception as exc:
            logger.error("vision: error inesperado — %s", exc)
            return VisionResult(verdict="review_needed", confidence=0.0, reason=str(exc))

        if attempt < _MAX_ATTEMPTS:
            logger.info("vision: reintentando en %ds...", _RETRY_DELAY)
            time.sleep(_RETRY_DELAY)

    # Todos los intentos fallaron
    logger.error("vision: todos los intentos fallaron — %s", last_exc)
    return VisionResult(
        verdict="review_needed",
        confidence=0.0,
        reason=f"Error tras {_MAX_ATTEMPTS} intentos: {last_exc}",
    )
