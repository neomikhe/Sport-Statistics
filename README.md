# SportStatistics

**Plataforma de análisis estadístico cuantitativo de eventos deportivos.**

SportStatistics estima la probabilidad real de los distintos resultados de un
encuentro a partir de modelos estadísticos entrenados con datos históricos, sin
recurrir a las cuotas del mercado. Cubre cuatro deportes —fútbol, baloncesto (NBA),
béisbol (MLB) y tenis— y presenta los resultados en un panel web interactivo.

> **Aviso.** Herramienta con fines educativos y de análisis estadístico. No
> constituye consejo de apuestas ni garantiza resultados.

---

## Índice

- [Descripción general](#descripción-general)
- [Características principales](#características-principales)
- [Metodología y modelos](#metodología-y-modelos)
- [Arquitectura](#arquitectura)
- [Stack tecnológico](#stack-tecnológico)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Puesta en marcha (local)](#puesta-en-marcha-local)
- [Despliegue](#despliegue)
- [Fuentes de datos](#fuentes-de-datos)
- [Validación y limitaciones](#validación-y-limitaciones)
- [Seguridad y privacidad](#seguridad-y-privacidad)
- [Licencia](#licencia)

---

## Descripción general

El sistema calcula, para cada enfrentamiento, la distribución de probabilidad de sus
posibles desenlaces (ganador, totales, hándicaps, marcadores exactos, etc.) mediante
modelos matemáticos específicos de cada deporte. Las probabilidades se derivan
íntegramente del modelo —no de las casas de apuestas—, lo que permite contrastar la
estimación propia con la del mercado como ejercicio analítico.

La aplicación se compone de dos vistas:

- **Panel de resultados**: métricas agregadas, histórico de selecciones y evolución
  de un capital simulado.
- **Analizador de partido**: se eligen deporte y dos equipos o jugadores y se obtiene
  el desglose completo de probabilidades por mercado, con visualizaciones y detalle
  por equipo.

---

## Características principales

- **Cuatro deportes** con modelos independientes y calibrados por separado.
- **Probabilidades por mercado** derivadas de una única distribución coherente por
  deporte (sin inconsistencias internas).
- **Calibración isotónica** con *gate* de validación fuera de muestra: un calibrador
  solo se despliega si mejora el *log-loss* out-of-sample; en caso contrario se
  descarta automáticamente.
- **Capa de contexto por IA (opcional)**: consulta información actual (bajas,
  lesiones, descansos) mediante un modelo de lenguaje con búsqueda web y ajusta de
  forma conservadora la fuerza de los equipos. El número lo sigue calculando el
  modelo matemático, no la IA.
- **Actualización automática de datos** mediante tareas programadas (GitHub Actions).
- **Monitor de deriva**: mide periódicamente la salud del modelo sobre partidos
  recientes y avisa en el panel si se degrada.
- **Interfaz responsive** con tema oscuro, iconografía SVG y tipografía técnica.
- **Acceso protegido** por contraseña con comparación en tiempo constante y
  mitigación de fuerza bruta.

---

## Metodología y modelos

| Deporte | Modelo base | Salidas principales |
|---|---|---|
| **Fútbol** | GLM Poisson + corrección **Dixon-Coles** sobre una matriz de marcadores; Elo por equipo | 1X2, doble oportunidad, Over/Under, BTTS, hándicaps, marcadores exactos |
| **Baloncesto (NBA)** | Elo + puntuación esperada, **simulación Monte Carlo** (Normal) | Ganador, hándicap (spread), total de puntos |
| **Béisbol (MLB)** | Elo logístico + expectativa **Pythagorean** | Ganador (moneyline), run line, totales |
| **Tenis** | **Elo por superficie** + modelo **Barnett-Clarke** (cadena de Markov de saque/resto) | Probabilidad de ganar, sets, juegos |

Todos los mercados de un deporte se derivan de una misma distribución, garantizando
coherencia interna. Las probabilidades del ganador se calibran a posteriori con
regresión isotónica cuando la validación fuera de muestra demuestra mejora.

---

## Arquitectura

El proyecto separa deliberadamente el **entrenamiento** (pesado, offline) del
**servicio** (ligero, en la nube):

- **Runtime de la aplicación**: solo dependencias ligeras (Streamlit, pandas, numpy,
  scipy, Plotly, driver de PostgreSQL). Los modelos se cargan ya entrenados y la
  inferencia usa numpy puro, sin `scikit-learn`, `statsmodels` ni `xgboost` en
  producción.
- **Pipeline de datos**: descarga, ingesta, cálculo de Elo, generación de *features*
  y de selecciones. Se ejecuta de forma programada contra la base de datos, nunca en
  el servidor web.
- **Persistencia**: base de datos PostgreSQL (la aplicación siempre lee el último
  estado; el refresco no toca el repositorio).
- **Automatización**: integración continua (tests en cada cambio), refresco diario de
  datos y monitor de salud del modelo.

---

## Stack tecnológico

- **Lenguaje**: Python 3.12
- **Interfaz**: Streamlit
- **Visualización**: Plotly
- **Base de datos**: PostgreSQL
- **Modelado (desarrollo)**: statsmodels, scikit-learn, XGBoost, NumPy, SciPy, pandas
- **IA (opcional)**: modelo de lenguaje con *grounding* de búsqueda web
- **CI/CD y automatización**: GitHub Actions

---

## Estructura del proyecto

```
app/        Aplicación Streamlit (panel, analizador, tema, autenticación, gráficos)
core/       Lógica transversal: base de datos, calibración, evaluación, IA, apuestas
sports/     Modelos por deporte (Elo, Poisson/Dixon-Coles, Barnett-Clarke, ...)
scripts/    Pipeline de datos, entrenamiento, evaluadores OOS y mantenimiento
tests/      Suite de tests automatizados
data/       Artefactos mínimos de despliegue (modelo entrenado y selecciones)
.github/    Flujos de trabajo (CI, refresco de datos)
```

---

## Puesta en marcha (local)

Requisitos: Python 3.12 y una base de datos PostgreSQL accesible.

```bash
# 1. Entorno virtual
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # macOS / Linux

# 2. Dependencias de la aplicación
pip install -r requirements.txt

# 3. Variables de entorno (no se versionan)
#    Crear un archivo .env con la cadena de conexión y, opcionalmente, la clave de acceso.

# 4. Ejecutar la aplicación
streamlit run app/streamlit_app.py
```

Para **entrenar modelos** o ejecutar la **suite completa de tests** se requieren,
además, las librerías científicas de desarrollo:

```bash
pip install scikit-learn statsmodels xgboost
pytest -q
```

---

## Despliegue

La aplicación está pensada para desplegarse en **Streamlit Community Cloud** con una
base de datos **PostgreSQL gestionada** y **GitHub Actions** para el refresco
programado. Las credenciales se configuran exclusivamente como *secrets* de la
plataforma (nunca en el repositorio).

El procedimiento detallado de operación y mantenimiento se documenta en
[`OPERACIONES.md`](OPERACIONES.md).

---

## Fuentes de datos

Los datos proceden de fuentes públicas de estadística deportiva (resultados
históricos por deporte). El proyecto no redistribuye conjuntos de datos de terceros;
los scripts de ingesta los descargan bajo demanda.

---

## Validación y limitaciones

El proyecto se ha validado con rigor **fuera de muestra** (out-of-sample), midiendo
*log-loss* y *Brier* sobre temporadas que los modelos no vieron en entrenamiento. Las
conclusiones, documentadas y reproducibles mediante los evaluadores incluidos en
`scripts/`, son:

- Los modelos alcanzan un rendimiento **comparable al de la línea de cierre del
  mercado**, que constituye el mejor estimador público de la probabilidad real.
- No se ha encontrado evidencia de que **superen** de forma sistemática a dicha línea
  con datos públicos: el margen de mejora restante depende de **información adicional**
  (p. ej. *expected goals* o alineaciones), no de más ajuste matemático.
- La calibración a posteriori aporta mejoras marginales y solo se aplica donde la
  validación lo respalda.

Este posicionamiento honesto es parte del diseño: el sistema es una herramienta de
**análisis y estimación**, no un método de rentabilidad garantizada.

---

## Seguridad y privacidad

- Acceso protegido por contraseña (comparación en tiempo constante, caducidad de
  sesión y retardo progresivo ante intentos fallidos).
- Sin secretos en el código ni en el historial: credenciales, claves y *tokens*
  residen únicamente en la configuración cifrada de la plataforma de despliegue.
- Entrada de usuario acotada a selectores y valores numéricos; consultas SQL
  parametrizadas; contenido HTML dinámico escapado.
- El repositorio público no contiene datos personales.

---

## Licencia

Pendiente de definir por el autor. Hasta entonces, todos los derechos reservados.
