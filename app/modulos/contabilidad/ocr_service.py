"""
Servicio OCR para extraer datos de comprobantes de pago Yape/Plin.
Usa Google Cloud Vision API; fallback a GPT-4 Vision si no hay key.
"""
import re
import os
import base64
from decimal import Decimal
import httpx


async def extraer_datos_comprobante(imagen_bytes: bytes) -> dict:
    """
    Extrae N de operacion, monto y banco de la foto del comprobante.
    Retorna dict con los datos encontrados.
    """
    imagen_b64 = base64.b64encode(imagen_bytes).decode("utf-8")

    vision_key = os.getenv("GOOGLE_VISION_KEY", os.getenv("VISION_API_KEY", ""))

    resultado = {
        "numero_operacion": None,
        "monto": None,
        "banco": None,
        "texto_completo": "",
        "confianza": "baja",
        "error": None,
    }

    if not vision_key:
        return await _extraer_con_gpt4_vision(imagen_b64, resultado)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://vision.googleapis.com/v1/images:annotate?key={vision_key}",
                json={
                    "requests": [{
                        "image": {"content": imagen_b64},
                        "features": [
                            {"type": "TEXT_DETECTION", "maxResults": 1}
                        ]
                    }]
                }
            )
            data = resp.json()

        if "responses" in data and data["responses"]:
            texto = data["responses"][0].get(
                "fullTextAnnotation", {}).get("text", "")
            resultado["texto_completo"] = texto
            resultado.update(_parsear_texto_comprobante(texto))

    except Exception as e:
        resultado["error"] = str(e)
        print(f"[OCR] Error Vision API: {e}")

    return resultado


async def _extraer_con_gpt4_vision(imagen_b64: str, resultado: dict) -> dict:
    """Fallback usando GPT-4 Vision."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        resultado["error"] = "Sin API key para OCR"
        return resultado

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "max_tokens": 200,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{imagen_b64}",
                                    "detail": "low"
                                }
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Extrae de este comprobante de pago peruano "
                                    "(Yape/Plin/Interbank/BCP/BBVA): "
                                    "1) numero de operacion o codigo, "
                                    "2) monto en soles, "
                                    "3) banco o app (yape/plin/interbank/bcp/bbva). "
                                    "Responde SOLO en formato: "
                                    "OPERACION:12345678|MONTO:9.50|BANCO:yape"
                                )
                            }
                        ]
                    }]
                }
            )
            data = resp.json()
            texto_resp = data["choices"][0]["message"]["content"].strip()
            resultado["texto_completo"] = texto_resp

            if "OPERACION:" in texto_resp:
                partes = dict(p.split(":") for p in texto_resp.split("|") if ":" in p)
                resultado["numero_operacion"] = partes.get("OPERACION", "").strip()
                try:
                    resultado["monto"] = Decimal(partes.get("MONTO", "0").strip())
                except Exception:
                    pass
                resultado["banco"] = partes.get("BANCO", "").strip().lower()
                resultado["confianza"] = "alta"

    except Exception as e:
        resultado["error"] = str(e)
        print(f"[OCR] Error GPT-4 Vision: {e}")

    return resultado


def _parsear_texto_comprobante(texto: str) -> dict:
    """
    Parsea el texto OCR de un comprobante peruano.
    Detecta formato Yape, Plin, Interbank, BCP, BBVA.
    """
    resultado = {
        "numero_operacion": None,
        "monto": None,
        "banco": None,
        "confianza": "media",
    }

    texto_lower = texto.lower()

    if "yape" in texto_lower:
        resultado["banco"] = "yape"
    elif "plin" in texto_lower:
        resultado["banco"] = "plin"
    elif "interbank" in texto_lower or "ibk" in texto_lower:
        resultado["banco"] = "interbank"
    elif "bcp" in texto_lower or "viabcp" in texto_lower:
        resultado["banco"] = "bcp"
    elif "bbva" in texto_lower:
        resultado["banco"] = "bbva"
    elif "scotiabank" in texto_lower:
        resultado["banco"] = "scotiabank"

    patrones_op = [
        r'[Cc][oó]digo[:\s]*(\d{6,12})',
        r'[Oo]peraci[oó]n[:\s]*(\d{6,12})',
        r'[Nn][°º][:\s]*(\d{6,12})',
        r'#\s*(\d{6,12})',
        r'\b(\d{8,10})\b',
    ]
    for patron in patrones_op:
        m = re.search(patron, texto, re.IGNORECASE)
        if m:
            resultado["numero_operacion"] = m.group(1)
            resultado["confianza"] = "alta"
            break

    patrones_monto = [
        r'S/[.\s]*(\d+[.,]\d{2})',
        r'S/[.\s]*(\d+)',
        r'(\d+[.,]\d{2})\s*soles',
        r'PEN[:\s]*(\d+[.,]\d{2})',
    ]
    for patron in patrones_monto:
        m = re.search(patron, texto, re.IGNORECASE)
        if m:
            try:
                monto_str = m.group(1).replace(",", ".")
                resultado["monto"] = Decimal(monto_str)
            except Exception:
                pass
            break

    return resultado
