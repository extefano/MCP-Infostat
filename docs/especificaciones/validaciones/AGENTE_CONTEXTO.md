# AGENTE_CONTEXTO.md
# Archivo de contexto de sesión para agente autónomo — MCP-InfoStat
# El agente debe leer este archivo al inicio de cada sesión antes de actuar.

## Qué es este proyecto

Servidor MCP local en Python que permite a una IA agéntica controlar InfoStat 2008
(software de análisis estadístico argentino) de forma automatizada en Windows.

Repositorio: https://github.com/extefano/MCP-Infostat

---

## Estado del código al inicio de esta especificación

Sprint 0+1 COMPLETO y Sprint 2 BLOQUE A (teclado) en progreso. Implementado y validado:

- `server.py` con tools: `infostat_launch`, `infostat_status`, `infostat_close`,
  `data_load` (carga UI por teclado para CSV/TXT), `data_get_info`, `results_get_last` (raw_text)
- Módulos: `config.py`, `errors.py`, `security.py`, `session.py`, `utils.py`
- UI: `launcher.py` | Results: `capture.py`
- Tests: suite unitaria verde
- Transporte: stdio

Lo que NO está implementado todavía:
- Análisis estadísticos (descriptivos, normalidad, ANOVA)
- Parser estructurado de resultados (`.ist` → JSON)
- `results_get_last` modo structured

---

## Tarea del agente en esta sesión

### Paso 1 — Verificar si ya existe diagnóstico previo

```powershell
if (Test-Path "diagnostico_log.txt") {
    Get-Content "diagnostico_log.txt" | Select-String "DECISION:|PASS:|FAIL:|WARN:"
}
```

Si existe `diagnostico_log.txt` con una DECISION clara, saltar al Paso 3.
Si no existe o está desactualizado (más de 7 días), ejecutar el Paso 2.

### Paso 2 — Ejecutar diagnóstico automático

```powershell
.\docs\especificaciones\validaciones\diagnostico_completo.ps1 | Tee-Object -FilePath diagnostico_log.txt
```

Este script (incluido en el repositorio en `docs/especificaciones/validaciones/`) evalúa
el entorno completo y termina con una línea `DECISION:` que indica el bloque.

### Paso 3 — Leer la decisión y actuar

Buscar en `diagnostico_log.txt` la última línea que empiece con `=>` o `!!`:

```powershell
Get-Content "diagnostico_log.txt" | Select-String "=> |!! "
```

Según el resultado:

| Decisión en el log                          | Acción del agente                          |
|---------------------------------------------|--------------------------------------------|
| `STOP: Hay tests rotos`                     | Leer output de pytest, reparar tests       |
| `BLOQUE C: Parser estructurado con mock`    | Ver sección BLOQUE C abajo                 |
| `BLOQUE C + investigar`                     | Ver sección BLOQUE C + investigar launch   |
| `BLOQUE A limitado`                         | Ver sección BLOQUE A LIMITADO abajo        |
| `BLOQUE A con estrategia teclado`           | Ver sección BLOQUE A TECLADO abajo         |
| `BLOQUE A COMPLETO + BLOQUE B habilitado`  | Ver sección BLOQUE A+B COMPLETO abajo      |

### Paso 3.1 — Verificar compatibilidad de instalacion

Antes de implementar, revisar estas lineas del resumen del log:

```powershell
Get-Content "diagnostico_log.txt" | Select-String "Compat arch ok|Version doc risk|Runtime errors30d|Installer ver risk|NOTA_COMPAT"
```

Reglas de accion:

- Si `Compat arch ok : False`, priorizar estrategia de teclado y evitar depender de arboles UI complejos.
- Si `Version doc risk : True`, no asumir etiquetas exactas del manual 2008; validar atajos sobre la instalacion real.
- Si `Runtime errors30d` es mayor que 0, registrar incidente y pausar cambios funcionales hasta estabilizar ejecucion.
- Si `Installer ver risk : True`, registrar discrepancia entre version MSI y ejecutable antes de automatizar menus.

---

## BLOQUE C — Parser estructurado (sin InfoStat corriendo)

**Cuándo:** InfoStat no está instalado o no lanza. El agente puede implementar
el parser de resultados usando archivos de ejemplo mockeados.

### Objetivo
Implementar `results/parser.py` que convierta output raw de InfoStat a JSON estructurado.
Agregar modo `structured` a `results_get_last` en `server.py`.

### Qué implementar

1. Crear `mcp_infostat/results/parser.py` con función:
   ```python
   def parse_infostat_output(raw_text: str, analysis_type: str) -> dict:
       """
       Parsea output raw de InfoStat.
       analysis_type: 'descriptivos' | 'normalidad' | 'anova_dca'
       Retorna dict con valores numéricos extraídos.
       """
   ```

2. Formato de salida esperado para descriptivos:
   ```json
   {
     "tipo": "descriptivos",
     "variables": [
       {
         "nombre": "Altura",
         "n": 30,
         "media": 172.3,
         "desvio": 8.5,
         "minimo": 155.0,
         "maximo": 191.0,
         "cv": 4.94
       }
     ]
   }
   ```

3. Crear archivos mock en `tests/fixtures/`:
   - `descriptivos_sample.txt` — output típico de descriptivos en InfoStat
   - `normalidad_sample.txt` — output de Shapiro-Wilk
   - `anova_dca_sample.txt` — output de ANOVA

4. Agregar tests en `tests/test_parser.py`

### Cómo crear los fixtures mock

InfoStat 2008 genera resultados en texto plano con este formato aproximado
para estadísticas descriptivas (recrear en los fixtures):

```
Estadísticas descriptivas
Variable: Altura
  N      : 30
  Media  : 172.30
  D.E.   : 8.50
  Mínimo : 155.00
  Máximo : 191.00
  C.V.%  : 4.94
```

Para ANOVA DCA:
```
Análisis de la Varianza
  F.V.       SC      gl   CM      F    p-valor
  Tratamiento 450.20  3   150.07  8.54  0.0002
  Error       422.60  24   17.61
  Total       872.80  27
```

---

## BLOQUE A LIMITADO — data_load sin UI

**Cuándo:** InfoStat lanza pero pywinauto no puede conectar.

### Objetivo
Implementar `data_load` que copia el archivo al directorio de trabajo de InfoStat
sin automatizar la UI. El usuario/agente debe abrir el archivo manualmente en InfoStat,
pero `data_get_info` puede leer metadata del archivo.

### Qué implementar

En `mcp_infostat/ui/launcher.py`, agregar:
```python
def prepare_data_file(source_path: str, infostat_data_dir: str) -> dict:
    """
    Copia el archivo al directorio de trabajo de InfoStat.
    No abre InfoStat UI — solo prepara el archivo.
    """
```

---

## BLOQUE A TECLADO — data_load con SendKeys

**Cuándo:** pywinauto conecta pero el menú no es accesible por objeto.

### Objetivo
Automatizar apertura de archivo en InfoStat usando teclas de acceso directo.

### Qué implementar

En `mcp_infostat/ui/launcher.py`:
```python
def load_file_via_keyboard(app, file_path: str) -> bool:
    """
    Usa Alt+A (Archivo), luego A (Abrir) o secuencia equivalente.
    Requiere inspeccionar el menú real de InfoStat para confirmar atajos.
    """
    main_win = app.top_window()
    main_win.set_focus()
    # Secuencia a confirmar contra InfoStat real:
    main_win.type_keys("%a")   # Alt+A = Archivo (verificar)
    time.sleep(0.5)
    main_win.type_keys("a")    # A = Abrir (verificar)
    time.sleep(1)
    # Completar path en diálogo de apertura
    ...
```

**IMPORTANTE:** El agente debe primero inspeccionar el menú real con la sección 3.5
del diagnóstico para conocer los atajos exactos antes de implementar esto.

---

## BLOQUE A+B COMPLETO — UI automation + análisis estadísticos

**Cuándo:** pywinauto conecta Y el menú es accesible por objeto.

### Objetivo
Implementar el ciclo completo: launch → load (UI real) → run analysis → capture results.

### Tools a implementar en server.py

```python
@mcp.tool()
async def analysis_run(
    variable: str,
    analysis_type: str  # 'descriptivos' | 'normalidad' | 'anova_dca'
) -> dict:
    """Ejecuta análisis en InfoStat sobre la variable indicada."""

@mcp.tool()
async def analysis_descriptivos(variables: list[str]) -> dict:
    """Estadísticas descriptivas básicas."""

@mcp.tool()
async def analysis_normalidad(variable: str, test: str = "shapiro") -> dict:
    """Test de normalidad (Shapiro-Wilk o K-S)."""

@mcp.tool()
async def analysis_anova_dca(
    variable_respuesta: str,
    factor: str
) -> dict:
    """ANOVA Diseño Completamente Aleatorizado."""
```

### Secuencia de automatización UI para cada análisis

El agente debe verificar contra el log de diagnóstico (sección 3.5)
qué items de menú están disponibles. La secuencia típica esperada en InfoStat:

1. Menú `Estadísticas` (o `Análisis`)
2. Submenú `Estadísticas descriptivas` → seleccionar variables
3. `Aceptar` en diálogo
4. Capturar ventana de resultados
5. Leer texto de resultados → `results_get_last`

---

## Convenciones de código a mantener

- Todos los tools MCP retornan el esquema estándar de `utils.py`
- Errores via `errors.py` (MCPError y subclases)
- Paths validados via `security.py` antes de cualquier operación de archivo
- Nuevo código en módulos bajo `mcp_infostat/`, no directamente en `server.py`
- Tests para cada módulo nuevo en `tests/`
- Después de implementar, ejecutar `pytest tests/ -v` y confirmar suite verde

---

## Al finalizar la sesión

El agente debe:
1. Correr `pytest tests/ -v` y confirmar que todos los tests pasan
2. Actualizar `diagnostico_log.txt` con el estado final
3. Hacer commit con mensaje descriptivo del bloque implementado
4. Actualizar `README.md` si el estado cambió

```powershell
git add -A
git commit -m "Sprint2: [descripcion de lo implementado] — tests: X/X"
git push origin main
```
