#!/usr/bin/env bash
# ==============================================================================
# SCRIPT DE INSTALACION Y DESPLIEGUE - BOT CALIDAD Y CAUSA RAIZ
# Servidor: 10.108.34.74 (root:Claro2026) | Puerto Web: 8505 | SSH: 822
# ==============================================================================

set -e

APP_DIR="/opt/bot_calidad"
SERVICE_NAME="bot-calidad"
DB_NAME="calidad_visitas"
DB_USER="root"
DB_PASS="Claro2026"
PORT=8505

echo "=========================================================================="
echo " INICIANDO INSTALACION DEL BOT DE CALIDAD Y CAUSA RAIZ EN UBUNTU/DEBIAN"
echo "=========================================================================="

# 1. Actualizar repositorios e instalar paquetes base
echo "[1/7] Instalando paquetes del sistema..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-pip python3-venv mysql-server ufw curl

# 2. Iniciar y asegurar MySQL Server
echo "[2/7] Configurando MySQL..."
systemctl enable mysql
systemctl start mysql

# Configurar usuarios y base de datos
mysql -u root <<EOF
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER USER 'root'@'localhost' IDENTIFIED BY '${DB_PASS}';
CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;
FLUSH PRIVILEGES;
EOF

# 3. Preparar directorio de la aplicacion
echo "[3/7] Preparando directorio ${APP_DIR}..."
mkdir -p ${APP_DIR}
mkdir -p ${APP_DIR}/uploads

# Copiar archivos si el script se ejecuta desde la carpeta descomprimida
if [ -f "app.py" ]; then
    cp -r * ${APP_DIR}/
fi

cd ${APP_DIR}

# 4. Crear entorno virtual de Python e instalar librerias
echo "[4/7] Configurando entorno virtual Python..."
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install pymysql flask pandas openpyxl requests

# 5. Inicializar Tablas en MySQL
echo "[5/7] Creando tablas en la base de datos ${DB_NAME}..."
mysql -u ${DB_USER} -p${DB_PASS} ${DB_NAME} < ${APP_DIR}/schema.sql

# Cargar matriz y base inicial si existen los archivos Excel
if [ -f "${APP_DIR}/Matriz_Causas_Subcausas.xlsx" ]; then
    echo "Cargando matriz de causas y subcausas..."
    DB_TYPE=mysql DB_HOST=localhost DB_USER=${DB_USER} DB_PASSWORD=${DB_PASS} DB_NAME=${DB_NAME} \
    ./venv/bin/python3 -c "import db; db.cargar_matriz_excel('${APP_DIR}/Matriz_Causas_Subcausas.xlsx')"
fi

if [ -f "${APP_DIR}/Visitas_Calidad.xlsx" ]; then
    echo "Cargando visitas iniciales desde Visitas_Calidad.xlsx..."
    DB_TYPE=mysql DB_HOST=localhost DB_USER=${DB_USER} DB_PASSWORD=${DB_PASS} DB_NAME=${DB_NAME} \
    ./venv/bin/python3 ${APP_DIR}/cargar_base.py "${APP_DIR}/Visitas_Calidad.xlsx"
fi

# 6. Crear archivo de servicio Systemd
echo "[6/7] Creando servicio systemd ${SERVICE_NAME}..."
cat <<EOF > /etc/systemd/system/${SERVICE_NAME}.service
[Unit]
Description=Bot de Telegram y Panel Web Calidad Causa Raiz (Puerto ${PORT})
After=network.target mysql.service
Wants=mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}
Environment="PATH=${APP_DIR}/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
Environment="DB_TYPE=mysql"
Environment="DB_HOST=127.0.0.1"
Environment="DB_PORT=3306"
Environment="DB_USER=${DB_USER}"
Environment="DB_PASSWORD=${DB_PASS}"
Environment="DB_NAME=${DB_NAME}"
Environment="PORT=${PORT}"
Environment="TELEGRAM_TOKEN=8978005290:AAHkQcCm8dnIrHJ9lnNFNAUZElVZ6OghN9k"
ExecStart=${APP_DIR}/venv/bin/python3 ${APP_DIR}/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl restart ${SERVICE_NAME}

# 7. Configurar Firewall para el puerto 8505
echo "[7/7] Habilitando puerto ${PORT} en el firewall..."
if command -v ufw &> /dev/null; then
    ufw allow ${PORT}/tcp || true
fi

echo "=========================================================================="
echo " ¡INSTALACION COMPLETADA EXITOSAMENTE!"
echo "=========================================================================="
echo " - Panel Web disponible en:  http://10.108.34.74:${PORT}/"
echo " - Bot de Telegram activo:   @causaraiz_bot"
echo " - Estado del servicio:      systemctl status ${SERVICE_NAME}"
echo " - Logs en tiempo real:      journalctl -u ${SERVICE_NAME} -f"
echo "=========================================================================="
