import os
import sys
import time
import json
import logging
import requests
from pathlib import Path

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

# Diccionario para almacenar el estado de la conversación por usuario
# chat_id -> dict
USER_SESSIONS = {}

def get_session(chat_id):
    if chat_id not in USER_SESSIONS:
        USER_SESSIONS[chat_id] = {
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
            'is_manual': False,
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
            'subcausas_list': []
        }
    return USER_SESSIONS[chat_id]

def reset_session(chat_id):
    USER_SESSIONS[chat_id] = {
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
        'is_manual': False,
        'page_ali': 0,
        'page_com': 0,
        'page_lls': 0,
        'page_cau': 0,
        'aliados_list': [],
        'segmentos_list': [],
        'comunidades_list': [],
        'rangos_list': [],
        'llamadas_list': [],
        'causas_list': [],
        'subcausas_list': []
    }
    return USER_SESSIONS[chat_id]

# -------------------------------------------------------------
# Funciones de Comunicacion con Telegram Bot API
# -------------------------------------------------------------

def send_message(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    """Envia un mensaje a un chat de Telegram."""
    url = f"{API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.json()
    except Exception as e:
        logger.error(f"Error al enviar mensaje a {chat_id}: {e}")
        return None

def edit_message(chat_id, message_id, text, reply_markup=None, parse_mode="Markdown"):
    """Edita el texto y botones de un mensaje existente."""
    url = f"{API_URL}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.json()
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
            "⚠️ *No hay registros de visitas disponibles en este momento.*\n"
            "Por favor asegúrate de que se haya cargado la base diaria `Visitas_Calidad.xlsx`."
        )
        markup = {"inline_keyboard": [[{"text": "🔄 Reintentar", "callback_data": "nav:restart"}]]}
        if message_id:
            edit_message(chat_id, message_id, texto, markup)
        else:
            send_message(chat_id, texto, markup)
        return

    session['step'] = 'SELECT_REGION'
    
    texto = (
        f"👋 ¡Hola *{first_name}*! Bienvenido al *Bot de Causa Raíz de Calidad*.\n\n"
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

def view_seleccionar_red(chat_id, message_id=None):
    """Paso 2: Solicitar Red para la Región elegida."""
    session = get_session(chat_id)
    region = session['region']
    redes = db.get_redes(region)
    
    if not redes:
        texto = f"⚠️ No se encontraron tipos de Red para la Región *{region}*."
        markup = {"inline_keyboard": [[{"text": "⬅️ Cambiar Región", "callback_data": "nav:restart"}]]}
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
    keyboard.append([{"text": "⬅️ Cambiar Región", "callback_data": "nav:restart"}])
    
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
                [{"text": "⬅️ Cambiar Ciudad", "callback_data": "nav:back_com"}]
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
    keyboard.append([{"text": "⬅️ Cambiar Ciudad", "callback_data": "nav:back_com"}])
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

def view_ingreso_manual_segmento(chat_id):
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
    send_message(chat_id, texto, markup)

def view_detalle_manual(chat_id, message_id=None):
    """Paso Manual 4: Resumen y botón para pasar a Realizar Causa Raíz."""
    session = get_session(chat_id)
    visita = session.get('visita', {})
    session['step'] = 'VIEW_DETAIL_MANUAL'

    texto = (
        "📄 *INFORMACIÓN DE LA VISITA (INGRESO MANUAL)*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛠️ *OT:* `{visita.get('ot')}`\n"
        f"👤 *Cuenta:* `{visita.get('cuenta')}`\n"
        f"🏢 *Segmento:* {visita.get('segmento')}\n"
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
    region_val = session.get('region') or visita.get('region') or ''
    is_manual = session.get('is_manual', False)

    # Preparar payload para insertar en MySQL
    datos_hallazgo = {
        'telegram_user_id': user_info.get('id'),
        'telegram_username': user_info.get('username', ''),
        'telegram_nombre': f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip(),
        'ot': visita.get('ot'),
        'cuenta': visita.get('cuenta'),
        'aliado': visita.get('aliado'),
        'region': region_val,
        'segmento': visita.get('segmento'),
        'red': visita.get('red'),
        'comunidad': visita.get('comunidad'),
        'primera_lls': visita.get('primera_lls'),
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
        session['visita'] = {
            'ot': session['manual_ot'],
            'cuenta': session['manual_cuenta'],
            'aliado': session.get('aliado', 'Sin Aliado'),
            'segmento': segmento,
            'red': session.get('red', 'Sin Red'),
            'region': session.get('region', 'Sin Región'),
            'comunidad': session.get('comunidad', 'Sin Ciudad'),
            'primera_lls': session['manual_ot'],
            'rango_primer_arreglo': 'Manual / Fuera de Base',
            'estado': 'Manual',
            'trabajo': 'Ingreso Manual',
            'fecha_trabajo_ini': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        session['primera_lls'] = session['manual_ot']
        view_detalle_manual(chat_id, message_id)
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

    # Selección Región
    if data.startswith("reg:"):
        region = data.split(":", 1)[1]
        session['region'] = region
        view_seleccionar_red(chat_id, message_id)
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
            view_seleccionar_rango(chat_id, message_id)
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
    text = message.get("text", "").strip()

    logger.info(f"Mensaje recibido de {from_user.get('username')}: '{text}'")

    session = get_session(chat_id)
    step = session.get('step')

    # Si el usuario envía comandos de reinicio
    if text.lower() in ["/start", "/inicio", "/reiniciar", "/reset"]:
        first_name = from_user.get("first_name", "Supervisor")
        view_seleccionar_region(chat_id, None, first_name)
        return

    # Si está en el paso de ingresar OT manual
    if step == 'MANUAL_OT':
        import re
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
        import re
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
