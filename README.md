# MCP-Infostat

Servidor MCP local para automatizar InfoStat en Windows, orientado inicialmente a InfoStat 2008.

## Estado actual

Este repositorio se encuentra en implementacion de Sprint 2 (Bloque A teclado) sobre la base de Sprint 0 + Sprint 1.

Incluye actualmente:
- Estructura base de servidor MCP en Python.
- Configuracion central en config.toml.
- Seguridad de rutas y extensiones para carga de datos.
- Gestion de sesion (launch, status, close).
- Carga de datos CSV/TXT con estrategia de teclado en InfoStat (Alt/Ctrl atajos + dialogo abrir).
- Lectura de resultados en formato raw_text.
- Tests unitarios iniciales.

No incluye aun:
- Analisis estadistico (descriptivos, ANOVA, regresion, etc).
- Parser estructurado de resultados por tipo de analisis.
- Transporte HTTP (solo stdio en este hito).

## Alcance del hito actual

Objetivo de infraestructura:

1. infostat_launch
2. infostat_status
3. infostat_close
4. data_load
5. data_get_info
6. results_get_last (raw_text)

## Requisitos

- Windows 10/11.
- InfoStat 2008 instalado en la maquina local.
- Python 3.11+.

## Configuracion

Editar config.toml segun tu entorno, especialmente:

- infostat.exe_path
- paths.data_base_dir
- paths.results_base_dir

## Instalacion

```powershell
python -m venv .venv
& ".\.venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Ejecucion del servidor

```powershell
& ".\.venv\Scripts\Activate.ps1"
python server.py
```

El transporte actual es stdio.

## Ejecutar tests

```powershell
& ".\.venv\Scripts\Activate.ps1"
pytest
```

## Estructura principal

```text
mcp-infostat/
	server.py
	config.toml
	mcp_infostat/
		config.py
		errors.py
		security.py
		session.py
		utils.py
		ui/
			launcher.py
		results/
			capture.py
	tests/
```

## Proximo paso

Completar Sprint 2 con los primeros analisis estadisticos (descriptivos, normalidad, ANOVA DCA) y parser estructurado de resultados.
