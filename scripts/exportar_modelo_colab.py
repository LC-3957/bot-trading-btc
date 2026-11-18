# Exporta el MLP elegido en el avance 2 (BTC-USD) a models/modelo_mlp.json.
# Pégalo en una celda nueva AL FINAL del notebook Cap8_Avance2_DL_Finanzas.ipynb (misma sesión),
# porque usa las variables RES, exp, SEED, X_va, predecir y OUT de ese notebook.
import json, datetime as dt
import numpy as np
import torch

mlps = exp[(exp["modelo"] == "MLP") & (exp["fase"] == "configuracion")]
fila = mlps.loc[mlps["RMSE_VA"].idxmin()]
h, lr_ = int(fila["neuronas"]), float(fila["lr"])
res = RES[("MLP", h, lr_, SEED)]
lineales = [m for m in res["model"].net if isinstance(m, torch.nn.Linear)]

export = {
    "nombre": f"MLP{h}",
    "version_modelo": "0.2.0",
    "entrenado_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    "datos": "BTC-USD diario (Yahoo Finance), TR del avance 1",
    "entradas": "20 rendimientos: lag_0 = r_t (más reciente) … lag_19",
    "configuracion": {"neuronas": h, "lr": lr_, "semilla": SEED, "capas": res["info"]["capas"]},
    "rmse_va": float(fila["RMSE_VA"]), "mae_va": float(fila["MAE_VA"]),
    "capas": [{"W": l.weight.detach().cpu().numpy().tolist(), "b": l.bias.detach().cpu().numpy().tolist()} for l in lineales],
    "escalador": {"media": res["xs"].mean_.tolist(), "escala": res["xs"].scale_.tolist()},
    "objetivo": {"media": float(res["mu"]), "desv": float(res["sd"])},
}

# Verificación: el paso hacia adelante en NumPy (igual al del bot) reproduce a PyTorch
def adelante(x):
    z = (x - np.array(export["escalador"]["media"])) / np.array(export["escalador"]["escala"])
    for i, c in enumerate(export["capas"]):
        z = z @ np.array(c["W"]).T + np.array(c["b"])
        if i < len(export["capas"]) - 1:
            z = np.maximum(z, 0)
    return z[:, 0] * export["objetivo"]["desv"] + export["objetivo"]["media"]

assert np.allclose(adelante(X_va[:50]), predecir(res, X_va[:50]), atol=1e-6), "La exportación no coincide con PyTorch"
ruta = os.path.join(OUT, "modelo_mlp.json")
json.dump(export, open(ruta, "w"), indent=1)
print(f"Exportado {export['nombre']} (RMSE VA {export['rmse_va']:.6f}) → {ruta}")
try:
    from google.colab import files
    files.download(ruta)
except ImportError:
    pass
