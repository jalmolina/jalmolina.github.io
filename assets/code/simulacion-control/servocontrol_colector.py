"""Servocontrol por realimentación de estados del colector solar.

Port a Python (NumPy/SciPy) del script MATLAB con el que calculé las
ganancias para el microcontrolador. Simula el modelo no lineal
(motor DC + reductor + colector como péndulo físico) con el control
discreto a Tm = 200 ms.

Uso: python servocontrol_colector.py   (requiere numpy, scipy, matplotlib)
"""
import numpy as np
import scipy.signal as sg
from scipy.integrate import solve_ivp
import matplotlib.pyplot as plt

# Motor DC (identificado con ident de MATLAB)
Ra, La = 3.3, 39.07e-3          # ohm, H
Kt = Kb = 6.6811e-2             # N·m/A, V/(rad/s)
Jm, Bm = 7.224e-5, 6.974e-5     # kg·m², N·m/(rad/s)
# Carga: colector como péndulo físico
M, L, Jl, Bl, g = 21.376, 0.09462, 0.22870565, 1e-3, 9.80665
R = 1 / 978.3                   # relación del reductor
Tm = 0.2                        # período de muestreo, s

# Estados: x = [corriente, velocidad del motor, ángulo del motor]
J = Jm / R + Jl * R
A = np.array([[-Ra / La, -Kb / La, 0],
              [(Kt / R) / J, -(Bm / R + Bl * R) / J, (M * g * L * R) / J],
              [0, 1, 0]])
B = np.array([[1 / La], [0], [0]])
C = np.array([[0, 0, R]])        # salida: ángulo del colector

print("Polos en s:", np.round(np.linalg.eigvals(A), 3))

Ad, Bd, *_ = sg.cont2discrete((A, B, C, np.zeros((1, 1))), Tm, "zoh")

# Se conservan los dos polos estables y el inestable pasa a -0.5 1/s
polos_s = np.array([-55.6232, -29.8174, -0.5])
K = sg.place_poles(Ad, Bd, np.exp(polos_s * Tm)).gain_matrix
print("K =", K)

# Ganancia de seguimiento: ganancia DC unitaria de referencia a salida
Acl = Ad - Bd @ K
N = 1 / (C @ np.linalg.solve(np.eye(3) - Acl, Bd))[0, 0]
print("N =", round(N, 3))


def planta(t, x, u):
    i, w, th = x
    di = (-Ra * i - Kb * w + u) / La
    dw = ((Kt / R) * i - (Bm / R + Bl * R) * w
          + M * g * L * np.sin(th * R)) / J
    return [di, dw, w]


def simular(ref_deg, vmax, t_fin=30.0, t_escalon=2.0):
    x = np.zeros(3)
    t, y, u_log, r_log = [], [], [], []
    for k in range(int(t_fin / Tm)):
        tk = k * Tm
        r = np.deg2rad(ref_deg) if tk >= t_escalon else 0.0
        u = float(np.clip(N * r - (K @ x)[0], -vmax, vmax))
        x = solve_ivp(planta, (0, Tm), x, args=(u,), max_step=1e-3).y[:, -1]
        t.append(tk); y.append(np.rad2deg(x[2] * R))
        u_log.append(u); r_log.append(np.rad2deg(r))
    return map(np.array, (t, y, u_log, r_log))


if __name__ == "__main__":
    fig, ax = plt.subplots(2, 1, sharex=True)
    for vmax, etiqueta in [(1e9, "sin límite"), (12, "±12 V")]:
        t, y, u, r = simular(-75, vmax)
        ax[0].plot(t, y, label=etiqueta)
        ax[1].step(t, u, where="post")
        print(f"{etiqueta}: posición final {y[-1]:.2f}°")
    ax[0].step(t, r, "k--", where="post", label="referencia")
    ax[0].set_ylabel("Colector (°)"); ax[0].legend()
    ax[1].set_ylabel("Tensión (V)"); ax[1].set_xlabel("Tiempo (s)")
    plt.show()
