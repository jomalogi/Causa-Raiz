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
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
    <style>
        body { background-color: #f4f6f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .navbar-custom { background: linear-gradient(135deg, #da291c, #9e1b12); }
        .card-stat { border-radius: 12px; border: none; box-shadow: 0 4px 12px rgba(0,0,0,0.06); transition: transform 0.2s; }
        .card-stat:hover { transform: translateY(-2px); }
        .table-responsive { max-height: 480px; }
        .badge-pill { border-radius: 50px; font-weight: 500; }
        .btn-claro { background-color: #da291c; color: white; }
        .btn-claro:hover { background-color: #b51f15; color: white; }
        .nav-pills .nav-link {
            color: #495057;
            border-radius: 8px;
            font-size: 0.95rem;
            background-color: #ffffff;
            border: 1px solid #dee2e6;
            margin-right: 8px;
            transition: all 0.2s ease-in-out;
        }
        .nav-pills .nav-link.active {
            background-color: #da291c;
            color: #ffffff;
            border-color: #da291c;
            box-shadow: 0 4px 10px rgba(218, 41, 28, 0.25);
        }
        .chart-container {
            position: relative;
            height: 250px;
            width: 100%;
        }
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

        <!-- Pestañas de Navegación Principal -->
        <ul class="nav nav-pills mb-4" id="mainTab" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active fw-bold px-4 py-2" id="tab-causa-raiz" data-bs-toggle="pill" data-bs-target="#content-causa-raiz" type="button" role="tab">
                    <i class="bi bi-shield-check me-2"></i>Causa Raíz y Visitas
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link fw-bold px-4 py-2" id="tab-vias-onnet" data-bs-toggle="pill" data-bs-target="#content-vias-onnet" type="button" role="tab">
                    <i class="bi bi-arrow-left-right me-2"></i>Validación Cambio Vías Onnet
                    {% if stats_vias.total > 0 %}
                        <span class="badge bg-danger ms-2">{{ stats_vias.total }}</span>
                    {% endif %}
                </button>
            </li>
        </ul>

        <div class="tab-content" id="mainTabContent">
            <!-- ======================================================== -->
            <!-- PESTAÑA 1: CAUSA RAÍZ Y VISITAS                         -->
            <!-- ======================================================== -->
            <div class="tab-pane fade show active" id="content-causa-raiz" role="tabpanel">
                <!-- KPIs Estadisticas Causa Raiz -->
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

            <!-- ======================================================== -->
            <!-- PESTAÑA 2: VALIDACIÓN CAMBIO VÍAS ONNET                  -->
            <!-- ======================================================== -->
            <div class="tab-pane fade" id="content-vias-onnet" role="tabpanel">
                <!-- Header con botón de descarga -->
                <div class="d-flex justify-content-between align-items-center mb-4 p-3 bg-white rounded-3 shadow-sm border-start border-4 border-danger">
                    <div>
                        <h4 class="fw-bold mb-1 text-dark"><i class="bi bi-arrow-left-right text-danger me-2"></i>Validación de Cambio de Vías Onnet (Red Neutra)</h4>
                        <p class="text-muted small mb-0">Métricas de automatización, efectividad en campo y satisfacción técnica en el cambio de vías Onnet.</p>
                    </div>
                    <a href="/descargar_validaciones_vias" class="btn btn-success btn-sm fw-bold px-3 py-2">
                        <i class="bi bi-file-earmark-excel me-1"></i>Descargar Excel Validaciones
                    </a>
                </div>

                <!-- KPIs de Vías Onnet -->
                <div class="row g-3 mb-4">
                    <div class="col-md-3">
                        <div class="card card-stat p-3 bg-white">
                            <div class="d-flex align-items-center">
                                <div class="p-3 bg-primary bg-opacity-10 text-primary rounded-3 me-3 fs-3">
                                    <i class="bi bi-card-checklist"></i>
                                </div>
                                <div>
                                    <div class="text-muted small">Total Validaciones</div>
                                    <h3 class="fw-bold mb-0 text-dark">{{ stats_vias.total }}</h3>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card card-stat p-3 bg-white">
                            <div class="d-flex align-items-center">
                                <div class="p-3 bg-success bg-opacity-10 text-success rounded-3 me-3 fs-3">
                                    <i class="bi bi-gear-wide-connected"></i>
                                </div>
                                <div>
                                    <div class="text-muted small">% Cambio Automático</div>
                                    <h3 class="fw-bold mb-0 text-dark">{{ stats_vias.pct_auto }}%</h3>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card card-stat p-3 bg-white">
                            <div class="d-flex align-items-center">
                                <div class="p-3 bg-info bg-opacity-10 text-info rounded-3 me-3 fs-3">
                                    <i class="bi bi-check2-all"></i>
                                </div>
                                <div>
                                    <div class="text-muted small">% Cambio Exitoso</div>
                                    <h3 class="fw-bold mb-0 text-dark">{{ stats_vias.pct_exito }}%</h3>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card card-stat p-3 bg-white">
                            <div class="d-flex align-items-center">
                                <div class="p-3 bg-warning bg-opacity-10 text-warning rounded-3 me-3 fs-3">
                                    <i class="bi bi-emoji-smile"></i>
                                </div>
                                <div>
                                    <div class="text-muted small">% Experiencia Positiva</div>
                                    <h3 class="fw-bold mb-0 text-dark">{{ stats_vias.pct_exp_pos }}%</h3>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Gráficos de Barras: Fila 1 -->
                <div class="row g-4 mb-4">
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-bar-chart-fill text-danger me-2"></i>1. ¿Cambio de Vías Automático?</h6>
                                <span class="badge bg-light text-dark">Pregunta 2</span>
                            </div>
                            <div class="chart-container">
                                <canvas id="chartAuto"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-bar-chart-fill text-success me-2"></i>2. ¿Cambio de Vías Exitoso?</h6>
                                <span class="badge bg-light text-dark">Pregunta 3</span>
                            </div>
                            <div class="chart-container">
                                <canvas id="chartExito"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Gráficos de Barras: Fila 2 -->
                <div class="row g-4 mb-4">
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-clock-history text-primary me-2"></i>3. Tiempo de Duración</h6>
                                <span class="badge bg-light text-dark">Pregunta 4</span>
                            </div>
                            <div class="chart-container">
                                <canvas id="chartTiempo"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-hand-thumbs-up-fill text-info me-2"></i>4. Experiencia del Técnico</h6>
                                <span class="badge bg-light text-dark">Pregunta 5</span>
                            </div>
                            <div class="chart-container">
                                <canvas id="chartExp"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Gráficos de Barras: Fila 3 -->
                <div class="row g-4 mb-4">
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-geo-alt-fill text-danger me-2"></i>5. Validaciones por Ciudad (Top 8)</h6>
                                <span class="badge bg-light text-dark">Distribución</span>
                            </div>
                            <div class="chart-container">
                                <canvas id="chartCiudades"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-people-fill text-warning me-2"></i>6. Validaciones por Aliado</h6>
                                <span class="badge bg-light text-dark">Distribución</span>
                            </div>
                            <div class="chart-container">
                                <canvas id="chartAliados"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Gráficos Fila 4: Región (Dona) y Errores (Barras) -->
                <div class="row g-4 mb-4">
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-pie-chart-fill text-primary me-2"></i>7. Validaciones por Región</h6>
                                <span class="badge bg-primary bg-opacity-10 text-primary">Dona / Región</span>
                            </div>
                            <div class="chart-container" style="position: relative; height: 280px;">
                                <canvas id="chartRegiones"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-exclamation-triangle-fill text-danger me-2"></i>8. Errores Presentados (Cuando no fue exitoso)</h6>
                                <span class="badge bg-danger bg-opacity-10 text-danger">Fallas Detectadas</span>
                            </div>
                            <div class="chart-container" style="position: relative; height: 280px;">
                                <canvas id="chartErrores"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Tabla de Registros de Validación de Vías -->
                <div class="card card-stat mb-4">
                    <div class="card-header bg-white py-3 border-0 d-flex justify-content-between align-items-center">
                        <div>
                            <h5 class="fw-bold mb-0 text-dark"><i class="bi bi-table me-2 text-primary"></i>Registros Recientes de Cambio de Vías</h5>
                            <p class="text-muted small mb-0">Detalle de cuentas validadas por supervisores vía Telegram.</p>
                        </div>
                    </div>
                    <div class="card-body p-0">
                        <div class="table-responsive">
                            <table class="table table-hover table-striped align-middle mb-0 small">
                                <thead class="table-light">
                                    <tr>
                                        <th>Fecha</th>
                                        <th>Cuenta</th>
                                        <th>Ciudad</th>
                                        <th>Aliado</th>
                                        <th>Segmento</th>
                                        <th>¿Automático?</th>
                                        <th>¿Exitoso?</th>
                                        <th>Error Presentado</th>
                                        <th>Duración</th>
                                        <th>Experiencia</th>
                                        <th>Supervisor</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% if validaciones_vias %}
                                        {% for v in validaciones_vias %}
                                            <tr>
                                                <td class="text-nowrap">{{ v.fecha_registro }}</td>
                                                <td><span class="badge bg-secondary">{{ v.cuenta }}</span></td>
                                                <td>{{ v.comunidad }} <br><span class="badge bg-light text-dark">{{ v.region }}</span></td>
                                                <td>{{ v.aliado }}</td>
                                                <td>{{ v.segmento }}</td>
                                                <td>
                                                    {% if v.cambio_vias_automatico in ['Si', 'SI', 'Sí'] %}
                                                        <span class="badge bg-success">Sí</span>
                                                    {% else %}
                                                        <span class="badge bg-danger">No</span>
                                                    {% endif %}
                                                </td>
                                                <td>
                                                    {% if v.cambio_vias_exitoso in ['Si', 'SI', 'Sí'] %}
                                                        <span class="badge bg-success">Sí</span>
                                                    {% else %}
                                                        <span class="badge bg-danger">No</span>
                                                    {% endif %}
                                                </td>
                                                <td>
                                                    {% if v.error_presentado and v.error_presentado != 'N/A' %}
                                                        <span class="badge bg-danger text-wrap text-start" style="max-width: 200px;">{{ v.error_presentado }}</span>
                                                    {% else %}
                                                        <span class="text-muted">-</span>
                                                    {% endif %}
                                                </td>
                                                <td><span class="badge bg-light text-dark border">{{ v.tiempo_duracion }}</span></td>
                                                <td>
                                                    {% if v.experiencia_tecnico == 'Positiva' %}
                                                        <span class="badge bg-primary"><i class="bi bi-hand-thumbs-up me-1"></i>Positiva</span>
                                                    {% else %}
                                                        <span class="badge bg-warning text-dark"><i class="bi bi-hand-thumbs-down me-1"></i>Negativa</span>
                                                    {% endif %}
                                                </td>
                                                <td>{{ v.telegram_nombre }} <br><small class="text-muted">@{{ v.telegram_username }}</small></td>
                                            </tr>
                                        {% endfor %}
                                    {% else %}
                                        <tr>
                                            <td colspan="11" class="text-center py-4 text-muted">
                                                <i class="bi bi-inbox fs-2 d-block mb-1"></i>
                                                Aún no se han registrado validaciones de cambio de vías Onnet.
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
    <script>
        const statsVias = {{ stats_vias | tojson }};

        // Registrar ChartDataLabels si está disponible desde CDN, o usar fallback canvas integrado
        if (typeof ChartDataLabels !== 'undefined') {
            Chart.register(ChartDataLabels);
        } else {
            Chart.register({
                id: 'customDataLabelsFallback',
                afterDatasetsDraw(chart) {
                    const { ctx } = chart;
                    if (chart.config.type === 'doughnut') {
                        const meta = chart.getDatasetMeta(0);
                        if (!meta.hidden) {
                            const dataset = chart.data.datasets[0];
                            const total = dataset.data.reduce((a, b) => a + (Number(b) || 0), 0);
                            meta.data.forEach((element, index) => {
                                const val = Number(dataset.data[index]);
                                if (val > 0) {
                                    const pct = total > 0 ? ((val / total) * 100).toFixed(1) + '%' : '';
                                    const label = `${val} (${pct})`;
                                    const pos = element.tooltipPosition();
                                    ctx.save();
                                    ctx.font = 'bold 11px sans-serif';
                                    ctx.fillStyle = '#ffffff';
                                    ctx.textAlign = 'center';
                                    ctx.textBaseline = 'middle';
                                    ctx.shadowColor = 'rgba(0,0,0,0.7)';
                                    ctx.shadowBlur = 4;
                                    ctx.fillText(label, pos.x, pos.y);
                                    ctx.restore();
                                }
                            });
                        }
                        return;
                    }
                    chart.data.datasets.forEach((dataset, datasetIndex) => {
                        const meta = chart.getDatasetMeta(datasetIndex);
                        if (!meta.hidden) {
                            const total = dataset.data.reduce((a, b) => a + (Number(b) || 0), 0);
                            meta.data.forEach((element, index) => {
                                const val = Number(dataset.data[index]);
                                if (val > 0) {
                                    const pct = total > 0 ? ((val / total) * 100).toFixed(1) + '%' : '';
                                    const label = `${val} (${pct})`;
                                    ctx.save();
                                    ctx.font = 'bold 11px sans-serif';
                                    ctx.fillStyle = '#1e293b';
                                    ctx.textAlign = 'center';
                                    ctx.textBaseline = 'bottom';
                                    ctx.fillText(label, element.x, element.y - 4);
                                    ctx.restore();
                                }
                            });
                        }
                    });
                }
            });
        }

        // Generador de opciones para que todas las gráficas muestren cantidad y porcentaje tanto en barras como en tooltip
        function buildBarOptions(metricLabel) {
            return {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const val = context.parsed.y;
                                const dataset = context.dataset;
                                const total = dataset.data.reduce((a, b) => a + (Number(b) || 0), 0);
                                const pct = total > 0 ? ((val / total) * 100).toFixed(1) + '%' : '0%';
                                return ` ${dataset.label || metricLabel || 'Total'}: ${val} (${pct})`;
                            }
                        }
                    },
                    datalabels: {
                        anchor: 'end',
                        align: 'top',
                        offset: 4,
                        font: {
                            weight: 'bold',
                            size: 11,
                            family: "'Segoe UI', Tahoma, sans-serif"
                        },
                        color: '#1e293b',
                        formatter: function(value, context) {
                            if (!value || value === 0) return '';
                            const dataset = context.chart.data.datasets[0];
                            const total = dataset.data.reduce((a, b) => a + (Number(b) || 0), 0);
                            if (total === 0) return value;
                            const pct = ((value / total) * 100).toFixed(1) + '%';
                            return `${value} (${pct})`;
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grace: '18%',
                        ticks: { precision: 0 }
                    }
                }
            };
        }

        function initCharts() {
            // 1. Chart Automatico
            new Chart(document.getElementById('chartAuto'), {
                type: 'bar',
                data: {
                    labels: statsVias.auto_labels,
                    datasets: [{
                        label: 'Validaciones',
                        data: statsVias.auto_values,
                        backgroundColor: ['#198754', '#dc3545'],
                        borderRadius: 6
                    }]
                },
                options: buildBarOptions('Validaciones')
            });

            // 2. Chart Exitoso
            new Chart(document.getElementById('chartExito'), {
                type: 'bar',
                data: {
                    labels: statsVias.exito_labels,
                    datasets: [{
                        label: 'Validaciones',
                        data: statsVias.exito_values,
                        backgroundColor: ['#198754', '#fd7e14'],
                        borderRadius: 6
                    }]
                },
                options: buildBarOptions('Validaciones')
            });

            // 3. Chart Tiempo
            new Chart(document.getElementById('chartTiempo'), {
                type: 'bar',
                data: {
                    labels: statsVias.tiempo_labels,
                    datasets: [{
                        label: 'Validaciones',
                        data: statsVias.tiempo_values,
                        backgroundColor: ['#0d6efd', '#0dcaf0', '#6c757d'],
                        borderRadius: 6
                    }]
                },
                options: buildBarOptions('Validaciones')
            });

            // 4. Chart Experiencia
            new Chart(document.getElementById('chartExp'), {
                type: 'bar',
                data: {
                    labels: statsVias.exp_labels,
                    datasets: [{
                        label: 'Técnicos',
                        data: statsVias.exp_values,
                        backgroundColor: ['#0d6efd', '#ffc107'],
                        borderRadius: 6
                    }]
                },
                options: buildBarOptions('Técnicos')
            });

            // 5. Chart Ciudades
            new Chart(document.getElementById('chartCiudades'), {
                type: 'bar',
                data: {
                    labels: statsVias.ciudades_labels.length ? statsVias.ciudades_labels : ['Sin datos'],
                    datasets: [{
                        label: 'Validaciones',
                        data: statsVias.ciudades_values.length ? statsVias.ciudades_values : [0],
                        backgroundColor: '#dc3545',
                        borderRadius: 6
                    }]
                },
                options: buildBarOptions('Validaciones')
            });

            // 6. Chart Aliados
            new Chart(document.getElementById('chartAliados'), {
                type: 'bar',
                data: {
                    labels: statsVias.aliados_labels.length ? statsVias.aliados_labels : ['Sin datos'],
                    datasets: [{
                        label: 'Validaciones',
                        data: statsVias.aliados_values.length ? statsVias.aliados_values : [0],
                        backgroundColor: '#6610f2',
                        borderRadius: 6
                    }]
                },
                options: buildBarOptions('Validaciones')
            });

            // 7. Chart Regiones (Dona)
            const coloresRegiones = [
                '#da291c', '#0d6efd', '#198754', '#ffc107', 
                '#6f42c1', '#fd7e14', '#20c997', '#0dcaf0'
            ];
            new Chart(document.getElementById('chartRegiones'), {
                type: 'doughnut',
                data: {
                    labels: statsVias.regiones_labels.length ? statsVias.regiones_labels : ['Sin datos'],
                    datasets: [{
                        label: 'Validaciones',
                        data: statsVias.regiones_values.length ? statsVias.regiones_values : [0],
                        backgroundColor: coloresRegiones,
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            position: 'right',
                            labels: {
                                boxWidth: 14,
                                padding: 10,
                                font: {
                                    size: 11,
                                    family: "'Segoe UI', Tahoma, sans-serif"
                                },
                                generateLabels: function(chart) {
                                    const data = chart.data;
                                    if (data.labels.length && data.datasets.length) {
                                        const dataset = data.datasets[0];
                                        const total = dataset.data.reduce((a, b) => a + (Number(b) || 0), 0);
                                        return data.labels.map((label, i) => {
                                            const val = Number(dataset.data[i]) || 0;
                                            const pct = total > 0 ? ((val / total) * 100).toFixed(1) + '%' : '0%';
                                            const fill = dataset.backgroundColor[i % dataset.backgroundColor.length];
                                            return {
                                                text: `${label}: ${val} (${pct})`,
                                                fillStyle: fill,
                                                strokeStyle: fill,
                                                lineWidth: 1,
                                                hidden: isNaN(dataset.data[i]) || (chart.getDatasetMeta(0).data[i] && chart.getDatasetMeta(0).data[i].hidden),
                                                index: i
                                            };
                                        });
                                    }
                                    return [];
                                }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const val = Number(context.raw) || 0;
                                    const dataset = context.dataset;
                                    const total = dataset.data.reduce((a, b) => a + (Number(b) || 0), 0);
                                    const pct = total > 0 ? ((val / total) * 100).toFixed(1) + '%' : '0%';
                                    return ` ${context.label}: ${val} (${pct})`;
                                }
                            }
                        },
                        datalabels: {
                            color: '#ffffff',
                            font: {
                                weight: 'bold',
                                size: 11,
                                family: "'Segoe UI', Tahoma, sans-serif"
                            },
                            formatter: function(value, context) {
                                if (!value || value === 0) return '';
                                const dataset = context.chart.data.datasets[0];
                                const total = dataset.data.reduce((a, b) => a + (Number(b) || 0), 0);
                                if (total === 0) return value;
                                const pct = ((value / total) * 100).toFixed(1) + '%';
                                return `${value} (${pct})`;
                            }
                        }
                    },
                    cutout: '55%'
                }
            });

            // 8. Chart Errores
            new Chart(document.getElementById('chartErrores'), {
                type: 'bar',
                data: {
                    labels: statsVias.errores_labels.length ? statsVias.errores_labels : ['Sin fallas registradas'],
                    datasets: [{
                        label: 'Ocurrencias',
                        data: statsVias.errores_values.length ? statsVias.errores_values : [0],
                        backgroundColor: '#dc3545',
                        borderRadius: 6
                    }]
                },
                options: buildBarOptions('Ocurrencias')
            });
        }

        document.addEventListener('DOMContentLoaded', () => {
            initCharts();
            const viasTab = document.getElementById('tab-vias-onnet');
            if (viasTab) {
                viasTab.addEventListener('shown.bs.tab', () => {
                    window.dispatchEvent(new Event('resize'));
                });
            }
        });
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    stats = db.get_estadisticas()
    hallazgos = db.get_ultimos_hallazgos(limit=50)
    stats_vias = db.get_estadisticas_vias()
    validaciones_vias = db.get_validaciones_vias(limit=50)
    return render_template_string(
        HTML_TEMPLATE,
        stats=stats,
        hallazgos=hallazgos,
        stats_vias=stats_vias,
        validaciones_vias=validaciones_vias
    )

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

@app.route("/descargar_validaciones_vias")
def descargar_validaciones_vias():
    validaciones = db.get_validaciones_vias(limit=10000)
    if not validaciones:
        flash("No hay validaciones de cambio de vías registradas para exportar.", "info")
        return redirect(url_for("index"))

    df = pd.DataFrame(validaciones)
    
    # Exportar a Excel en memoria
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="Validacion_Cambio_Vias_Onnet", index=False)
    output.seek(0)

    filename = f"Validaciones_Cambio_Vias_Onnet_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

@app.route("/api/status")
def api_status():
    stats = db.get_estadisticas()
    stats_vias = db.get_estadisticas_vias()
    return jsonify({
        "status": "online",
        "port": 8505,
        "bot": "@causaraiz_bot",
        "stats": stats,
        "stats_vias": stats_vias
    })

if __name__ == "__main__":
    db.init_db()
    port = int(os.getenv("PORT", 8505))
    print(f"Servidor Web ejecutándose en http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
