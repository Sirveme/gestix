"""
Servicio de lectura de correos bancarios via IMAP.
Verificacion DKIM via Authentication-Results (Hostinger ya verifica).
Sistema de aprendizaje de dominios + deteccion de correos sospechosos.
"""
import imaplib
import email
import html as html_lib
import re
import os
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, date, timedelta
from decimal import Decimal


# -- Configuracion -----------------------------------------------

IMAP_HOST = os.getenv("IMAP_HOST", "imap.hostinger.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_EMAIL", "info@perusistemas.pro")
IMAP_PASS = os.getenv("IMAP_PASSWORD", "")


# -- Dominios bancarios confirmados (precargados via micropago) ---

DOMINIOS_CONFIRMADOS = {
    # BCP
    "notificaciones.viabcp.com": "bcp",
    "viabcp.com": "bcp",
    "alertas.viabcp.com": "bcp",
    # BBVA
    "bbva.pe": "bbva",
    "alertas.bbva.pe": "bbva",
    "bbvaprovincialmail.com": "bbva",
    # Interbank
    "netinterbank.com.pe": "interbank",
    "interbank.com.pe": "interbank",
    # Scotiabank
    "scotiabank.com.pe": "scotiabank",
    "alertas.scotiabank.com.pe": "scotiabank",
    # BanBif
    "banbif.com.pe": "banbif",
    # Yape (es de BCP)
    "yape.com.pe": "yape",
    "alertas.yape.com.pe": "yape",
    # Plin (es de Interbank/BBVA/Scotiabank)
    "plin.pe": "plin",
    "intercorp.pe": "plin",
}

KEYWORDS_BANCARIOS = [
    "yape", "plin", "transferencia", "abono", "deposito",
    "cargo", "operacion", "movimiento", "constancia de pago",
    "pago recibido", "te enviaron", "recibiste",
    "notificacion", "alerta", "saldo",
]


# -- Extraccion DKIM del header Authentication-Results ------------

def parsear_authentication_results(auth_header: str) -> dict:
    """
    Parsea el header Authentication-Results de Hostinger.
    Ejemplo:
      Authentication-Results: mx.hostinger.com;
        dkim=pass header.d=netinterbank.com.pe header.s=default;
        spf=pass smtp.mailfrom=netinterbank.com.pe
    """
    resultado = {
        "dkim": "none",
        "dkim_domain": None,
        "spf": "none",
        "raw": auth_header[:500] if auth_header else "",
    }

    if not auth_header:
        return resultado

    dkim_match = re.search(r"dkim=(pass|fail|neutral|none|temperror|permerror)",
                           auth_header, re.IGNORECASE)
    if dkim_match:
        resultado["dkim"] = dkim_match.group(1).lower()

    domain_patterns = [
        r"header\.d=([\w.\-]+)",
        r"dkim=pass[^;]*?d=([\w.\-]+)",
        r"@([\w.\-]+).*?dkim=pass",
    ]
    for pattern in domain_patterns:
        match = re.search(pattern, auth_header, re.IGNORECASE)
        if match:
            resultado["dkim_domain"] = match.group(1).lower()
            break

    spf_match = re.search(r"spf=(pass|fail|neutral|none|softfail)",
                          auth_header, re.IGNORECASE)
    if spf_match:
        resultado["spf"] = spf_match.group(1).lower()

    return resultado


def detectar_banco_por_dkim(dkim_domain: str | None,
                             dominios_aprendidos: dict) -> tuple[str | None, str]:
    """
    Detecta el banco usando el dominio DKIM.
    Retorna (banco, confianza): alta/media/None
    """
    if not dkim_domain:
        return None, "ninguna"

    if dkim_domain in DOMINIOS_CONFIRMADOS:
        return DOMINIOS_CONFIRMADOS[dkim_domain], "alta"

    if dkim_domain in dominios_aprendidos:
        dominio_info = dominios_aprendidos[dkim_domain]
        if dominio_info["estado"] == "confirmado":
            return dominio_info["banco"], "alta"
        elif dominio_info["estado"] == "nuevo":
            return dominio_info["banco"], "media"
        elif dominio_info["estado"] == "bloqueado":
            return None, "bloqueado"

    for dominio_conf, banco in DOMINIOS_CONFIRMADOS.items():
        if dkim_domain.endswith("." + dominio_conf) or \
           dominio_conf.endswith("." + dkim_domain):
            return banco, "alta"

    return None, "desconocido"


def es_correo_bancario_por_asunto(subject: str) -> bool:
    """Detecta si el asunto sugiere que es un correo bancario."""
    subject_lower = subject.lower()
    return any(kw in subject_lower for kw in KEYWORDS_BANCARIOS)


# -- Patrones de extraccion de datos ---------------------------------

EXTRACTORES = {
    "monto": [
        r"S/\s*\.?\s*([\d,]+\.?\d*)",
        r"PEN\s+([\d,]+\.?\d*)",
        r"importe[:\s]+S/\s*([\d,]+\.?\d*)",
        r"monto[:\s]+S/\s*([\d,]+\.?\d*)",
        r"por\s+S/\s*([\d,]+\.?\d*)",
        r"de\s+S/\s*([\d,]+\.?\d*)",
    ],
    "referencia": [
        r"n[.]\s*(?:de\s+)?operacion[:\s]+(\w+)",
        r"operacion[:\s#]+(\w+)",
        r"referencia[:\s]+(\w+)",
        r"codigo[:\s]+(\w+)",
        r"n[.]\s*(\d{6,})",
    ],
    "numero_operacion": [
        r"n[°ºo.]*\s*(?:de\s+)?operaci[oó]n[:\s#]+(\w{4,30})",
        r"operaci[oó]n[:\s#]+(\w{4,30})",
        r"c[oó]digo\s+de\s+operaci[oó]n[:\s#]+(\w{4,30})",
        r"n[°ºo.]*\s+(\d{6,})",
    ],
    "nombre": [
        r"(?:de|desde|remitente)[:\s]+([A-Z][a-zA-Z\s]{2,50})",
        r"(?:enviado por|pagado por)[:\s]+([A-Z][a-zA-Z\s]{2,50})",
    ],
    "destinatario": [
        r"(?:destinatario|para|beneficiario|enviado a|transferiste a|pagaste a)[:\s]+([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ\s\.]{2,80})",
    ],
    "celular": [
        r"(\+?51\s?9\d{8})",
        r"\b(9\d{8})\b",
    ],
}

PALABRAS_ABONO = [
    "recibid", "abono", "ingreso", "yaparon", "recibiste",
    "deposito", "transferencia recibida", "pago recibido",
    "te enviaron", "has recibido", "constancia de pago",
]
PALABRAS_CARGO = [
    "cargo", "debito", "pago realizado", "retiro",
    "pagaste", "enviaste", "has enviado",
]

# Palabras que nunca deben aparecer en un nombre de persona/empresa
# (si la captura las contiene, es texto de descripcion, no una contraparte)
PALABRAS_NO_NOMBRE = [
    "pago", "plin", "yape", "transferencia", "abono", "deposito",
    "cargo", "interbank", "bcp", "bbva", "scotiabank", "banbif",
    "constancia", "notificacion", "alerta", "saldo", "operacion",
]


def _es_nombre_valido(texto: str) -> bool:
    """Descarta capturas que son texto de descripcion (no nombres reales)."""
    if not texto or len(texto) < 3:
        return False
    t = texto.lower()
    return not any(p in t for p in PALABRAS_NO_NOMBRE)


def extraer_datos_movimiento(subject: str, body: str, banco: str) -> dict:
    """Extrae monto, tipo, referencia, nombre del cuerpo del correo."""
    texto = f"{subject}\n{body}"
    datos = {
        "banco": banco,
        "tipo": "abono",
        "monto": None,
        "referencia": None,
        "numero_operacion": None,
        "nombre_contraparte": None,
        "destinatario": None,
        "celular_contraparte": None,
        "tipo_operacion": banco if banco in ("yape", "plin") else "transferencia",
    }

    for pattern in EXTRACTORES["monto"]:
        match = re.search(pattern, texto, re.IGNORECASE)
        if match:
            try:
                monto = Decimal(match.group(1).replace(",", ""))
                if monto > 0:
                    datos["monto"] = monto
                    break
            except Exception:
                pass

    texto_lower = texto.lower()
    if "cuenta cargo:" in texto_lower or \
       "realizaste" in texto_lower or \
       "enviaste" in texto_lower:
        datos["tipo"] = "cargo"
    elif any(w in texto_lower for w in PALABRAS_ABONO):
        datos["tipo"] = "abono"
    elif any(w in texto_lower for w in PALABRAS_CARGO):
        datos["tipo"] = "cargo"

    for pattern in EXTRACTORES["referencia"]:
        match = re.search(pattern, texto, re.IGNORECASE)
        if match:
            datos["referencia"] = match.group(1).strip()[:50]
            break

    patrones_op = [
        r'[Cc][oó]digo de operaci[oó]n[:\s]*(\d+)',
        r'[Cc]odigo de operacion[:\s]*(\d+)',
        r'[Nn][uú]mero de operaci[oó]n[:\s]*(\d+)',
        r'[Oo]peraci[oó]n[:\s#]*(\d{6,})',
        r'N[°º]\s*operaci[oó]n[:\s]*(\d+)',
    ]
    for pat in patrones_op:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            datos["numero_operacion"] = m.group(1).strip()
            print(f"[DEBUG OPERACION FOUND] {datos['numero_operacion']}")
            break
    else:
        print(f"[DEBUG OPERACION NOT FOUND] primeros 200 chars: {texto[:200]}")

    for pattern in EXTRACTORES["destinatario"]:
        match = re.search(pattern, texto, re.IGNORECASE)
        if match:
            dest = match.group(1).strip()
            dest = re.sub(r'\s+', ' ', dest)
            # Si el regex tambien absorbio "Destino: <app>" al final, separarlo
            destino_app = None
            m_dest = re.search(r'\bdestino\b[:\s]+(.+)$', dest, re.IGNORECASE)
            if m_dest:
                destino_app = m_dest.group(1).strip()
                dest = dest[:m_dest.start()].strip()
            if len(dest) > 2 and _es_nombre_valido(dest):
                datos["destinatario"] = dest
                if destino_app:
                    destino_lower = destino_app.lower().strip()
                    if "yape" in destino_lower:
                        datos["tipo_operacion"] = "yape"
                    elif "plin" in destino_lower:
                        datos["tipo_operacion"] = "plin"
                    else:
                        datos["tipo_operacion"] = "transferencia"
                break

    for pattern in EXTRACTORES["nombre"]:
        match = re.search(pattern, texto, re.IGNORECASE)
        if match:
            nombre = re.sub(r'\s+', ' ', match.group(1).strip())
            if 3 < len(nombre) < 100 and _es_nombre_valido(nombre):
                datos["nombre_contraparte"] = nombre
                break

    for pattern in EXTRACTORES["celular"]:
        match = re.search(pattern, texto)
        if match:
            datos["celular_contraparte"] = match.group(1).strip()
            break

    return datos


def get_email_body(msg) -> str:
    """Extrae cuerpo del correo -- texto plano preferido."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            charset = part.get_content_charset() or "utf-8"
            if ctype == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode(
                        charset, errors="replace")
                    break
                except Exception:
                    pass
            elif ctype == "text/html" and not body:
                try:
                    html_content = part.get_payload(decode=True).decode(
                        charset, errors="replace")
                    body = re.sub(r"<[^>]+>", " ", html_content)
                    body = html_lib.unescape(body)
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
    return body[:15000]


# -- Funcion principal ------------------------------------------------

async def importar_movimientos_bancarios(
    db,
    dias_atras: int = 7,
    carpeta: str = "INBOX",
    solo_no_leidos: bool = False,
) -> dict:
    """
    Lee correos IMAP, verifica DKIM, guarda movimientos y correos sospechosos.
    """
    from sqlalchemy import select
    from app.modulos.contabilidad.models import (
        MovimientoBancario, DominioBancario, CorreoSospechoso
    )

    if not IMAP_PASS:
        raise ValueError("IMAP_PASSWORD no configurado")

    # Cargar dominios aprendidos de la DB
    result = await db.execute(select(DominioBancario))
    dominios_aprendidos = {
        d.dominio: {"banco": d.banco, "estado": d.estado}
        for d in result.scalars().all()
    }

    stats = {
        "nuevos": 0, "duplicados": 0, "sospechosos": 0,
        "dominios_nuevos": 0, "total_leidos": 0,
        "errores": 0,
    }

    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(IMAP_USER, IMAP_PASS)
        mail.select(carpeta)

        desde = date.fromordinal(date.today().toordinal() - dias_atras)
        fecha_busqueda = desde.strftime("%d-%b-%Y")

        criterio = f'(SINCE "{fecha_busqueda}")'
        if solo_no_leidos:
            criterio = f'(UNSEEN SINCE "{fecha_busqueda}")'

        _, msg_nums = mail.search(None, criterio)
        if not msg_nums[0]:
            mail.logout()
            return stats

        all_nums = msg_nums[0].split()
        stats["total_leidos"] = len(all_nums)
        print(f"[IMAP] {len(all_nums)} correos encontrados en los ultimos {dias_atras} dias")

        for num in all_nums:
            try:
                _, msg_data = mail.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])

                # PRIMERO: obtener Message-ID
                message_id = msg.get("Message-ID", "").strip()

                # SEGUNDO: verificar duplicado ANTES de todo lo demás
                if message_id:
                    r_dup = await db.execute(
                        select(MovimientoBancario).where(
                            MovimientoBancario.email_mensaje_id == message_id
                        ).limit(1)
                    )
                    if r_dup.scalar_one_or_none():
                        print(f"[IMAP] Duplicado ignorado: {message_id[:50]}")
                        stats["duplicados"] += 1
                        continue

                    r_dup2 = await db.execute(
                        select(CorreoSospechoso).where(
                            CorreoSospechoso.email_mensaje_id == message_id
                        ).limit(1)
                    )
                    if r_dup2.scalar_one_or_none():
                        stats["duplicados"] += 1
                        continue

                # RECIEN AQUI: decodificar subject, from, etc.
                subject = _decode_header_str(msg.get("Subject", ""))
                from_addr = msg.get("From", "")
                auth_results = msg.get("Authentication-Results", "")
                date_str = msg.get("Date", "")

                print(f"[IMAP] Procesando: from={from_addr[:60]}, subject={subject[:60]}")

                # Parsear DKIM
                auth = parsear_authentication_results(auth_results)
                print(f"[IMAP] DKIM={auth['dkim']} domain={auth['dkim_domain']} SPF={auth['spf']}")

                # CASO 1: DKIM falla
                if auth["dkim"] in ("fail", "permerror"):
                    if es_correo_bancario_por_asunto(subject):
                        body = get_email_body(msg)
                        sospechoso = CorreoSospechoso(
                            from_addr=from_addr[:300],
                            asunto=subject[:300],
                            fecha_correo=_parse_email_date(date_str),
                            dominio_dkim=auth["dkim_domain"],
                            dkim_resultado=auth["dkim"],
                            spf_resultado=auth["spf"],
                            auth_results_raw=auth_results[:500],
                            razon="dkim_fail",
                            descripcion_razon=f"DKIM={auth['dkim']} para dominio {auth['dkim_domain']}. Posible phishing.",
                            cuerpo_preview=body[:2000],
                            email_mensaje_id=message_id or None,
                        )
                        db.add(sospechoso)
                        stats["sospechosos"] += 1
                        print(f"[IMAP] SOSPECHOSO (dkim_fail): {subject[:50]}")
                    continue

                # CASO 2: Detectar banco por DKIM
                banco, confianza = detectar_banco_por_dkim(
                    auth["dkim_domain"], dominios_aprendidos)

                # CASO 3: Dominio bloqueado
                if confianza == "bloqueado":
                    print(f"[IMAP] Dominio bloqueado: {auth['dkim_domain']}")
                    continue

                # CASO 4: Dominio desconocido pero DKIM pasa
                if not banco and auth["dkim"] == "pass" and auth["dkim_domain"]:
                    if es_correo_bancario_por_asunto(subject):
                        body = get_email_body(msg)
                        sospechoso = CorreoSospechoso(
                            from_addr=from_addr[:300],
                            asunto=subject[:300],
                            fecha_correo=_parse_email_date(date_str),
                            dominio_dkim=auth["dkim_domain"],
                            dkim_resultado=auth["dkim"],
                            spf_resultado=auth["spf"],
                            auth_results_raw=auth_results[:500],
                            razon="dominio_desconocido",
                            descripcion_razon=f"DKIM pass pero dominio '{auth['dkim_domain']}' no esta en lista de bancos conocidos.",
                            cuerpo_preview=body[:2000],
                            email_mensaje_id=message_id or None,
                        )
                        db.add(sospechoso)
                        stats["sospechosos"] += 1

                        if auth["dkim_domain"] not in dominios_aprendidos:
                            nuevo_dominio = DominioBancario(
                                dominio=auth["dkim_domain"],
                                banco="desconocido",
                                estado="nuevo",
                                fuente="automatico",
                                total_correos=1,
                            )
                            db.add(nuevo_dominio)
                            dominios_aprendidos[auth["dkim_domain"]] = {
                                "banco": "desconocido", "estado": "nuevo"}
                            stats["dominios_nuevos"] += 1
                            print(f"[IMAP] Nuevo dominio registrado: {auth['dkim_domain']}")
                    continue

                # CASO 5: No es correo bancario conocido
                if not banco:
                    continue

                # CASO 6: Correo bancario legitimo
                body = get_email_body(msg)
                print(f"[IMAP BODY INICIO] {body[:500]}")
                print(f"[IMAP BODY FINAL] {body[-1000:]}")
                montos = re.findall(r"\d+[\.,]\d{2}", body)
                print(f"[IMAP NUMEROS] {montos[:20]}")
                datos = extraer_datos_movimiento(subject, body, banco)

                if not datos.get("monto"):
                    print(f"[IMAP] Sin monto detectado en correo de {banco}")
                    continue

                if auth["dkim_domain"]:
                    await _actualizar_dominio(db, auth["dkim_domain"], banco,
                                              confianza, dominios_aprendidos)

                fecha_mov, hora_mov = _parse_fecha_hora(date_str)

                mov = MovimientoBancario(
                    banco=banco,
                    fecha=fecha_mov,
                    hora=hora_mov,
                    tipo=datos["tipo"],
                    monto=datos["monto"],
                    descripcion=subject[:300],
                    referencia=datos.get("referencia"),
                    numero_operacion=datos.get("numero_operacion"),
                    tipo_operacion=datos.get("tipo_operacion", "transferencia"),
                    nombre_contraparte=datos.get("destinatario") or datos.get("nombre_contraparte"),
                    celular_contraparte=datos.get("celular_contraparte"),
                    confianza=confianza,
                    email_mensaje_id=message_id or None,
                    email_asunto=subject[:300],
                    email_fecha=_parse_email_date(date_str),
                    dominio_dkim=auth["dkim_domain"],
                    estado_cruce="pendiente",
                )
                db.add(mov)
                stats["nuevos"] += 1
                print(f"[IMAP] {banco.upper()} {datos['tipo']} S/{datos['monto']}")

                mail.store(num, "+FLAGS", "\\Seen")

            except Exception as e:
                print(f"[IMAP] Error en correo {num}: {e}")
                stats["errores"] += 1
                continue

        mail.logout()

    except imaplib.IMAP4.error as e:
        raise ConnectionError(f"Error IMAP: {e}")

    if stats["nuevos"] > 0 or stats["sospechosos"] > 0:
        await db.commit()

    return stats


# -- Helpers ----------------------------------------------------------

def _decode_header_str(raw: str) -> str:
    parts = decode_header(raw)
    result = ""
    for part, enc in parts:
        if isinstance(part, bytes):
            result += part.decode(enc or "utf-8", errors="replace")
        else:
            result += str(part)
    return result


def _parse_email_date(date_str: str) -> datetime:
    try:
        return parsedate_to_datetime(date_str).replace(tzinfo=None)
    except Exception:
        return datetime.now()


def _parse_fecha_hora(date_str: str) -> tuple[date, str | None]:
    try:
        dt = parsedate_to_datetime(date_str).replace(tzinfo=None)
        return dt.date(), dt.strftime("%H:%M:%S")
    except Exception:
        return date.today(), None


async def _actualizar_dominio(db, dominio: str, banco: str,
                               confianza: str, dominios_aprendidos: dict):
    from sqlalchemy import text as sql_text

    hoy = date.today()
    estado = "confirmado" if confianza == "alta" else "nuevo"

    await db.execute(sql_text("""
        INSERT INTO cont_dominios_bancarios
            (dominio, banco, estado, fuente, primera_vez, ultima_vez,
             total_correos, total_hoy, fecha_conteo_hoy, created_at, updated_at)
        VALUES
            (:dom, :banco, :estado, 'automatico', NOW(), NOW(),
             1, 1, :hoy, NOW(), NOW())
        ON CONFLICT (dominio) DO UPDATE SET
            ultima_vez = NOW(),
            total_correos = cont_dominios_bancarios.total_correos + 1,
            total_hoy = CASE
                WHEN cont_dominios_bancarios.fecha_conteo_hoy = :hoy
                THEN cont_dominios_bancarios.total_hoy + 1
                ELSE 1
            END,
            fecha_conteo_hoy = :hoy,
            updated_at = NOW()
    """), {"dom": dominio, "banco": banco, "estado": estado, "hoy": hoy})

    if dominio not in dominios_aprendidos:
        dominios_aprendidos[dominio] = {"banco": banco, "estado": estado}
