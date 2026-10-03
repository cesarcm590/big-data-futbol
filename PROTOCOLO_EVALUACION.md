# Protocolo de evaluación del modelo de pronóstico

Documento metodológico. Define **cómo se va a juzgar** el modelo de resultados del proyecto
(Poisson + Dixon-Coles) *antes* de volver a mirar los números, y qué se puede concluir de cada
medida. Sigue el esquema del protocolo de tesis: planteamiento, etapas, modelos con sus supuestos
y limitaciones, y catálogo de variables.

El principio que lo gobierna es el mismo del proyecto: **una cifra no se publica hasta saber si mide
algo.** Un modelo de pronóstico es especialmente fácil de evaluar mal, porque casi cualquier medida
aislada admite una lectura favorable.

---

## 1. Propuesta de análisis para la evaluación del modelo

### 1.1 Planteamiento general del problema

Evaluar un pronóstico probabilístico de resultados de fútbol involucra varias dimensiones
estadísticas que no se reducen una a otra:

- **Calidad de la probabilidad, no del acierto.** Un modelo que acierta más puede estar peor
  calibrado. El *accuracy* del pick descarta la información que el modelo sí entrega: cuánta
  confianza tiene (reglas de puntuación propias: RPS, logarítmica, Brier).
- **Calibración frente a discriminación.** Son independientes: un modelo puede dar probabilidades
  perfectamente calibradas y no distinguir un partido de otro (predice la tasa base siempre), o
  discriminar bien y estar sistemáticamente sobreconfiado (descomposición de Murphy).
- **Orden de las categorías.** Local, Empate y Visitante no son tres clases intercambiables: están
  ordenadas. Equivocarse dando Visitante cuando fue Local es peor que dar Empate (RPS).
- **Dependencia entre observaciones.** Los partidos de una misma jornada comparten clima, calendario
  y rachas; los de un mismo equipo comparten plantilla. Tratarlos como independientes subestima el
  error estándar (bootstrap por bloques, errores HAC).
- **Existencia de un referente informado.** A diferencia de casi cualquier otro problema de
  predicción, aquí hay un competidor público que agrega información que nosotros no tenemos
  —lesiones, alineaciones, dinero informado—: el mercado de apuestas. Esto convierte la pregunta
  «¿es bueno?» en una pregunta respondible: «¿cuánto le falta para el mercado, y aporta algo que el
  mercado no tenga?».
- **Multiplicidad y selección.** Cinco ligas, varios tipos de apuesta, varios subgrupos y varias
  métricas generan decenas de comparaciones. Sin control, aparecerán «hallazgos» por azar.
- **Hallazgos encontrados mirando los mismos datos.** El proyecto ya tiene uno —el exceso de empates
  en partidos parejos— descubierto explorando la muestra completa. Un hallazgo así **no puede
  confirmarse con los datos que lo produjeron**, por bien que se mida.

Estas características implican que el modelo no puede evaluarse con una sola métrica ni con una sola
partición de los datos, por lo que se propone un esquema integrado en cinco etapas.

### 1.2 Etapas del análisis

#### 1.2.1 Etapa 1: Congelamiento del pronóstico y trazabilidad

Toda evaluación parte de pronósticos emitidos **antes** del partido y guardados con sello de tiempo
(`registro/predicciones_congeladas*.csv`). El ajuste histórico usa validación *walk-forward* por
temporada: cada temporada de prueba se predice con un modelo estimado únicamente con temporadas
anteriores, y las variables pre-partido de cada encuentro se construyen solo con partidos previos.

**Justificación.** Separa dos cosas que suelen confundirse: la *reconstrucción* del pasado (ajustar y
predecir lo ya visto) y el *pronóstico*. Solo lo segundo es evaluable. El congelamiento además hace
la evaluación irrepetible en el sentido bueno: si el viernes no se congela, esa jornada se pierde
para siempre del seguimiento prospectivo, y eso es preferible a rellenarla después.

#### 1.2.2 Etapa 2: Calibración

Se evalúa si las probabilidades significan lo que dicen: de los partidos a los que el modelo asignó
30 % de empate, ¿empató cerca del 30 %? Se usan curvas de fiabilidad por clase, calibración en el
agregado (*calibration-in-the-large*), error de calibración esperado (ECE) y una recalibración
ajustada fuera de muestra para cuantificar cuánta mejora queda sobre la mesa.

**Justificación.** Es la propiedad que vuelve utilizable un pronóstico para decidir. Un modelo mal
calibrado puede tener buen poder de discriminación y aun así ser inservible para apostar o para
comunicar riesgo.

#### 1.2.3 Etapa 3: Puntuación propia y descomposición

Se calculan RPS (métrica principal), pérdida logarítmica y Brier por partido, y se descompone el
Brier en fiabilidad, resolución e incertidumbre.

**Justificación.** Las reglas propias (*proper scoring rules*) no se pueden mejorar mintiendo sobre
la propia confianza. La descomposición responde *por qué* un modelo puntúa como puntúa: si pierde por
estar mal calibrado (corregible con recalibración) o por no distinguir partidos (no corregible sin
mejor información).

#### 1.2.4 Etapa 4: Comparación contra referentes

Tres referentes, en orden de exigencia: frecuencias históricas de Local/Empate/Visitante (piso),
mercado de apuestas con el margen removido (techo informativo) y, opcionalmente, un Elo simple
(referente barato y sin variables). La comparación es **pareada partido a partido** y se acompaña de
su intervalo por bootstrap por bloques.

**Justificación.** Una métrica sola no dice nada: un log-loss de 0.98 no es bueno ni malo hasta
compararlo. Y la comparación debe ser pareada porque modelo y mercado ven exactamente los mismos
partidos; la correlación entre ambos reduce la varianza de la diferencia en más de un factor dos
(§1.6.4), que es lo que hace la prueba viable con el tamaño de muestra disponible.

#### 1.2.5 Etapa 5: Valor de decisión

Traducción a la única pregunta que no es estadística: ¿sirve para algo? Valor esperado por apuesta a
precios reales de mercado, simulación de criterios de apuesta (plano y fraccional de Kelly) y
contraste contra el registro personal de jugadas (`registro_personal/`, privado y nunca publicado).

**Justificación.** Un modelo puede ser estadísticamente peor que el mercado y aun así tener valor en
un subconjunto, o ser mejor en métricas y no tenerlo porque el margen de la casa se come la ventaja.
Son preguntas distintas y se responden por separado.

### 1.3 Reglas de puntuación

#### 1.3.1 Ranked Probability Score (métrica principal)

$$\text{RPS} = \frac{1}{r-1}\sum_{i=1}^{r-1}\left(\sum_{j\le i} p_j - \sum_{j\le i} o_j\right)^2,
\qquad r = 3$$

con las categorías en orden Local $\prec$ Empate $\prec$ Visitante.

**Parámetros.** $p_j$: probabilidad pronosticada de la categoría $j$. $o_j$: indicador del resultado
observado. $r$: número de categorías ordenadas.

**Supuestos.** Que el orden Local–Empate–Visitante es significativo, es decir, que el empate está
«entre» las dos victorias.

**Utilidad.** Es la métrica estándar en pronóstico de fútbol justamente porque penaliza más los
errores que cruzan el orden. Regla propia.

**Limitaciones.** Menos sensible que la logarítmica a probabilidades cercanas a cero; no descompone
de forma natural en calibración y resolución.

#### 1.3.2 Pérdida logarítmica (ignorancia)

$$\text{LL} = -\frac{1}{n}\sum_{i=1}^{n}\log p_{i,y_i}$$

**Parámetros.** $p_{i,y_i}$: probabilidad que el modelo dio al resultado que ocurrió.

**Supuestos.** Ninguno más allá de $p_{i,y_i} > 0$.

**Utilidad.** Regla propia, interpretable en nats y directamente ligada a la teoría de la información
y al crecimiento logarítmico del capital (Kelly). Es la métrica que ya reporta el panel.

**Limitaciones.** No acotada: un solo partido con probabilidad asignada casi nula domina el promedio.
Exige revisar la cola antes de interpretar el promedio.

#### 1.3.3 Brier multiclase y descomposición de Murphy

$$\text{BS} = \frac{1}{n}\sum_{i=1}^{n}\sum_{j=1}^{r}(p_{ij}-o_{ij})^2
\qquad
\text{BS} = \underbrace{\text{fiabilidad}}_{\text{calibración}} - \underbrace{\text{resolución}}_{\text{discriminación}} + \underbrace{\text{incertidumbre}}_{\text{del fenómeno}}$$

**Parámetros.** Partición en $K$ cubetas de probabilidad para calcular los tres términos.

**Supuestos.** La descomposición es exacta solo con cubetas; su valor depende de $K$, por lo que se
reporta la sensibilidad a esa elección.

**Utilidad.** Separa «estar mal calibrado» de «no distinguir partidos», que exigen remedios
distintos. El término de incertidumbre fija el techo: cuánto de la pérdida es irreducible.

**Limitaciones.** Acotada y menos discriminante que la logarítmica entre modelos parecidos.

### 1.4 Modelos de calibración

#### 1.4.1 Curva de fiabilidad y ECE

$$\text{ECE} = \sum_{k=1}^{K}\frac{n_k}{n}\left|\bar{o}_k - \bar{p}_k\right|$$

**Utilidad.** Cuantifica el desajuste medio entre probabilidad declarada y frecuencia observada.

**Limitaciones.** Depende de $K$ y es insensible a desajustes que se cancelan entre cubetas; se
acompaña siempre de la curva, no se reporta solo el número.

#### 1.4.2 Recalibración

Regresión logística multinomial sobre los log-odds del modelo (Platt multiclase), o escalado de
temperatura con un único parámetro, **ajustada fuera de muestra**.

**Utilidad.** Convierte una pregunta vaga («¿está bien calibrado?») en una medible: cuánto mejora el
RPS si solo se corrige la calibración. Esa mejora es la parte del error que **no** requiere más
información, solo mejor expresión de la que ya hay.

**Limitaciones.** Si se ajusta con los mismos datos de evaluación, la mejora es ilusoria. Debe
estimarse en una partición distinta y aplicarse ciega.

### 1.5 Referentes de comparación

#### 1.5.1 Frecuencias históricas (piso)

Probabilidad constante igual a las frecuencias de Local/Empate/Visitante del conjunto de
entrenamiento. Es el mínimo que cualquier modelo debe superar: no mirar el partido.

#### 1.5.2 Mercado (techo informativo)

$$p_i = \frac{1/c_i}{\sum_{j} 1/c_j}$$

**Parámetros.** $c_i$: cuota decimal de la categoría $i$ (Bet365 previa y Pinnacle de cierre).

**Supuestos.** Que el margen de la casa se reparte **proporcionalmente** entre las tres categorías.
Es una simplificación conocida: la literatura documenta que el margen se carga más sobre los
*longshots*, y que los métodos de Shin o de *odds-ratio* recuperan probabilidades mejor calibradas.

**Limitaciones y sensibilidad obligatoria.** Como el supuesto de margen afecta directamente al
referente contra el que nos medimos, la comparación se repite con los tres métodos de normalización.
Si la conclusión cambia según el método, la conclusión es sobre el método, no sobre el modelo.

#### 1.5.3 Elo (referente barato)

Referente opcional sin variables de juego, solo resultados. Sirve para responder cuánto aportan las
ocho variables pre-partido por encima de «quién ha venido ganando».

### 1.6 Inferencia

#### 1.6.1 Skill score

$$SS = 1 - \frac{S_{\text{modelo}}}{S_{\text{referente}}}$$

Positivo si el modelo mejora al referente. Se reporta con intervalo, nunca como punto.

#### 1.6.2 Prueba pareada y bootstrap por bloques

Para cada partido se calcula el diferencial de pérdida $d_i = S_i^{\text{modelo}} - S_i^{\text{ref}}$
y se contrasta $H_0: \mathbb{E}[d]=0$ (Diebold–Mariano). El intervalo se obtiene por **bootstrap por
bloques de jornada**, no por partido.

**Justificación del bloque.** Los partidos de una misma jornada comparten factores; remuestrear
partidos sueltos trataría como independiente lo que no lo es y daría intervalos demasiado estrechos.

#### 1.6.3 Multiplicidad

Toda comparación secundaria (por liga, por subgrupo, por tipo de apuesta) se declara de antemano y se
ajusta por Benjamini–Hochberg al 5 %. Las no declaradas se reportan como exploratorias y **no** se
interpretan como evidencia.

#### 1.6.4 Potencia y tamaño de muestra

Con la muestra actual, el diferencial pareado de log-loss contra el mercado tiene desviación estándar
$\approx 0.205$ (muy inferior a la de cada serie por separado, $\approx 0.55$, porque modelo y
mercado aciertan y fallan en los mismos partidos). Para 80 % de potencia y $\alpha = 0.05$:

| Diferencia a detectar | Partidos necesarios |
|---|---|
| 0.030 nats | 367 |
| 0.020 nats | 825 |
| 0.010 nats | 3,299 |
| 0.005 nats | 13,194 |

Las cinco ligas producen **~32 partidos por semana** en temporada. Reunir 450 partidos nuevos lleva
unas **14 semanas**; reunir 3,300, unos **dos años**. Esta tabla es lo que decide qué preguntas se
pueden responder y cuáles hay que declarar fuera de alcance.

### 1.7 Hipótesis específica: el exceso de empates en partidos parejos

El proyecto observó que en partidos con probabilidades parejas (rango máximo–mínimo $\le 0.125$) la
frecuencia de empate sube. **Ese hallazgo se encontró explorando la misma muestra con la que se
mediría**, por lo que aquí se trata como hipótesis a confirmar, no como resultado.

**Tamaño del efecto en la muestra que lo generó.** Sobre 13,283 partidos de las cinco ligas, los
parejos son el **15.2 %**, y en ellos el empate ocurre el **28.5 %** de las veces frente al **24.5 %**
en el resto: **+3.9 puntos porcentuales**, con intervalo por bloques de jornada de **[+1.8, +6.1]**.
Es un efecto real en esta muestra, pero **moderado**, y el proyecto lo ha venido describiendo como que
«sube de forma clara», lo que sobrestima lo que estos números soportan. Esa redacción debe corregirse
en el sitio y en el plan.

**Pre-registro.** Se fija de antemano: (a) el umbral de 0.125, sin reajustarlo; (b) la métrica
primaria —RPS del modelo contra el mercado, restringido a ese subgrupo—; (c) el tamaño mínimo
(§1.6.4); (d) que una sola prueba decide, sin variantes de umbral.

**Muestra confirmatoria, y por qué la vía prospectiva no es viable.** Solo las predicciones congeladas
prospectivamente (49 partidos a la fecha de este documento) son limpias respecto a este hallazgo.
Detectar una diferencia de 3.9 puntos con 80 % de potencia exige unos **1,985 partidos parejos**. Las
cinco ligas producen ~32 partidos por semana, de los cuales ~4.9 son parejos: eso son **cerca de ocho
años** de seguimiento. Si se exigiera detectar 3 puntos, trece años.

Esta cuenta es el resultado más útil del protocolo: **la hipótesis estrella del proyecto no se puede
confirmar esperando.** Las salidas honestas son tres, en este orden:

1. **Replicar en ligas no usadas para explorar el hallazgo** (Ligue 1, Eredivisie), construyendo para
   ellas el mismo flujo. No es prospectivo, pero sí independiente del proceso que generó la
   hipótesis, y da ~2,000 partidos parejos adicionales de inmediato.
2. **Ampliar el universo** a más ligas con cuotas en football-data, con el mismo criterio.
3. **Si ninguna de las dos es posible, declararlo permanentemente exploratorio** y decirlo así donde
   se publique, en vez de presentarlo como resultado. Es preferible una afirmación con la etiqueta
   correcta que una conclusión que la muestra no sostiene.

### 1.7.1 Pre-registro del test confirmatorio en Ligue 1 y Eredivisie

Este apartado se escribe y se sube **antes de descargar los datos y antes de ver ningún resultado**. El historial
del repositorio es la prueba: cualquier cambio posterior a estas reglas queda fechado después del resultado y debe
leerse como lo que sería, un ajuste a posteriori.

**Hipótesis.** En los partidos donde el modelo da probabilidades parejas, el empate ocurre con mayor frecuencia que
en el resto.

**Población.** Ligue 1 y Eredivisie, todas las temporadas disponibles en football-data (2015-16 en adelante),
evaluadas fuera de muestra con el mismo esquema *walk-forward* por temporada que las otras cuatro ligas. Ninguna de
las dos se usó para encontrar el hallazgo.

**Definición de «parejo», fijada de antemano.** Rango máximo − mínimo de las tres probabilidades del modelo
$\le 0.125$. **No se prueba ningún otro umbral.**

**Especificación del modelo, fijada de antemano y sin ajustar en estas ligas.** Mismas 8 variables pre-partido
(más tiros a puerta si la liga los publica, igual que en las otras), mismos mínimos (10 partidos previos por lado,
300 para entrenar) y **ventana expandible**, que es la que usan las dos ligas de 18 equipos ya montadas
(Bundesliga, y Serie A por el mismo criterio). Ligue 1 y Eredivisie tienen 18 equipos. **No se probarán ventanas
alternativas para elegir la mejor**: hacerlo convertiría el test confirmatorio en otra exploración.

**Medida primaria.** Diferencia de frecuencia de empate entre partidos parejos y el resto, en puntos porcentuales,
agrupando las dos ligas.

**Inferencia.** Intervalo de confianza al 95 % por bootstrap de **bloques de jornada** (2,000 réplicas).

**Regla de decisión, fijada de antemano.**

- Si el intervalo **excluye el cero y el signo es positivo** → la hipótesis queda **confirmada** en muestra
  independiente, y se publica como resultado, con su tamaño de efecto.
- Si el intervalo **incluye el cero** → **no confirmada**. Se publica así, y la afirmación se retira del sitio en
  vez de buscar un subgrupo donde sí salga.
- Si el intervalo excluye el cero **con signo negativo** → el hallazgo original era un artefacto de la muestra que
  lo produjo, y se dice.

**Medidas secundarias** (declaradas, se reportan con el ajuste de §1.6.3 y no deciden nada por sí solas): la misma
diferencia por liga separada, y el RPS del modelo contra el mercado restringido a los partidos parejos.

### 1.8 Estimación del valor de decisión

$$\text{VE}_i = p_i^{\text{modelo}} \cdot c_i - 1,
\qquad
f^{*} = \frac{p\,(c-1) - (1-p)}{c-1}$$

**Parámetros.** $c_i$: cuota ofrecida (precio real, con margen). $f^{*}$: fracción de Kelly.

**Supuestos.** Que la cuota estaba disponible al momento de congelar el pronóstico, que es aceptable
el tamaño de apuesta sin mover el precio, y que las probabilidades del modelo son las verdaderas
—supuesto fuerte y justamente el que se está evaluando—.

**Limitaciones.** El ROI es **muy ruidoso**: con unos cientos de apuestas, su intervalo abarca
cómodamente tanto ganar como perder. Se reporta siempre con intervalo por bootstrap y nunca como cifra
suelta. El registro personal sirve para estudiar hábitos propios (¿va peor cuando se aparta del
modelo?), no para concluir que una estrategia funciona.

### 1.9 Justificación integral

El uso combinado permite:

- separar la calidad de la probabilidad de la del acierto,
- distinguir fallo de calibración de fallo de información,
- medir contra un piso y contra un techo informativo, no en abstracto,
- cuantificar qué preguntas admite el tamaño de muestra y cuáles no,
- y evitar que un hallazgo exploratorio se publique como confirmado.

### 1.10 Conclusión metodológica y estado actual

Lo que la evidencia **ya establece** con la muestra histórica fuera de muestra:

| Liga | n | Acierto modelo | Acierto mercado | LL modelo | LL mercado | LL base | Δ LL (modelo−mercado) | IC 95 % por bloques |
|---|---|---|---|---|---|---|---|---|
| Liga MX | 1,427 | 0.486 | — | 1.0298 | — | 1.0646 | — | — |
| Bundesliga | 2,543 | 0.498 | 0.524 | 1.0073 | 0.9790 | 1.0747 | +0.0284 | [+0.0197, +0.0370] |
| La Liga | 3,141 | 0.516 | 0.534 | 0.9987 | 0.9730 | 1.0694 | +0.0256 | [+0.0182, +0.0334] |
| Premier | 3,114 | 0.535 | 0.550 | 0.9807 | 0.9574 | 1.0678 | +0.0233 | [+0.0156, +0.0305] |
| Serie A | 3,058 | 0.529 | 0.551 | 0.9813 | 0.9556 | 1.0820 | +0.0257 | [+0.0192, +0.0321] |

El intervalo es el de §1.6.2: remuestreando **jornadas completas**, no partidos. Se reporta ése y no
el estadístico $t$ pareado —que da valores de 6 a 7.5— porque el $t$ supone independencia entre
partidos, que es falsa. En este caso ambos coinciden en la conclusión; eso no es garantía de que
coincidan en la siguiente comparación, y por eso la regla es usar bloques siempre.

El modelo **supera claramente al piso** y **pierde contra el mercado en las cuatro ligas**, con
diferencias de 0.023 a 0.028 nats y estadísticos pareados de 6 a 7.5: esa desventaja **no es ruido**,
y la muestra disponible está holgadamente sobrada para detectarla (se necesitaban ~400–650 partidos,
hay 2,500–3,100). La pregunta abierta no es si el modelo pierde contra el mercado —pierde—, sino si
aporta algo en algún subgrupo donde el mercado sea débil, y eso exige la muestra prospectiva de §1.7.

**Limitación de fondo que este protocolo no resuelve.** El esquema *walk-forward* evita la fuga
temporal en los coeficientes, pero **la elección de las ocho variables, de la ventana y de la propia
familia del modelo se hizo mirando el conjunto completo**. Eso es selección sobre toda la muestra, un
nivel por encima del que controla la validación. La única corrección real es evaluar sobre datos
posteriores a esa elección, que es exactamente lo que acumula el seguimiento congelado.

---

## 2. Variables disponibles: definición y descripción

### 2.1 Estructura general de los datos

El análisis se realiza a tres niveles:

- **Nivel partido:** cada observación es un encuentro con su pronóstico y su resultado. Es el nivel de
  las reglas de puntuación.
- **Nivel jornada:** unidad de remuestreo para el bootstrap por bloques y unidad de congelamiento del
  pronóstico.
- **Nivel liga-temporada:** unidad de reajuste del modelo en el esquema *walk-forward*.

### 2.2 Variables de respuesta

#### 2.2.1 Resultado del partido ($Y_i$)

- **Tipo:** categórica ordenada (3 niveles).
- **Nivel:** partido.
- **Definición:** Local $\prec$ Empate $\prec$ Visitante al tiempo reglamentario.
- **Uso:** variable dependiente de todas las reglas de puntuación.

#### 2.2.2 Goles de cada equipo ($g^L_i, g^V_i$)

- **Tipo:** discreta (conteo).
- **Nivel:** partido.
- **Distribución supuesta:** Poisson con dependencia Dixon–Coles en marcadores bajos.
- **Uso:** respuesta del modelo generativo; permite derivar probabilidades de over/under y de
  marcador exacto, y por tanto evaluar el modelo en mercados distintos del 1X2.

#### 2.2.3 Empate (indicador)

- **Tipo:** binaria.
- **Uso:** respuesta de la hipótesis específica de §1.7 y del AUC de $P(\text{empate})$.

### 2.3 Unidad de observación y pesos

No hay un *offset* poblacional como en un modelo de conteos: cada partido pesa igual en las métricas
de puntuación. Donde sí aparece un peso es en la evaluación económica, donde cada apuesta pesa por su
monto. **Se reportan por separado** el resultado no ponderado (calidad del pronóstico) y el ponderado
por monto (resultado económico), porque mezclarlos permite que una sola apuesta grande domine la
conclusión.

### 2.4 Variables de pronóstico

Tres fuentes de probabilidad sobre el mismo evento:

- **Modelo del proyecto**
  - Origen: `scripts/modelo_goles.py` (Poisson + Dixon–Coles).
  - Variables de entrada: 8 pre-partido (goles a favor y en contra, corners y tarjetas a favor, del
    local como local y del visitante como visitante), más tiros a puerta en las ligas que los
    publican.
  - Parámetro de dependencia $\rho$ estimado por máxima verosimilitud: de $-0.013$ (La Liga) a
    $-0.128$ (Bundesliga).
  - Disponibilidad: Liga MX desde 2022-23; ligas europeas desde 2017-18.
  - Resolución temporal: una probabilidad por partido, congelada antes del inicio.
- **Mercado**
  - Origen: football-data.co.uk, cuotas 1X2 de Bet365 (previa) y Pinnacle (cierre).
  - Transformación: normalización proporcional (y Shin / odds-ratio como sensibilidad, §1.5.2).
  - Disponibilidad: ligas europeas desde 2015-16; **no existe para Liga MX**, que por eso solo puede
    compararse contra el piso.
- **Piso de frecuencias**
  - Origen: frecuencias de Local/Empate/Visitante del conjunto de entrenamiento de cada corte.
  - Disponibilidad: siempre.

### 2.5 Estructura temporal

- **Esquema de ajuste:** *walk-forward* por temporada; cada temporada de prueba se predice con un
  modelo estimado solo con temporadas anteriores.
- **Construcción de variables:** para cada partido, el perfil de cada equipo usa exclusivamente sus
  partidos anteriores en ese mismo campo (local como local, visitante como visitante).
- **Ventanas evaluadas:** expandible (todo el pasado), últimos 38 y últimos 19 partidos en ese lado.
- **Mínimos:** 10 partidos previos para tener perfil; 300 partidos con perfil para poder entrenar una
  temporada. Los equipos recién ascendidos quedan fuera hasta acumular historial, lo que introduce
  una **exclusión no aleatoria** que debe reportarse (§2.8).

### 2.6 Covariables de estratificación

Declaradas de antemano, con su hipótesis asociada:

| Covariable | Nivel | Hipótesis |
|---|---|---|
| Liga | partido | El modelo rinde distinto según el estilo y la competitividad de la liga |
| Temporada | partido | Deterioro o mejora con el tiempo (cambio de régimen) |
| Partido parejo (rango $\le 0.125$) | partido | Donde el proyecto cree aportar algo (§1.7) |
| Favorito claro | partido | Donde el mercado debería ser más difícil de batir |
| Jornada inicial de temporada | partido | Perfiles con poca historia: peor rendimiento esperado |

### 2.7 Variables derivadas

#### 2.7.1 Diferencial de pérdida ($d_i$)

$$d_i = S_i^{\text{modelo}} - S_i^{\text{referente}}$$

- **Tipo:** continua. **Interpretación:** $d_i > 0$, el referente fue mejor en ese partido.
- **Uso:** base de toda la inferencia pareada (§1.6.2).

#### 2.7.2 Ventaja sobre el precio (*edge*)

$$e_i = p_i^{\text{modelo}} - \frac{1}{c_i}$$

- **Interpretación:** diferencia entre lo que creemos y lo que la casa cobra, **incluido su margen**;
  por eso un *edge* ligeramente positivo no es ventaja real.

#### 2.7.3 Skill score y componentes de la descomposición

Definidos en §1.6.1 y §1.3.3.

### 2.8 Consideraciones sobre las variables

- **Dependencia entre partidos.** Jornada y equipo inducen correlación; toda inferencia usa bloques.
- **Exclusión no aleatoria.** Los equipos sin historial suficiente se excluyen, y son
  sistemáticamente los recién ascendidos: los pronósticos evaluados son, por construcción, sobre
  partidos *más predecibles* que el promedio. Debe reportarse la proporción excluida por temporada.
- **Margen de la casa.** El referente de mercado depende del método de normalización; es un supuesto,
  no un dato (§1.5.2).
- **Simultaneidad del precio.** Nuestra probabilidad se congela el viernes; la cuota registrada es de
  otro instante. No es una carrera perfectamente simultánea, y eso favorece al mercado en una
  magnitud no medida con los datos actuales.
- **Cambios de régimen.** Reglas (VAR), calendario y pandemia 2019-20 alteran tasas base; las
  comparaciones entre temporadas no son automáticamente comparables.
- **Tarjetas y corners.** Entran como variables del modelo y como mercados evaluables, pero su
  conteo puede diferir del de las casas (una roja puede valer dos); cualquier evaluación en esos
  mercados lleva la advertencia.
- **Liga MX sin mercado.** Solo admite comparación contra el piso; sus conclusiones no son
  trasladables a las europeas ni al revés.

### 2.9 Resumen

El conjunto de variables integra:

- respuesta (resultado, goles, empate),
- pronósticos de tres fuentes (modelo, mercado, piso),
- estructura temporal que garantiza ausencia de fuga,
- covariables de estratificación declaradas,
- y variables derivadas (diferencial de pérdida, *edge*, skill score).

Este conjunto permite responder, con el tamaño de muestra disponible, si el modelo supera al piso
(sí), si alcanza al mercado (no, y la diferencia no es ruido) y —solo con muestra prospectiva futura—
si aporta algo en el subgrupo donde se cree que aporta.
