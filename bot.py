import os
import io
import re
import sys
import time
import json
import datetime
import logging
import requests
from pathlib import Path
from PIL import Image

import db

# Configuracion de Logging
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("BotCalidad")

# Token de Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8978005290:AAHkQcCm8dnIrHJ9lnNFNAUZElVZ6OghN9k")
API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Carpeta para evidencias fotográficas comprimidas de inventario
EVIDENCIAS_DIR = Path(__file__).resolve().parent / "uploads" / "evidencias"
EVIDENCIAS_DIR.mkdir(parents=True, exist_ok=True)

# Opciones de error para Validación Cambio de Vías Onnet
ERRORES_CAMBIO_VIAS = [
    "Error Consumiendo el servicio Resources",
    "Acceso Denegado",
    "Error Consumiendo el servicio ChangeRequest",
    "Sin CTO Sugerida",
    "Sin puertos Disponibles"
]

# Lista oficial de herramientas para el Inventario de Herramientas
HERRAMIENTAS_INVENTARIO = [
    "Cortadora de precisión",
    "Striper",
    "Kit de limpieza",
    "Lápiz limpiador",
    "Cortacables",
    "Alcohol isopropílico",
    "Toallas limpiadoras",
    "Power Meter",
    "Ponchadora UTP",
    "Probador UTP"
]

# Opciones de novedad cuando una herramienta está en mal estado / dañada
NOVEDADES_HERRAMIENTAS = [
    ("🔴 No funciona", "No funciona"),
    ("🟠 Funciona parcialmente", "Funciona parcialmente"),
    ("🟡 Deterioro físico", "Deterioro físico"),
    ("🔵 Falta accesorio", "Falta accesorio")
]

# Diccionario para almacenar el estado de la conversación por usuario
# chat_id -> dict
USER_SESSIONS = {}

def _default_session():
    return {
        'step': 'START',
        'region': None,
        'red': None,
        'aliado': None,
        'segmento': None,
        'comunidad': None,
        'rango': None,
        'primera_lls': None,
        'visita': None,
        'causa_idx': None,
        'causa_nombre': None,
        'subcausa_nombre': None,
        'manual_ot': None,
        'manual_cuenta': None,
        'manual_segmento': None,
        'manual_proveedor_red': None,
        'is_manual': False,
        'vias_cuenta': None,
        'vias_auto': None,
        'vias_exito': None,
        'vias_error': None,
        'vias_tiempo': None,
        'vias_exp': None,
        'page_ali': 0,
        'page_com': 0,
        'page_lls': 0,
        'page_cau': 0,
        # Cache de listas activas para indexacion rapida y segura en callback_data
        'aliados_list': [],
        'segmentos_list': [],
        'comunidades_list': [],
        'rangos_list': [],
        'llamadas_list': [],
        'causas_list': [],
        'subcausas_list': [],
        # Estado de Inventario de Herramientas
        'inv_tecnico': None,
        'inv_items': {},
        'inv_current_idx': 0,
        'inv_foto_general': None,
        'inv_editing_from_summary': False,
        'inv_aliados_list': [],
        'inv_ciudades_list': [],
        'inv_ciudades_all_regions': False,
        'page_inv_ali': 0,
        'page_inv_ciu': 0
    }

def get_session(chat_id):
    if chat_id not in USER_SESSIONS:
        USER_SESSIONS[chat_id] = _default_session()
    return USER_SESSIONS[chat_id]

def reset_session(chat_id):
    USER_SESSIONS[chat_id] = _default_session()
    return USER_SESSIONS[chat_id]

# -------------------------------------------------------------
# Funciones de Comunicacion con Telegram Bot API
# -------------------------------------------------------------

def send_message(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    """Envia un mensaje a un chat de Telegram."""
    url = f"{API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        resp = requests.post(url, json=payload, timeout=10)
        res_json = resp.json()
        if not res_json.get("ok") and parse_mode:
            payload.pop("parse_mode", None)
            resp = requests.post(url, json=payload, timeout=10)
            res_json = resp.json()
        return res_json
    except Exception as e:
        logger.error(f"Error al enviar mensaje a {chat_id}: {e}")
        return None

def edit_message(chat_id, message_id, text, reply_markup=None, parse_mode="Markdown"):
    """Edita el texto y botones de un mensaje existente."""
    if not message_id:
        return send_message(chat_id, text, reply_markup, parse_mode)
    url = f"{API_URL}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        resp = requests.post(url, json=payload, timeout=10)
        res_json = resp.json()
        if not res_json.get("ok") and parse_mode:
            payload.pop("parse_mode", None)
            resp = requests.post(url, json=payload, timeout=10)
            res_json = resp.json()
        return res_json
    except Exception as e:
        logger.error(f"Error al editar mensaje {message_id}: {e}")
        return None

def answer_callback_query(callback_query_id, text=None, show_alert=False):
    """Responde al callback query para quitar el relojito de carga en Telegram."""
    url = f"{API_URL}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = show_alert
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Error answer_callback_query: {e}")

def descargar_y_comprimir_foto(file_id, prefix="inv"):
    """Descarga una imagen desde Telegram, la comprime en JPEG y retorna la ruta relativa."""
    try:
        r_info = requests.get(f"{API_URL}/getFile", params={"file_id": file_id}, timeout=15).json()
        if not r_info.get("ok"):
            logger.error(f"Error getFile Telegram: {r_info}")
            return None
        file_path_tg = r_info["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path_tg}"
        r_bytes = requests.get(file_url, timeout=25)
        if r_bytes.status_code != 200:
            logger.error(f"Error descargando foto de Telegram HTTP {r_bytes.status_code}")
            return None

        img = Image.open(io.BytesIO(r_bytes.content))
        if img.mode != "RGB":
            img = img.convert("RGB")

        img.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
        ts_str = db.now_colombia_str().replace("-", "").replace(":", "").replace(" ", "_")
        filename = f"{prefix}_{ts_str}_{int(time.time() * 1000) % 10000}.jpg"
        out_path = EVIDENCIAS_DIR / filename
        img.save(out_path, format="JPEG", quality=72, optimize=True)
        return f"evidencias/{filename}"
    except Exception as e:
        logger.error(f"Error al descargar/comprimir foto: {e}")
        return None

def render_progress_bar(current_step, total_steps=10):
    """Genera una barra de avance visual para el inventario."""
    pct = int(round((current_step / total_steps) * 100))
    filled = int(round((current_step / total_steps) * 10))
    empty = 10 - filled
    bar = "█" * filled + "░" * empty
    return f"📊 *Avance:* `[{bar}]` *{pct}%* ({current_step}/{total_steps})"

def _is_missing_val(val):
    if val is None:
        return True
    s = str(val).strip()
    return s == "" or s.upper() in ("NA", "N/A", "NAN", "NONE", "NULL", "0", "SIN DATO")

# -------------------------------------------------------------
# Pantallas y Vistas del Bot
# -------------------------------------------------------------

def view_seleccionar_region(chat_id, message_id=None, first_name="Supervisor"):
    """Paso 1: Solicitar Región."""
    session = reset_session(chat_id)
    regiones = db.get_regiones()
    
    if not regiones:
        texto = (
            f"👋 ¡Hola *{first_name}*!\n\n"
            "⚠️ *No hay registros disponibles en este momento.*\n"
            "Por favor asegúrate de que se haya cargado la base en el sistema."
        )
        markup = {"inline_keyboard": [[{"text": "🔄 Reintentar", "callback_data": "nav:restart"}]]}
        if message_id:
            edit_message(chat_id, message_id, texto, markup)
        else:
            send_message(chat_id, texto, markup)
        return

    session['step'] = 'SELECT_REGION'
    
    texto = (
        f"👋 ¡Hola *{first_name}*! Bienvenido al *Bot de Gestión de Calidad*.\n\n"
        "📍 Para comenzar, por favor selecciona la *Región*:"
    )
    
    # Botones de Región (2 por fila)
    keyboard = []
    row = []
    for reg in regiones:
        row.append({"text": f"📍 {reg}", "callback_data": f"reg:{reg}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    markup = {"inline_keyboard": keyboard}
    
    if message_id:
        edit_message(chat_id, message_id, texto, markup)
    else:
        send_message(chat_id, texto, markup)

def view_seleccionar_modulo_region(chat_id, message_id=None):
    """Paso 1.5: Después de seleccionar la Región, elegir entre Causa Raíz o Inventario de Herramientas."""
    session = get_session(chat_id)
    region = session.get('region') or ''
    session['step'] = 'SELECT_MODULO_REGION'

    texto = (
        f"📍 Región seleccionada: *{region}*\n\n"
        "🛠️ *Selecciona la opción que deseas gestionar:*"
    )
    keyboard = [
        [{"text": "🔍 Causa Raíz", "callback_data": "mod_reg:causa_raiz"}],
        [{"text": "🧰 Inventario de Herramientas", "callback_data": "mod_reg:inventario"}],
        [{"text": "⬅️ Cambiar Región", "callback_data": "nav:restart"}]
    ]
    markup = {"inline_keyboard": keyboard}
    edit_message(chat_id, message_id, texto, markup)

# -------------------------------------------------------------
# Vistas del Módulo: Inventario de Herramientas
# -------------------------------------------------------------

def _cargar_inventario_mes_en_sesion(session, inv_mes):
    """Pre-carga en la sesión los datos e ítems del inventario del mes en curso para permitir actualizar herramientas."""
    if not inv_mes:
        return
    session['inv_update_id'] = inv_mes.get('id')
    session['inv_update_codigo'] = inv_mes.get('codigo_auditoria', '')
    session['inv_foto_general'] = inv_mes.get('foto_general_path') or ''
    session['inv_editing_from_summary'] = True

    det_map = {}
    for d in (inv_mes.get('detalles') or []):
        h_name = (d.get('herramienta') or '').strip()
        if h_name:
            det_map[h_name.upper()] = d

    items_dict = {}
    for idx, tool_name in enumerate(HERRAMIENTAS_INVENTARIO):
        d = det_map.get(tool_name.upper(), {})
        st_d = (d.get('estado') or 'OK').upper()
        prop_d = 'N/A' if st_d == 'FALTANTE' else (d.get('propiedad') or 'Aliado')
        items_dict[idx] = {
            'herramienta': tool_name,
            'estado': st_d,
            'propiedad': prop_d,
            'novedad': d.get('novedad') if st_d in ('NOVEDAD', 'FALTANTE') else None,
            'foto_path': d.get('foto_path') or d.get('evidencia_path') or None
        }
    session['inv_items'] = items_dict

def view_inv_pedir_cedula(chat_id, message_id=None):
    """Solicita el número de cédula del técnico para iniciar el inventario."""
    session = get_session(chat_id)
    region = session.get('region') or ''
    session['step'] = 'INV_CEDULA'
    session['inv_tecnico'] = None
    session['inv_items'] = {}
    session['inv_current_idx'] = 0
    session['inv_foto_general'] = None
    session['inv_editing_from_summary'] = False
    session['inv_mes_existente'] = None
    session['inv_update_id'] = None
    session['inv_update_codigo'] = None

    texto = (
        "🧰 *INVENTARIO DE HERRAMIENTAS*\n"
        f"📍 Región seleccionada: *{region}*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🪪 Por favor digita y envía el *Número de Cédula* del técnico:"
    )
    keyboard = [
        [{"text": "⬅️ Volver", "callback_data": "nav:back_mod_reg"}]
    ]
    markup = {"inline_keyboard": keyboard}
    edit_message(chat_id, message_id, texto, markup)

def view_inv_ficha_tecnico(chat_id, message_id=None):
    """Muestra la información del técnico, verifica si ya tiene inventario en el mes en curso y permite actualizarlo."""
    session = get_session(chat_id)
    session['step'] = 'INV_FICHA_TECNICO'
    tec = session.get('inv_tecnico') or {}

    cedula = tec.get('cedula', '')
    nombre = tec.get('nombre_tecnico', '')
    aliado = tec.get('aliado', '')
    region = tec.get('region', '')
    ciudad = tec.get('comunidad', '')
    area = tec.get('area', '')

    if cedula and session.get('inv_mes_existente') is None:
        session['inv_mes_existente'] = db.get_inventario_mes_actual(cedula)
    inv_mes = session.get('inv_mes_existente')

    falta_nombre = _is_missing_val(nombre)
    falta_aliado = _is_missing_val(aliado)
    falta_region = _is_missing_val(region)
    falta_ciudad = _is_missing_val(ciudad)
    datos_completos = not (falta_nombre or falta_aliado or falta_region or falta_ciudad)

    nombre_txt = nombre if not falta_nombre else "⚠️ _En blanco / Sin dato_"
    aliado_txt = aliado if not falta_aliado else "⚠️ _En blanco / Sin dato_"
    region_txt = region if not falta_region else "⚠️ _En blanco / Sin dato_"
    ciudad_txt = ciudad if not falta_ciudad else "⚠️ _En blanco / Sin dato_"
    area_txt = area if not _is_missing_val(area) else "N/D"

    bloque_mes = ""
    if inv_mes:
        pendientes_lines = []
        for d in (inv_mes.get('detalles') or []):
            st_d = (d.get('estado') or 'OK').upper()
            if st_d == 'NOVEDAD':
                pendientes_lines.append(f"  • ⚠️ {d.get('herramienta')}: {d.get('novedad')}")
            elif st_d == 'FALTANTE':
                pendientes_lines.append(f"  • ❌ {d.get('herramienta')}: Faltante / No disponible")
        detalle_pend = (
            "🔧 *Herramientas con novedad o faltantes:*\n" + "\n".join(pendientes_lines) + "\n"
            if pendientes_lines
            else "✅ _Todas las herramientas quedaron OK en este mes._\n"
        )
        bloque_mes = (
            "📅 *INVENTARIO DEL MES EN CURSO YA REALIZADO*\n"
            f"• *Código:* `{inv_mes.get('codigo_auditoria')}`\n"
            f"• *Fecha:* {inv_mes.get('fecha_registro')}\n"
            f"• *Estado:* ✅ {inv_mes.get('herramientas_ok', 0)} OK | "
            f"⚠️ {inv_mes.get('herramientas_novedad', 0)} Nov | "
            f"❌ {inv_mes.get('herramientas_faltantes', 0)} Falt\n"
            f"{detalle_pend}"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
        )

    aviso_estado = ""
    if not tec.get('en_base', True):
        aviso_estado = "ℹ️ _La cédula no estaba en la base inicial. Por favor completa los datos del técnico para registrarlo._\n\n"
    elif not datos_completos:
        aviso_estado = "⚠️ *Algunos datos están en blanco o NA.* Por favor actualízalos antes de continuar.\n\n"
    elif inv_mes:
        aviso_estado = (
            "ℹ️ *Este técnico ya cuenta con inventario en el mes en curso.* "
            "Puedes **Actualizar el inventario** si ya tiene la herramienta faltante o corregida, "
            "o realizar uno nuevo.\n\n"
        )
    else:
        aviso_estado = "✅ _Verifica los datos del técnico. Si alguno está errado puedes corregirlo o continuar al inventario._\n\n"

    texto = (
        "🧰 *INFORMACIÓN DEL TÉCNICO*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🪪 *Cédula:* `{cedula}`\n"
        f"👷 *Nombre:* {nombre_txt}\n"
        f"🤝 *Aliado:* {aliado_txt}\n"
        f"🗺️ *Región:* {region_txt}\n"
        f"🏙️ *Ciudad:* {ciudad_txt}\n"
        f"📍 *Zona / Área:* {area_txt}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{bloque_mes}"
        f"{aviso_estado}"
    )

    keyboard = []
    if datos_completos:
        if session.get('inv_editing_from_summary'):
            keyboard.append([{"text": "✅ Volver al Resumen del Inventario", "callback_data": "inv_act:resumen"}])
        elif inv_mes:
            keyboard.append([{"text": "🔄 Actualizar Inventario (Herramienta Faltante/Corregida)", "callback_data": "inv_act:update_mes"}])
            keyboard.append([{"text": "🆕 Realizar Nuevo Inventario Completo", "callback_data": "inv_act:start_tools_new"}])
        else:
            keyboard.append([{"text": "▶️ Iniciar Inventario de Herramientas", "callback_data": "inv_act:start_tools"}])

    keyboard.append([
        {"text": ("⚠️ " if falta_aliado else "✏️ ") + "Actualizar Aliado", "callback_data": "inv_edit:aliado"},
        {"text": ("⚠️ " if falta_ciudad else "✏️ ") + "Actualizar Ciudad", "callback_data": "inv_edit:ciudad"}
    ])
    keyboard.append([
        {"text": ("⚠️ " if falta_region else "✏️ ") + "Actualizar Región", "callback_data": "inv_edit:region"},
        {"text": ("⚠️ " if falta_nombre else "✏️ ") + "Corregir Nombre", "callback_data": "inv_edit:nombre"}
    ])
    keyboard.append([{"text": "🪪 Consultar otra Cédula", "callback_data": "mod_reg:inventario"}])
    keyboard.append([{"text": "🏠 Menú Principal", "callback_data": "nav:restart"}])

    markup = {"inline_keyboard": keyboard}
    edit_message(chat_id, message_id, texto, markup)

def view_inv_pedir_nombre(chat_id, message_id=None):
    """Solicita escribir el nombre del técnico para actualizarlo."""
    session = get_session(chat_id)
    session['step'] = 'INV_NOMBRE'
    tec = session.get('inv_tecnico') or {}

    texto = (
        "👷 *ACTUALIZAR NOMBRE DEL TÉCNICO*\n"
        f"🪪 *Cédula:* `{tec.get('cedula', '')}`\n\n"
        "✍️ Por favor escribe en el chat el *Nombre Completo* del técnico:"
    )
    markup = {"inline_keyboard": [[{"text": "⬅️ Cancelar", "callback_data": "inv_act:ficha"}]]}
    edit_message(chat_id, message_id, texto, markup)

def view_inv_seleccionar_region(chat_id, message_id=None):
    """Permite seleccionar/actualizar la Región del técnico."""
    session = get_session(chat_id)
    session['step'] = 'INV_SELECT_REGION'
    regiones = db.get_regiones()

    texto = (
        "🗺️ *ACTUALIZAR REGIÓN DEL TÉCNICO*\n\n"
        "Selecciona la *Región* correspondiente:"
    )
    keyboard = []
    row = []
    for reg in regiones:
        row.append({"text": f"📍 {reg}", "callback_data": f"inv_set_reg:{reg}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([{"text": "⬅️ Volver a Datos del Técnico", "callback_data": "inv_act:ficha"}])
    edit_message(chat_id, message_id, texto, {"inline_keyboard": keyboard})

def view_inv_seleccionar_aliado(chat_id, message_id=None, page=0):
    """Lista los aliados conocidos de la BD para actualizar el aliado del técnico."""
    session = get_session(chat_id)
    session['step'] = 'INV_SELECT_ALIADO'
    aliados = db.get_aliados_inventario(region=None)
    session['inv_aliados_list'] = aliados
    session['page_inv_ali'] = page

    ITEMS_PER_PAGE = 8
    total_pages = max(1, (len(aliados) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(aliados))
    page_items = aliados[start_idx:end_idx]

    texto = (
        "🤝 *ACTUALIZAR ALIADO DEL TÉCNICO*\n"
        f"Selecciona el *Aliado* de la base de datos (Página {page + 1} de {total_pages}):"
    )
    keyboard = []
    for idx_in_page, ali in enumerate(page_items):
        global_idx = start_idx + idx_in_page
        keyboard.append([{"text": f"🤝 {ali}", "callback_data": f"inv_set_ali:{global_idx}"}])

    nav_row = []
    if page > 0:
        nav_row.append({"text": "◀️ Anterior", "callback_data": f"p_inv_ali:{page - 1}"})
    if page < total_pages - 1:
        nav_row.append({"text": "Siguiente ▶️", "callback_data": f"p_inv_ali:{page + 1}"})
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([{"text": "⬅️ Volver a Datos del Técnico", "callback_data": "inv_act:ficha"}])
    edit_message(chat_id, message_id, texto, {"inline_keyboard": keyboard})

def view_inv_seleccionar_ciudad(chat_id, message_id=None, page=0, search_query=None):
    """Lista las ciudades conocidas de la BD para actualizar la ciudad del técnico."""
    session = get_session(chat_id)
    session['step'] = 'INV_SELECT_CIUDAD'
    tec = session.get('inv_tecnico') or {}
    reg_filter = None if session.get('inv_ciudades_all_regions') else (tec.get('region') or session.get('region'))

    ciudades = db.get_ciudades_inventario(region=reg_filter)
    if not ciudades and reg_filter:
        ciudades = db.get_ciudades_inventario(region=None)
        session['inv_ciudades_all_regions'] = True
        reg_filter = None

    if search_query:
        q = search_query.strip().upper()
        ciudades = [c for c in ciudades if q in c.upper()]

    session['inv_ciudades_list'] = ciudades
    session['page_inv_ciu'] = page

    ITEMS_PER_PAGE = 10
    total_pages = max(1, (len(ciudades) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(ciudades))
    page_items = ciudades[start_idx:end_idx]

    scope_txt = f"Región {reg_filter}" if reg_filter else "Nacional"
    filtro_txt = f" | Filtro: `{search_query}`" if search_query else ""
    texto = (
        f"🏙️ *ACTUALIZAR CIUDAD DEL TÉCNICO* ({scope_txt}{filtro_txt})\n"
        f"Selecciona la *Ciudad* o escribe parte del nombre en el chat para buscar (Página {page + 1} de {total_pages}):"
    )

    keyboard = []
    row = []
    for idx_in_page, ciu in enumerate(page_items):
        global_idx = start_idx + idx_in_page
        row.append({"text": f"🏙️ {ciu}", "callback_data": f"inv_set_ciu:{global_idx}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    nav_row = []
    if page > 0:
        nav_row.append({"text": "◀️ Anterior", "callback_data": f"p_inv_ciu:{page - 1}"})
    if page < total_pages - 1:
        nav_row.append({"text": "Siguiente ▶️", "callback_data": f"p_inv_ciu:{page + 1}"})
    if nav_row:
        keyboard.append(nav_row)

    if reg_filter:
        keyboard.append([{"text": "🌐 Ver ciudades de todas las regiones", "callback_data": "inv_ciu_scope:all"}])
    else:
        keyboard.append([{"text": f"📍 Filtrar por región actual ({tec.get('region') or session.get('region')})", "callback_data": "inv_ciu_scope:reg"}])

    keyboard.append([{"text": "⬅️ Volver a Datos del Técnico", "callback_data": "inv_act:ficha"}])
    edit_message(chat_id, message_id, texto, {"inline_keyboard": keyboard})

def view_inv_herramienta(chat_id, idx, message_id=None):
    """Muestra la evaluación de la herramienta #idx con barra de avance."""
    session = get_session(chat_id)
    total = len(HERRAMIENTAS_INVENTARIO)
    if idx < 0 or idx >= total:
        view_inv_foto_general(chat_id, message_id)
        return

    session['step'] = 'INV_EVAL_TOOL'
    session['inv_current_idx'] = idx
    tool_name = HERRAMIENTAS_INVENTARIO[idx]
    tec = session.get('inv_tecnico') or {}
    bar_str = render_progress_bar(idx + 1, total)

    actual = session.get('inv_items', {}).get(idx)
    estado_previo = ""
    if actual:
        if actual['estado'] == 'FALTANTE':
            estado_previo = "\n_(Actual: ❌ Faltante — no cuenta en inventario)_\n"
        else:
            st_lbl = "✅ OK" if actual['estado'] == 'OK' else f"⚠️ {actual.get('novedad')}"
            prop_lbl = actual.get('propiedad') or 'Sin definir'
            estado_previo = f"\n_(Actual: {st_lbl} | Propiedad: {prop_lbl})_\n"

    texto = (
        "🧰 *INVENTARIO DE HERRAMIENTAS*\n"
        f"👷 *Técnico:* {tec.get('nombre_tecnico', '')}\n"
        f"{bar_str}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔧 *Herramienta {idx + 1} de {total}:*\n"
        f"👉 *{tool_name}*\n"
        f"{estado_previo}\n"
        "1️⃣ Selecciona el *estado* de la herramienta:"
    )

    keyboard = [
        [{"text": "✅ OK (Buen estado)", "callback_data": f"inv_st:{idx}:OK"}],
        [{"text": "⚠️ Con novedad / Dañado", "callback_data": f"inv_st:{idx}:NOVEDAD"}],
        [{"text": "❌ Faltante / No disponible", "callback_data": f"inv_st:{idx}:FALTANTE"}]
    ]

    if session.get('inv_editing_from_summary'):
        keyboard.append([{"text": "⬅️ Volver al Resumen", "callback_data": "inv_act:resumen"}])
    elif idx > 0:
        keyboard.append([{"text": "⬅️ Herramienta anterior", "callback_data": f"inv_tool:{idx - 1}"}])
    else:
        keyboard.append([{"text": "⬅️ Volver a Datos del Técnico", "callback_data": "inv_act:ficha"}])

    edit_message(chat_id, message_id, texto, {"inline_keyboard": keyboard})

def view_inv_propiedad(chat_id, idx, message_id=None):
    """Pregunta si la herramienta #idx es propiedad del Técnico o del Aliado."""
    session = get_session(chat_id)
    total = len(HERRAMIENTAS_INVENTARIO)
    session['step'] = 'INV_SELECT_PROPIEDAD'
    session['inv_current_idx'] = idx
    tool_name = HERRAMIENTAS_INVENTARIO[idx]
    tec = session.get('inv_tecnico') or {}
    bar_str = render_progress_bar(idx + 1, total)

    item = session.get('inv_items', {}).get(idx, {})
    st = item.get('estado', 'OK')
    st_lbl = "✅ OK (Buen estado)" if st == 'OK' else ("⚠️ Con novedad / Dañado" if st == 'NOVEDAD' else "❌ Faltante / No disponible")

    texto = (
        "🧰 *INVENTARIO DE HERRAMIENTAS*\n"
        f"👷 *Técnico:* {tec.get('nombre_tecnico', '')}\n"
        f"{bar_str}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔧 *Herramienta {idx + 1} de {total}:* *{tool_name}*\n"
        f"📌 *Estado:* {st_lbl}\n\n"
        "2️⃣ *¿Esta herramienta es propiedad del Técnico o del Aliado?*"
    )

    keyboard = [
        [{"text": "👷 Propiedad del Técnico", "callback_data": f"inv_prop:{idx}:Técnico"}],
        [{"text": "🤝 Propiedad del Aliado", "callback_data": f"inv_prop:{idx}:Aliado"}],
        [{"text": "⬅️ Cambiar estado de la herramienta", "callback_data": f"inv_tool:{idx}"}]
    ]
    edit_message(chat_id, message_id, texto, {"inline_keyboard": keyboard})

def view_inv_novedad(chat_id, idx, message_id=None):
    """Pregunta ¿Qué novedad presenta? cuando la herramienta está dañada."""
    session = get_session(chat_id)
    total = len(HERRAMIENTAS_INVENTARIO)
    session['step'] = 'INV_SELECT_NOVEDAD'
    session['inv_current_idx'] = idx
    tool_name = HERRAMIENTAS_INVENTARIO[idx]
    item = session.get('inv_items', {}).get(idx, {})
    prop_txt = item.get('propiedad', 'Aliado')
    bar_str = render_progress_bar(idx + 1, total)

    texto = (
        "🧰 *INVENTARIO DE HERRAMIENTAS*\n"
        f"{bar_str}\n"
        f"🔧 *Herramienta:* {tool_name}\n"
        f"🏷️ *Propiedad:* {prop_txt}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*¿Qué novedad presenta?*"
    )

    keyboard = []
    for nov_idx, (btn_label, _) in enumerate(NOVEDADES_HERRAMIENTAS):
        keyboard.append([{"text": btn_label, "callback_data": f"inv_nov:{idx}:{nov_idx}"}])

    keyboard.append([{"text": "⬅️ Cambiar propiedad (Técnico/Aliado)", "callback_data": f"inv_back_prop:{idx}"}])
    edit_message(chat_id, message_id, texto, {"inline_keyboard": keyboard})

def view_inv_foto_herramienta(chat_id, idx, message_id=None):
    """Solicita tomar o subir una foto de la herramienta con novedad."""
    session = get_session(chat_id)
    total = len(HERRAMIENTAS_INVENTARIO)
    session['step'] = 'INV_FOTO_TOOL'
    session['inv_current_idx'] = idx
    tool_name = HERRAMIENTAS_INVENTARIO[idx]
    item = session.get('inv_items', {}).get(idx, {})
    nov_txt = item.get('novedad', 'Con novedad')
    prop_txt = item.get('propiedad', 'Aliado')
    bar_str = render_progress_bar(idx + 1, total)

    texto = (
        "📸 *EVIDENCIA DE HERRAMIENTA EN MAL ESTADO*\n"
        f"{bar_str}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔧 *Herramienta:* {tool_name}\n"
        f"🏷️ *Propiedad:* {prop_txt}\n"
        f"⚠️ *Novedad:* {nov_txt}\n\n"
        "📷 *Por favor toma o envía una foto de la herramienta:*\n"
        "_(La imagen se comprimirá automáticamente al subirla)_"
    )
    keyboard = [
        [{"text": "⬅️ Cambiar tipo de novedad", "callback_data": f"inv_back_nov:{idx}"}]
    ]
    edit_message(chat_id, message_id, texto, {"inline_keyboard": keyboard})

def view_inv_foto_general(chat_id, message_id=None):
    """Solicita una foto general de toda la herramienta inventariada al finalizar."""
    session = get_session(chat_id)
    total = len(HERRAMIENTAS_INVENTARIO)
    session['step'] = 'INV_FOTO_GENERAL'
    bar_str = render_progress_bar(total, total)

    texto = (
        "📸 *FOTO GENERAL DEL INVENTARIO*\n"
        f"{bar_str}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📷 *Para finalizar, por favor toma y envía una foto general de toda la herramienta inventariada:*\n"
        "_(La imagen se comprimirá automáticamente al subirla)_"
    )
    keyboard = []
    if session.get('inv_editing_from_summary') and session.get('inv_foto_general'):
        keyboard.append([{"text": "⬅️ Volver al Resumen", "callback_data": "inv_act:resumen"}])
    else:
        keyboard.append([{"text": "⬅️ Volver a la última herramienta", "callback_data": f"inv_tool:{total - 1}"}])

    edit_message(chat_id, message_id, texto, {"inline_keyboard": keyboard})

def view_inv_resumen(chat_id, message_id=None):
    """Muestra el resumen completo del inventario antes de confirmar."""
    session = get_session(chat_id)
    session['step'] = 'INV_RESUMEN'
    session['inv_editing_from_summary'] = False

    tec = session.get('inv_tecnico') or {}
    items_dict = session.get('inv_items') or {}
    es_actualizacion = bool(session.get('inv_update_id'))

    ok_count = 0
    nov_count = 0
    falt_count = 0
    prop_tec_count = 0
    prop_ali_count = 0
    evidencias_count = 1 if session.get('inv_foto_general') else 0
    lineas_novedades = []

    for idx, tool_name in enumerate(HERRAMIENTAS_INVENTARIO):
        it = items_dict.get(idx, {'herramienta': tool_name, 'estado': 'OK', 'propiedad': 'Aliado', 'novedad': None, 'foto_path': None})
        st = it.get('estado', 'OK')
        prop = it.get('propiedad') or 'Aliado'

        if it.get('foto_path'):
            evidencias_count += 1
        if st == 'OK':
            ok_count += 1
            if 'técnico' in prop.lower() or 'tecnico' in prop.lower():
                prop_tec_count += 1
            else:
                prop_ali_count += 1
        elif st == 'NOVEDAD':
            nov_count += 1
            if 'técnico' in prop.lower() or 'tecnico' in prop.lower():
                prop_tec_count += 1
            else:
                prop_ali_count += 1
            nov_desc = (it.get('novedad') or 'deterioro').lower()
            lineas_novedades.append(f"⚠️ {tool_name} ({prop}): {nov_desc}")
        elif st == 'FALTANTE':
            falt_count += 1
            lineas_novedades.append(f"❌ {tool_name}: no disponible")

    now_col = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)
    fecha_str = now_col.strftime("%d/%m/%Y")

    bloque_novedades = "\n".join(lineas_novedades) if lineas_novedades else "✅ Sin novedades"
    titulo_res = (
        f"📋 *Resumen de actualización ({session.get('inv_update_codigo')})*"
        if es_actualizacion
        else "📋 *Resumen del inventario*"
    )
    btn_conf_label = "✅ Confirmar actualización de inventario" if es_actualizacion else "✅ Confirmar inventario"
    herr_en_inv = ok_count + nov_count

    texto = (
        f"{titulo_res}\n\n"
        f"Técnico: {tec.get('nombre_tecnico', '')}\n"
        f"Fecha: {fecha_str}\n\n"
        f"📦 {herr_en_inv} herramientas en inventario\n"
        f"✅ {ok_count} herramientas OK\n"
        f"⚠️ {nov_count} herramientas con novedad\n"
        f"❌ {falt_count} herramienta{'s' if falt_count != 1 else ''} faltante{'s' if falt_count != 1 else ''} _(no cuenta en inventario)_\n"
        f"👷 {prop_tec_count} propiedad del Técnico\n"
        f"🤝 {prop_ali_count} propiedad del Aliado\n"
        f"📸 {evidencias_count} evidencias cargadas\n\n"
        "*Novedades*\n\n"
        f"{bloque_novedades}"
    )

    keyboard = [
        [{"text": btn_conf_label, "callback_data": "inv_act:confirmar"}],
        [{"text": "✏️ Corregir / Actualizar otra herramienta", "callback_data": "inv_act:corregir"}]
    ]
    edit_message(chat_id, message_id, texto, {"inline_keyboard": keyboard})

def view_inv_menu_corregir(chat_id, message_id=None):
    """Permite elegir qué herramienta, foto general o dato del técnico corregir o actualizar."""
    session = get_session(chat_id)
    session['step'] = 'INV_CORREGIR'
    session['inv_editing_from_summary'] = True
    items_dict = session.get('inv_items') or {}
    es_actualizacion = bool(session.get('inv_update_id'))

    if es_actualizacion:
        texto = (
            "🔄 *ACTUALIZAR INVENTARIO DEL MES*\n"
            f"📋 *Código:* `{session.get('inv_update_codigo', '')}`\n\n"
            "Selecciona la herramienta *faltante o corregida* para actualizar su estado:"
        )
    else:
        texto = (
            "✏️ *CORREGIR INVENTARIO*\n\n"
            "Selecciona la herramienta o sección que deseas modificar:"
        )

    keyboard = []
    for idx, tool_name in enumerate(HERRAMIENTAS_INVENTARIO):
        it = items_dict.get(idx, {})
        st = it.get('estado', 'OK')
        prop = it.get('propiedad') or ''
        prop_tag = f" [{prop}]" if (st != 'FALTANTE' and prop and prop not in ('N/A', 'No aplica')) else ""
        icon = "✅" if st == 'OK' else ("⚠️" if st == 'NOVEDAD' else "❌")
        extra_st = ""
        if st == 'NOVEDAD':
            extra_st = f" - {it.get('novedad') or 'Con novedad'}"
        elif st == 'FALTANTE':
            extra_st = " - FALTANTE"
        keyboard.append([{"text": f"{icon} {idx + 1}. {tool_name}{prop_tag}{extra_st}", "callback_data": f"inv_tool:{idx}"}])

    keyboard.append([{"text": "📸 Cambiar foto general", "callback_data": "inv_act:foto_general"}])
    keyboard.append([{"text": "👷 Corregir datos del técnico", "callback_data": "inv_act:ficha"}])
    keyboard.append([{"text": "✅ Ver Resumen y Confirmar", "callback_data": "inv_act:resumen"}])

    edit_message(chat_id, message_id, texto, {"inline_keyboard": keyboard})

def view_inv_confirmar_guardar(chat_id, from_user, message_id=None):
    """Guarda o actualiza el inventario en la BD, genera/mantiene el código de auditoría y muestra el mensaje final."""
    session = get_session(chat_id)
    tec = session.get('inv_tecnico') or {}
    items_dict = session.get('inv_items') or {}

    items_list = []
    for idx, tool_name in enumerate(HERRAMIENTAS_INVENTARIO):
        it = items_dict.get(idx, {'herramienta': tool_name, 'estado': 'OK', 'propiedad': 'Aliado', 'novedad': None, 'foto_path': None})
        items_list.append(it)

    user_info = from_user or {}
    nombre_sup = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip() or "Supervisor"
    username_sup = user_info.get('username', '')

    payload = {
        'inventario_id_actualizar': session.get('inv_update_id'),
        'telegram_user_id': chat_id,
        'telegram_username': username_sup,
        'telegram_nombre': nombre_sup,
        'cedula_tecnico': tec.get('cedula', ''),
        'nombre_tecnico': tec.get('nombre_tecnico', ''),
        'aliado': tec.get('aliado', ''),
        'region': tec.get('region') or session.get('region', ''),
        'comunidad': tec.get('comunidad', ''),
        'area': tec.get('area', ''),
        'foto_general_path': session.get('inv_foto_general'),
        'items': items_list
    }

    res = db.guardar_inventario_herramientas(payload)
    session['step'] = 'INV_DONE'
    session['inv_update_id'] = None
    session['inv_mes_existente'] = None

    novedades_encontradas = res['herramientas_novedad'] + res['herramientas_faltantes']
    titulo_fin = (
        "✅ *Inventario actualizado correctamente*"
        if res.get('actualizado')
        else "✅ *Inventario registrado correctamente*"
    )

    texto = (
        f"{titulo_fin}\n\n"
        f"Código: `{res['codigo_auditoria']}`\n\n"
        f"Herramientas registradas: {res['total_herramientas']}\n"
        f"Propiedad Técnico: {res.get('herramientas_tecnico', 0)} | Aliado: {res.get('herramientas_aliado', 0)}\n"
        f"Novedades encontradas: {novedades_encontradas}\n"
        f"Evidencias: {res['evidencias_cargadas']}\n\n"
        "Gracias."
    )

    keyboard = [
        [{"text": "🧰 Nuevo Inventario de Herramientas", "callback_data": "mod_reg:inventario"}],
        [{"text": "🏠 Menú Principal", "callback_data": "nav:restart"}]
    ]
    edit_message(chat_id, message_id, texto, {"inline_keyboard": keyboard})

def view_seleccionar_red(chat_id, message_id=None):
    """Paso 2: Solicitar Red para la Región elegida."""
    session = get_session(chat_id)
    region = session['region']
    redes = db.get_redes(region)
    
    if not redes:
        texto = f"⚠️ No se encontraron tipos de Red para la Región *{region}*."
        markup = {"inline_keyboard": [[{"text": "⬅️ Volver", "callback_data": "nav:back_mod_reg"}]]}
        edit_message(chat_id, message_id, texto, markup)
        return

    session['step'] = 'SELECT_RED'
    
    texto = (
        f"📍 Región seleccionada: *{region}*\n\n"
        "🌐 Selecciona el tipo de *Red*:"
    )
    
    keyboard = []
    for r in redes:
        keyboard.append([{"text": f"📶 {r}", "callback_data": f"red:{r}"}])
    keyboard.append([{"text": "⬅️ Volver", "callback_data": "nav:back_mod_reg"}])
    
    markup = {"inline_keyboard": keyboard}
    edit_message(chat_id, message_id, texto, markup)

def view_seleccionar_aliado(chat_id, message_id=None, page=0):
    """Paso 3: Listar Aliados disponibles para la Región y Red elegida."""
    session = get_session(chat_id)
    region = session['region']
    red = session['red']

    aliados = db.get_aliados(region, red)
    session['aliados_list'] = aliados
    session['page_ali'] = page
    session['step'] = 'SELECT_ALIADO'

    if not aliados:
        texto = f"⚠️ No se encontraron aliados para Región *{region}* y Red *{red}*."
        markup = {"inline_keyboard": [[{"text": "⬅️ Cambiar Red", "callback_data": "nav:back_red"}]]}
        edit_message(chat_id, message_id, texto, markup)
        return

    ITEMS_PER_PAGE = 8
    total_pages = (len(aliados) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(aliados))
    page_items = aliados[start_idx:end_idx]

    texto = (
        f"📍 Región: *{region}* | Red: *{red}*\n\n"
        f"🤝 Selecciona el *Aliado* (Total: {len(aliados)}):\n"
        f"_(Página {page + 1} de {total_pages})_"
    )

    keyboard = []
    for idx_in_page, aliado in enumerate(page_items):
        global_idx = start_idx + idx_in_page
        keyboard.append([{"text": f"🤝 {aliado}", "callback_data": f"ali:{global_idx}"}])

    nav_row = []
    if page > 0:
        nav_row.append({"text": "◀️ Anterior", "callback_data": f"p_ali:{page - 1}"})
    if page < total_pages - 1:
        nav_row.append({"text": "Siguiente ▶️", "callback_data": f"p_ali:{page + 1}"})
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([{"text": "⬅️ Cambiar Red", "callback_data": "nav:back_red"}])
    markup = {"inline_keyboard": keyboard}
    edit_message(chat_id, message_id, texto, markup)

def view_seleccionar_segmento(chat_id, message_id=None):
    """Paso 4: Seleccionar Segmento (Masivo o Corporativo) después del Aliado."""
    session = get_session(chat_id)
    region = session['region']
    red = session['red']
    aliado = session['aliado']

    segmentos = db.get_segmentos(region, red, aliado)
    if not segmentos:
        segmentos = ['Masivo', 'Corporativo']
    session['segmentos_list'] = segmentos
    session['step'] = 'SELECT_SEGMENTO'

    texto = (
        f"📍 Región: *{region}* | Red: *{red}*\n"
        f"🤝 Aliado: *{aliado}*\n\n"
        "👥 Selecciona el *Segmento*:"
    )

    keyboard = []
    for seg in segmentos:
        icono = "🏠" if "masiv" in seg.lower() else "🏢"
        keyboard.append([{"text": f"{icono} {seg}", "callback_data": f"seg:{seg}"}])

    keyboard.append([{"text": "⬅️ Cambiar Aliado", "callback_data": "nav:back_aliado"}])
    markup = {"inline_keyboard": keyboard}
    if message_id:
        edit_message(chat_id, message_id, texto, markup)
    else:
        send_message(chat_id, texto, markup)

def view_seleccionar_comunidad(chat_id, message_id=None, page=0):
    """Paso 5: Listar Ciudades (Comunidad) donde hay OTs para el Aliado y Segmento seleccionados."""
    session = get_session(chat_id)
    region = session['region']
    red = session['red']
    aliado = session['aliado']
    segmento = session.get('segmento')
    
    comunidades = db.get_comunidades(region, red, aliado=aliado, segmento=segmento)
    session['comunidades_list'] = comunidades
    session['page_com'] = page
    session['step'] = 'SELECT_COMUNIDAD'
    
    if not comunidades:
        texto = f"⚠️ No hay ciudades con OTs para Aliado *{aliado}* ({segmento}) en Región *{region}* y Red *{red}*."
        markup = {"inline_keyboard": [[{"text": "⬅️ Cambiar Segmento", "callback_data": "nav:back_seg"}]]}
        edit_message(chat_id, message_id, texto, markup)
        return

    ITEMS_PER_PAGE = 8
    total_pages = (len(comunidades) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(comunidades))
    page_items = comunidades[start_idx:end_idx]

    texto = (
        f"📍 Región: *{region}* | Red: *{red}*\n"
        f"🤝 Aliado: *{aliado}* | 👥 Segmento: *{segmento}*\n\n"
        f"🏙️ Selecciona la *Ciudad / Comunidad* (Total: {len(comunidades)}):\n"
        f"_(Página {page + 1} de {total_pages})_"
    )

    keyboard = []
    # 2 botones por fila
    row = []
    for idx_in_page, com in enumerate(page_items):
        global_idx = start_idx + idx_in_page
        row.append({"text": f"🏙️ {com}", "callback_data": f"com:{global_idx}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    # Botones de paginacion
    nav_row = []
    if page > 0:
        nav_row.append({"text": "◀️ Anterior", "callback_data": f"p_com:{page - 1}"})
    if page < total_pages - 1:
        nav_row.append({"text": "Siguiente ▶️", "callback_data": f"p_com:{page + 1}"})
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([{"text": "⬅️ Cambiar Segmento", "callback_data": "nav:back_seg"}])
    
    markup = {"inline_keyboard": keyboard}
    edit_message(chat_id, message_id, texto, markup)

def view_opciones_red_neutra(chat_id, message_id=None):
    """Muestra opciones para Red Neutra tras seleccionar la Ciudad: Realizar Causa Raíz o Validación Cambio Vías Onnet."""
    session = get_session(chat_id)
    region = session.get('region')
    aliado = session.get('aliado')
    segmento = session.get('segmento')
    comunidad = session.get('comunidad')
    
    session['step'] = 'SELECT_OPCION_NEUTRA'
    
    texto = (
        f"📍 Región: *{region}* | Red: *Red Neutra*\n"
        f"🤝 Aliado: *{aliado}* | 👥 Segmento: *{segmento}*\n"
        f"🏙️ Ciudad: *{comunidad}*\n\n"
        "🛠️ *Selecciona la opción que deseas gestionar:*"
    )
    keyboard = [
        [{"text": "🔍 Realizar Causa Raíz", "callback_data": "neutra_opt:causa_raiz"}],
        [{"text": "🔄 Validación Cambio Vías Onnet", "callback_data": "neutra_opt:cambio_vias"}],
        [{"text": "⬅️ Cambiar Ciudad", "callback_data": "nav:back_com"}]
    ]
    markup = {"inline_keyboard": keyboard}
    if message_id:
        edit_message(chat_id, message_id, texto, markup)
    else:
        send_message(chat_id, texto, markup)

def view_vias_paso1_cuenta(chat_id, message_id=None):
    """Paso 1 Validación Vías: Ingrese Número de Cuenta."""
    session = get_session(chat_id)
    session['step'] = 'VIAS_CUENTA'
    comunidad = session.get('comunidad')
    aliado = session.get('aliado')
    
    texto = (
        "🔄 *Validación Cambio de Vías Onnet*\n"
        f"🏙️ *Ciudad:* {comunidad} | 🤝 *Aliado:* {aliado}\n\n"
        "1️⃣ *Ingrese Número de Cuenta:*\n\n"
        "✍️ _Por favor escribe el número de cuenta en el chat a continuación:_"
    )
    keyboard = [
        [{"text": "⬅️ Volver", "callback_data": "nav:back_neutra_opt"}]
    ]
    markup = {"inline_keyboard": keyboard}
    if message_id:
        edit_message(chat_id, message_id, texto, markup)
    else:
        send_message(chat_id, texto, markup)

def view_vias_paso2_auto(chat_id, message_id=None):
    """Paso 2 Validación Vías: ¿Cambio de vías automático? (Si / No)."""
    session = get_session(chat_id)
    session['step'] = 'VIAS_AUTO'
    cuenta = session.get('vias_cuenta')
    
    texto = (
        "🔄 *Validación Cambio de Vías Onnet*\n"
        f"📋 Cuenta: *{cuenta}*\n\n"
        "2️⃣ *Cambio de vías automático:*"
    )
    keyboard = [
        [
            {"text": "✅ Sí", "callback_data": "vias_auto:Si"},
            {"text": "❌ No", "callback_data": "vias_auto:No"}
        ],
        [{"text": "⬅️ Corregir Cuenta", "callback_data": "vias_back:cuenta"}]
    ]
    markup = {"inline_keyboard": keyboard}
    if message_id:
        edit_message(chat_id, message_id, texto, markup)
    else:
        send_message(chat_id, texto, markup)

def view_vias_paso3_exitoso(chat_id, message_id=None):
    """Paso 3 Validación Vías: ¿Cambio de vías exitoso? (Si / No)."""
    session = get_session(chat_id)
    session['step'] = 'VIAS_EXITO'
    cuenta = session.get('vias_cuenta')
    auto = session.get('vias_auto')
    
    texto = (
        "🔄 *Validación Cambio de Vías Onnet*\n"
        f"📋 Cuenta: *{cuenta}* | Automático: *{auto}*\n\n"
        "3️⃣ *Cambio de vías exitoso:*"
    )
    keyboard = [
        [
            {"text": "✅ Sí", "callback_data": "vias_exito:Si"},
            {"text": "❌ No", "callback_data": "vias_exito:No"}
        ],
        [{"text": "⬅️ Volver", "callback_data": "vias_back:auto"}]
    ]
    markup = {"inline_keyboard": keyboard}
    edit_message(chat_id, message_id, texto, markup)

def view_vias_paso_error(chat_id, message_id=None):
    """Paso intermedio Validación Vías: Error presentado cuando el cambio no fue exitoso."""
    session = get_session(chat_id)
    session['step'] = 'VIAS_ERROR'
    cuenta = session.get('vias_cuenta')
    
    texto = (
        "🔄 *Validación Cambio de Vías Onnet*\n"
        f"📋 Cuenta: *{cuenta}* | Exitoso: *No*\n\n"
        "⚠️ *Selecciona el Error presentado:*"
    )
    keyboard = []
    for idx, err in enumerate(ERRORES_CAMBIO_VIAS):
        keyboard.append([{"text": f"❌ {err}", "callback_data": f"vias_err:{idx}"}])
    keyboard.append([{"text": "⬅️ Volver", "callback_data": "vias_back:exito"}])
    markup = {"inline_keyboard": keyboard}
    if message_id:
        edit_message(chat_id, message_id, texto, markup)
    else:
        send_message(chat_id, texto, markup)

def view_vias_paso4_tiempo(chat_id, message_id=None):
    """Paso 4 Validación Vías: Tiempo de duración."""
    session = get_session(chat_id)
    session['step'] = 'VIAS_TIEMPO'
    cuenta = session.get('vias_cuenta')
    exito = session.get('vias_exito')
    
    back_target = "vias_back:error" if exito == 'No' else "vias_back:exito"

    texto = (
        "🔄 *Validación Cambio de Vías Onnet*\n"
        f"📋 Cuenta: *{cuenta}* | Exitoso: *{exito}*\n\n"
        "4️⃣ *Tiempo de duración:*"
    )
    keyboard = [
        [{"text": "⏱️ 1 a 2 Minutos", "callback_data": "vias_tiempo:1 a 2 Minutos"}],
        [{"text": "⏱️ 2 a 3 Minutos", "callback_data": "vias_tiempo:2 a 3 Minutos"}],
        [{"text": "⏱️ Más de 3 Minutos", "callback_data": "vias_tiempo:Mas de 3 Minutos"}],
        [{"text": "⬅️ Volver", "callback_data": back_target}]
    ]
    markup = {"inline_keyboard": keyboard}
    edit_message(chat_id, message_id, texto, markup)

def view_vias_paso5_experiencia(chat_id, message_id=None):
    """Paso 5 Validación Vías: Experiencia del Técnico (Positiva / Negativa)."""
    session = get_session(chat_id)
    session['step'] = 'VIAS_EXP'
    cuenta = session.get('vias_cuenta')
    tiempo = session.get('vias_tiempo')
    
    texto = (
        "🔄 *Validación Cambio de Vías Onnet*\n"
        f"📋 Cuenta: *{cuenta}* | Duración: *{tiempo}*\n\n"
        "5️⃣ *Experiencia del Técnico:*"
    )
    keyboard = [
        [
            {"text": "👍 Positiva", "callback_data": "vias_exp:Positiva"},
            {"text": "👎 Negativa", "callback_data": "vias_exp:Negativa"}
        ],
        [{"text": "⬅️ Volver", "callback_data": "vias_back:tiempo"}]
    ]
    markup = {"inline_keyboard": keyboard}
    edit_message(chat_id, message_id, texto, markup)

def view_seleccionar_rango(chat_id, message_id=None):
    """Paso 6: Listar Rango de Primera LLS (RangoPrimerArreglo) o Ingresar OT Manualmente."""
    session = get_session(chat_id)
    region = session.get('region')
    red = session.get('red')
    aliado = session.get('aliado')
    segmento = session.get('segmento')
    comunidad = session.get('comunidad')
    
    rangos = db.get_rangos_primer_arreglo(region, red, comunidad, aliado=aliado, segmento=segmento)
    session['rangos_list'] = rangos
    session['step'] = 'SELECT_RANGO'
    
    back_target = "nav:back_neutra_opt" if red == 'Red Neutra' else "nav:back_com"
    back_label = "⬅️ Volver a Opciones" if red == 'Red Neutra' else "⬅️ Cambiar Ciudad"

    if not rangos:
        texto = (
            f"📍 *Ciudad:* {comunidad}\n"
            f"🤝 *Aliado:* {aliado} | 👥 *Segmento:* {segmento}\n"
            f"Red: *{red}* | Región: *{region}*\n\n"
            "⚠️ No hay llamadas de servicio en base para esta selección.\n\n"
            "¿Deseas ingresar la OT manualmente?"
        )
        markup = {
            "inline_keyboard": [
                [{"text": "✍️ Ingresar OT Manualmente", "callback_data": "man:start"}],
                [{"text": back_label, "callback_data": back_target}]
            ]
        }
        edit_message(chat_id, message_id, texto, markup)
        return

    texto = (
        f"📍 Ciudad: *{comunidad}*\n"
        f"🤝 Aliado: *{aliado}* | 👥 Segmento: *{segmento}*\n"
        f"Red: *{red}* | Región: *{region}*\n\n"
        "⏱️ Selecciona el *Rango de Primera LLS* o ingresa una OT manual:"
    )

    keyboard = []
    for idx, rng in enumerate(rangos):
        keyboard.append([{"text": f"⏱️ {rng}", "callback_data": f"rng:{idx}"}])
        
    keyboard.append([{"text": "✍️ Ingresar OT Manualmente", "callback_data": "man:start"}])
    keyboard.append([{"text": back_label, "callback_data": back_target}])
    markup = {"inline_keyboard": keyboard}
    edit_message(chat_id, message_id, texto, markup)

def view_listar_llamadas(chat_id, message_id=None, page=0):
    """Paso 7: Listar Llamadas de servicio en orden descendente de PrimeraLLS."""
    session = get_session(chat_id)
    region = session['region']
    red = session['red']
    aliado = session['aliado']
    segmento = session.get('segmento')
    comunidad = session['comunidad']
    rango = session['rango']
    
    llamadas = db.get_llamadas_servicio(region, red, comunidad, rango, aliado=aliado, segmento=segmento, limit=300)
    session['llamadas_list'] = llamadas
    session['page_lls'] = page
    session['step'] = 'SELECT_LLAMADA'
    
    if not llamadas:
        texto = (
            f"⚠️ No se encontraron llamadas de servicio pendientes para:\n"
            f"Aliado: *{aliado}* | Segmento: *{segmento}*\n"
            f"Ciudad: *{comunidad}* | Rango: *{rango}*.\n\n"
            "¿Deseas ingresar la OT manualmente?"
        )
        markup = {
            "inline_keyboard": [
                [{"text": "✍️ Ingresar OT Manualmente", "callback_data": "man:start"}],
                [{"text": "⬅️ Cambiar Rango", "callback_data": "nav:back_rng"}],
                [{"text": "🏙️ Cambiar Ciudad", "callback_data": "nav:back_com"}]
            ]
        }
        edit_message(chat_id, message_id, texto, markup)
        return

    ITEMS_PER_PAGE = 15
    total_pages = (len(llamadas) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(llamadas))
    page_items = llamadas[start_idx:end_idx]

    texto = (
        f"📋 *Llamadas de Servicio* (Orden descendente por Primera LLS):\n"
        f"🤝 Aliado: *{aliado}* | 👥 Segmento: *{segmento}*\n"
        f"📍 Ciudad: *{comunidad}* | Red: *{red}*\n"
        f"⏱️ Rango: *{rango}*\n\n"
        f"Selecciona una llamada para ver el detalle y registrar causa raíz:\n"
        f"_(Página {page + 1} de {total_pages} - Total {len(llamadas)} llamadas disponibles)_"
    )

    keyboard = []
    for item in page_items:
        lls = item['primera_lls']
        ot = item['ot']
        btn_text = f"📞 LLS: {lls} | OT: {ot}"
        keyboard.append([{"text": btn_text, "callback_data": f"lls:{lls}"}])

    nav_row = []
    if page > 0:
        nav_row.append({"text": "◀️ Anterior", "callback_data": f"p_lls:{page - 1}"})
    if page < total_pages - 1:
        nav_row.append({"text": "Siguiente ▶️", "callback_data": f"p_lls:{page + 1}"})
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([{"text": "✍️ ¿No encuentras la OT? Ingresar Manualmente", "callback_data": "man:start"}])
    keyboard.append([{"text": "⬅️ Cambiar Rango", "callback_data": "nav:back_rng"}])
    markup = {"inline_keyboard": keyboard}
    edit_message(chat_id, message_id, texto, markup)

def view_ingreso_manual_ot(chat_id, message_id=None):
    """Paso Manual 1: Solicitar número de OT al usuario."""
    session = get_session(chat_id)
    
    # Validar que existan los datos territoriales previos (Región, Aliado, Ciudad)
    # Si la sesión se reinició o no hay región seleccionada, redirigir a seleccionar región
    if not session.get('region') or not session.get('comunidad'):
        texto = (
            "⚠️ *Selección requerida*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Para registrar una OT manual, primero debes seleccionar la *Región*, *Red* y *Ciudad* a la que pertenece la orden.\n\n"
            "📍 Por favor selecciona la *Región*:"
        )
        view_seleccionar_region(chat_id, message_id)
        return

    session['step'] = 'MANUAL_OT'
    session['is_manual'] = True
    session['manual_ot'] = None
    session['manual_cuenta'] = None
    session['manual_segmento'] = session.get('segmento')

    texto = (
        "✍️ *INGRESO MANUAL DE OT*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🗺️ *Región:* {session.get('region')}\n"
        f"🌐 *Red:* {session.get('red')}\n"
        f"🤝 *Aliado:* {session.get('aliado')}\n"
        f"👥 *Segmento previo:* {session.get('segmento', 'N/A')}\n"
        f"🏙️ *Ciudad:* {session.get('comunidad')}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Por favor escribe por este chat el *Número de la Orden (OT)*:"
    )
    markup = {"inline_keyboard": [[{"text": "⬅️ Cancelar", "callback_data": "nav:cancel_manual"}]]}
    if message_id:
        edit_message(chat_id, message_id, texto, markup)
    else:
        send_message(chat_id, texto, markup)

def view_ingreso_manual_cuenta(chat_id):
    """Paso Manual 2: Solicitar número de Cuenta al usuario."""
    session = get_session(chat_id)
    session['step'] = 'MANUAL_CUENTA'

    texto = (
        "✍️ *INGRESO MANUAL DE OT*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛠️ *OT Ingresada:* `{session['manual_ot']}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Ahora, por favor escribe por este chat el *Número de la Cuenta*:"
    )
    markup = {"inline_keyboard": [[{"text": "⬅️ Cancelar", "callback_data": "nav:cancel_manual"}]]}
    send_message(chat_id, texto, markup)

def view_ingreso_manual_segmento(chat_id, message_id=None):
    """Paso Manual 3: Seleccionar Segmento (Masivo o Corporativo)."""
    session = get_session(chat_id)
    session['step'] = 'MANUAL_SEGMENTO'
    seg_actual = session.get('segmento') or 'Masivo'

    texto = (
        "📋 *DATOS DE LA ORDEN MANUAL*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛠️ *OT:* `{session['manual_ot']}`\n"
        f"👤 *Cuenta:* `{session['manual_cuenta']}`\n"
        f"🏙️ *Ciudad:* {session.get('comunidad')}\n"
        f"🤝 *Aliado:* {session.get('aliado')}\n"
        f"🌐 *Red:* {session.get('red')} | 🗺️ *Región:* {session.get('region')}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Segmento predeterminado: *{seg_actual}*\n"
        "Confirma o selecciona el *Segmento* de la orden:"
    )
    keyboard = [
        [
            {"text": "🏠 Masivo" + (" ✅" if seg_actual == "Masivo" else ""), "callback_data": "man_seg:Masivo"},
            {"text": "🏢 Corporativo" + (" ✅" if seg_actual == "Corporativo" else ""), "callback_data": "man_seg:Corporativo"}
        ],
        [{"text": "⬅️ Cancelar", "callback_data": "nav:cancel_manual"}]
    ]
    markup = {"inline_keyboard": keyboard}
    if message_id:
        edit_message(chat_id, message_id, texto, markup)
    else:
        send_message(chat_id, texto, markup)

def view_ingreso_manual_proveedor(chat_id, message_id=None):
    """Paso Manual 4: Seleccionar Proveedor de Red (Claro, OnNet, Atp)."""
    session = get_session(chat_id)
    session['step'] = 'MANUAL_PROVEEDOR'
    prov_actual = session.get('manual_proveedor_red')

    texto = (
        "📡 *SELECCIÓN DE PROVEEDOR DE RED*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛠️ *OT:* `{session['manual_ot']}`\n"
        f"👤 *Cuenta:* `{session['manual_cuenta']}`\n"
        f"🏢 *Segmento:* {session.get('manual_segmento', 'Masivo')}\n"
        f"🏙️ *Ciudad:* {session.get('comunidad')}\n"
        f"🤝 *Aliado:* {session.get('aliado')}\n"
        f"🌐 *Red:* {session.get('red')} | 🗺️ *Región:* {session.get('region')}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Selecciona el *Proveedor de Red* correspondiente a esta orden:"
    )
    keyboard = [
        [
            {"text": "🔴 Claro" + (" ✅" if prov_actual == "Claro" else ""), "callback_data": "man_prov:Claro"},
            {"text": "🔵 OnNet" + (" ✅" if prov_actual == "OnNet" else ""), "callback_data": "man_prov:OnNet"},
            {"text": "🟡 Atp" + (" ✅" if prov_actual == "Atp" else ""), "callback_data": "man_prov:Atp"}
        ],
        [{"text": "⬅️ Cambiar Segmento", "callback_data": "nav:back_man_seg"}],
        [{"text": "❌ Cancelar", "callback_data": "nav:cancel_manual"}]
    ]
    markup = {"inline_keyboard": keyboard}
    if message_id:
        edit_message(chat_id, message_id, texto, markup)
    else:
        send_message(chat_id, texto, markup)

def view_detalle_manual(chat_id, message_id=None):
    """Paso Manual 5: Resumen y botón para pasar a Realizar Causa Raíz."""
    session = get_session(chat_id)
    visita = session.get('visita', {})
    session['step'] = 'VIEW_DETAIL_MANUAL'

    texto = (
        "📄 *INFORMACIÓN DE LA VISITA (INGRESO MANUAL)*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛠️ *OT:* `{visita.get('ot')}`\n"
        f"👤 *Cuenta:* `{visita.get('cuenta')}`\n"
        f"🏢 *Segmento:* {visita.get('segmento')}\n"
        f"📡 *Proveedor Red:* *{visita.get('proveedor_red')}*\n"
        f"🤝 *Aliado:* {visita.get('aliado')}\n"
        f"🌐 *Red:* {visita.get('red')}\n"
        f"📍 *Ciudad:* {visita.get('comunidad')}\n"
        f"🗺️ *Región:* {visita.get('region')}\n"
        f"⏱️ *Rango:* {visita.get('rango_primer_arreglo')}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "¿Deseas clasificar la causa de este hallazgo?"
    )

    keyboard = [
        [{"text": "🔍 Realizar Causa Raiz", "callback_data": "action:causa_raiz"}],
        [{"text": "📡 Cambiar Proveedor Red", "callback_data": "nav:back_man_prov"}],
        [{"text": "✍️ Cambiar Datos", "callback_data": "man:start"}],
        [{"text": "⬅️ Cancelar", "callback_data": "nav:cancel_manual"}]
    ]
    markup = {"inline_keyboard": keyboard}
    if message_id:
        edit_message(chat_id, message_id, texto, markup)
    else:
        send_message(chat_id, texto, markup)

def view_detalle_llamada(chat_id, primera_lls, message_id=None):
    """Paso 8: Detalle de la visita y botón Realizar Causa Raíz."""
    session = get_session(chat_id)
    visita = db.get_detalle_visita(primera_lls)
    
    if not visita:
        texto = f"⚠️ No se encontró la información para la llamada *{primera_lls}*."
        markup = {"inline_keyboard": [[{"text": "⬅️ Volver a la lista", "callback_data": "nav:back_lls"}]]}
        edit_message(chat_id, message_id, texto, markup)
        return

    # Verificar si ya fue diligenciada para evitar duplicidad entre supervisores
    diligenciada = db.is_ot_diligenciada(visita.get('ot'), primera_lls)
    if diligenciada:
        texto = (
            "⚠️ *ESTA OT YA FUE DILIGENCIADA*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛠️ *OT:* `{visita.get('ot')}` | 🔢 *Primera LLS:* `{visita.get('primera_lls')}`\n"
            f"👮 *Gestionada por:* {diligenciada.get('telegram_nombre', 'Otro supervisor')}\n"
            f"🕒 *Fecha:* {diligenciada.get('fecha_registro', 'Previamente')}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Esta orden ya fue clasificada y no está disponible para evitar duplicados."
        )
        markup = {"inline_keyboard": [[{"text": "🔄 Volver a la lista de llamadas", "callback_data": "nav:back_lls"}]]}
        edit_message(chat_id, message_id, texto, markup)
        return

    session['primera_lls'] = primera_lls
    session['visita'] = visita
    session['step'] = 'VIEW_DETAIL'

    # Campos requeridos por el usuario: Cuenta, Aliado, Segmento, Red, Comunidad
    texto = (
        "📄 *INFORMACIÓN DE LA VISITA*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔢 *Primera LLS:* `{visita.get('primera_lls')}`\n"
        f"🛠️ *OT:* `{visita.get('ot')}`\n"
        f"👤 *Cuenta:* `{visita.get('cuenta')}`\n"
        f"🤝 *Aliado:* {visita.get('aliado')}\n"
        f"🏢 *Segmento:* {visita.get('segmento')}\n"
        f"🌐 *Red:* {visita.get('red')}\n"
        f"📡 *Proveedor Red:* {visita.get('proveedor_red', 'N/D')}\n"
        f"📍 *Comunidad:* {visita.get('comunidad')}\n"
        f"⏱️ *Rango Primer Arreglo:* {visita.get('rango_primer_arreglo')}\n"
        f"📋 *Trabajo:* {visita.get('trabajo', 'N/A')}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "¿Deseas clasificar la causa de este hallazgo?"
    )

    keyboard = [
        [{"text": "🔍 Realizar Causa Raiz", "callback_data": "action:causa_raiz"}],
        [{"text": "⬅️ Volver a la lista de llamadas", "callback_data": "nav:back_lls"}]
    ]
    markup = {"inline_keyboard": keyboard}
    edit_message(chat_id, message_id, texto, markup)

def view_seleccionar_causa(chat_id, message_id=None, page=0):
    """Paso 7: Selección de Causa Raíz (Lista completa sin paginación)."""
    session = get_session(chat_id)
    causas = db.get_causas()
    session['causas_list'] = causas
    session['step'] = 'SELECT_CAUSA'

    visita = session.get('visita') or {}
    back_cb = "man:confirm" if session.get('is_manual') else f"lls:{session.get('primera_lls')}"

    if not causas:
        texto = "⚠️ No hay causas configuradas en la matriz."
        markup = {"inline_keyboard": [[{"text": "⬅️ Volver", "callback_data": back_cb}]]}
        edit_message(chat_id, message_id, texto, markup)
        return

    texto = (
        "🔍 *CLASIFICACIÓN DE CAUSA RAÍZ*\n"
        f"🛠️ OT: `{visita.get('ot')}` | 👤 Cuenta: `{visita.get('cuenta')}`\n"
        f"🏢 Segmento: *{visita.get('segmento')}* | 🤝 Aliado: *{visita.get('aliado')}*\n"
        f"📍 Ciudad: *{visita.get('comunidad')}* ({visita.get('red')})\n\n"
        f"Por favor selecciona la *Causa* correspondiente (Total: {len(causas)}):"
    )

    keyboard = []
    for idx, causa in enumerate(causas):
        keyboard.append([{"text": f"⚠️ {causa}", "callback_data": f"cau:{idx}"}])

    keyboard.append([{"text": "⬅️ Cancelar y Volver", "callback_data": back_cb}])
    markup = {"inline_keyboard": keyboard}
    edit_message(chat_id, message_id, texto, markup)

def view_seleccionar_subcausa(chat_id, causa_idx, message_id=None):
    """Paso 8: Selección de Subcausa habilitada según la Causa."""
    session = get_session(chat_id)
    causas = session.get('causas_list') or db.get_causas()
    if causa_idx >= len(causas):
        view_seleccionar_causa(chat_id, message_id)
        return

    causa = causas[causa_idx]
    session['causa_idx'] = causa_idx
    session['causa_nombre'] = causa

    subcausas = db.get_subcausas(causa)
    session['subcausas_list'] = subcausas
    session['step'] = 'SELECT_SUBCAUSA'

    if not subcausas:
        texto = f"⚠️ No hay subcausas registradas para la causa:\n*{causa}*."
        markup = {"inline_keyboard": [[{"text": "⬅️ Elegir otra causa", "callback_data": "action:causa_raiz"}]]}
        edit_message(chat_id, message_id, texto, markup)
        return

    texto = (
        f"⚠️ Causa seleccionada:\n*{causa}*\n\n"
        "🔍 Ahora selecciona la *Subcausa*:"
    )

    keyboard = []
    for idx, sub in enumerate(subcausas):
        keyboard.append([{"text": f"🔹 {sub}", "callback_data": f"sub:{idx}"}])

    keyboard.append([{"text": "⬅️ Elegir otra Causa", "callback_data": "action:causa_raiz"}])
    markup = {"inline_keyboard": keyboard}
    edit_message(chat_id, message_id, texto, markup)

def view_guardar_resultado(chat_id, subcausa_idx, user_info, message_id=None):
    """Paso 9: Guardar en MySQL y confirmar al usuario."""
    session = get_session(chat_id)
    subcausas = session.get('subcausas_list') or []
    if subcausa_idx >= len(subcausas):
        view_seleccionar_causa(chat_id, message_id)
        return

    subcausa = subcausas[subcausa_idx]
    session['subcausa_nombre'] = subcausa

    visita = session.get('visita') or {}
    causa = session.get('causa_nombre')
    is_manual = session.get('is_manual', False)

    ot_val = visita.get('ot') or session.get('manual_ot')
    cuenta_val = visita.get('cuenta') or session.get('manual_cuenta')

    # Región con fallback seguro
    region_val = session.get('region') or visita.get('region') or ''
    aliado_val = visita.get('aliado') or session.get('aliado') or ''
    red_val = visita.get('red') or session.get('red') or ''
    comunidad_val = visita.get('comunidad') or session.get('comunidad') or ''
    segmento_val = visita.get('segmento') or session.get('manual_segmento') or session.get('segmento') or 'Masivo'
    proveedor_val = visita.get('proveedor_red') or session.get('manual_proveedor_red') or session.get('proveedor_red')

    # Si faltara algún dato territorial y la OT existe en la base, autocompletar
    if ot_val and (not region_val or not aliado_val or not red_val or not comunidad_val):
        info_db = db.get_info_by_ot_or_lls(ot_val)
        if info_db:
            if not region_val and info_db.get('region'):
                region_val = info_db['region']
            if not aliado_val and info_db.get('aliado'):
                aliado_val = info_db['aliado']
            if not red_val and info_db.get('red'):
                red_val = info_db['red']
            if not comunidad_val and info_db.get('comunidad'):
                comunidad_val = info_db['comunidad']
            if not proveedor_val and info_db.get('proveedor_red'):
                proveedor_val = info_db['proveedor_red']

    # Preparar payload para insertar en MySQL
    datos_hallazgo = {
        'telegram_user_id': user_info.get('id'),
        'telegram_username': user_info.get('username', ''),
        'telegram_nombre': f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip(),
        'ot': ot_val,
        'cuenta': cuenta_val,
        'aliado': aliado_val or ('Ingreso Manual' if is_manual else 'Sin Aliado'),
        'region': region_val or ('Sin Región' if is_manual else ''),
        'segmento': segmento_val,
        'red': red_val or ('Sin Red' if is_manual else ''),
        'proveedor_red': proveedor_val,
        'comunidad': comunidad_val or ('Sin Ciudad' if is_manual else ''),
        'primera_lls': visita.get('primera_lls') or ot_val,
        'rango_primer_arreglo': visita.get('rango_primer_arreglo', 'Manual / Fuera de Base'),
        'causa': causa,
        'subcausa': subcausa,
        'observaciones': 'Ingreso manual fuera de base' if is_manual else ''
    }

    hallazgo_id = db.guardar_hallazgo(datos_hallazgo)

    texto = (
        "✅ *¡CAUSA RAÍZ REGISTRADA CON ÉXITO!*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 *Registro #:* `{hallazgo_id}`\n"
        f"🛠️ *OT:* `{visita.get('ot')}`\n"
        f"👤 *Cuenta:* `{visita.get('cuenta')}`\n"
        f"🏢 *Segmento:* {visita.get('segmento')}\n"
        f"📡 *Proveedor Red:* {datos_hallazgo.get('proveedor_red', 'N/D')}\n"
        f"🤝 *Aliado:* {visita.get('aliado')}\n"
        f"📍 *Ciudad:* {visita.get('comunidad')} ({visita.get('red')})\n"
        f"🗺️ *Región:* {region_val}\n"
        f"⚠️ *Causa:* {causa}\n"
        f"🔍 *Subcausa:* {subcausa}\n"
        f"👮 *Supervisor:* {datos_hallazgo['telegram_nombre']} (@{datos_hallazgo['telegram_username']})\n"
        f"🕒 *Fecha:* {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "La información ha sido almacenada en la base de datos."
    )

    keyboard = []
    if is_manual:
        keyboard.append([{"text": "✍️ Ingresar otra OT Manual", "callback_data": "man:start"}])
        keyboard.append([{"text": "📋 Ver llamadas de la Ciudad", "callback_data": "nav:back_rng"}])
    else:
        keyboard.append([{"text": "🔄 Continuar con otra llamada", "callback_data": "nav:back_lls"}])
    keyboard.append([{"text": "🏙️ Cambiar Ciudad", "callback_data": "nav:back_com"}])
    keyboard.append([{"text": "👥 Cambiar Segmento", "callback_data": "nav:back_seg"}])
    keyboard.append([{"text": "🏠 Menú Principal", "callback_data": "nav:restart"}])

    markup = {"inline_keyboard": keyboard}
    edit_message(chat_id, message_id, texto, markup)

# -------------------------------------------------------------
# Enrutamiento de Callbacks y Mensajes
# -------------------------------------------------------------

def handle_callback(update):
    cb = update.get("callback_query")
    if not cb:
        return

    cb_id = cb["id"]
    data = cb.get("data", "")
    message = cb.get("message")
    chat_id = message["chat"]["id"] if message else None
    message_id = message["message_id"] if message else None
    from_user = cb.get("from", {})

    answer_callback_query(cb_id)

    session = get_session(chat_id)

    logger.info(f"Callback de @{from_user.get('username')}: data='{data}'")

    # Navegación general
    if data == "nav:restart":
        view_seleccionar_region(chat_id, message_id, from_user.get("first_name", "Supervisor"))
        return

    if data == "nav:cancel_manual":
        session['is_manual'] = False
        session['manual_ot'] = None
        session['manual_cuenta'] = None
        session['manual_segmento'] = None
        session['manual_proveedor_red'] = None
        view_seleccionar_rango(chat_id, message_id)
        return

    if data == "man:start":
        view_ingreso_manual_ot(chat_id, message_id)
        return

    if data == "man:confirm":
        view_detalle_manual(chat_id, message_id)
        return

    if data.startswith("man_seg:"):
        segmento = data.split(":", 1)[1]
        session['manual_segmento'] = segmento
        view_ingreso_manual_proveedor(chat_id, message_id)
        return

    if data.startswith("man_prov:"):
        prov = data.split(":", 1)[1]
        if prov.upper() == "ONNET":
            prov = "OnNet"
        elif prov.upper() == "ATP":
            prov = "Atp"
        else:
            prov = "Claro"
        session['manual_proveedor_red'] = prov
        reg = session.get('region') or ''
        ali = session.get('aliado') or ''
        red_val = session.get('red') or ''
        com = session.get('comunidad') or ''
        seg = session.get('manual_segmento') or session.get('segmento') or 'Masivo'

        # Si la OT o LLS existe en visitas_calidad, autocompletar si falta algún dato
        info_db = db.get_info_by_ot_or_lls(session.get('manual_ot'))
        if info_db:
            if not reg and info_db.get('region'):
                reg = info_db['region']
                session['region'] = reg
            if not ali and info_db.get('aliado'):
                ali = info_db['aliado']
                session['aliado'] = ali
            if not red_val and info_db.get('red'):
                red_val = info_db['red']
                session['red'] = red_val
            if not com and info_db.get('comunidad'):
                com = info_db['comunidad']
                session['comunidad'] = com

        session['visita'] = {
            'ot': session['manual_ot'],
            'cuenta': session['manual_cuenta'],
            'aliado': ali or 'Sin Aliado',
            'segmento': seg,
            'red': red_val or 'Sin Red',
            'proveedor_red': prov,
            'region': reg or 'Sin Región',
            'comunidad': com or 'Sin Ciudad',
            'primera_lls': session['manual_ot'],
            'rango_primer_arreglo': 'Manual / Fuera de Base',
            'estado': 'Manual',
            'trabajo': 'Ingreso Manual',
            'fecha_trabajo_ini': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        session['primera_lls'] = session['manual_ot']
        view_detalle_manual(chat_id, message_id)
        return

    if data == "nav:back_man_seg":
        view_ingreso_manual_segmento(chat_id, message_id)
        return

    if data == "nav:back_man_prov":
        view_ingreso_manual_proveedor(chat_id, message_id)
        return

    if data == "nav:back_red":
        view_seleccionar_red(chat_id, message_id)
        return

    if data == "nav:back_aliado":
        view_seleccionar_aliado(chat_id, message_id, session.get('page_ali', 0))
        return

    if data == "nav:back_seg":
        view_seleccionar_segmento(chat_id, message_id)
        return

    if data == "nav:back_com":
        view_seleccionar_comunidad(chat_id, message_id, session.get('page_com', 0))
        return

    if data == "nav:back_rng":
        view_seleccionar_rango(chat_id, message_id)
        return

    if data == "nav:back_lls":
        view_listar_llamadas(chat_id, message_id, session.get('page_lls', 0))
        return

    # Paginaciones
    if data.startswith("p_ali:"):
        page = int(data.split(":")[1])
        view_seleccionar_aliado(chat_id, message_id, page)
        return

    if data.startswith("p_com:"):
        page = int(data.split(":")[1])
        view_seleccionar_comunidad(chat_id, message_id, page)
        return

    if data.startswith("p_lls:"):
        page = int(data.split(":")[1])
        view_listar_llamadas(chat_id, message_id, page)
        return

    if data.startswith("p_cau:"):
        page = int(data.split(":")[1])
        view_seleccionar_causa(chat_id, message_id, page)
        return

    # Selección Región -> Ahora muestra opciones: Causa Raíz vs Inventario de Herramientas
    if data.startswith("reg:"):
        region = data.split(":", 1)[1]
        session['region'] = region
        view_seleccionar_modulo_region(chat_id, message_id)
        return

    if data == "nav:back_mod_reg":
        view_seleccionar_modulo_region(chat_id, message_id)
        return

    # Selección de Módulo tras elegir Región
    if data.startswith("mod_reg:"):
        opt = data.split(":", 1)[1]
        if opt == "causa_raiz":
            view_seleccionar_red(chat_id, message_id)
        elif opt == "inventario":
            view_inv_pedir_cedula(chat_id, message_id)
        return

    # ---------------------------------------------------------
    # Callbacks Módulo: Inventario de Herramientas
    # ---------------------------------------------------------
    if data == "inv_act:ficha":
        view_inv_ficha_tecnico(chat_id, message_id)
        return

    if data == "inv_act:update_mes":
        tec = session.get('inv_tecnico') or {}
        inv_mes = session.get('inv_mes_existente')
        if not inv_mes and tec.get('cedula'):
            inv_mes = db.get_inventario_mes_actual(tec.get('cedula'))
            session['inv_mes_existente'] = inv_mes
        if inv_mes:
            _cargar_inventario_mes_en_sesion(session, inv_mes)
            view_inv_menu_corregir(chat_id, message_id)
        else:
            session['inv_editing_from_summary'] = False
            view_inv_herramienta(chat_id, 0, message_id)
        return

    if data in ("inv_act:start_tools", "inv_act:start_tools_new"):
        session['inv_update_id'] = None
        session['inv_update_codigo'] = None
        session['inv_items'] = {}
        session['inv_foto_general'] = None
        session['inv_editing_from_summary'] = False
        view_inv_herramienta(chat_id, 0, message_id)
        return

    if data == "inv_act:foto_general":
        view_inv_foto_general(chat_id, message_id)
        return

    if data == "inv_act:resumen":
        view_inv_resumen(chat_id, message_id)
        return

    if data == "inv_act:corregir":
        view_inv_menu_corregir(chat_id, message_id)
        return

    if data == "inv_act:confirmar":
        view_inv_confirmar_guardar(chat_id, from_user, message_id)
        return

    if data == "inv_edit:aliado":
        view_inv_seleccionar_aliado(chat_id, message_id, 0)
        return

    if data == "inv_edit:ciudad":
        session['inv_ciudades_all_regions'] = False
        view_inv_seleccionar_ciudad(chat_id, message_id, 0)
        return

    if data == "inv_edit:region":
        view_inv_seleccionar_region(chat_id, message_id)
        return

    if data == "inv_edit:nombre":
        view_inv_pedir_nombre(chat_id, message_id)
        return

    if data.startswith("p_inv_ali:"):
        page = int(data.split(":", 1)[1])
        view_inv_seleccionar_aliado(chat_id, message_id, page)
        return

    if data.startswith("p_inv_ciu:"):
        page = int(data.split(":", 1)[1])
        view_inv_seleccionar_ciudad(chat_id, message_id, page)
        return

    if data.startswith("inv_ciu_scope:"):
        scope = data.split(":", 1)[1]
        session['inv_ciudades_all_regions'] = (scope == "all")
        view_inv_seleccionar_ciudad(chat_id, message_id, 0)
        return

    if data.startswith("inv_set_reg:"):
        reg = data.split(":", 1)[1]
        tec = session.get('inv_tecnico') or {}
        tec['region'] = reg
        session['region'] = reg
        session['inv_tecnico'] = tec
        if tec.get('cedula'):
            db.upsert_tecnico_inventario(tec)
            tec['en_base'] = True
        view_inv_ficha_tecnico(chat_id, message_id)
        return

    if data.startswith("inv_set_ali:"):
        idx = int(data.split(":", 1)[1])
        aliados = session.get('inv_aliados_list') or []
        if 0 <= idx < len(aliados):
            tec = session.get('inv_tecnico') or {}
            tec['aliado'] = aliados[idx]
            session['inv_tecnico'] = tec
            if tec.get('cedula'):
                db.upsert_tecnico_inventario(tec)
                tec['en_base'] = True
        view_inv_ficha_tecnico(chat_id, message_id)
        return

    if data.startswith("inv_set_ciu:"):
        idx = int(data.split(":", 1)[1])
        ciudades = session.get('inv_ciudades_list') or []
        if 0 <= idx < len(ciudades):
            ciu = ciudades[idx]
            tec = session.get('inv_tecnico') or {}
            tec['comunidad'] = ciu
            area_db = db.get_area_por_ciudad(ciu)
            if area_db:
                tec['area'] = area_db
            session['inv_tecnico'] = tec
            if tec.get('cedula'):
                db.upsert_tecnico_inventario(tec)
                tec['en_base'] = True
        view_inv_ficha_tecnico(chat_id, message_id)
        return

    if data.startswith("inv_tool:"):
        idx = int(data.split(":", 1)[1])
        view_inv_herramienta(chat_id, idx, message_id)
        return

    if data.startswith("inv_st:"):
        parts = data.split(":")
        idx = int(parts[1])
        estado = parts[2]
        tool_name = HERRAMIENTAS_INVENTARIO[idx]
        prev_item = session['inv_items'].get(idx, {})
        if estado == "FALTANTE":
            session['inv_items'][idx] = {
                'herramienta': tool_name,
                'estado': 'FALTANTE',
                'propiedad': 'N/A',
                'novedad': 'no disponible',
                'foto_path': None
            }
            if session.get('inv_editing_from_summary') and (session.get('inv_foto_general') or session.get('inv_update_id')):
                view_inv_resumen(chat_id, message_id)
            elif idx + 1 < len(HERRAMIENTAS_INVENTARIO):
                view_inv_herramienta(chat_id, idx + 1, message_id)
            else:
                view_inv_foto_general(chat_id, message_id)
            return

        prev_prop = prev_item.get('propiedad')
        if not prev_prop or prev_prop in ('N/A', 'No aplica'):
            prev_prop = 'Aliado'
        session['inv_items'][idx] = {
            'herramienta': tool_name,
            'estado': estado,
            'propiedad': prev_prop,
            'novedad': prev_item.get('novedad') if estado == "NOVEDAD" else None,
            'foto_path': prev_item.get('foto_path') if estado == "NOVEDAD" else None
        }
        view_inv_propiedad(chat_id, idx, message_id)
        return

    if data.startswith("inv_prop:"):
        parts = data.split(":")
        idx = int(parts[1])
        prop = parts[2]
        tool_name = HERRAMIENTAS_INVENTARIO[idx]
        item = session['inv_items'].get(idx, {'herramienta': tool_name, 'estado': 'OK'})
        item['propiedad'] = prop
        session['inv_items'][idx] = item

        estado = item.get('estado', 'OK')
        if estado == "NOVEDAD":
            view_inv_novedad(chat_id, idx, message_id)
        else:
            if session.get('inv_editing_from_summary') and (session.get('inv_foto_general') or session.get('inv_update_id')):
                view_inv_resumen(chat_id, message_id)
            elif idx + 1 < len(HERRAMIENTAS_INVENTARIO):
                view_inv_herramienta(chat_id, idx + 1, message_id)
            else:
                view_inv_foto_general(chat_id, message_id)
        return

    if data.startswith("inv_back_prop:"):
        idx = int(data.split(":", 1)[1])
        view_inv_propiedad(chat_id, idx, message_id)
        return

    if data.startswith("inv_back_nov:"):
        idx = int(data.split(":", 1)[1])
        view_inv_novedad(chat_id, idx, message_id)
        return

    if data.startswith("inv_nov:"):
        parts = data.split(":")
        idx = int(parts[1])
        nov_idx = int(parts[2])
        tool_name = HERRAMIENTAS_INVENTARIO[idx]
        _, nov_label = NOVEDADES_HERRAMIENTAS[nov_idx]
        prev_prop = session['inv_items'].get(idx, {}).get('propiedad') or 'Aliado'
        session['inv_items'][idx] = {
            'herramienta': tool_name,
            'estado': 'NOVEDAD',
            'propiedad': prev_prop,
            'novedad': nov_label,
            'foto_path': None
        }
        view_inv_foto_herramienta(chat_id, idx, message_id)
        return

    # Selección Red -> Ahora pasa a seleccionar Aliado
    if data.startswith("red:"):
        red = data.split(":", 1)[1]
        session['red'] = red
        view_seleccionar_aliado(chat_id, message_id, 0)
        return

    # Selección Aliado -> Pasa a seleccionar Segmento
    if data.startswith("ali:"):
        idx = int(data.split(":", 1)[1])
        aliados = session.get('aliados_list', [])
        if idx < len(aliados):
            session['aliado'] = aliados[idx]
            view_seleccionar_segmento(chat_id, message_id)
        return

    # Selección Segmento -> Pasa a seleccionar Ciudad (Comunidad)
    if data.startswith("seg:"):
        segmento = data.split(":", 1)[1]
        session['segmento'] = segmento
        view_seleccionar_comunidad(chat_id, message_id, 0)
        return

    # Selección Comunidad
    if data.startswith("com:"):
        idx = int(data.split(":", 1)[1])
        comunidades = session.get('comunidades_list', [])
        if idx < len(comunidades):
            session['comunidad'] = comunidades[idx]
            if session.get('red') == 'Red Neutra':
                view_opciones_red_neutra(chat_id, message_id)
            else:
                view_seleccionar_rango(chat_id, message_id)
        return

    # Opciones Red Neutra (Causa Raíz vs Validación Cambio Vías Onnet)
    if data.startswith("neutra_opt:"):
        opt = data.split(":", 1)[1]
        if opt == "causa_raiz":
            view_seleccionar_rango(chat_id, message_id)
        elif opt == "cambio_vias":
            view_vias_paso1_cuenta(chat_id, message_id)
        return

    # Callbacks Validación Cambio Vías Onnet
    if data.startswith("vias_auto:"):
        session['vias_auto'] = data.split(":", 1)[1]
        view_vias_paso3_exitoso(chat_id, message_id)
        return

    if data.startswith("vias_exito:"):
        resp_exito = data.split(":", 1)[1]
        session['vias_exito'] = resp_exito
        if resp_exito == "No":
            view_vias_paso_error(chat_id, message_id)
        else:
            session['vias_error'] = 'N/A'
            view_vias_paso4_tiempo(chat_id, message_id)
        return

    if data.startswith("vias_err:"):
        try:
            err_idx = int(data.split(":", 1)[1])
            session['vias_error'] = ERRORES_CAMBIO_VIAS[err_idx]
        except (ValueError, IndexError):
            session['vias_error'] = 'N/A'
        view_vias_paso4_tiempo(chat_id, message_id)
        return

    if data.startswith("vias_tiempo:"):
        session['vias_tiempo'] = data.split(":", 1)[1]
        view_vias_paso5_experiencia(chat_id, message_id)
        return

    if data.startswith("vias_exp:"):
        exp = data.split(":", 1)[1]
        session['vias_exp'] = exp
        
        user_info = from_user or {}
        first_name = user_info.get("first_name", "")
        last_name = user_info.get("last_name", "")
        nombre_completo = f"{first_name} {last_name}".strip() or "Supervisor"
        username = user_info.get("username", "")

        error_pres = session.get('vias_error') or 'N/A'
        datos = {
            'telegram_user_id': chat_id,
            'telegram_username': username,
            'telegram_nombre': nombre_completo,
            'region': session.get('region', ''),
            'red': session.get('red', 'Red Neutra'),
            'aliado': session.get('aliado', ''),
            'segmento': session.get('segmento', ''),
            'comunidad': session.get('comunidad', ''),
            'cuenta': int(session.get('vias_cuenta', 0)),
            'cambio_vias_automatico': session.get('vias_auto', ''),
            'cambio_vias_exitoso': session.get('vias_exito', ''),
            'error_presentado': error_pres,
            'tiempo_duracion': session.get('vias_tiempo', ''),
            'experiencia_tecnico': exp,
            'observaciones': ''
        }
        registro_id = db.guardar_validacion_vias(datos)
        
        error_line = f"• *Error presentado:* {error_pres}\n" if error_pres != 'N/A' else ""
        texto_confirmacion = (
            "✅ *¡Validación Cambio de Vías Onnet Guardada!*\n\n"
            f"🆔 *Registro:* `#{registro_id}`\n"
            f"📋 *Cuenta:* `{datos['cuenta']}`\n"
            f"🏙️ *Ciudad:* {datos['comunidad']} ({datos['region']})\n"
            f"🤝 *Aliado:* {datos['aliado']} | 👥 *Segmento:* {datos['segmento']}\n\n"
            f"• *Cambio automático:* {datos['cambio_vias_automatico']}\n"
            f"• *Cambio exitoso:* {datos['cambio_vias_exitoso']}\n"
            f"{error_line}"
            f"• *Duración:* {datos['tiempo_duracion']}\n"
            f"• *Experiencia:* {'👍 Positiva' if exp == 'Positiva' else '👎 Negativa'}\n"
            f"• *Registrado por:* {nombre_completo} (@{username})\n\n"
            "¡Los datos ya están disponibles en el panel de control web!"
        )
        keyboard = [
            [{"text": "🔄 Nueva Validación de Vías", "callback_data": "neutra_opt:cambio_vias"}],
            [{"text": "🏠 Menú Principal", "callback_data": "nav:restart"}]
        ]
        markup = {"inline_keyboard": keyboard}
        edit_message(chat_id, message_id, texto_confirmacion, markup)
        return

    if data == "vias_back:cuenta":
        view_vias_paso1_cuenta(chat_id, message_id)
        return

    if data == "vias_back:auto":
        view_vias_paso2_auto(chat_id, message_id)
        return

    if data == "vias_back:exito":
        view_vias_paso3_exitoso(chat_id, message_id)
        return

    if data == "vias_back:error":
        view_vias_paso_error(chat_id, message_id)
        return

    if data == "vias_back:tiempo":
        view_vias_paso4_tiempo(chat_id, message_id)
        return

    if data == "nav:back_neutra_opt":
        view_opciones_red_neutra(chat_id, message_id)
        return

    # Selección Rango
    if data.startswith("rng:"):
        idx = int(data.split(":", 1)[1])
        rangos = session.get('rangos_list', [])
        if idx < len(rangos):
            session['rango'] = rangos[idx]
            view_listar_llamadas(chat_id, message_id, 0)
        return

    # Selección Llamada de servicio
    if data.startswith("lls:"):
        primera_lls = int(data.split(":", 1)[1])
        view_detalle_llamada(chat_id, primera_lls, message_id)
        return

    # Botón Realizar Causa Raíz
    if data == "action:causa_raiz":
        visita = session.get('visita') or {}
        if not session.get('is_manual') and visita:
            diligenciada = db.is_ot_diligenciada(visita.get('ot'), visita.get('primera_lls'))
            if diligenciada:
                answer_callback_query(cb_id, text="⚠️ Esta OT ya fue diligenciada por otro supervisor.", show_alert=True)
                view_listar_llamadas(chat_id, message_id, session.get('page_lls', 0))
                return
        view_seleccionar_causa(chat_id, message_id, 0)
        return

    # Selección Causa
    if data.startswith("cau:"):
        idx = int(data.split(":", 1)[1])
        view_seleccionar_subcausa(chat_id, idx, message_id)
        return

    # Selección Subcausa -> Guardar
    if data.startswith("sub:"):
        idx = int(data.split(":", 1)[1])
        view_guardar_resultado(chat_id, idx, from_user, message_id)
        return

def handle_message(update):
    message = update.get("message")
    if not message:
        return

    chat_id = message["chat"]["id"]
    from_user = message.get("from", {})
    text = (message.get("text") or message.get("caption") or "").strip()

    session = get_session(chat_id)
    step = session.get('step')

    # Extraer foto si el mensaje contiene imagen
    file_id_foto = None
    if message.get("photo"):
        file_id_foto = message["photo"][-1]["file_id"]
    elif message.get("document") and str(message["document"].get("mime_type", "")).startswith("image/"):
        file_id_foto = message["document"]["file_id"]

    logger.info(f"Mensaje recibido de {from_user.get('username')} (step={step}): text='{text}', has_photo={bool(file_id_foto)}")

    # Si el usuario envía comandos de reinicio
    if text.lower() in ["/start", "/inicio", "/reiniciar", "/reset"]:
        first_name = from_user.get("first_name", "Supervisor")
        view_seleccionar_region(chat_id, None, first_name)
        return

    # ---------------------------------------------------------
    # Mensajes y Fotos del Módulo: Inventario de Herramientas
    # ---------------------------------------------------------
    if step == 'INV_CEDULA':
        digits = re.sub(r"\D", "", text)
        if not digits:
            send_message(
                chat_id,
                "⚠️ *Número de Cédula inválido.*\n"
                "Por favor digita el número de cédula del técnico (solo números):",
                {"inline_keyboard": [[{"text": "⬅️ Volver", "callback_data": "nav:back_mod_reg"}]]}
            )
            return
        tec = db.get_tecnico_by_cedula(digits)
        if tec:
            tec['en_base'] = True
            if _is_missing_val(tec.get('region')) and session.get('region'):
                tec['region'] = session['region']
        else:
            tec = {
                'cedula': digits,
                'nombre_tecnico': '',
                'aliado': '',
                'region': session.get('region') or '',
                'comunidad': '',
                'area': '',
                'en_base': False
            }
        session['inv_tecnico'] = tec
        session['inv_mes_existente'] = db.get_inventario_mes_actual(digits)
        session['inv_update_id'] = None
        session['inv_update_codigo'] = None
        view_inv_ficha_tecnico(chat_id)
        return

    if step == 'INV_NOMBRE':
        nombre_clean = text.strip().upper()
        if len(nombre_clean) < 3:
            send_message(
                chat_id,
                "⚠️ Por favor escribe el *Nombre Completo* válido del técnico:",
                {"inline_keyboard": [[{"text": "⬅️ Cancelar", "callback_data": "inv_act:ficha"}]]}
            )
            return
        tec = session.get('inv_tecnico') or {}
        tec['nombre_tecnico'] = nombre_clean
        session['inv_tecnico'] = tec
        if tec.get('cedula'):
            db.upsert_tecnico_inventario(tec)
            tec['en_base'] = True
        view_inv_ficha_tecnico(chat_id)
        return

    if step == 'INV_SELECT_CIUDAD' and text:
        view_inv_seleccionar_ciudad(chat_id, None, 0, search_query=text)
        return

    if step == 'INV_FOTO_TOOL':
        idx = session.get('inv_current_idx', 0)
        if not file_id_foto:
            send_message(
                chat_id,
                "⚠️ *Imagen requerida.*\n"
                f"Por favor toma o adjunta una *foto* de la herramienta *{HERRAMIENTAS_INVENTARIO[idx]}*:",
                {"inline_keyboard": [[{"text": "⬅️ Cambiar tipo de novedad", "callback_data": f"inv_back_nov:{idx}"}]]}
            )
            return
        foto_rel = descargar_y_comprimir_foto(file_id_foto, prefix=f"tool_{idx + 1}")
        if not foto_rel:
            send_message(
                chat_id,
                "⚠️ No se pudo procesar la foto. Por favor intenta enviarla nuevamente:",
                {"inline_keyboard": [[{"text": "⬅️ Cambiar tipo de novedad", "callback_data": f"inv_back_nov:{idx}"}]]}
            )
            return
        if idx in session['inv_items']:
            session['inv_items'][idx]['foto_path'] = foto_rel

        if session.get('inv_editing_from_summary') and (session.get('inv_foto_general') or session.get('inv_update_id')):
            view_inv_resumen(chat_id)
        elif idx + 1 < len(HERRAMIENTAS_INVENTARIO):
            view_inv_herramienta(chat_id, idx + 1)
        else:
            view_inv_foto_general(chat_id)
        return

    if step == 'INV_FOTO_GENERAL':
        total = len(HERRAMIENTAS_INVENTARIO)
        if not file_id_foto:
            send_message(
                chat_id,
                "⚠️ *Foto general requerida.*\n"
                "Por favor toma o adjunta una *foto general de toda la herramienta inventariada*:",
                {"inline_keyboard": [[{"text": "⬅️ Volver a la última herramienta", "callback_data": f"inv_tool:{total - 1}"}]]}
            )
            return
        foto_rel = descargar_y_comprimir_foto(file_id_foto, prefix="general")
        if not foto_rel:
            send_message(
                chat_id,
                "⚠️ No se pudo procesar la foto general. Por favor intenta enviarla nuevamente:"
            )
            return
        session['inv_foto_general'] = foto_rel
        view_inv_resumen(chat_id)
        return

    # Si está en el paso de ingresar OT manual
    if step == 'MANUAL_OT':
        digits = re.sub(r"\D", "", text)
        if not digits:
            send_message(
                chat_id,
                "⚠️ *Número de OT inválido.*\n"
                "Por favor escribe el número de la Orden de Trabajo (solo números):",
                {"inline_keyboard": [[{"text": "⬅️ Cancelar", "callback_data": "nav:cancel_manual"}]]}
            )
            return
        session['manual_ot'] = int(digits)
        view_ingreso_manual_cuenta(chat_id)
        return

    # Si está en el paso de ingresar Cuenta manual
    if step == 'MANUAL_CUENTA':
        digits = re.sub(r"\D", "", text)
        if not digits:
            send_message(
                chat_id,
                "⚠️ *Número de Cuenta inválido.*\n"
                "Por favor escribe el número de la Cuenta (solo números):",
                {"inline_keyboard": [[{"text": "⬅️ Cancelar", "callback_data": "nav:cancel_manual"}]]}
            )
            return
        session['manual_cuenta'] = int(digits)
        view_ingreso_manual_segmento(chat_id)
        return

    # Si está en el paso de ingresar Cuenta para Validación Cambio de Vías Onnet
    if step == 'VIAS_CUENTA':
        digits = re.sub(r"\D", "", text)
        if not digits:
            send_message(
                chat_id,
                "⚠️ *Número de Cuenta inválido.*\n"
                "Por favor escribe el número de la Cuenta (solo números):",
                {"inline_keyboard": [[{"text": "⬅️ Volver", "callback_data": "nav:back_neutra_opt"}]]}
            )
            return
        session['vias_cuenta'] = int(digits)
        view_vias_paso2_auto(chat_id)
        return

    # Ante cualquier otro mensaje fuera de flujo guiado
    first_name = from_user.get("first_name", "Supervisor")
    view_seleccionar_region(chat_id, None, first_name)

def poll_updates():
    """Bucle principal de Long Polling para escuchar eventos de Telegram."""
    last_update_id = 0
    logger.info(f"Iniciando Bot de Telegram con token: {TELEGRAM_TOKEN[:10]}... (Poller activo)")
    
    # Verificar información del Bot
    try:
        me_resp = requests.get(f"{API_URL}/getMe", timeout=10).json()
        if me_resp.get("ok"):
            bot_info = me_resp["result"]
            logger.info(f"Bot conectado exitosamente: @{bot_info.get('username')} ({bot_info.get('first_name')})")
        else:
            logger.error(f"Error verificando Bot Token: {me_resp}")
    except Exception as e:
        logger.error(f"Fallo al conectar con Telegram API: {e}")

    while True:
        try:
            url = f"{API_URL}/getUpdates?offset={last_update_id + 1}&timeout=30"
            resp = requests.get(url, timeout=35)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        last_update_id = update["update_id"]
                        if "callback_query" in update:
                            handle_callback(update)
                        elif "message" in update:
                            handle_message(update)
            else:
                logger.warning(f"Respuesta inesperada de Telegram: {resp.status_code}")
                time.sleep(2)
        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            logger.error(f"Error en bucle de polling: {e}")
            time.sleep(3)

if __name__ == "__main__":
    db.init_db()
    poll_updates()
