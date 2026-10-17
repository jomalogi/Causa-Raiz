import os
import sys
import threading
import time
import logging
from pathlib import Path

import db
import bot
from web_app import app

logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("AppRunner")

def run_bot_thread():
    logger.info("Iniciando hilo del Bot de Telegram...")
    try:
        bot.poll_updates()
    except Exception as e:
        logger.critical(f"Error fatal en hilo del Bot de Telegram: {e}")

if __name__ == "__main__":
    print("=" * 70)
    print("SISTEMA DE CALIDAD, CAUSA RAÍZ Y BOT DE TELEGRAM")
    print("=" * 70)
    
    # 1. Inicializar Base de Datos y Tablas
    db.init_db()

    # 2. Cargar matriz de causas si no tiene datos
    causas_actuales = db.get_causas()
    if not causas_actuales:
        matriz_file = Path(__file__).resolve().parent / "Matriz_Causas_Subcausas.xlsx"
        if matriz_file.exists():
            logger.info("Cargando matriz inicial de causas y subcausas...")
            db.cargar_matriz_excel(str(matriz_file))

    # 3. Iniciar el hilo del Bot de Telegram en segundo plano
    t = threading.Thread(target=run_bot_thread, daemon=True)
    t.start()
    logger.info("Hilo del Bot de Telegram iniciado exitosamente.")

    # 4. Iniciar la aplicacion Web en el puerto 8505
    port = int(os.getenv("PORT", 8505))
    logger.info(f"Iniciando panel web en http://0.0.0.0:{port} ...")
    try:
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario.")
