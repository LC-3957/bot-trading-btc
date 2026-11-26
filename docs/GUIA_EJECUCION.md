# Guía de ejecución y pruebas (Windows)

Todos los comandos se escriben en la **terminal de VS Code** (menú Terminal → New Terminal), abierta en la carpeta del repositorio. En Mac o Linux usa los mismos pasos con los scripts de `scripts/mac-linux/` y `bash` en lugar de `powershell`.

## 0. Antes de empezar (una sola vez)

Instala estos tres programas y luego cierra y vuelve a abrir VS Code:
- **Python 3.11 o superior**, desde python.org. En el instalador marca **"Add python.exe to PATH"**.
- **Node.js 20 LTS**, desde nodejs.org.
- **Ollama**, desde ollama.com/download. Después de instalarlo, ábrelo una vez para que quede corriendo.

Desde Colab, exporta tu modelo con `scripts/exportar_modelo_colab.py` y copia `modelo_mlp.json` a la carpeta `models/`.

## 1. Instalar (una sola vez)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\1_instalar.ps1
```

Este script:
- Revisa que tengas Python, Node y Ollama.
- Crea el entorno de Python e instala las dependencias del backend y de la interfaz.
- Crea tu archivo `.env` con una clave nueva.
- Descarga el modelo del LLM (la primera vez tarda varios minutos).

## 2. Encender el bot y el panel

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\2_iniciar.ps1
```

Se abren dos ventanas, una del backend y otra del panel, y el navegador en `http://127.0.0.1:5173`.
1. Abre el archivo `.env`, copia el valor de `BOT_API_KEY` y pégalo en el panel.
2. Presiona **Iniciar** y luego **Revisar vela ahora**. En unos segundos aparece la decisión con la propuesta del LLM, la acción final y el motivo.

Para apagar todo, cierra las dos ventanas de PowerShell.

## 3. Generar toda la evidencia

Con Ollama encendido (el backend puede estar encendido o apagado):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\3_evidencia.ps1
```

Tarda varios minutos, porque el replay consulta al LLM 25 veces. Al terminar, la carpeta `docs/` tiene:

| Archivo | Qué demuestra |
|---|---|
| `pruebas_automaticas.txt` | Las pruebas automáticas, una por línea, con su resultado |
| `entorno_llm.md` | Hardware de tu compu, versión de Ollama, modelo y tiempo de respuesta: el LLM es local |
| `validacion_mexc.md` | Error del MLP con precios reales de BTCUSDT en MEXC frente al pronóstico cero |
| `errores/` | Los 9 errores provocados, cada uno con cómo se provocó, qué respondió el agente y su registro |
| `comparacion_replay.md` | 25 ciclos de replay y la comparación entre comprar y mantener, el modelo sin LLM y el agente con LLM |
| `informe.md` | Informe con todas tus cifras reales |

Si quieres otro periodo o más ciclos:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\3_evidencia.ps1 -Desde 2026-09-15 -Ciclos 30
```

## 4. Capturas del panel (recomendado)

Los archivos de `docs/errores/` ya son evidencia. Aun así, al profe le ayuda ver el panel. Guarda estas capturas en `docs/capturas/` con estos nombres exactos; así el informe las detecta solo:

| Archivo | Cómo provocarlo en el panel |
|---|---|
| `03_ollama_detenido.png` | **Hazla primero, antes de cualquier otro ciclo del día** (cada vela se decide una sola vez): cierra Ollama (ícono junto al reloj → Quit), inicia el bot y presiona **Revisar vela ahora**. La acción final sale MANTENER y el error aparece en "Errores recientes". Después vuelve a abrir Ollama. |
| `05_clave_incorrecta.png` | Recarga el panel y escribe una clave equivocada: aparece "Clave incorrecta". |
| `07_evento_duplicado.png` | Presiona **Revisar vela ahora** dos veces: la segunda dice "vela ya procesada". |
| `08_reinicio_backend.png` | Cierra la ventana del backend, vuelve a correr `2_iniciar.ps1` y muestra que la posición y el patrimonio siguen iguales. |
| `09_boton_detener.png` | Presiona **Detener**: el estado cambia a DETENIDO y los botones de ciclo se desactivan. |
| `panel_replay.png` | Botón **Replay histórico**: gráfica, evidencia de 25/20 ciclos y tabla de comparación. |

Después vuelve a generar el informe para que marque las capturas:

```powershell
cd backend; .\.venv\Scripts\python.exe -m app.informe; cd ..
```

## 5. Terminar el informe y subir todo

1. Abre `docs/informe.md` y escribe la sección **10. Conclusiones** (3 a 5 líneas).
2. Sube la evidencia:

```powershell
git add docs models
git commit -m "Evidencia: pruebas, LLM local, validación MEXC, errores provocados, replay e informe"
git push
```

La base de datos (`data/`) y tu `.env` no se suben: ya están en `.gitignore`.

## Si algo falla

| Mensaje | Solución |
|---|---|
| "la ejecución de scripts está deshabilitada" | Usa el comando completo con `-ExecutionPolicy Bypass`, como en esta guía. |
| "Falta Python/Node/Ollama" | Instálalo, cierra y abre VS Code, y repite el paso 1. |
| "OLLAMA_URL debe ser local" o el LLM "no responde" | Abre la app de Ollama. Revisa que `ollama list` muestre el modelo de `.env`. |
| "BOT_API_KEY debe tener al menos 16 caracteres" | Borra `.env` y vuelve a correr `1_instalar.ps1`. |
| "address already in use" (puerto 8000 o 5173) | Ya hay otra ventana del bot abierta: ciérrala. |
| Un error provocado sale "✘ revisar" | Abre su archivo en `docs/errores/`: dice qué respondió el agente. Casi siempre es falta de internet o de Ollama; corrígelo y repite con `python -m app.provocar N`. |
| La validación dice que el MLP no mejora al pronóstico cero | No es un error del programa: es un resultado. Coméntalo en las conclusiones. |
