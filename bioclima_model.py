#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bioclima 3D Model - Standalone Script
-------------------------------------
Genera un modelo 3D conceptual tipo "torres por mes" a partir de series
climáticas (tmax, tmin, viento, radiación). Puede leer un CSV o usar
series dummy con estacionalidad.
"""

from __future__ import annotations
import argparse
import sys
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
         "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


@dataclass
class ClimaMensual:
    tmax: np.ndarray       # (12,)
    tmin: np.ndarray       # (12,)
    viento: np.ndarray     # (12,)
    radiacion: Optional[np.ndarray] = None  # (12,) o None


def _as_array(x: Sequence[float] | np.ndarray, name: str) -> np.ndarray:
    arr = np.asarray(x, dtype=float).reshape(-1)
    if arr.size != 12:
        raise ValueError(f"{name} debe tener 12 valores (uno por mes). Recibido: {arr.size}")
    return arr


def series_dummy(n: int = 12) -> ClimaMensual:
    """Series con estacionalidad simple para demo."""
    m = np.arange(n)
    # Sencillas variaciones senoidales
    tmax = 30 + 8 * np.sin(2*np.pi*(m-2)/n)    # pico hacia verano
    tmin = 15 + 6 * np.sin(2*np.pi*(m-3)/n)
    viento = 4 + 1.2 * np.sin(2*np.pi*(m+1)/n)
    radiacion = 180 + 60 * np.sin(2*np.pi*(m-2)/n)
    return ClimaMensual(tmax=tmax, tmin=tmin, viento=viento, radiacion=radiacion)


def leer_csv(path: str) -> ClimaMensual:
    """
    Lee CSV con columnas: mes(optional), tmax, tmin, viento, radiacion(optional)
    - Ignora encabezados si existen.
    - No requiere la columna 'mes', pero si está, se usa para ordenar por mes.
    """
    import csv

    filas = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # Si no hay encabezados estándar, intentar como reader normal
        if reader.fieldnames is None or all(h.strip() == "" for h in reader.fieldnames):
            f.seek(0)
            reader2 = csv.reader(f)
            # Espera orden fijo: tmax,tmin,viento,(radiacion)
            for row in reader2:
                if not row or all(c.strip() == "" for c in row):
                    continue
                filas.append({
                    "tmax": row[0],
                    "tmin": row[1],
                    "viento": row[2],
                    "radiacion": row[3] if len(row) > 3 else ""
                })
        else:
            # Normalizar headers
            norm = {h: h.strip().lower() for h in reader.fieldnames}
            for r in reader:
                filas.append({k.strip().lower(): v for k, v in r.items()})

    # Intentar mapear nombres
    def pick(row, keys):
        for k in keys:
            if k in row and row[k] != "":
                return row[k]
        return ""

    tmax, tmin, viento, radiacion = [], [], [], []
    for r in filas:
        tmax.append(pick(r, ["tmax", "temp_max", "tempmax"]))
        tmin.append(pick(r, ["tmin", "temp_min", "tempmin"]))
        viento.append(pick(r, ["viento", "wind", "vel_viento", "wind_speed"]))
        radiacion.append(pick(r, ["radiacion", "radiation", "rad"]))

    # Convertir a float ignorando vacíos
    def to_float_list(lst):
        out = []
        for v in lst:
            if v is None or str(v).strip() == "":
                out.append(np.nan)
            else:
                out.append(float(v))
        return out

    tmax = np.array(to_float_list(tmax), dtype=float)
    tmin = np.array(to_float_list(tmin), dtype=float)
    viento = np.array(to_float_list(viento), dtype=float)
    radiacion = np.array(to_float_list(radiacion), dtype=float)

    # Remover filas NaN y limitar a 12 primeras
    mask = ~(np.isnan(tmax) | np.isnan(tmin) | np.isnan(viento))
    tmax = tmax[mask][:12]
    tmin = tmin[mask][:12]
    viento = viento[mask][:12]
    rad = radiacion[mask][:12] if not np.all(np.isnan(radiacion)) else None

    if tmax.size != 12 or tmin.size != 12 or viento.size != 12:
        raise ValueError("El CSV debe contener al menos 12 filas válidas (meses).")

    return ClimaMensual(tmax=tmax, tmin=tmin, viento=viento, radiacion=rad)


def alturas_conceptuales(clima: ClimaMensual) -> np.ndarray:
    """
    Calcula alturas conceptuales normalizadas en [0,100].
    Fórmula base: h = tmax + 0.5*viento + 0.1*radiacion (si hay)
    """
    rad = np.zeros_like(clima.tmax) if clima.radiacion is None else clima.radiacion
    h = clima.tmax + 0.5 * clima.viento + 0.1 * rad
    max_h = float(np.max(h)) if np.any(np.isfinite(h)) else 1.0
    if max_h == 0:
        max_h = 1.0
    return (h / max_h) * 100.0


def plot_modelo_3d(alturas: np.ndarray,
                   elev: float = 25,
                   azim: float = 210,
                   paso: float = 8.0,
                   escala: float = 0.3,
                   torre_xy: float = 2.0,
                   alpha: float = 0.85,
                   titulo: str = "Modelo Paramétrico Bioclimático del Rascacielos") -> plt.Figure:
    """
    Dibuja torres planas (con tapas). Para cerrar laterales, se podrían agregar caras extra.
    """
    fig = plt.figure(figsize=(10, 6))
    ax = fig.add_subplot(111, projection='3d')

    for i, h in enumerate(alturas):
        x = np.array([-torre_xy, -torre_xy,  torre_xy,  torre_xy], dtype=float)
        y = np.array([-torre_xy,  torre_xy,  torre_xy, -torre_xy], dtype=float)
        z_base = i * paso
        z_top = z_base + float(h) * escala

        base = list(zip(x, y, [z_base]*4))
        top = list(zip(x, y, [z_top]*4))

        caras = [base, top]
        poly = Poly3DCollection(caras, facecolor=cm.viridis(i / max(1, len(alturas)-1)), alpha=alpha)
        ax.add_collection3d(poly)

        # Etiqueta del mes en el borde
        ax.text(torre_xy*1.2, torre_xy*1.2, z_base, MESES[i % 12], fontsize=8, zdir='x')

    ax.set_title(titulo)
    ax.set_xlabel("Eje X")
    ax.set_ylabel("Eje Y")
    ax.set_zlabel("Altura (conceptual)")
    ax.view_init(elev=elev, azim=azim)

    # Rango Z agradable
    zmax = len(alturas) * paso + 30
    ax.set_zlim(0, zmax)

    plt.tight_layout()
    return fig


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Genera un modelo 3D bioclimático (12 meses).")
    p.add_argument("--csv", type=str, default=None,
                   help="Ruta a CSV con columnas (tmax, tmin, viento, radiacion opcional). Debe tener >=12 filas.")
    p.add_argument("--lat", type=float, default=None, help="Latitud (informativo).")
    p.add_argument("--lon", type=float, default=None, help="Longitud (informativo).")
    p.add_argument("--save", type=str, default=None, help="Ruta para guardar PNG del gráfico (ej. out.png).")
    p.add_argument("--no-show", action="store_true", help="No mostrar la ventana de matplotlib.")
    p.add_argument("--elev", type=float, default=25.0, help="Ángulo de elevación de cámara.")
    p.add_argument("--azim", type=float, default=210.0, help="Ángulo azimutal de cámara.")
    args = p.parse_args(argv)

    # Cargar datos
    if args.csv:
        clima = leer_csv(args.csv)
    else:
        clima = series_dummy(12)

    # Calcular alturas normalizadas
    alturas = alturas_conceptuales(clima)

    # Plot
    fig = plot_modelo_3d(alturas, elev=args.elev, azim=args.azim)

    # Guardar si se solicita
    if args.save:
        fig.savefig(args.save, dpi=200, bbox_inches="tight")
        print(f"Imagen guardada en: {args.save}")

    # Mostrar
    if not args.no_show:
        plt.show()

    return 0


if __name__ == "__main__":
    sys.exit(main())
