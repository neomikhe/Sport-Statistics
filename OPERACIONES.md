# 🛠️ Operaciones y mantenimiento

Guía mínima para que el proyecto se mantenga solo con **una intervención ocasional**.
Escrita para tu yo del futuro: qué corre solo, qué hacer si algo falla y el único
comando de mantenimiento periódico.

---

## 1. Qué corre solo (sin que toques nada)

| Automatismo | Cuándo | Qué hace | Escribe en |
|---|---|---|---|
| **Refresco de datos** (`.github/workflows/refresh.yml`) | Diario, 23:00 UTC | Descarga → ingesta → Elo → features → picks de los 4 deportes | BD (no el repo) |
| **Monitor de deriva** (paso del mismo workflow) | Diario, tras el refresco | Mide el log-loss del modelo con partidos recientes; marca `model_health` | BD (`app_meta`) |
| **CI** (`.github/workflows/ci.yml`) | Cada push/PR | Compila todo + corre los 58 tests | — (solo valida) |

La app **siempre lee lo último de la BD**, así que el refresco no necesita tocar el
repositorio. Si el modelo se degrada, la portada muestra un aviso automático.

**Requisito:** el secret `DB_URL` en GitHub → Settings → Secrets → Actions
(conexión en modo **sesión**, puerto 5432, no el pooler de transacciones).

---

## 2. Mantenimiento periódico: **1 comando**

Los modelos y calibradores no se re-entrenan solos en la nube (el cron no puede
escribir en el repo). Re-entrénalos **en local** cada **temporada** (o cuando el
dashboard avise de degradación):

```bash
venv\Scripts\activate
python scripts/retrain_all.py
```

Esto, de forma segura:
1. Respalda los modelos actuales en `data/models/.backup/`.
2. Reconstruye features y re-entrena modelos + calibradores (por deporte, aislado).
3. **Gate OOS**: si el nuevo modelo de fútbol empeora vs el anterior, hace **rollback**
   automático. Los calibradores solo se guardan si mejoran (gate interno).
4. Sella `app_meta` con la hora y el reporte.

Después, **revisa y commitea** los modelos actualizados (tú haces los commits):

```bash
git add -f data/models/*.joblib
git commit -m "retrain: modelos y calibradores de <temporada>"
git push
```

> ⚠️ Los `.joblib` están en `.gitignore`; usa `git add -f`. Solo lo que commitees
> llega a la nube. Hoy están commiteados el GLM de fútbol y las CSV de picks; si
> quieres que la calibración de NBA/MLB también aplique en la nube, commitea sus
> `*_calibrator_v1.joblib`.

---

## 3. Salud del modelo (¿está prediciendo bien?)

- El monitor compara el log-loss reciente (últimos 90 días) con la línea base del
  modelo (su rendimiento en el hold-out). Si supera la base × 1.15 → **degradado**.
- Verlo a mano en cualquier momento:
  ```bash
  python scripts/monitor_drift.py
  ```
- Auditar si un cambio (features, modelo, calibración) mejora de verdad:
  ```bash
  python scripts/eval_probability_vs_market.py      # ¿le gana al mercado? (no, y es normal)
  python scripts/eval_football_ensemble.py          # ¿ayuda el ensemble?
  ```
  **Regla de oro:** nada se despliega si no baja el log-loss OOS.

---

## 4. Si algo falla

| Síntoma | Causa probable | Solución |
|---|---|---|
| App: "No hay picks todavía" | La BD no tiene picks | Corre `python scripts/refresh_cloud.py` (con `DATABASE_URL`) |
| Aviso "Modelo degradado" en la portada | El modelo envejeció | `python scripts/retrain_all.py` + commitea los modelos |
| Workflow `refresh-data` en rojo | Fuente caída (p. ej. nba_api) o falta `DB_URL` | Cada deporte es aislado; revisa el log. El refresco no rompe datos previos |
| Workflow `ci` en rojo | Un cambio rompió tests/compilación | Mira qué test falla; el CI te dice exactamente qué |
| NBA/otros analizadores fallan en la nube | Falta el `.joblib` del modelo en el repo | `git add -f data/models/<modelo>.joblib` y push |
| Despliegue rompe tras semanas | Una dependencia se actualizó sola | Ya no pasa: `requirements.txt` tiene versiones fijadas (`==`) |

---

## 5. Mapa de scripts clave

| Script | Para qué |
|---|---|
| `refresh_cloud.py` | Refresco completo de datos (lo corre el cron) |
| `retrain_all.py` | **Re-entrenar todo con gate** (mantenimiento local periódico) |
| `monitor_drift.py` | Chequeo de salud del modelo (lo corre el cron) |
| `eval_*.py` | Auditar OOS cualquier cambio antes de desplegarlo |
| `train_*_calibrator.py` | Calibradores individuales (auto-gated) |

---

## 6. Estado conocido (medido, no re-litigar)

La precisión del modelo está **en su techo** con datos públicos: iguala al mercado
pero no lo supera (probado OOS). Calibración activa solo en NBA y MLB (marginal);
en fútbol y tenis el gate la descartó por no mejorar. El siguiente salto real
requeriría **datos de pago** (xG/alineaciones), no más matemática. Ver el análisis
en los `scripts/eval_*.py`.
