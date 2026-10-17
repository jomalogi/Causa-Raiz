# 🎯 Sistema de Calidad y Clasificación Causa Raíz

Sistema integral para la gestión, auditoría y análisis de causa raíz en visitas técnicas y llamadas de servicio de telecomunicaciones. Integra un **Bot interactivo de Telegram**, un **Panel Web administrativo en Flask** y un **Dashboard de visualización y métricas en Streamlit**, respaldados por una base de datos **MySQL**.

---

## 🏗️ Arquitectura del Sistema

```
                      ┌───────────────────────────────────────────────┐
                      │            Supervisores en Campo              │
                      └──────────────────────┬────────────────────────┘
                                             │
                                             ▼
                                   ┌──────────────────┐
                                   │  @causaraiz_bot  │  (Telegram Bot)
                                   └─────────┬────────┘
                                             │
                   ┌─────────────────────────┴─────────────────────────┐
                   ▼                                                   ▼
┌──────────────────────────────────────┐             ┌───────────────────────────────────┐
│     Panel Web Administrativo         │             │      Tablero Causa Raíz           │
│     (Flask - Puerto 8505)            │             │    (Streamlit - Puerto 8506)      │
│  - Carga masiva Visitas_Calidad.xlsx │             │  - Filtro por Región y Segmento   │
│  - Descarga consolidada de hallazgos │             │  - Gráfico de dona participación  │
│  - Estadísticas en tiempo real       │             │  - Desglose por Causas/Subcausas  │
└──────────────────┬───────────────────┘             └─────────────────┬─────────────────┘
                   │                                                   │
                   └─────────────────────────┬─────────────────────────┘
                                             ▼
                                  ┌────────────────────┐
                                  │    Base de Datos   │
                                  │       MySQL        │
                                  │ (calidad_visitas)  │
                                  └────────────────────┘
```

---

## 🌟 Características Principales

### 1. 🤖 Bot de Telegram (`@causaraiz_bot`)
* **Flujo Guiado Paso a Paso:**
  $$\text{Región} \longrightarrow \text{Red} \longrightarrow \text{Aliado} \longrightarrow \mathbf{\text{Segmento}} \longrightarrow \text{Ciudad / Comunidad} \longrightarrow \text{Rango} \longrightarrow \text{Lista de OTs / LLS} \longrightarrow \text{Causa Raíz}$$
* **Filtrado Dinámico:** Cada nivel de selección filtra en cascada las opciones del siguiente paso.
* **Exclusión Automática de OTs Diligenciadas (`NOT EXISTS`):**
  * Cuando una OT es completada por un supervisor, desaparece automáticamente de la lista de pendientes de Telegram.
  * Si un registro es eliminado de la base de datos, la OT vuelve a estar disponible inmediatamente sin reiniciar servicios ni borrar cachés.
* **Control de Concurrencia:** Previene que dos supervisores clasifiquen la misma OT en paralelo mediante validación en tiempo real.
* **Ingreso Manual de OTs:** Permite ingresar OTs fuera de base solicitando Orden, Cuenta y Segmento (`Masivo` / `Corporativo`), conservando la trazabilidad completa.
* **Matriz Oficial de Causas:** Despliega las 17 causas principales y filtra sus subcausas específicas según la matriz corporativa.

### 2. 🌐 Panel Web Administrativo (Puerto 8505)
* Carga diaria del archivo `Visitas_Calidad.xlsx` con control de lotes (`cargues_control`).
* Visualización de métricas globales (Total de visitas en base, total de hallazgos registrados).
* Descarga de reportes consolidados en formato Excel con un solo clic.
* Historial de auditoría de los últimos hallazgos registrados por los supervisores.

### 3. 📊 Dashboard Analítico (Streamlit - Puerto 8506)
* Módulo: **Causa Raíz Nacional**.
* Filtros interactivos por **Región**, **Segmento** (`Masivo` / `Corporativo`), **Aliado** y rangos de fechas.
* Gráfico de dona con la distribución porcentual de hallazgos por Región.
* Gráfico de barras de Pareto con las Causas y Subcausas más incidentes.

---

## 🗄️ Modelo de Base de Datos (MySQL: `calidad_visitas`)

| Tabla | Descripción |
| :--- | :--- |
| `cargues_control` | Historial y metadatos de los archivos Excel cargados (ID lote, fecha, usuario, total registros). |
| `visitas_calidad` | Registro detallado de llamadas de servicio y órdenes de trabajo (OT, Cuenta, Aliado, Red, Región, Segmento, Comunidad, PrimeraLLS, RangoPrimerArreglo). |
| `matriz_causas_subcausas` | Catálogo de referencia de causas raíz y subcausas autorizadas. |
| `hallazgos_respuestas` | Registro de causas raíz capturadas por supervisores (Supervisor, OT, Cuenta, Causa, Subcausa, Observaciones, Timestamp). |

---

## 🚀 Instalación y Despliegue

### Requisitos Previos
* Python 3.10 o superior.
* Servidor MySQL 8.0 o compatible.
* Bot Token de Telegram obtenido mediante [@BotFather](https://t.me/BotFather).

### 1. Clonar el Repositorio
```bash
git clone https://github.com/jomalogi/Causa-Raiz.git
cd Causa-Raiz
```

### 2. Crear Entorno Virtual e Instalar Dependencias
```bash
python -m venv venv
# En Windows:
venv\Scripts\activate
# En Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configurar Variables de Entorno
Copia el archivo de ejemplo y configura tus credenciales:
```bash
cp .env.example .env
```
Edita `.env` con los datos de tu entorno:
```ini
TELEGRAM_TOKEN=tu_token_de_telegram_aqui
DB_TYPE=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=tu_password_aqui
DB_NAME=calidad_visitas
PORT=8505
```

### 4. Inicializar la Base de Datos
Ejecuta el script SQL en tu servidor MySQL:
```bash
mysql -u root -p < schema.sql
```

### 5. Iniciar la Aplicación
```bash
python app.py
```
El sistema iniciará automáticamente:
1. El verificador e inicializador de tablas MySQL.
2. El hilo de escucha activa (Long Polling) del Bot de Telegram.
3. El servidor Web Flask en `http://0.0.0.0:8505`.

---

## 🐧 Configuración como Servicio en Linux (Systemd)

Para entornos de producción (Ubuntu/Debian), el proyecto incluye el instalador automático `instalar_servidor.sh` que configura el servicio `/etc/systemd/system/bot-calidad.service`:

```bash
chmod +x instalar_servidor.sh
sudo ./instalar_servidor.sh
```

### Comandos de Administración del Servicio:
```bash
# Ver estado del servicio
sudo systemctl status bot-calidad

# Reiniciar el servicio
sudo systemctl restart bot-calidad

# Consultar logs en tiempo real
sudo journalctl -u bot-calidad -f
```

---

## 📂 Estructura del Proyecto

```
Causa-Raiz/
│
├── app.py                      # Punto de entrada principal (Inicia Bot + Web)
├── bot.py                      # Lógica interactiva del Bot de Telegram
├── db.py                       # Capa de abstracción de datos (MySQL / SQLite)
├── web_app.py                  # Servidor y rutas del Panel Web Flask (8505)
├── schema.sql                  # Definición del esquema DDL de MySQL
├── cargar_base.py              # Script ETL para carga de Visitas_Calidad.xlsx
├── unificar_aliado.py          # Normalizador y homologador de nombres de aliados
├── Matriz_Causas_Subcausas.xlsx# Matriz oficial de Causas y Subcausas
│
├── Iniciar_Bot_Local.bat       # Lanzador rápido en entorno local (Windows)
├── Subir_Excel_Diario.bat      # Lanzador para subida diaria de bases
├── Desplegar_Al_Servidor.bat   # Script de despliegue automatizado por SSH
├── desplegar_remoto.py         # Conector Paramiko para despliegue remoto
├── actualizar_servidor.py      # Actualizador remoto de código
│
├── requirements.txt            # Dependencias del proyecto
├── .env.example                # Plantilla de variables de entorno
├── .gitignore                  # Reglas de exclusión de Git
└── diagnostics/                # Scripts de diagnóstico, pruebas y conectividad
```

---

## 👥 Contribuciones y Autoría
* **Autor:** Johan Mauricio López ([@jomalogi](https://github.com/jomalogi))
* **Organización:** Gestión de Calidad y Operaciones
