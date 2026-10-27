-- ========================================================
-- BASE DE DATOS Y TABLAS PARA BOT CALIDAD Y CAUSA RAÍZ
-- ========================================================

CREATE DATABASE IF NOT EXISTS `calidad_visitas`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `calidad_visitas`;

-- 1. Tabla de control de cargues diarios
CREATE TABLE IF NOT EXISTS `cargues_control` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `nombre_archivo` VARCHAR(255) NOT NULL,
    `total_registros` INT NOT NULL DEFAULT 0,
    `fecha_cargue` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `usuario_cargue` VARCHAR(100) DEFAULT 'Sistema',
    `activo` TINYINT(1) DEFAULT 1,
    INDEX `idx_fecha_cargue` (`fecha_cargue`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Tabla de visitas de calidad (cargue diario desde Visitas_Calidad.xlsx)
CREATE TABLE IF NOT EXISTS `visitas_calidad` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `cargue_id` INT NOT NULL,
    `fecha_cargue` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `ot` BIGINT NULL,
    `cuenta` BIGINT NULL,
    `aliado` VARCHAR(150) NULL,
    `fecha_trabajo_ini` DATETIME NULL,
    `estado` VARCHAR(100) NULL,
    `trabajo` VARCHAR(150) NULL,
    `tipo` VARCHAR(100) NULL,
    `subtipo` VARCHAR(100) NULL,
    `tecnico` VARCHAR(100) NULL,
    `segmento` VARCHAR(100) NULL,
    `fecha_creacion` VARCHAR(50) NULL,
    `cuenta_matriz` VARCHAR(100) NULL,
    `ubicacion` VARCHAR(150) NULL,
    `red` VARCHAR(50) NULL,
    `region` VARCHAR(50) NULL,
    `area` VARCHAR(150) NULL,
    `distrito` VARCHAR(150) NULL,
    `comunidad` VARCHAR(150) NULL,
    `aliado_zonificado` VARCHAR(150) NULL,
    `proveedor_red` VARCHAR(150) NULL,
    `mes_trabajo` VARCHAR(50) NULL,
    `cantidad_lls` INT NULL DEFAULT 0,
    `primera_lls` BIGINT NULL,
    `fecha_primera_lls` DATETIME NULL,
    `primer_dia_arreglo` INT NULL DEFAULT 0,
    `rango_primer_arreglo` VARCHAR(100) NULL,
    `tuvo_arreglo_30dias` VARCHAR(50) NULL,
    INDEX `idx_cargue_id` (`cargue_id`),
    INDEX `idx_reg_red_com` (`region`, `red`, `comunidad`),
    INDEX `idx_com_rango` (`comunidad`, `rango_primer_arreglo`),
    INDEX `idx_primera_lls` (`primera_lls`),
    INDEX `idx_ot` (`ot`),
    CONSTRAINT `fk_visitas_cargue` FOREIGN KEY (`cargue_id`) REFERENCES `cargues_control`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Tabla Matriz de Causas y Subcausas
CREATE TABLE IF NOT EXISTS `matriz_causas_subcausas` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `causa` VARCHAR(200) NOT NULL,
    `subcausa` VARCHAR(200) NOT NULL,
    `activo` TINYINT(1) DEFAULT 1,
    `fecha_creacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_causa` (`causa`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Tabla de Hallazgos y Respuestas de Causa Raíz registradas por supervisores en Telegram
CREATE TABLE IF NOT EXISTS `hallazgos_respuestas` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `fecha_registro` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `telegram_user_id` BIGINT NOT NULL,
    `telegram_username` VARCHAR(100) NULL,
    `telegram_nombre` VARCHAR(150) NULL,
    `ot` BIGINT NULL,
    `cuenta` BIGINT NULL,
    `aliado` VARCHAR(150) NULL,
    `region` VARCHAR(50) NULL,
    `segmento` VARCHAR(100) NULL,
    `red` VARCHAR(50) NULL,
    `proveedor_red` VARCHAR(150) NULL,
    `comunidad` VARCHAR(150) NULL,
    `primera_lls` BIGINT NULL,
    `rango_primer_arreglo` VARCHAR(100) NULL,
    `causa` VARCHAR(200) NOT NULL,
    `subcausa` VARCHAR(200) NOT NULL,
    `observaciones` TEXT NULL,
    `estado` VARCHAR(50) NOT NULL DEFAULT 'Completado',
    INDEX `idx_resp_ot` (`ot`),
    INDEX `idx_resp_primera_lls` (`primera_lls`),
    INDEX `idx_resp_telegram_user` (`telegram_user_id`),
    INDEX `idx_resp_fecha` (`fecha_registro`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Tabla de Validación Cambio Vías Onnet (Red Neutra)
CREATE TABLE IF NOT EXISTS `validacion_cambio_vias_onnet` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `fecha_registro` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `telegram_user_id` BIGINT NOT NULL,
    `telegram_username` VARCHAR(100) NULL,
    `telegram_nombre` VARCHAR(150) NULL,
    `region` VARCHAR(50) NULL,
    `red` VARCHAR(50) DEFAULT 'Red Neutra',
    `aliado` VARCHAR(150) NULL,
    `segmento` VARCHAR(100) NULL,
    `comunidad` VARCHAR(150) NULL,
    `cuenta` BIGINT NULL,
    `cambio_vias_automatico` VARCHAR(20) NULL,
    `cambio_vias_exitoso` VARCHAR(20) NULL,
    `error_presentado` VARCHAR(150) NULL,
    `tiempo_duracion` VARCHAR(50) NULL,
    `experiencia_tecnico` VARCHAR(50) NULL,
    `observaciones` TEXT NULL,
    INDEX `idx_vias_cuenta` (`cuenta`),
    INDEX `idx_vias_comunidad` (`comunidad`),
    INDEX `idx_vias_fecha` (`fecha_registro`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Tabla Base Nacional de Técnicos para Inventario (Base_Tecnicos_Inventario.xlsx)
CREATE TABLE IF NOT EXISTS `base_tecnicos_inventario` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `cedula` BIGINT NOT NULL UNIQUE,
    `nombre_tecnico` VARCHAR(200) NOT NULL,
    `fecha_ingreso` VARCHAR(50) NULL,
    `antiguedad` VARCHAR(100) NULL,
    `aliado` VARCHAR(150) NULL,
    `region` VARCHAR(50) NULL,
    `area` VARCHAR(150) NULL,
    `comunidad` VARCHAR(150) NULL,
    `owner` VARCHAR(200) NULL,
    `q30` VARCHAR(100) NULL,
    `fecha_actualizacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_tec_cedula` (`cedula`),
    INDEX `idx_tec_region` (`region`),
    INDEX `idx_tec_aliado` (`aliado`),
    INDEX `idx_tec_comunidad` (`comunidad`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Tabla Cabecera de Auditorías de Inventario de Herramientas
CREATE TABLE IF NOT EXISTS `inventarios_herramientas` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `codigo_auditoria` VARCHAR(50) NOT NULL UNIQUE,
    `fecha_registro` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `telegram_user_id` BIGINT NOT NULL,
    `telegram_username` VARCHAR(100) NULL,
    `telegram_nombre` VARCHAR(150) NULL,
    `cedula_tecnico` BIGINT NOT NULL,
    `nombre_tecnico` VARCHAR(200) NOT NULL,
    `aliado` VARCHAR(150) NULL,
    `region` VARCHAR(50) NULL,
    `area` VARCHAR(150) NULL,
    `comunidad` VARCHAR(150) NULL,
    `total_herramientas` INT NOT NULL DEFAULT 10,
    `herramientas_ok` INT NOT NULL DEFAULT 0,
    `herramientas_novedad` INT NOT NULL DEFAULT 0,
    `herramientas_faltantes` INT NOT NULL DEFAULT 0,
    `total_evidencias` INT NOT NULL DEFAULT 0,
    `foto_general_path` VARCHAR(300) NULL,
    `resumen_novedades` TEXT NULL,
    `observaciones` TEXT NULL,
    INDEX `idx_inv_codigo` (`codigo_auditoria`),
    INDEX `idx_inv_cedula` (`cedula_tecnico`),
    INDEX `idx_inv_region` (`region`),
    INDEX `idx_inv_fecha` (`fecha_registro`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. Tabla Detalle por Herramienta de cada Inventario
CREATE TABLE IF NOT EXISTS `inventarios_herramientas_detalle` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `inventario_id` BIGINT NOT NULL,
    `codigo_auditoria` VARCHAR(50) NOT NULL,
    `herramienta` VARCHAR(100) NOT NULL,
    `estado` VARCHAR(50) NOT NULL,
    `novedad` VARCHAR(100) NULL,
    `evidencia_path` VARCHAR(300) NULL,
    INDEX `idx_invdet_inv_id` (`inventario_id`),
    INDEX `idx_invdet_codigo` (`codigo_auditoria`),
    CONSTRAINT `fk_invdet_inventario` FOREIGN KEY (`inventario_id`) REFERENCES `inventarios_herramientas`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
