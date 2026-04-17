"""
Servicio de lectura de correos bancarios via IMAP.
Lee notificaciones de BCP, BBVA, Interbank, Scotiabank.
Extrae: monto, tipo (abono/cargo), fecha, referencia.
"""
import imaplib
import email
import re
import os
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, date, timedelta
from decimal import Decimal


# -- Configuracion IMAP -----------------------------------------------

IMAP_HOST = os.getenv("IMAP_HOST", "imap.hostinger.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_EMAIL", "info@perusistemas.pro")
IMAP_PASS = os.getenv("IMAP_PASSWORD", "")


# -- Patrones de extraccion por banco ---------------------------------

PATRONES_BANCO = {
    "bcp": {
        "from_patterns": ["alertas@notificaciones.viabcp.com",
                          "notificaciones@viabcp.com"],
        "subject_patterns": ["operacion", "movimiento", "abono", "cargo",
                             "yape", "transferencia"],
        "extractors": {
            "monto": [
                r"S/\s*([\d,]+\.?\d*)",
                r"importe[:\s]+S/\s*([\d,]+\.?\d*)",
                r"monto[:\s]+S/\s*([\d,]+\.?\d*)",
            ],
            "tipo": [
                r"(abono|deposito|transferencia recibida)",
                r"(cargo|retiro|pago|debito)",
            ],
            "referencia": [
                r"operacion[:\s#]+(\w+)",
                r"n[.]\s*de\s*operacion[:\s]+(\w+)",
            ],
            "nombre": [
                r"de[:\s]+([A-Z][a-zA-Z\s]+)",
                r"remitente[:\s]+(.+?)(?:\n|$)",
            ],
        }
    },
    "bbva": {
        "from_patterns": ["alertas@bbva.pe", "notificaciones@bbva.pe"],
        "subject_patterns": ["has recibido", "transferencia", "movimiento",
                             "yape", "abono"],
        "extractors": {
            "monto": [
                r"S/\.([\d,]+\.?\d*)",
                r"PEN\s+([\d,]+\.?\d*)",
                r"S/\s*([\d,]+\.?\d*)",
            ],
            "tipo": [
                r"(recibid[oa]|abono|ingreso)",
                r"(cargo|pago|debito)",
            ],
            "referencia": [
                r"referencia[:\s]+(\w+)",
                r"operacion[:\s]+(\w+)",
            ],
            "nombre": [
                r"(?:de|desde)[:\s]+([A-Z].+?)(?:\n|\.)",
            ],
        }
    },
    "interbank": {
        "from_patterns": ["alertas@interbank.com.pe",
                          "noreply@interbank.com.pe"],
        "subject_patterns": ["operacion", "transferencia", "yape", "abono",
                             "movimiento"],
        "extractors": {
            "monto": [
                r"S/\s*([\d,]+\.?\d*)",
                r"por\s+S/\s*([\d,]+\.?\d*)",
            ],
            "tipo": [
                r"(recibiste|abono|transferencia recibida)",
                r"(pagaste|cargo|retiro)",
            ],
            "referencia": [
                r"codigo[:\s]+(\w+)",
                r"n[.]\s*operacion[:\s]+(\w+)",
            ],
        }
    },
    "yape": {
        "from_patterns": ["noreply@yape.com.pe", "alertas@yape.com.pe"],
        "subject_patterns": ["yape", "pago recibido", "te yaparon",
                             "transferencia yape"],
        "extractors": {
            "monto": [r"S/\s*([\d,]+\.?\d*)"],
            "tipo": [r"(recibiste|te yaparon)"],
            "nombre": [r"(?:de|desde)\s+([A-Z].+?)(?:\n|\.)"],
            "celular": [r"(\+?51\s?9\d{8}|\d{9})"],
        }
    },
    "plin": {
        "from_patterns": ["noreply@plin.pe", "alertas@plin.pe",
                          "noreply@intercorp.pe"],
        "subject_patterns": ["plin", "pago recibido"],
        "extractors": {
            "monto": [r"S/\s*([\d,]+\.?\d*)"],
            "tipo": [r"(recibiste|pago recibido)"],
            "nombre": [r"(?:de|desde)\s+([A-Z].+?)(?:\n|\.)"],
        }
    },
}


def detectar_banco(from_addr: str, subject: str) -> str | None:
    """Detecta el banco/app basado en remitente y asunto."""
    from_lower = from_addr.lower()
    subject_lower = subject.lower()

    for banco, config in PATRONES_BANCO.items():
        for pattern in config["from_patterns"]:
            if pattern in from_lower:
                return banco

    # Fallback por asunto
    if "yape" in subject_lower:
        return "yape"
    if "plin" in subject_lower:
        return "plin"

    # Deteccion adicional por dominio
    if "viabcp" in from_lower or "bcp" in from_lower:
        return "bcp"
    if "bbva" in from_lower:
        return "bbva"
    if "interbank" in from_lower or "ibk" in from_lower:
        return "interbank"

    return None


def limpiar_monto(texto: str) -> Decimal | None:
    """Convierte string de monto a Decimal."""
    try:
        limpio = texto.replace(",", "").replace(" ", "")
        return Decimal(limpio)
    except Exception:
        return None


def extraer_datos_correo(banco: str, subject: str, body: str) -> dict:
    """Extrae datos del movimiento del cuerpo del correo."""
    config = PATRONES_BANCO.get(banco, {})
    extractors = config.get("extractors", {})
    datos = {
        "banco": banco,
        "tipo": "abono",
        "monto": None,
        "referencia": None,
        "nombre_contraparte": None,
        "celular_contraparte": None,
        "tipo_operacion": banco if banco in ("yape", "plin") else "transferencia",
    }

    texto = f"{subject}\n{body}"

    # Extraer monto
    for pattern in extractors.get("monto", []):
        match = re.search(pattern, texto, re.IGNORECASE)
        if match:
            monto = limpiar_monto(match.group(1))
            if monto and monto > 0:
                datos["monto"] = monto
                break

    # Extraer tipo (abono/cargo)
    abono_words = ["recibid", "abono", "ingreso", "yaparon",
                   "recibiste", "deposito", "transferencia recibida"]
    cargo_words = ["cargo", "debito", "pago", "retiro", "pagaste"]

    texto_lower = texto.lower()
    if any(w in texto_lower for w in abono_words):
        datos["tipo"] = "abono"
    elif any(w in texto_lower for w in cargo_words):
        datos["tipo"] = "cargo"

    # Extraer referencia
    for pattern in extractors.get("referencia", []):
        match = re.search(pattern, texto, re.IGNORECASE)
        if match:
            datos["referencia"] = match.group(1).strip()
            break

    # Extraer nombre
    for pattern in extractors.get("nombre", []):
        match = re.search(pattern, texto, re.IGNORECASE)
        if match:
            nombre = match.group(1).strip()
            if 2 < len(nombre) < 100:
                datos["nombre_contraparte"] = nombre
                break

    # Extraer celular
    for pattern in extractors.get("celular", []):
        match = re.search(pattern, texto, re.IGNORECASE)
        if match:
            datos["celular_contraparte"] = match.group(1).strip()
            break

    return datos


def get_email_body(msg) -> str:
    """Extrae el cuerpo del correo (texto plano preferido)."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                charset = part.get_content_charset() or "utf-8"
                try:
                    body = part.get_payload(decode=True).decode(
                        charset, errors="replace")
                    break
                except Exception:
                    pass
            elif ctype == "text/html" and not body:
                charset = part.get_content_charset() or "utf-8"
                try:
                    html = part.get_payload(decode=True).decode(
                        charset, errors="replace")
                    body = re.sub(r"<[^>]+>", " ", html)
                    body = re.sub(r"\s+", " ", body)
                except Exception:
                    pass
    else:
        charset = msg.get_content_charset() or "utf-8"
        try:
            body = msg.get_payload(decode=True).decode(
                charset, errors="replace")
        except Exception:
            pass
    return body


def leer_correos_bancarios(
    dias_atras: int = 7,
    carpeta: str = "INBOX",
    solo_no_leidos: bool = True,
) -> list[dict]:
    """
    Conecta al IMAP y lee correos bancarios.
    Retorna lista de movimientos detectados.
    """
    if not IMAP_PASS:
        raise ValueError("IMAP_PASSWORD no configurado en variables de entorno")

    movimientos = []

    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(IMAP_USER, IMAP_PASS)
        mail.select(carpeta)

        desde = date.today() - timedelta(days=dias_atras)
        fecha_busqueda = desde.strftime("%d-%b-%Y")

        criterio = f'(SINCE "{fecha_busqueda}")'
        if solo_no_leidos:
            criterio = f'(UNSEEN SINCE "{fecha_busqueda}")'

        _, msg_nums = mail.search(None, criterio)

        for num in msg_nums[0].split():
            try:
                _, msg_data = mail.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])

                # Decodificar asunto
                subject_raw = msg.get("Subject", "")
                subject_parts = decode_header(subject_raw)
                subject = ""
                for part, enc in subject_parts:
                    if isinstance(part, bytes):
                        subject += part.decode(enc or "utf-8", errors="replace")
                    else:
                        subject += str(part)

                from_addr = msg.get("From", "")
                message_id = msg.get("Message-ID", "")
                date_str = msg.get("Date", "")

                banco = detectar_banco(from_addr, subject)
                if not banco:
                    continue

                body = get_email_body(msg)
                datos = extraer_datos_correo(banco, subject, body)

                if not datos.get("monto"):
                    continue

                try:
                    email_dt = parsedate_to_datetime(date_str)
                    fecha_mov = email_dt.date()
                    hora_mov = email_dt.strftime("%H:%M:%S")
                except Exception:
                    fecha_mov = date.today()
                    hora_mov = None

                movimientos.append({
                    **datos,
                    "fecha": fecha_mov,
                    "hora": hora_mov,
                    "email_mensaje_id": message_id,
                    "email_asunto": subject[:300],
                    "email_fecha": datetime.now(),
                    "origen": "email",
                })

                mail.store(num, "+FLAGS", "\\Seen")

            except Exception as e:
                print(f"[IMAP] Error procesando correo {num}: {e}")
                continue

        mail.logout()

    except imaplib.IMAP4.error as e:
        raise ConnectionError(f"Error IMAP: {e}")

    return movimientos


async def importar_movimientos_bancarios(
    db,
    id_cuenta: int | None = None,
    dias_atras: int = 7,
) -> dict:
    """
    Lee correos y guarda movimientos nuevos en la DB.
    Evita duplicados por email_mensaje_id.
    """
    from sqlalchemy import select
    from app.modulos.contabilidad.models import MovimientoBancario

    movimientos_raw = leer_correos_bancarios(dias_atras=dias_atras)
    nuevos = 0
    duplicados = 0

    for mov in movimientos_raw:
        if mov.get("email_mensaje_id"):
            result = await db.execute(
                select(MovimientoBancario).where(
                    MovimientoBancario.email_mensaje_id == mov["email_mensaje_id"]
                )
            )
            if result.scalar_one_or_none():
                duplicados += 1
                continue

        mb = MovimientoBancario(
            id_cuenta=id_cuenta,
            banco=mov["banco"],
            fecha=mov["fecha"],
            hora=mov.get("hora"),
            tipo=mov["tipo"],
            monto=mov["monto"],
            descripcion=mov.get("email_asunto"),
            referencia=mov.get("referencia"),
            tipo_operacion=mov.get("tipo_operacion", "transferencia"),
            nombre_contraparte=mov.get("nombre_contraparte"),
            celular_contraparte=mov.get("celular_contraparte"),
            email_mensaje_id=mov.get("email_mensaje_id"),
            email_asunto=mov.get("email_asunto"),
            email_fecha=mov.get("email_fecha"),
            estado_cruce="pendiente",
        )
        db.add(mb)
        nuevos += 1

    if nuevos > 0:
        await db.commit()

    return {"nuevos": nuevos, "duplicados": duplicados,
            "total_leidos": len(movimientos_raw)}
