import os
import io
import time
import logging
from pathlib import Path
from flask import Flask, request, render_template_string, redirect, url_for, flash, send_file, jsonify
import pandas as pd

import db

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "calidad_visitas_claro_2026_key")

UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Panel de Control - Calidad y Causa Raíz (Puerto 8505)</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    <style>
        body { background-color: #f4f6f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .navbar-custom { background: linear-gradient(135deg, #da291c, #9e1b12); }
        .card-stat { border-radius: 12px; border: none; box-shadow: 0 4px 12px rgba(0,0,0,0.06); transition: transform 0.2s; }
        .card-stat:hover { transform: translateY(-3px); }
        .table-responsive { max-height: 480px; }
        .badge-pill { border-radius: 50px; font-weight: 500; }
        .btn-claro { background-color: #da291c; color: white; }
        .btn-claro:hover { background-color: #b51f15; color: white; }
    </style>
</head>
<body>
    <!-- Navbar -->
    <nav class="navbar navbar-expand-lg navbar-dark navbar-custom shadow-sm mb-4">
        <div class="container-fluid px-4">
            <a class="navbar-brand fw-bold" href="/">
                <i class="bi bi-shield-check me-2"></i>Calidad y Causa Raíz - Supervisión
            </a>
            <div class="d-flex align-items-center text-white">
                <span class="badge bg-success me-3"><i class="bi bi-robot me-1"></i>Bot: @causaraiz_bot</span>
                <span class="badge bg-light text-dark"><i class="bi bi-hdd-network me-1"></i>Puerto: 8505</span>
            </div>
        </div>
    </nav>

    <div class="container-fluid px-4">
        <!-- Notificaciones Flash -->
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show shadow-sm" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <!-- KPIs Estadisticas -->
        <div class="row g-3 mb-4">
            <div class="col-md-3">
                <div class="card card-stat p-3 bg-white">
                    <div class="d-flex align-items-center">
                        <div class="p-3 bg-primary bg-opacity-10 text-primary rounded-3 me-3 fs-3">
                            <i class="bi bi-table"></i>
                        </div>
                        <div>
                            <div class="text-muted small">Total Visitas Cargadas</div>
                            <h3 class="fw-bold mb-0 text-dark">{{ "{:,}".format(stats.total_visitas or 0) }}</h3>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-md-3">
                <div class="card card-stat p-3 bg-white">
                    <div class="d-flex align-items-center">
                        <div class="p-3 bg-success bg-opacity-10 text-success rounded-3 me-3 fs-3">
                            <i class="bi bi-check2-circle"></i>
                        </div>
                        <div>
                            <div class="text-muted small">Causa Raíz Registradas</div>
                            <h3 class="fw-bold mb-0 text-dark">{{ "{:,}".format(stats.total_hallazgos or 0) }}</h3>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-md-3">
                <div class="card card-stat p-3 bg-white">
                    <div class="d-flex align-items-center">
                        <div class="p-3 bg-info bg-opacity-10 text-info rounded-3 me-3 fs-3">
                            <i class="bi bi-clock-history"></i>
                        </div>
                        <div>
                            <div class="text-muted small">Último Cargue de Base</div>
                            <div class="fw-bold text-dark" style="font-size: 0.95rem;">
                                {% if stats.ultimo_cargue %}
                                    Lote #{{ stats.ultimo_cargue.id }} ({{ stats.ultimo_cargue.total_registros }} reg)
                                {% else %}
                                    Sin cargues aún
                                {% endif %}
                            </div>
                            <div class="text-muted small" style="font-size: 0.78rem;">
                                {{ stats.ultimo_cargue.fecha_cargue if stats.ultimo_cargue else '' }}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-md-3">
                <div class="card card-stat p-3 bg-white">
                    <div class="d-flex align-items-center">
                        <div class="p-3 bg-danger bg-opacity-10 text-danger rounded-3 me-3 fs-3">
                            <i class="bi bi-telegram"></i>
                        </div>
                        <div>
                            <div class="text-muted small">Bot de Telegram</div>
                            <div class="fw-bold text-dark">Activo (@causaraiz_bot)</div>
                            <a href="https://t.me/causaraiz_bot" target="_blank" class="small text-decoration-none">Abrir Bot en Telegram &rarr;</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="row g-4 mb-4">
            <!-- Columna Izquierda: Formulario de Cargue Diario -->
            <div class="col-lg-5">
                <div class="card card-stat h-100">
                    <div class="card-header bg-white py-3 border-0">
                        <h5 class="fw-bold mb-0 text-dark"><i class="bi bi-cloud-arrow-up me-2 text-danger"></i>Cargue Diario de Visitas</h5>
                        <p class="text-muted small mb-0">Sube el archivo Excel <code>Visitas_Calidad.xlsx</code> para actualizar la base.</p>
                    </div>
                    <div class="card-body">
                        <form action="/cargar_visitas" method="POST" enctype="multipart/form-data" class="mb-4">
                            <div class="mb-3">
                                <label class="form-label small fw-bold">Seleccionar archivo Excel:</label>
                                <input class="form-control" type="file" name="archivo_visitas" accept=".xlsx, .xls" required>
                            </div>
                            <button type="submit" class="btn btn-claro w-100 fw-bold">
                                <i class="bi bi-upload me-1"></i>Cargar Base y Registrar Timestamp
                            </button>
                        </form>

                        <hr class="my-3">

                        <h6 class="fw-bold mb-2 text-secondary"><i class="bi bi-folder-check me-1"></i>O recargar desde archivo local:</h6>
                        <p class="text-muted small">Si colocas <code>Visitas_Calidad.xlsx</code> directamente en la carpeta del servidor, presiona este botón:</p>
                        <form action="/recargar_local" method="POST">
                            <button type="submit" class="btn btn-outline-secondary w-100 btn-sm">
                                <i class="bi bi-arrow-clockwise me-1"></i>Procesar Visitas_Calidad.xlsx local
                            </button>
                        </form>

                        <hr class="my-4">

                        <h6 class="fw-bold mb-2 text-secondary"><i class="bi bi-diagram-3 me-1"></i>Actualizar Matriz de Causas:</h6>
                        <form action="/cargar_matriz" method="POST" enctype="multipart/form-data">
                            <div class="input-group input-group-sm">
                                <input class="form-control" type="file" name="archivo_matriz" accept=".xlsx, .xls" required>
                                <button type="submit" class="btn btn-dark">Actualizar Matriz</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>

            <!-- Columna Derecha: Exportar y Ultimos Hallazgos -->
            <div class="col-lg-7">
                <div class="card card-stat h-100">
                    <div class="card-header bg-white py-3 border-0 d-flex justify-content-between align-items-center">
                        <div>
                            <h5 class="fw-bold mb-0 text-dark"><i class="bi bi-journal-text me-2 text-success"></i>Respuestas a Hallazgos</h5>
                            <p class="text-muted small mb-0">Información capturada por supervisores vía Telegram.</p>
                        </div>
                        <a href="/descargar_hallazgos" class="btn btn-success btn-sm fw-bold">
                            <i class="bi bi-file-earmark-excel me-1"></i>Descargar Excel
                        </a>
                    </div>
                    <div class="card-body p-0">
                        <div class="table-responsive">
                            <table class="table table-hover table-striped align-middle mb-0 small">
                                <thead class="table-light">
                                    <tr>
                                        <th>Fecha</th>
                                        <th>OT</th>
                                        <th>Cuenta</th>
                                        <th>Ciudad / Red</th>
                                        <th>Causa</th>
                                        <th>Subcausa</th>
                                        <th>Supervisor</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% if hallazgos %}
                                        {% for h in hallazgos %}
                                            <tr>
                                                <td class="text-nowrap">{{ h.fecha_registro }}</td>
                                                <td><span class="badge bg-secondary">{{ h.ot }}</span></td>
                                                <td>{{ h.cuenta }}</td>
                                                <td>{{ h.comunidad }} <br><span class="badge bg-light text-dark">{{ h.red }}</span></td>
                                                <td class="fw-semibold text-danger">{{ h.causa }}</td>
                                                <td class="text-primary">{{ h.subcausa }}</td>
                                                <td>{{ h.telegram_nombre }} <br><small class="text-muted">@{{ h.telegram_username }}</small></td>
                                            </tr>
                                        {% endfor %}
                                    {% else %}
                                        <tr>
                                            <td colspan="7" class="text-center py-4 text-muted">
                                                <i class="bi bi-inbox fs-2 d-block mb-1"></i>
                                                Aún no se han registrado respuestas de causa raíz.
                                            </td>
                                        </tr>
                                    {% endif %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

@app.route("/")
def index():
    stats = db.get_estadisticas()
    hallazgos = db.get_ultimos_hallazgos(limit=50)
    return render_template_string(HTML_TEMPLATE, stats=stats, hallazgos=hallazgos)

@app.route("/cargar_visitas", methods=["POST"])
def cargar_visitas():
    file = request.files.get("archivo_visitas")
    if not file or file.filename == "":
        flash("No se seleccionó ningún archivo.", "warning")
        return redirect(url_for("index"))

    dest = UPLOAD_DIR / f"Visitas_Calidad_{int(time.time())}.xlsx"
    file.save(str(dest))
    try:
        cargue_id, total = db.cargar_visitas_excel(str(dest), usuario=request.remote_addr)
        flash(f"¡Cargue exitoso! Lote #{cargue_id} procesado con {total:,} registros.", "success")
    except Exception as e:
        flash(f"Error procesando el archivo: {e}", "danger")
    return redirect(url_for("index"))

@app.route("/recargar_local", methods=["POST"])
def recargar_local():
    base_dir = Path(__file__).resolve().parent
    local_excel = base_dir / "Visitas_Calidad.xlsx"
    if not local_excel.exists():
        # Buscar en D:\IM\hallazgos
        alt_path = Path("D:/IM/hallazgos/Visitas_Calidad.xlsx")
        if alt_path.exists():
            local_excel = alt_path

    if not local_excel.exists():
        flash("No se encontró el archivo Visitas_Calidad.xlsx en el servidor.", "danger")
        return redirect(url_for("index"))

    try:
        cargue_id, total = db.cargar_visitas_excel(str(local_excel), usuario="LocalAdmin")
        flash(f"¡Base local recargada! Lote #{cargue_id} con {total:,} registros.", "success")
    except Exception as e:
        flash(f"Error procesando base local: {e}", "danger")
    return redirect(url_for("index"))

@app.route("/cargar_matriz", methods=["POST"])
def cargar_matriz():
    file = request.files.get("archivo_matriz")
    if not file or file.filename == "":
        flash("No se seleccionó ningún archivo de matriz.", "warning")
        return redirect(url_for("index"))

    dest = UPLOAD_DIR / f"Matriz_{int(time.time())}.xlsx"
    file.save(str(dest))
    try:
        total = db.cargar_matriz_excel(str(dest))
        flash(f"¡Matriz actualizada con éxito! {total} combinaciones causa-subcausa cargadas.", "success")
    except Exception as e:
        flash(f"Error cargando la matriz: {e}", "danger")
    return redirect(url_for("index"))

@app.route("/descargar_hallazgos")
def descargar_hallazgos():
    hallazgos = db.get_ultimos_hallazgos(limit=10000)
    if not hallazgos:
        flash("No hay hallazgos registrados para exportar.", "info")
        return redirect(url_for("index"))

    df = pd.DataFrame(hallazgos)
    
    # Exportar a Excel en memoria
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="Hallazgos_Causa_Raiz", index=False)
    output.seek(0)

    filename = f"Hallazgos_Causa_Raiz_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

@app.route("/api/status")
def api_status():
    stats = db.get_estadisticas()
    return jsonify({
        "status": "online",
        "port": 8505,
        "bot": "@causaraiz_bot",
        "stats": stats
    })

if __name__ == "__main__":
    db.init_db()
    port = int(os.getenv("PORT", 8505))
    print(f"Servidor Web ejecutándose en http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
