# SportStatistics

Probabilidades calibradas para **fútbol, NBA, MLB y tenis**, con una app privada en
Streamlit que muestra cada enfrentamiento, la agenda del día y comprueba cada noche qué
predicciones se cumplieron.

> Herramienta educativa de análisis estadístico. No es consejo de apuestas ni garantiza
> resultados: un favorito del 75 % pierde 1 de cada 4 veces.

## Qué hace

- **Motores por deporte** (`core/forecast/`): GLM Poisson + ratings Dixon-Coles (fútbol),
  ratings por posesión + Elo (NBA), carreras con estadio neutral y binomial negativa (MLB) y
  Elo con K dinámico por superficie (tenis). Cada partido tiene una sola distribución y todos
  sus mercados salen de ella.
- **App** con seis secciones: Inicio, Partidos, Resumen del día, Analizador, Rendimiento y
  Valor. Diseño oscuro, responsivo y accesible.
- **Automatización** con GitHub Actions: refresco diario de datos y cierre del día a las 23:00
  (hora del Pacífico), que resuelve las predicciones y mantiene activa la base de datos.
- **Calibración verificada**: el historial compara lo prometido con lo que pasó.

| Deporte | Log-loss del ganador, v1 → v2 (fuera de muestra) |
|---|---|
| Fútbol (1X2) | 1,0172 → **1,0130** |
| NBA | 0,6115 → **0,6088** |
| MLB | 0,7222 → **0,6779** |
| Tenis | 0,6377 → **0,6275** |

## Inicio rápido

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

Necesita una base de datos PostgreSQL con los esquemas de `core/database/` y la variable
`DATABASE_URL`. Configuración, despliegue gratuito y secretos: [documentacion/operacion.md](documentacion/operacion.md).

## Documentación

| | |
|---|---|
| [Arquitectura](documentacion/arquitectura.md) | piezas, flujo de datos y carpetas |
| [Modelos](documentacion/modelos.md) | fórmulas, parámetros y evaluación |
| [La app](documentacion/app.md) | secciones, diseño y capa de datos |
| [Datos y automatización](documentacion/datos-y-automatizacion.md) | BD, workflows y resumen diario |
| [Seguridad](documentacion/seguridad.md) | qué se protege y cómo |
| [Operación](documentacion/operacion.md) | ejecutar, desplegar y resolver problemas |
| [Referencia del código](documentacion/codigo.md) | qué hace cada módulo |

## Stack

Python 3.12+ · Streamlit · PostgreSQL · pandas · NumPy · SciPy · Plotly · GitHub Actions.

## Créditos y licencias de terceros

- Fútbol: [football-data.co.uk](https://www.football-data.co.uk) y [football-data.org](https://www.football-data.org).
- MLB: [MLB Stats API](https://statsapi.mlb.com). *The information used here was obtained
  free of charge from and is copyrighted by Retrosheet. Interested parties may contact
  Retrosheet at [www.retrosheet.org](https://www.retrosheet.org).*
- Tenis: datos de Jeff Sackmann ([tennis_atp](https://github.com/JeffSackmann/tennis_atp),
  [tennis_wta](https://github.com/JeffSackmann/tennis_wta)), licencia CC BY-NC-SA 4.0.
- Tipografías Big Shoulders Display, Schibsted Grotesk y Geist Mono, licencia SIL Open Font
  License 1.1 (`app/static/fonts/LICENSE-OFL.txt`).
