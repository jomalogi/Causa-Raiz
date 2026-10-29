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
            <li class="nav-item" role="presentation">
                <button class="nav-link fw-bold px-4 py-2" id="tab-inventario" data-bs-toggle="pill" data-bs-target="#content-inventario" type="button" role="tab">
                    <i class="bi bi-tools me-2"></i>Inventario de Herramientas
                    {% if stats_inv.total_inventarios > 0 %}
                        <span class="badge bg-danger ms-2">{{ stats_inv.total_inventarios }}</span>
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
                <div class="d-flex justify-content-between align-items-center mb-3 p-3 bg-white rounded-3 shadow-sm border-start border-4 border-danger">
                    <div>
                        <h4 class="fw-bold mb-1 text-dark"><i class="bi bi-arrow-left-right text-danger me-2"></i>Validación de Cambio de Vías Onnet (Red Neutra)</h4>
                        <p class="text-muted small mb-0">Métricas de automatización, efectividad en campo y satisfacción técnica en el cambio de vías Onnet.</p>
                    </div>
                    <a href="/descargar_validaciones_vias" id="btnDescargarViasExcel" class="btn btn-success btn-sm fw-bold px-3 py-2">
                        <i class="bi bi-file-earmark-excel me-1"></i>Descargar Excel Validaciones
                    </a>
                </div>

                <!-- Barra de Filtros Interactivos (Región, Zona, Aliado, Ciudad) -->
                <div class="card card-stat p-3 bg-white mb-4 border-0 shadow-sm">
                    <div class="d-flex flex-wrap justify-content-between align-items-center mb-2">
                        <span class="fw-bold text-dark small"><i class="bi bi-funnel-fill text-danger me-1"></i>Filtros de Reporting (Cambio de Vías Onnet)</span>
                        <div class="d-flex align-items-center gap-2">
                            <span id="badgeFiltroVias" class="badge bg-secondary">Mostrando: Nacional (Todos)</span>
                            <button type="button" class="btn btn-outline-secondary btn-sm py-0 px-2" onclick="limpiarFiltrosVias()">
                                <i class="bi bi-x-circle me-1"></i>Limpiar Filtros
                            </button>
                        </div>
                    </div>
                    <div class="row g-2">
                        <div class="col-md-3">
                            <label class="form-label small text-muted mb-1 fw-semibold">Región</label>
                            <select id="filtroViasRegion" class="form-select form-select-sm" onchange="aplicarFiltrosVias()">
                                <option value="">Todas las Regiones</option>
                                {% for r in stats_inv.filtros.regiones %}
                                    <option value="{{ r }}">{{ r }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small text-muted mb-1 fw-semibold">Zona / Área</label>
                            <select id="filtroViasZona" class="form-select form-select-sm" onchange="aplicarFiltrosVias()">
                                <option value="">Todas las Zonas</option>
                                {% for z in stats_inv.filtros.zonas %}
                                    <option value="{{ z }}">{{ z }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small text-muted mb-1 fw-semibold">Aliado</label>
                            <select id="filtroViasAliado" class="form-select form-select-sm" onchange="aplicarFiltrosVias()">
                                <option value="">Todos los Aliados</option>
                                {% for a in stats_inv.filtros.aliados %}
                                    <option value="{{ a }}">{{ a }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label small text-muted mb-1 fw-semibold">Ciudad</label>
                            <select id="filtroViasCiudad" class="form-select form-select-sm" onchange="aplicarFiltrosVias()">
                                <option value="">Todas las Ciudades</option>
                                {% for c in stats_inv.filtros.ciudades %}
                                    <option value="{{ c }}">{{ c }}</option>
                                {% endfor %}
                            </select>
                        </div>
                    </div>
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
                                    <h3 class="fw-bold mb-0 text-dark" id="kpiViasTotal">{{ stats_vias.total }}</h3>
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
                                    <h3 class="fw-bold mb-0 text-dark" id="kpiViasAuto">{{ stats_vias.pct_auto }}%</h3>
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
                                    <h3 class="fw-bold mb-0 text-dark" id="kpiViasExito">{{ stats_vias.pct_exito }}%</h3>
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
                                    <h3 class="fw-bold mb-0 text-dark" id="kpiViasExp">{{ stats_vias.pct_exp_pos }}%</h3>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Gráficos Diversificados: Fila 1 (Dona + Pastel) -->
                <div class="row g-4 mb-4">
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-pie-chart-fill text-danger me-2"></i>1. ¿Cambio de Vías Automático?</h6>
                                <span class="badge bg-danger bg-opacity-10 text-danger">Dona · Cant y %</span>
                            </div>
                            <div class="chart-container" style="position: relative; height: 270px;">
                                <canvas id="chartAuto"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-check-circle-fill text-success me-2"></i>2. ¿Cambio de Vías Exitoso?</h6>
                                <span class="badge bg-success bg-opacity-10 text-success">Pastel · Cant y %</span>
                            </div>
                            <div class="chart-container" style="position: relative; height: 270px;">
                                <canvas id="chartExito"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Gráficos Diversificados: Fila 2 (Barras Horizontales + Dona) -->
                <div class="row g-4 mb-4">
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-clock-history text-primary me-2"></i>3. Tiempo de Duración</h6>
                                <span class="badge bg-primary bg-opacity-10 text-primary">Barras Horizontales · Cant y %</span>
                            </div>
                            <div class="chart-container" style="position: relative; height: 270px;">
                                <canvas id="chartTiempo"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-hand-thumbs-up-fill text-info me-2"></i>4. Experiencia del Técnico</h6>
                                <span class="badge bg-info bg-opacity-10 text-info">Dona · Cant y %</span>
                            </div>
                            <div class="chart-container" style="position: relative; height: 270px;">
                                <canvas id="chartExp"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Gráficos Diversificados: Fila 3 (Barras Horizontales Ciudades y Aliados) -->
                <div class="row g-4 mb-4">
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-geo-alt-fill text-danger me-2"></i>5. Validaciones por Ciudad (Top 8)</h6>
                                <span class="badge bg-danger bg-opacity-10 text-danger">Barras Horizontales · Cant y %</span>
                            </div>
                            <div class="chart-container" style="position: relative; height: 280px;">
                                <canvas id="chartCiudades"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-people-fill text-warning me-2"></i>6. Validaciones por Aliado</h6>
                                <span class="badge bg-warning bg-opacity-10 text-dark">Barras Horizontales · Cant y %</span>
                            </div>
                            <div class="chart-container" style="position: relative; height: 280px;">
                                <canvas id="chartAliados"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Gráficos Fila 4: Región (Dona) y Errores (Área Polar) -->
                <div class="row g-4 mb-4">
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-pie-chart-fill text-primary me-2"></i>7. Validaciones por Región</h6>
                                <span class="badge bg-primary bg-opacity-10 text-primary">Dona · Cant y %</span>
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
                                <span class="badge bg-danger bg-opacity-10 text-danger">Área Polar · Cant y %</span>
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
                                        <th>Ciudad / Zona</th>
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
                                <tbody id="tablaViasBody">
                                    {% if validaciones_vias %}
                                        {% for v in validaciones_vias %}
                                            <tr class="fila-vias"
                                                data-region="{{ v.region or '' }}"
                                                data-zona="{{ v.area or '' }}"
                                                data-aliado="{{ v.aliado or '' }}"
                                                data-ciudad="{{ v.comunidad or '' }}">
                                                <td class="text-nowrap">{{ v.fecha_registro }}</td>
                                                <td><span class="badge bg-secondary">{{ v.cuenta }}</span></td>
                                                <td>
                                                    {{ v.comunidad }} <br>
                                                    <span class="badge bg-light text-dark border">{{ v.region }}</span>
                                                    {% if v.area %}<span class="badge bg-secondary bg-opacity-10 text-secondary">{{ v.area }}</span>{% endif %}
                                                </td>
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

            <!-- ======================================================== -->
            <!-- PESTAÑA 3: INVENTARIO DE HERRAMIENTAS                    -->
            <!-- ======================================================== -->
            <div class="tab-pane fade" id="content-inventario" role="tabpanel">
                <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 p-3 bg-white rounded-3 shadow-sm border-start border-4 border-danger">
                    <div>
                        <h4 class="fw-bold mb-1 text-dark"><i class="bi bi-tools text-danger me-2"></i>Auditoría e Inventario de Herramientas</h4>
                        <p class="text-muted small mb-0">Control nacional de cumplimiento por ítem de herramienta, novedades físicas y evidencias fotográficas.</p>
                    </div>
                    <div class="d-flex gap-2 mt-2 mt-md-0">
                        <form action="/cargar_tecnicos_inventario" method="POST" enctype="multipart/form-data" class="d-flex align-items-center gap-2">
                            <input type="file" name="archivo_tecnicos" accept=".xlsx, .xls" class="form-control form-control-sm" style="max-width: 230px;" required>
                            <button type="submit" class="btn btn-outline-dark btn-sm text-nowrap">
                                <i class="bi bi-person-lines-fill me-1"></i>Actualizar Base Técnicos
                            </button>
                        </form>
                        <a href="/descargar_inventarios" id="btnDescargarInvExcel" class="btn btn-success btn-sm fw-bold px-3 py-2 text-nowrap">
                            <i class="bi bi-file-earmark-excel me-1"></i>Descargar Excel Inventarios
                        </a>
                    </div>
                </div>

                <!-- Barra de Filtros Interactivos (Mes, Región, Zona, Aliado, Ciudad) -->
                <div class="card card-stat p-3 bg-white mb-4 border-0 shadow-sm">
                    <div class="d-flex flex-wrap justify-content-between align-items-center mb-2">
                        <span class="fw-bold text-dark small"><i class="bi bi-funnel-fill text-danger me-1"></i>Filtros de Reporting (Mes, Región, Zona, Aliado, Ciudad)</span>
                        <div class="d-flex align-items-center gap-2">
                            <span id="badgeFiltroInv" class="badge bg-danger">Filtrado: Mes: {{ stats_inv.mes_actual_label }} (Mes en curso)</span>
                            <button type="button" class="btn btn-outline-secondary btn-sm py-0 px-2" onclick="limpiarFiltrosInventario()">
                                <i class="bi bi-x-circle me-1"></i>Limpiar Filtros
                            </button>
                        </div>
                    </div>
                    <div class="row row-cols-1 row-cols-md-5 g-2">
                        <div class="col">
                            <label class="form-label small text-muted mb-1 fw-semibold"><i class="bi bi-calendar-month text-danger me-1"></i>Mes</label>
                            <select id="filtroInvMes" class="form-select form-select-sm border-danger" onchange="aplicarFiltrosInventario()">
                                <option value="">Todos los Meses (Histórico)</option>
                                {% for m in stats_inv.filtros.meses %}
                                    <option value="{{ m.value }}" {% if m.value == stats_inv.mes_actual %}selected{% endif %}>{{ m.label }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="col">
                            <label class="form-label small text-muted mb-1 fw-semibold">Región</label>
                            <select id="filtroInvRegion" class="form-select form-select-sm" onchange="aplicarFiltrosInventario()">
                                <option value="">Todas las Regiones</option>
                                {% for r in stats_inv.filtros.regiones %}
                                    <option value="{{ r }}">{{ r }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="col">
                            <label class="form-label small text-muted mb-1 fw-semibold">Zona / Área</label>
                            <select id="filtroInvZona" class="form-select form-select-sm" onchange="aplicarFiltrosInventario()">
                                <option value="">Todas las Zonas</option>
                                {% for z in stats_inv.filtros.zonas %}
                                    <option value="{{ z }}">{{ z }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="col">
                            <label class="form-label small text-muted mb-1 fw-semibold">Aliado</label>
                            <select id="filtroInvAliado" class="form-select form-select-sm" onchange="aplicarFiltrosInventario()">
                                <option value="">Todos los Aliados</option>
                                {% for a in stats_inv.filtros.aliados %}
                                    <option value="{{ a }}">{{ a }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="col">
                            <label class="form-label small text-muted mb-1 fw-semibold">Ciudad</label>
                            <select id="filtroInvCiudad" class="form-select form-select-sm" onchange="aplicarFiltrosInventario()">
                                <option value="">Todas las Ciudades</option>
                                {% for c in stats_inv.filtros.ciudades %}
                                    <option value="{{ c }}">{{ c }}</option>
                                {% endfor %}
                            </select>
                        </div>
                    </div>
                </div>

                <!-- KPIs Inventario -->
                <div class="row row-cols-1 row-cols-md-5 g-3 mb-4">
                    <div class="col">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex align-items-center">
                                <div class="p-3 bg-secondary bg-opacity-10 text-secondary rounded-3 me-3 fs-3">
                                    <i class="bi bi-people-fill"></i>
                                </div>
                                <div>
                                    <div class="text-muted small">Técnicos en Base</div>
                                    <h3 class="fw-bold mb-0 text-dark" id="kpiInvTecnicosBase">{{ "{:,}".format(stats_inv.total_tecnicos_base or 0) }}</h3>
                                    <div class="text-muted small" style="font-size: 0.76rem;" id="kpiInvSubBase">Población según filtro</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex align-items-center">
                                <div class="p-3 bg-primary bg-opacity-10 text-primary rounded-3 me-3 fs-3">
                                    <i class="bi bi-clipboard2-check-fill"></i>
                                </div>
                                <div>
                                    <div class="text-muted small">Auditorías Registradas</div>
                                    <h3 class="fw-bold mb-0 text-dark" id="kpiInvAuditorias">{{ stats_inv.total_inventarios }}</h3>
                                    <div class="text-muted small" style="font-size: 0.76rem;" id="kpiInvSubAuditorias">Inventarios cerrados</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex align-items-center">
                                <div class="p-3 bg-success bg-opacity-10 text-success rounded-3 me-3 fs-3">
                                    <i class="bi bi-check-circle-fill"></i>
                                </div>
                                <div>
                                    <div class="text-muted small">% Cumplimiento (OK)</div>
                                    <h3 class="fw-bold mb-0 text-dark" id="kpiInvPctOk">{{ stats_inv.pct_ok }}%</h3>
                                    <div class="text-muted small" style="font-size: 0.76rem;" id="kpiInvSubOk">{{ stats_inv.total_ok }} OK de {{ stats_inv.total_herramientas_eval }} requeridas</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex align-items-center">
                                <div class="p-3 bg-info bg-opacity-10 text-info rounded-3 me-3 fs-3">
                                    <i class="bi bi-person-badge-fill"></i>
                                </div>
                                <div>
                                    <div class="text-muted small">Propiedad Herramientas</div>
                                    <h5 class="fw-bold mb-0 text-dark" id="kpiInvPropiedad">👷 {{ stats_inv.total_prop_tecnico }} ({{ stats_inv.pct_prop_tecnico }}%)</h5>
                                    <div class="text-muted small" style="font-size: 0.76rem;" id="kpiInvSubPropiedad">🤝 Aliado: {{ stats_inv.total_prop_aliado }} ({{ stats_inv.pct_prop_aliado }}%)</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex align-items-center">
                                <div class="p-3 bg-warning bg-opacity-10 text-warning rounded-3 me-3 fs-3">
                                    <i class="bi bi-camera-fill"></i>
                                </div>
                                <div>
                                    <div class="text-muted small">Novedades / Faltantes</div>
                                    <h3 class="fw-bold mb-0 text-dark" id="kpiInvNovedades">{{ stats_inv.total_novedad + stats_inv.total_faltante }}</h3>
                                    <div class="text-muted small" style="font-size: 0.76rem;" id="kpiInvSubFotos">📸 {{ stats_inv.total_evidencias }} fotos cargadas</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Gráficos Inventario Fila 1: Barras Horizontales por Ítem de Herramienta y Cumplimiento -->
                <div class="row g-4 mb-4">
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-bar-chart-steps text-success me-2"></i>1. Cumplimiento por Ítem de Herramienta (OK y %)</h6>
                                <span class="badge bg-success bg-opacity-10 text-success">Barras Horizontales · Cant y %</span>
                            </div>
                            <div class="chart-container" style="position: relative; height: 370px;">
                                <canvas id="chartInvCumplimientoItems"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-layers-fill text-primary me-2"></i>2. Desglose por Ítem (OK vs Novedad vs Faltante)</h6>
                                <span class="badge bg-primary bg-opacity-10 text-primary">Horizontales Apiladas · Cant y %</span>
                            </div>
                            <div class="chart-container" style="position: relative; height: 370px;">
                                <canvas id="chartInvDesgloseItems"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Gráficos Inventario Fila 2: Vista de Propiedad de Herramientas (Técnico vs Aliado) -->
                <div class="row g-4 mb-4">
                    <div class="col-lg-5">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-person-vcard-fill text-info me-2"></i>3. Propiedad Global (Técnico vs Aliado)</h6>
                                <span class="badge bg-info bg-opacity-10 text-info">Dona · Cant y %</span>
                            </div>
                            <div class="chart-container" style="position: relative; height: 350px;">
                                <canvas id="chartInvPropiedadGlobal"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-7">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-tags-fill text-primary me-2"></i>4. Propiedad por Ítem de Herramienta (👷 Técnico vs 🤝 Aliado)</h6>
                                <span class="badge bg-primary bg-opacity-10 text-primary">Horizontales Apiladas · Cant y %</span>
                            </div>
                            <div class="chart-container" style="position: relative; height: 350px;">
                                <canvas id="chartInvPropiedadItems"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Gráficos Inventario Fila 3: Diversificación (Dona + Área Polar + Pastel) -->
                <div class="row g-4 mb-4">
                    <div class="col-lg-4">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-pie-chart-fill text-success me-2"></i>5. Estado Global Herramientas</h6>
                                <span class="badge bg-success bg-opacity-10 text-success">Dona · Cant y %</span>
                            </div>
                            <div class="chart-container" style="position: relative; height: 280px;">
                                <canvas id="chartInvEstado"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-4">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-bullseye text-warning me-2"></i>6. Tipos de Novedad</h6>
                                <span class="badge bg-warning bg-opacity-10 text-dark">Área Polar · Cant y %</span>
                            </div>
                            <div class="chart-container" style="position: relative; height: 280px;">
                                <canvas id="chartInvNovedades"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-4">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-compass-fill text-info me-2"></i>7. Inventarios por Zona</h6>
                                <span class="badge bg-info bg-opacity-10 text-info">Pastel · Cant y %</span>
                            </div>
                            <div class="chart-container" style="position: relative; height: 280px;">
                                <canvas id="chartInvZonas"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Gráficos Inventario Fila 4: Región (Dona) y Aliados (Barras Horizontales) -->
                <div class="row g-4 mb-4">
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-globe-americas text-primary me-2"></i>8. Inventarios por Región</h6>
                                <span class="badge bg-primary bg-opacity-10 text-primary">Dona · Cant y %</span>
                            </div>
                            <div class="chart-container" style="position: relative; height: 280px;">
                                <canvas id="chartInvRegiones"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <div class="card card-stat p-3 bg-white h-100">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="fw-bold text-dark mb-0"><i class="bi bi-building-fill-check text-danger me-2"></i>9. Auditorías de Inventario por Aliado</h6>
                                <span class="badge bg-danger bg-opacity-10 text-danger">Barras Horizontales · Cant y %</span>
                            </div>
                            <div class="chart-container" style="position: relative; height: 280px;">
                                <canvas id="chartInvAliados"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Tabla de Auditorías de Inventario -->
                <div class="card card-stat mb-4">
                    <div class="card-header bg-white py-3 border-0 d-flex justify-content-between align-items-center">
                        <div>
                            <h5 class="fw-bold mb-0 text-dark"><i class="bi bi-list-check me-2 text-danger"></i>Auditorías de Inventario Registradas</h5>
                            <p class="text-muted small mb-0">Detalle de inventarios cerrados con código de auditoría, propiedad de herramientas y evidencias fotográficas.</p>
                        </div>
                    </div>
                    <div class="card-body p-0">
                        <div class="table-responsive">
                            <table class="table table-hover table-striped align-middle mb-0 small">
                                <thead class="table-light">
                                    <tr>
                                        <th>Código Auditoría</th>
                                        <th>Fecha</th>
                                        <th>Técnico</th>
                                        <th>Aliado</th>
                                        <th>Ciudad / Región / Zona</th>
                                        <th>Resumen Estado y Propiedad</th>
                                        <th>Detalle Novedades / Faltantes</th>
                                        <th>Foto General</th>
                                        <th>Supervisor</th>
                                    </tr>
                                </thead>
                                <tbody id="tablaInventariosBody">
                                    {% if inventarios %}
                                        {% for inv in inventarios %}
                                            <tr class="fila-inventario"
                                                data-cedula="{{ inv.cedula_tecnico or inv.id }}"
                                                data-mes="{{ inv.mes_registro or (inv.fecha_registro or '')[:7] }}"
                                                data-region="{{ inv.region or '' }}"
                                                data-zona="{{ inv.area or '' }}"
                                                data-aliado="{{ inv.aliado or '' }}"
                                                data-ciudad="{{ inv.comunidad or '' }}">
                                                <td><span class="badge bg-dark font-monospace">{{ inv.codigo_auditoria }}</span></td>
                                                <td class="text-nowrap">{{ inv.fecha_registro }}</td>
                                                <td>
                                                    <div class="fw-bold text-dark">{{ inv.nombre_tecnico }}</div>
                                                    <small class="text-muted">CC: {{ inv.cedula_tecnico }}</small>
                                                </td>
                                                <td>{{ inv.aliado }}</td>
                                                <td>
                                                    {{ inv.comunidad }}<br>
                                                    <span class="badge bg-light text-dark border">{{ inv.region }}</span>
                                                    {% if inv.area %}<span class="badge bg-secondary bg-opacity-10 text-secondary">{{ inv.area }}</span>{% endif %}
                                                </td>
                                                <td class="text-nowrap">
                                                    <div class="mb-1">
                                                        <span class="badge bg-dark me-1">📊 Cumplimiento: {{ (((inv.herramientas_ok or 0) / 10) * 100) | round(0) | int }}% ({{ inv.herramientas_ok }}/10)</span>
                                                        <span class="badge bg-success me-1">✅ {{ inv.herramientas_ok }} OK</span>
                                                        <span class="badge bg-warning text-dark me-1">⚠️ {{ inv.herramientas_novedad }} Nov</span>
                                                        <span class="badge bg-danger">❌ {{ inv.herramientas_faltantes }} Falt</span>
                                                    </div>
                                                    <div>
                                                        <span class="badge bg-info text-dark me-1">👷 Técnico: {{ inv.herramientas_tecnico or 0 }}</span>
                                                        <span class="badge bg-primary">🤝 Aliado: {{ inv.herramientas_aliado or 0 }}</span>
                                                    </div>
                                                </td>
                                                <td style="max-width: 300px;">
                                                    {% set ns = namespace(has_nov=false) %}
                                                    {% for d in inv.detalles %}
                                                        {% if d.estado == 'NOVEDAD' %}
                                                            {% set ns.has_nov = true %}
                                                            <div class="mb-1">
                                                                <span class="badge bg-warning text-dark">⚠️ {{ d.herramienta }} ({{ d.propiedad or 'N/A' }}): {{ d.novedad }}</span>
                                                                {% if d.foto_path %}
                                                                    <a href="/{{ d.foto_path }}" target="_blank" class="badge bg-primary text-decoration-none ms-1">
                                                                        <i class="bi bi-image"></i> Ver foto
                                                                    </a>
                                                                {% endif %}
                                                            </div>
                                                        {% elif d.estado == 'FALTANTE' %}
                                                            {% set ns.has_nov = true %}
                                                            <div class="mb-1">
                                                                <span class="badge bg-danger">❌ {{ d.herramienta }}: no disponible</span>
                                                            </div>
                                                        {% endif %}
                                                    {% endfor %}
                                                    {% if not ns.has_nov %}
                                                        <span class="text-success fw-semibold"><i class="bi bi-check2-all"></i> Sin novedades</span>
                                                    {% endif %}
                                                </td>
                                                <td>
                                                    {% if inv.foto_general_path %}
                                                        <a href="/{{ inv.foto_general_path }}" target="_blank" class="btn btn-outline-primary btn-sm py-0 px-2">
                                                            <i class="bi bi-camera me-1"></i>Ver General
                                                        </a>
                                                    {% else %}
                                                        <span class="text-muted">-</span>
                                                    {% endif %}
                                                </td>
                                                <td>{{ inv.telegram_nombre }} <br><small class="text-muted">@{{ inv.telegram_username }}</small></td>
                                            </tr>
                                        {% endfor %}
                                    {% else %}
                                        <tr>
                                            <td colspan="9" class="text-center py-4 text-muted">
                                                <i class="bi bi-inbox fs-2 d-block mb-1"></i>
                                                Aún no se han registrado auditorías de inventario de herramientas.
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
        const statsInv = {{ stats_inv | tojson }};
        const rawVias = {{ validaciones_vias | tojson }};
        const rawInventarios = {{ inventarios | tojson }};
        const HERRAMIENTAS_OFICIALES = [
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
        ];
        const PALETA_COLORES = [
            '#da291c', '#0d6efd', '#198754', '#ffc107',
            '#6f42c1', '#fd7e14', '#20c997', '#0dcaf0',
            '#6610f2', '#d63384'
        ];

        // Instancias de gráficos para actualización dinámica con filtros
        let chartsVias = {};
        let chartsInv = {};

        // Registrar ChartDataLabels si está disponible desde CDN, o usar fallback canvas integrado
        if (typeof ChartDataLabels !== 'undefined') {
            Chart.register(ChartDataLabels);
        } else {
            Chart.register({
                id: 'customDataLabelsFallback',
                afterDatasetsDraw(chart) {
                    const { ctx } = chart;
                    const type = chart.config.type;
                    const isHorizontal = chart.options && chart.options.indexAxis === 'y';
                    if (type === 'doughnut' || type === 'pie' || type === 'polarArea') {
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
                                    ctx.shadowColor = 'rgba(0,0,0,0.75)';
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
                                    let pct = total > 0 ? ((val / total) * 100).toFixed(1) + '%' : '';
                                    if (dataset.customPcts && dataset.customPcts[index] !== undefined) {
                                        pct = dataset.customPcts[index] + '%';
                                    }
                                    const label = `${val} (${pct})`;
                                    ctx.save();
                                    ctx.font = 'bold 11px sans-serif';
                                    ctx.fillStyle = '#1e293b';
                                    if (isHorizontal) {
                                        ctx.textAlign = 'left';
                                        ctx.textBaseline = 'middle';
                                        ctx.fillText(label, element.x + 6, element.y);
                                    } else {
                                        ctx.textAlign = 'center';
                                        ctx.textBaseline = 'bottom';
                                        ctx.fillText(label, element.x, element.y - 4);
                                    }
                                    ctx.restore();
                                }
                            });
                        }
                    });
                }
            });
        }

        // Opciones para Barras Horizontales (indexAxis: 'y') con Cantidad y %
        function buildHorizontalBarOptions(metricLabel, useCustomPct = false) {
            return {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const val = Number(context.parsed.x) || 0;
                                const dataset = context.dataset;
                                if (useCustomPct && dataset.customPcts) {
                                    const pct = dataset.customPcts[context.dataIndex] ?? 0;
                                    const tot = dataset.customTotals ? dataset.customTotals[context.dataIndex] : val;
                                    return ` ${dataset.label || metricLabel}: ${val} de ${tot} (${pct}%)`;
                                }
                                const total = dataset.data.reduce((a, b) => a + (Number(b) || 0), 0);
                                const pct = total > 0 ? ((val / total) * 100).toFixed(1) + '%' : '0%';
                                return ` ${dataset.label || metricLabel || 'Total'}: ${val} (${pct})`;
                            }
                        }
                    },
                    datalabels: {
                        anchor: 'end',
                        align: 'right',
                        offset: 4,
                        clamp: true,
                        font: {
                            weight: 'bold',
                            size: 11,
                            family: "'Segoe UI', Tahoma, sans-serif"
                        },
                        color: '#1e293b',
                        formatter: function(value, context) {
                            const val = Number(value) || 0;
                            const dataset = context.dataset;
                            if (useCustomPct && dataset.customPcts) {
                                const pct = dataset.customPcts[context.dataIndex] ?? 0;
                                return `${val} (${pct}%)`;
                            }
                            if (val === 0) return '0 (0%)';
                            const total = dataset.data.reduce((a, b) => a + (Number(b) || 0), 0);
                            if (total === 0) return `${val} (0%)`;
                            const pct = ((val / total) * 100).toFixed(1) + '%';
                            return `${val} (${pct})`;
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        grace: '25%',
                        ticks: { precision: 0 }
                    },
                    y: {
                        ticks: {
                            font: { size: 11, weight: '600' }
                        }
                    }
                }
            };
        }

        // Opciones para Barras Horizontales Apiladas (con Cantidad y %)
        function buildStackedHorizontalBarOptions() {
            return {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: { boxWidth: 12, font: { size: 11, weight: '600' } }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const val = Number(context.parsed.x) || 0;
                                const idx = context.dataIndex;
                                const datasets = context.chart.data.datasets;
                                const rowTotal = datasets.reduce((acc, ds) => acc + (Number(ds.data[idx]) || 0), 0);
                                const pct = rowTotal > 0 ? ((val / rowTotal) * 100).toFixed(1) + '%' : '0%';
                                return ` ${context.dataset.label}: ${val} (${pct})`;
                            }
                        }
                    },
                    datalabels: {
                        anchor: 'center',
                        align: 'center',
                        color: '#ffffff',
                        font: {
                            weight: 'bold',
                            size: 10,
                            family: "'Segoe UI', Tahoma, sans-serif"
                        },
                        formatter: function(value, context) {
                            const val = Number(value) || 0;
                            if (val === 0) return '';
                            const idx = context.dataIndex;
                            const datasets = context.chart.data.datasets;
                            const rowTotal = datasets.reduce((acc, ds) => acc + (Number(ds.data[idx]) || 0), 0);
                            const pct = rowTotal > 0 ? ((val / rowTotal) * 100).toFixed(0) + '%' : '0%';
                            return `${val} (${pct})`;
                        }
                    }
                },
                scales: {
                    x: {
                        stacked: true,
                        beginAtZero: true,
                        ticks: { precision: 0 }
                    },
                    y: {
                        stacked: true,
                        ticks: { font: { size: 11, weight: '600' } }
                    }
                }
            };
        }

        // Opciones para Gráficos Circulares (Doughnut, Pie, PolarArea) siempre con Cantidad y %
        function buildCircularOptions(type = 'doughnut') {
            const opts = {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'right',
                        labels: {
                            boxWidth: 13,
                            padding: 9,
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
                                        const bg = Array.isArray(dataset.backgroundColor)
                                            ? dataset.backgroundColor[i % dataset.backgroundColor.length]
                                            : dataset.backgroundColor;
                                        return {
                                            text: `${label}: ${val} (${pct})`,
                                            fillStyle: bg,
                                            strokeStyle: bg,
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
                        textStrokeColor: 'rgba(0,0,0,0.45)',
                        textStrokeWidth: 2,
                        font: {
                            weight: 'bold',
                            size: 11,
                            family: "'Segoe UI', Tahoma, sans-serif"
                        },
                        formatter: function(value, context) {
                            const val = Number(value) || 0;
                            if (val === 0) return '';
                            const dataset = context.chart.data.datasets[0];
                            const total = dataset.data.reduce((a, b) => a + (Number(b) || 0), 0);
                            if (total === 0) return `${val}`;
                            const pct = ((val / total) * 100).toFixed(1) + '%';
                            return `${val} (${pct})`;
                        }
                    }
                }
            };
            if (type === 'doughnut') {
                opts.cutout = '55%';
            }
            if (type === 'polarArea') {
                opts.scales = {
                    r: {
                        beginAtZero: true,
                        ticks: { display: false }
                    }
                };
            }
            return opts;
        }

        function coloresSemaforoCumplimiento(pcts) {
            return pcts.map(p => {
                if (p >= 90) return '#198754';
                if (p >= 70) return '#fd7e14';
                return '#dc3545';
            });
        }

        function initCharts() {
            // =========================================================================
            // PESTAÑA 2: VALIDACIÓN CAMBIO DE VÍÁS ONNET (Diversificados con Cant y %)
            // =========================================================================
            // 1. Dona: ¿Cambio de Vías Automático?
            chartsVias.auto = new Chart(document.getElementById('chartAuto'), {
                type: 'doughnut',
                data: {
                    labels: statsVias.auto_labels,
                    datasets: [{
                        label: 'Validaciones',
                        data: statsVias.auto_values,
                        backgroundColor: ['#198754', '#dc3545'],
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: buildCircularOptions('doughnut')
            });

            // 2. Pastel (Pie): ¿Cambio de Vías Exitoso?
            chartsVias.exito = new Chart(document.getElementById('chartExito'), {
                type: 'pie',
                data: {
                    labels: statsVias.exito_labels,
                    datasets: [{
                        label: 'Validaciones',
                        data: statsVias.exito_values,
                        backgroundColor: ['#198754', '#fd7e14'],
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: buildCircularOptions('pie')
            });

            // 3. Barras Horizontales: Tiempo de Duración
            chartsVias.tiempo = new Chart(document.getElementById('chartTiempo'), {
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
                options: buildHorizontalBarOptions('Validaciones')
            });

            // 4. Dona: Experiencia del Técnico
            chartsVias.exp = new Chart(document.getElementById('chartExp'), {
                type: 'doughnut',
                data: {
                    labels: statsVias.exp_labels,
                    datasets: [{
                        label: 'Técnicos',
                        data: statsVias.exp_values,
                        backgroundColor: ['#0d6efd', '#ffc107'],
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: buildCircularOptions('doughnut')
            });

            // 5. Barras Horizontales: Ciudades (Top 8)
            chartsVias.ciudades = new Chart(document.getElementById('chartCiudades'), {
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
                options: buildHorizontalBarOptions('Validaciones')
            });

            // 6. Barras Horizontales: Aliados
            chartsVias.aliados = new Chart(document.getElementById('chartAliados'), {
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
                options: buildHorizontalBarOptions('Validaciones')
            });

            // 7. Dona: Regiones
            chartsVias.regiones = new Chart(document.getElementById('chartRegiones'), {
                type: 'doughnut',
                data: {
                    labels: statsVias.regiones_labels.length ? statsVias.regiones_labels : ['Sin datos'],
                    datasets: [{
                        label: 'Validaciones',
                        data: statsVias.regiones_values.length ? statsVias.regiones_values : [0],
                        backgroundColor: PALETA_COLORES,
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: buildCircularOptions('doughnut')
            });

            // 8. Área Polar: Errores Presentados
            chartsVias.errores = new Chart(document.getElementById('chartErrores'), {
                type: 'polarArea',
                data: {
                    labels: statsVias.errores_labels.length ? statsVias.errores_labels : ['Sin fallas registradas'],
                    datasets: [{
                        label: 'Ocurrencias',
                        data: statsVias.errores_values.length ? statsVias.errores_values : [0],
                        backgroundColor: [
                            'rgba(220, 53, 69, 0.85)',
                            'rgba(253, 126, 20, 0.85)',
                            'rgba(255, 193, 7, 0.85)',
                            'rgba(13, 110, 253, 0.85)',
                            'rgba(111, 66, 193, 0.85)'
                        ],
                        borderWidth: 1,
                        borderColor: '#ffffff'
                    }]
                },
                options: buildCircularOptions('polarArea')
            });

            // =========================================================================
            // PESTAÑA 3: INVENTARIO DE HERRAMIENTAS (Barras Horizontales por Ítem + Propiedad + Diversificados)
            // =========================================================================
            const hLabels = (statsInv.herramientas_labels && statsInv.herramientas_labels.length)
                ? statsInv.herramientas_labels
                : HERRAMIENTAS_OFICIALES;
            const hOk = (statsInv.herramientas_ok_values && statsInv.herramientas_ok_values.length)
                ? statsInv.herramientas_ok_values
                : hLabels.map(() => 0);
            const hNov = (statsInv.herramientas_nov_values && statsInv.herramientas_nov_values.length)
                ? statsInv.herramientas_nov_values
                : hLabels.map(() => 0);
            const hFalt = (statsInv.herramientas_falt_values && statsInv.herramientas_falt_values.length)
                ? statsInv.herramientas_falt_values
                : hLabels.map(() => 0);
            const hPcts = (statsInv.herramientas_pct_cumplimiento && statsInv.herramientas_pct_cumplimiento.length)
                ? statsInv.herramientas_pct_cumplimiento
                : hLabels.map(() => 0);
            const hPropTec = (statsInv.herramientas_prop_tecnico_values && statsInv.herramientas_prop_tecnico_values.length)
                ? statsInv.herramientas_prop_tecnico_values
                : hLabels.map(() => 0);
            const hPropAli = (statsInv.herramientas_prop_aliado_values && statsInv.herramientas_prop_aliado_values.length)
                ? statsInv.herramientas_prop_aliado_values
                : hLabels.map(() => 0);
            const hTotals = hLabels.map((_, idx) => (Number(hOk[idx]) || 0) + (Number(hNov[idx]) || 0) + (Number(hFalt[idx]) || 0));

            // 1. Barras Horizontales: Cumplimiento por cada Ítem de Herramienta (Cant OK y % Cumplimiento)
            chartsInv.cumplimientoItems = new Chart(document.getElementById('chartInvCumplimientoItems'), {
                type: 'bar',
                data: {
                    labels: hLabels,
                    datasets: [{
                        label: 'Herramientas OK (Cumplimiento)',
                        data: hOk,
                        customPcts: hPcts,
                        customTotals: hTotals,
                        backgroundColor: coloresSemaforoCumplimiento(hPcts),
                        borderRadius: 6
                    }]
                },
                options: buildHorizontalBarOptions('Cumplimiento OK', true)
            });

            // 2. Barras Horizontales Apiladas: Estado Detallado por cada Ítem de Herramienta
            chartsInv.desgloseItems = new Chart(document.getElementById('chartInvDesgloseItems'), {
                type: 'bar',
                data: {
                    labels: hLabels,
                    datasets: [
                        {
                            label: '✅ OK',
                            data: hOk,
                            backgroundColor: '#198754',
                            borderRadius: 4
                        },
                        {
                            label: '⚠️ Con Novedad',
                            data: hNov,
                            backgroundColor: '#fd7e14',
                            borderRadius: 4
                        },
                        {
                            label: '❌ Faltante',
                            data: hFalt,
                            backgroundColor: '#dc3545',
                            borderRadius: 4
                        }
                    ]
                },
                options: buildStackedHorizontalBarOptions()
            });

            // 3. Dona: Propiedad Global de Herramientas (Técnico vs Aliado)
            chartsInv.propiedadGlobal = new Chart(document.getElementById('chartInvPropiedadGlobal'), {
                type: 'doughnut',
                data: {
                    labels: statsInv.propiedad_labels || ['Propiedad del Técnico', 'Propiedad del Aliado'],
                    datasets: [{
                        label: 'Herramientas',
                        data: statsInv.propiedad_values || [0, 0],
                        backgroundColor: ['#0dcaf0', '#6610f2'],
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: buildCircularOptions('doughnut')
            });

            // 4. Barras Horizontales Apiladas: Propiedad por cada Ítem de Herramienta (Técnico vs Aliado)
            chartsInv.propiedadItems = new Chart(document.getElementById('chartInvPropiedadItems'), {
                type: 'bar',
                data: {
                    labels: hLabels,
                    datasets: [
                        {
                            label: '👷 Propiedad del Técnico',
                            data: hPropTec,
                            backgroundColor: '#0dcaf0',
                            borderRadius: 4
                        },
                        {
                            label: '🤝 Propiedad del Aliado',
                            data: hPropAli,
                            backgroundColor: '#6610f2',
                            borderRadius: 4
                        }
                    ]
                },
                options: buildStackedHorizontalBarOptions()
            });

            // 5. Dona: Estado Global de Herramientas
            chartsInv.estado = new Chart(document.getElementById('chartInvEstado'), {
                type: 'doughnut',
                data: {
                    labels: statsInv.estado_labels,
                    datasets: [{
                        label: 'Herramientas',
                        data: statsInv.estado_values,
                        backgroundColor: ['#198754', '#fd7e14', '#dc3545'],
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: buildCircularOptions('doughnut')
            });

            // 6. Área Polar: Tipos de Novedad Presentados
            chartsInv.novedades = new Chart(document.getElementById('chartInvNovedades'), {
                type: 'polarArea',
                data: {
                    labels: statsInv.novedades_labels,
                    datasets: [{
                        label: 'Novedades',
                        data: statsInv.novedades_values,
                        backgroundColor: [
                            'rgba(220, 53, 69, 0.85)',
                            'rgba(253, 126, 20, 0.85)',
                            'rgba(255, 193, 7, 0.85)',
                            'rgba(13, 110, 253, 0.85)'
                        ],
                        borderWidth: 1,
                        borderColor: '#ffffff'
                    }]
                },
                options: buildCircularOptions('polarArea')
            });

            // 7. Pastel (Pie): Inventarios por Zona / Área
            chartsInv.zonas = new Chart(document.getElementById('chartInvZonas'), {
                type: 'pie',
                data: {
                    labels: (statsInv.zonas_labels && statsInv.zonas_labels.length) ? statsInv.zonas_labels : ['Sin datos'],
                    datasets: [{
                        label: 'Inventarios',
                        data: (statsInv.zonas_values && statsInv.zonas_values.length) ? statsInv.zonas_values : [0],
                        backgroundColor: ['#0dcaf0', '#6f42c1', '#20c997', '#fd7e14', '#0d6efd', '#ffc107', '#da291c'],
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: buildCircularOptions('pie')
            });

            // 8. Dona: Inventarios por Región
            chartsInv.regiones = new Chart(document.getElementById('chartInvRegiones'), {
                type: 'doughnut',
                data: {
                    labels: statsInv.regiones_labels.length ? statsInv.regiones_labels : ['Sin datos'],
                    datasets: [{
                        label: 'Inventarios',
                        data: statsInv.regiones_values.length ? statsInv.regiones_values : [0],
                        backgroundColor: PALETA_COLORES,
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: buildCircularOptions('doughnut')
            });

            // 9. Barras Horizontales: Auditorías por Aliado
            chartsInv.aliados = new Chart(document.getElementById('chartInvAliados'), {
                type: 'bar',
                data: {
                    labels: (statsInv.aliados_labels && statsInv.aliados_labels.length) ? statsInv.aliados_labels : ['Sin datos'],
                    datasets: [{
                        label: 'Auditorías',
                        data: (statsInv.aliados_values && statsInv.aliados_values.length) ? statsInv.aliados_values : [0],
                        backgroundColor: '#da291c',
                        borderRadius: 6
                    }]
                },
                options: buildHorizontalBarOptions('Auditorías')
            });
        }

        // =========================================================================
        // LÓGICA DE FILTRADO REACTIVO: INVENTARIO DE HERRAMIENTAS
        // =========================================================================
        function eqIgnoreCase(a, b) {
            return String(a || '').trim().toUpperCase() === String(b || '').trim().toUpperCase();
        }

        function aplicarFiltrosInventario() {
            const mesSelect = document.getElementById('filtroInvMes');
            const mes = mesSelect ? mesSelect.value : '';
            const mesLabel = (mesSelect && mesSelect.selectedIndex >= 0) ? mesSelect.options[mesSelect.selectedIndex].text : mes;
            const region = document.getElementById('filtroInvRegion').value;
            const zona = document.getElementById('filtroInvZona').value;
            const aliado = document.getElementById('filtroInvAliado').value;
            const ciudad = document.getElementById('filtroInvCiudad').value;

            // Actualizar badge y link de descarga Excel
            const activos = [];
            const params = new URLSearchParams();
            if (mes) { activos.push(`Mes: ${mesLabel}`); params.set('mes', mes); }
            if (region) { activos.push(`Región: ${region}`); params.set('region', region); }
            if (zona) { activos.push(`Zona: ${zona}`); params.set('zona', zona); }
            if (aliado) { activos.push(`Aliado: ${aliado}`); params.set('aliado', aliado); }
            if (ciudad) { activos.push(`Ciudad: ${ciudad}`); params.set('ciudad', ciudad); }

            const badge = document.getElementById('badgeFiltroInv');
            if (activos.length > 0) {
                badge.className = 'badge bg-danger';
                badge.textContent = 'Filtrado: ' + activos.join(' | ');
            } else {
                badge.className = 'badge bg-secondary';
                badge.textContent = 'Mostrando: Nacional (Todos los Meses)';
            }

            const btnExcel = document.getElementById('btnDescargarInvExcel');
            if (btnExcel) {
                const qs = params.toString();
                btnExcel.href = qs ? `/descargar_inventarios?${qs}` : '/descargar_inventarios';
            }

            // 1. Filtrar Técnicos en Base Nacional según desglose territorial
            let totalTecnicosFiltrados = statsInv.total_tecnicos_base || 0;
            if ((region || zona || aliado || ciudad) && Array.isArray(statsInv.tecnicos_territorial)) {
                totalTecnicosFiltrados = statsInv.tecnicos_territorial
                    .filter(t => (!region || eqIgnoreCase(t.region, region))
                              && (!zona || eqIgnoreCase(t.zona, zona))
                              && (!aliado || eqIgnoreCase(t.aliado, aliado))
                              && (!ciudad || eqIgnoreCase(t.ciudad, ciudad)))
                    .reduce((acc, t) => acc + (Number(t.cnt) || 0), 0);
            }
            document.getElementById('kpiInvTecnicosBase').textContent = totalTecnicosFiltrados.toLocaleString('es-CO');

            // 2. Filtrar registros de inventario (incluyendo Mes) y tomar solo la última auditoría por técnico
            const invFiltradosRaw = rawInventarios.filter(inv => {
                const invMes = String(inv.mes_registro || inv.fecha_registro || '').slice(0, 7);
                return (!mes || invMes === mes)
                    && (!region || eqIgnoreCase(inv.region, region))
                    && (!zona || eqIgnoreCase(inv.area, zona))
                    && (!aliado || eqIgnoreCase(inv.aliado, aliado))
                    && (!ciudad || eqIgnoreCase(inv.comunidad, ciudad));
            });

            const seenCedulas = new Set();
            const invFiltrados = [];
            invFiltradosRaw.forEach(inv => {
                const cedNum = Number(inv.cedula_tecnico) || 0;
                if (cedNum <= 0) return;
                const key = String(cedNum);
                if (!seenCedulas.has(key)) {
                    seenCedulas.add(key);
                    invFiltrados.push(inv);
                }
            });

            // 3. Recalcular KPIs y métricas por cada una de las 10 herramientas (1 auditoría vigente por técnico)
            const totalInv = invFiltrados.length;
            const tecnicosUnicos = totalInv;
            const pctCobertura = totalTecnicosFiltrados > 0 ? ((tecnicosUnicos / totalTecnicosFiltrados) * 100).toFixed(1) : '0.0';
            let totalOk = 0, totalNov = 0, totalFalt = 0, totalEvid = 0;
            let totalPropTec = 0, totalPropAli = 0;

            const mapTools = {};
            HERRAMIENTAS_OFICIALES.forEach(h => { mapTools[h] = { ok: 0, nov: 0, falt: 0, tec: 0, ali: 0 }; });
            const novMap = {
                'No funciona': 0,
                'Funciona parcialmente': 0,
                'Deterioro físico': 0,
                'Falta accesorio': 0
            };

            invFiltrados.forEach(inv => {
                totalOk += Number(inv.herramientas_ok) || 0;
                totalNov += Number(inv.herramientas_novedad) || 0;
                totalFalt += Number(inv.herramientas_faltantes) || 0;
                totalEvid += Number(inv.evidencias_cargadas) || Number(inv.total_evidencias) || 0;

                (inv.detalles || []).forEach(d => {
                    const hName = d.herramienta;
                    if (!mapTools[hName]) {
                        mapTools[hName] = { ok: 0, nov: 0, falt: 0, tec: 0, ali: 0 };
                    }
                    const est = String(d.estado || '').toUpperCase();
                    if (est === 'OK') mapTools[hName].ok++;
                    else if (est === 'NOVEDAD') {
                        mapTools[hName].nov++;
                        const nv = String(d.novedad || '');
                        if (nv.toLowerCase().includes('no funciona')) novMap['No funciona']++;
                        else if (nv.toLowerCase().includes('parcial')) novMap['Funciona parcialmente']++;
                        else if (nv.toLowerCase().includes('deterioro')) novMap['Deterioro físico']++;
                        else if (nv.toLowerCase().includes('accesorio')) novMap['Falta accesorio']++;
                    } else if (est === 'FALTANTE') {
                        mapTools[hName].falt++;
                    }

                    if (est !== 'FALTANTE') {
                        const prop = String(d.propiedad || '').toUpperCase();
                        if (prop.includes('TECNICO') || prop.includes('TÉCNICO')) {
                            mapTools[hName].tec++;
                            totalPropTec++;
                        } else if (prop.includes('ALIADO')) {
                            mapTools[hName].ali++;
                            totalPropAli++;
                        }
                    }
                });
            });

            const totalRequeridas = Math.max(totalInv * HERRAMIENTAS_OFICIALES.length, totalOk + totalNov + totalFalt);
            const pctOk = totalRequeridas > 0 ? ((totalOk / totalRequeridas) * 100).toFixed(1) : '0.0';
            const totalProp = totalPropTec + totalPropAli;
            const pctPropTec = totalProp > 0 ? ((totalPropTec / totalProp) * 100).toFixed(1) : '0.0';
            const pctPropAli = totalProp > 0 ? ((totalPropAli / totalProp) * 100).toFixed(1) : '0.0';

            document.getElementById('kpiInvAuditorias').textContent = totalInv;
            const subAudEl = document.getElementById('kpiInvSubAuditorias');
            if (subAudEl) {
                subAudEl.textContent = `${tecnicosUnicos} técnicos (${pctCobertura}% cobertura)`;
            }
            document.getElementById('kpiInvPctOk').textContent = `${pctOk}%`;
            document.getElementById('kpiInvSubOk').textContent = `${totalOk} OK de ${totalRequeridas} requeridas`;
            document.getElementById('kpiInvPropiedad').textContent = `👷 ${totalPropTec} (${pctPropTec}%)`;
            document.getElementById('kpiInvSubPropiedad').textContent = `🤝 Aliado: ${totalPropAli} (${pctPropAli}%)`;
            document.getElementById('kpiInvNovedades').textContent = (totalNov + totalFalt);
            document.getElementById('kpiInvSubFotos').textContent = `📸 ${totalEvid} fotos cargadas`;

            const hLabels = HERRAMIENTAS_OFICIALES;
            const hOk = hLabels.map(h => mapTools[h].ok);
            const hNov = hLabels.map(h => mapTools[h].nov);
            const hFalt = hLabels.map(h => mapTools[h].falt);
            const hPropTec = hLabels.map(h => mapTools[h].tec);
            const hPropAli = hLabels.map(h => mapTools[h].ali);
            const hTotals = hLabels.map((_, i) => Math.max(totalInv, hOk[i] + hNov[i] + hFalt[i]));
            const hPcts = hLabels.map((_, i) => hTotals[i] > 0 ? Number(((hOk[i] / hTotals[i]) * 100).toFixed(1)) : 0);

            // Actualizar Gráfico 1: Cumplimiento por Ítem
            chartsInv.cumplimientoItems.data.labels = hLabels;
            chartsInv.cumplimientoItems.data.datasets[0].data = hOk;
            chartsInv.cumplimientoItems.data.datasets[0].customPcts = hPcts;
            chartsInv.cumplimientoItems.data.datasets[0].customTotals = hTotals;
            chartsInv.cumplimientoItems.data.datasets[0].backgroundColor = coloresSemaforoCumplimiento(hPcts);
            chartsInv.cumplimientoItems.update();

            // Actualizar Gráfico 2: Desglose Apilado por Ítem
            chartsInv.desgloseItems.data.labels = hLabels;
            chartsInv.desgloseItems.data.datasets[0].data = hOk;
            chartsInv.desgloseItems.data.datasets[1].data = hNov;
            chartsInv.desgloseItems.data.datasets[2].data = hFalt;
            chartsInv.desgloseItems.update();

            // Actualizar Gráfico 3: Propiedad Global (Dona)
            chartsInv.propiedadGlobal.data.datasets[0].data = [totalPropTec, totalPropAli];
            chartsInv.propiedadGlobal.update();

            // Actualizar Gráfico 4: Propiedad por Ítem (Barras Horizontales Apiladas)
            chartsInv.propiedadItems.data.labels = hLabels;
            chartsInv.propiedadItems.data.datasets[0].data = hPropTec;
            chartsInv.propiedadItems.data.datasets[1].data = hPropAli;
            chartsInv.propiedadItems.update();

            // Actualizar Gráfico 5: Estado Global
            chartsInv.estado.data.datasets[0].data = [totalOk, totalNov, totalFalt];
            chartsInv.estado.update();

            // Actualizar Gráfico 6: Novedades
            chartsInv.novedades.data.datasets[0].data = [
                novMap['No funciona'],
                novMap['Funciona parcialmente'],
                novMap['Deterioro físico'],
                novMap['Falta accesorio']
            ];
            chartsInv.novedades.update();

            // Agrupaciones por Zona, Región y Aliado
            function agruparPor(lista, campo, defaultLabel = 'Sin definir') {
                const counts = {};
                lista.forEach(item => {
                    const k = String(item[campo] || defaultLabel).trim() || defaultLabel;
                    counts[k] = (counts[k] || 0) + 1;
                });
                const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
                return {
                    labels: entries.length ? entries.map(e => e[0]) : ['Sin datos'],
                    values: entries.length ? entries.map(e => e[1]) : [0]
                };
            }

            const grpZonas = agruparPor(invFiltrados, 'area', 'Sin Zona');
            chartsInv.zonas.data.labels = grpZonas.labels;
            chartsInv.zonas.data.datasets[0].data = grpZonas.values;
            chartsInv.zonas.update();

            const grpRegiones = agruparPor(invFiltrados, 'region', 'Sin Región');
            chartsInv.regiones.data.labels = grpRegiones.labels;
            chartsInv.regiones.data.datasets[0].data = grpRegiones.values;
            chartsInv.regiones.update();

            const grpAliados = agruparPor(invFiltrados, 'aliado', 'Sin Aliado');
            chartsInv.aliados.data.labels = grpAliados.labels.slice(0, 10);
            chartsInv.aliados.data.datasets[0].data = grpAliados.values.slice(0, 10);
            chartsInv.aliados.update();

            // Filtrar filas de la tabla de inventarios (mostrando solo la última auditoría por técnico)
            const seenTablaCedulas = new Set();
            document.querySelectorAll('.fila-inventario').forEach(tr => {
                const match = (!mes || tr.dataset.mes === mes)
                           && (!region || eqIgnoreCase(tr.dataset.region, region))
                           && (!zona || eqIgnoreCase(tr.dataset.zona, zona))
                           && (!aliado || eqIgnoreCase(tr.dataset.aliado, aliado))
                           && (!ciudad || eqIgnoreCase(tr.dataset.ciudad, ciudad));
                const cedKey = String(tr.dataset.cedula || '').trim();
                let showRow = false;
                if (match && (!cedKey || !seenTablaCedulas.has(cedKey))) {
                    if (cedKey) seenTablaCedulas.add(cedKey);
                    showRow = true;
                }
                tr.style.display = showRow ? '' : 'none';
            });
        }

        function limpiarFiltrosInventario() {
            const mesSelect = document.getElementById('filtroInvMes');
            if (mesSelect) {
                mesSelect.value = statsInv.mes_actual || '';
            }
            document.getElementById('filtroInvRegion').value = '';
            document.getElementById('filtroInvZona').value = '';
            document.getElementById('filtroInvAliado').value = '';
            document.getElementById('filtroInvCiudad').value = '';
            aplicarFiltrosInventario();
        }

        // =========================================================================
        // LÓGICA DE FILTRADO REACTIVO: CAMBIO DE VÍÁS ONNET
        // =========================================================================
        function aplicarFiltrosVias() {
            const region = document.getElementById('filtroViasRegion').value;
            const zona = document.getElementById('filtroViasZona').value;
            const aliado = document.getElementById('filtroViasAliado').value;
            const ciudad = document.getElementById('filtroViasCiudad').value;

            const activos = [];
            if (region) activos.push(`Región: ${region}`);
            if (zona) activos.push(`Zona: ${zona}`);
            if (aliado) activos.push(`Aliado: ${aliado}`);
            if (ciudad) activos.push(`Ciudad: ${ciudad}`);

            const badge = document.getElementById('badgeFiltroVias');
            if (activos.length > 0) {
                badge.className = 'badge bg-danger';
                badge.textContent = 'Filtrado: ' + activos.join(' | ');
            } else {
                badge.className = 'badge bg-secondary';
                badge.textContent = 'Mostrando: Nacional (Todos)';
            }

            const viasFiltradas = rawVias.filter(v => {
                return (!region || eqIgnoreCase(v.region, region))
                    && (!zona || eqIgnoreCase(v.area, zona))
                    && (!aliado || eqIgnoreCase(v.aliado, aliado))
                    && (!ciudad || eqIgnoreCase(v.comunidad, ciudad));
            });

            const total = viasFiltradas.length;
            let autoSi = 0, autoNo = 0;
            let exitoSi = 0, exitoNo = 0;
            let t12 = 0, t23 = 0, tMas3 = 0;
            let expPos = 0, expNeg = 0;
            const errCounts = {};

            viasFiltradas.forEach(v => {
                const a = String(v.cambio_vias_automatico || '').toUpperCase();
                if (a === 'SI' || a === 'SÍ') autoSi++; else autoNo++;

                const e = String(v.cambio_vias_exitoso || '').toUpperCase();
                if (e === 'SI' || e === 'SÍ') exitoSi++; else {
                    exitoNo++;
                    const err = String(v.error_presentado || '').trim();
                    if (err && err !== 'N/A') {
                        errCounts[err] = (errCounts[err] || 0) + 1;
                    }
                }

                const t = String(v.tiempo_duracion || '').toLowerCase();
                if (t.includes('1 a 2')) t12++;
                else if (t.includes('2 a 3')) t23++;
                else tMas3++;

                const ex = String(v.experiencia_tecnico || '').toLowerCase();
                if (ex.includes('positiva')) expPos++; else expNeg++;
            });

            const pctAuto = total > 0 ? ((autoSi / total) * 100).toFixed(1) : '0.0';
            const pctExito = total > 0 ? ((exitoSi / total) * 100).toFixed(1) : '0.0';
            const pctExp = total > 0 ? ((expPos / total) * 100).toFixed(1) : '0.0';

            document.getElementById('kpiViasTotal').textContent = total;
            document.getElementById('kpiViasAuto').textContent = `${pctAuto}%`;
            document.getElementById('kpiViasExito').textContent = `${pctExito}%`;
            document.getElementById('kpiViasExp').textContent = `${pctExp}%`;

            chartsVias.auto.data.datasets[0].data = [autoSi, autoNo];
            chartsVias.auto.update();

            chartsVias.exito.data.datasets[0].data = [exitoSi, exitoNo];
            chartsVias.exito.update();

            chartsVias.tiempo.data.datasets[0].data = [t12, t23, tMas3];
            chartsVias.tiempo.update();

            chartsVias.exp.data.datasets[0].data = [expPos, expNeg];
            chartsVias.exp.update();

            function agruparTop(lista, campo, topN = 8) {
                const counts = {};
                lista.forEach(item => {
                    const k = String(item[campo] || 'Sin datos').trim() || 'Sin datos';
                    counts[k] = (counts[k] || 0) + 1;
                });
                const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, topN);
                return {
                    labels: entries.length ? entries.map(e => e[0]) : ['Sin datos'],
                    values: entries.length ? entries.map(e => e[1]) : [0]
                };
            }

            const grpCiudades = agruparTop(viasFiltradas, 'comunidad', 8);
            chartsVias.ciudades.data.labels = grpCiudades.labels;
            chartsVias.ciudades.data.datasets[0].data = grpCiudades.values;
            chartsVias.ciudades.update();

            const grpAliados = agruparTop(viasFiltradas, 'aliado', 8);
            chartsVias.aliados.data.labels = grpAliados.labels;
            chartsVias.aliados.data.datasets[0].data = grpAliados.values;
            chartsVias.aliados.update();

            const grpRegiones = agruparTop(viasFiltradas, 'region', 10);
            chartsVias.regiones.data.labels = grpRegiones.labels;
            chartsVias.regiones.data.datasets[0].data = grpRegiones.values;
            chartsVias.regiones.update();

            const errEntries = Object.entries(errCounts).sort((a, b) => b[1] - a[1]);
            chartsVias.errores.data.labels = errEntries.length ? errEntries.map(e => e[0]) : ['Sin fallas registradas'];
            chartsVias.errores.data.datasets[0].data = errEntries.length ? errEntries.map(e => e[1]) : [0];
            chartsVias.errores.update();

            document.querySelectorAll('.fila-vias').forEach(tr => {
                const match = (!region || eqIgnoreCase(tr.dataset.region, region))
                           && (!zona || eqIgnoreCase(tr.dataset.zona, zona))
                           && (!aliado || eqIgnoreCase(tr.dataset.aliado, aliado))
                           && (!ciudad || eqIgnoreCase(tr.dataset.ciudad, ciudad));
                tr.style.display = match ? '' : 'none';
            });
        }

        function limpiarFiltrosVias() {
            document.getElementById('filtroViasRegion').value = '';
            document.getElementById('filtroViasZona').value = '';
            document.getElementById('filtroViasAliado').value = '';
            document.getElementById('filtroViasCiudad').value = '';
            aplicarFiltrosVias();
        }

        document.addEventListener('DOMContentLoaded', () => {
            initCharts();
            aplicarFiltrosInventario();
            ['tab-vias-onnet', 'tab-inventario'].forEach(tabId => {
                const el = document.getElementById(tabId);
                if (el) {
                    el.addEventListener('shown.bs.tab', () => {
                        window.dispatchEvent(new Event('resize'));
                    });
                }
            });
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
    validaciones_vias = db.get_validaciones_vias(limit=500)
    stats_inv = db.get_estadisticas_inventario()
    inventarios = db.get_inventarios_herramientas(limit=2000)
    return render_template_string(
        HTML_TEMPLATE,
        stats=stats,
        hallazgos=hallazgos,
        stats_vias=stats_vias,
        validaciones_vias=validaciones_vias,
        stats_inv=stats_inv,
        inventarios=inventarios
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

@app.route("/cargar_tecnicos_inventario", methods=["POST"])
def cargar_tecnicos_inventario():
    file = request.files.get("archivo_tecnicos")
    if not file or file.filename == "":
        flash("No se seleccionó ningún archivo de técnicos.", "warning")
        return redirect(url_for("index"))

    dest = UPLOAD_DIR / f"Base_Tecnicos_Inventario_{int(time.time())}.xlsx"
    file.save(str(dest))
    try:
        total = db.cargar_tecnicos_inventario_excel(str(dest))
        flash(f"¡Base Nacional de Técnicos actualizada con éxito! {total:,} técnicos cargados.", "success")
    except Exception as e:
        flash(f"Error procesando la base de técnicos: {e}", "danger")
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

@app.route("/descargar_inventarios")
def descargar_inventarios():
    mes = request.args.get("mes") or None
    region = request.args.get("region") or None
    aliado = request.args.get("aliado") or None
    ciudad = request.args.get("ciudad") or None
    zona = request.args.get("zona") or None

    inventarios = db.get_inventarios_herramientas(
        limit=10000,
        region=region,
        aliado=aliado,
        comunidad=ciudad,
        area=zona,
        mes=mes
    )
    if not inventarios:
        flash("No hay inventarios registrados para los filtros seleccionados.", "info")
        return redirect(url_for("index"))

    resumen_rows = []
    seen_cedulas = set()
    codigos_vigentes = set()
    for inv in inventarios:
        ced_key = str(inv.get('cedula_tecnico') or '').strip() or f"id_{inv.get('id')}"
        if ced_key in seen_cedulas:
            continue
        seen_cedulas.add(ced_key)
        if inv.get('codigo_auditoria'):
            codigos_vigentes.add(inv['codigo_auditoria'])
        r = {k: v for k, v in inv.items() if k != 'detalles'}
        resumen_rows.append(r)

    detalles_rows = db.get_inventarios_detalle_export(
        limit=50000,
        region=region,
        aliado=aliado,
        comunidad=ciudad,
        area=zona,
        mes=mes
    )
    if codigos_vigentes:
        detalles_rows = [d for d in detalles_rows if d.get('codigo_auditoria') in codigos_vigentes]

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame(resumen_rows).to_excel(writer, sheet_name="Resumen_Auditorias", index=False)
        if detalles_rows:
            pd.DataFrame(detalles_rows).to_excel(writer, sheet_name="Detalle_Herramientas", index=False)
    output.seek(0)

    filename = f"Inventarios_Herramientas_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

@app.route("/evidencias/<path:filename>")
def ver_evidencia(filename):
    clean_name = Path(filename).name
    file_path = UPLOAD_DIR / "evidencias" / clean_name
    if not file_path.exists():
        return "Archivo de evidencia no encontrado", 404
    return send_file(str(file_path), mimetype="image/jpeg")

@app.route("/api/status")
def api_status():
    stats = db.get_estadisticas()
    stats_vias = db.get_estadisticas_vias()
    stats_inv = db.get_estadisticas_inventario()
    return jsonify({
        "status": "online",
        "port": 8505,
        "bot": "@causaraiz_bot",
        "stats": stats,
        "stats_vias": stats_vias,
        "stats_inv": stats_inv
    })

if __name__ == "__main__":
    db.init_db()
    port = int(os.getenv("PORT", 8505))
    print(f"Servidor Web ejecutándose en http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
