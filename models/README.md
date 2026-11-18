# Modelo

Aquí va `modelo_mlp.json`: el MLP del avance 2 (16, 32 o 64 neuronas, el de menor RMSE de VA), entrenado con BTC-USD en Colab.

1. En Colab, ejecuta completo el avance 2 con GPU T4.
2. Al final, en la misma sesión, pega y ejecuta `scripts/exportar_modelo_colab.py`. Descarga `modelo_mlp.json`.
3. Copia el archivo aquí y haz commit: el modelo y su escalador quedan versionados.
4. Mide cómo se comporta con datos reales de MEXC: `cd backend && python -m app.validar` (genera `docs/validacion_mexc.md`).

Si el archivo no existe, el bot usa el pronóstico cero y lo indica en la interfaz.
