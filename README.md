# Calendario Hoy: calendarios laborales y escolares de España

Sitio estático en GitHub Pages construido por GitHub Actions. Los datos salen de boletines oficiales, las páginas se generan con plantillas en Python y el robot publica hasta 24 URLs nuevas al día. No hay credenciales ni servidores: todo corre en la nube con el permiso del propio repositorio.

Sitio: https://davarooo.github.io/calendarios/

## Estado (19 nov 2026)

| Paso | Estado |
|---|---|
| Fuente oficial 2027 | Ubicada y transcrita: **BOE-A-2026-21254** (BOE n.º 254, 13-10-2026). 35 fiestas, 19 territorios. Coherencia comprobada: 12 por comunidad, Canarias 11 + 1 insular. |
| Prueba de fuente desde GitHub | Lista (`prueba-fuente.yml`). Vuelve a leer el XML del BOE y falla si no coincide con lo publicado. Falta ejecutarla en tu repo. |
| Validación SERP | 7 búsquedas en tu Chrome (escritorio, gl=es). Resultados abajo. |
| Diseño | Concepto azulejo: festivos nacionales en cobalto, autonómicos en ocre, fiestas locales en verde. Calendario anual interactivo (consulta por defecto, planificador de vacaciones aparte), columna lateral con descarga y calculadora, mosaico de comunidades. |
| Piloto | 20 URLs publicadas en GitHub Pages (España como portada + 19 territorios) y 5 páginas de confianza. 20/20 responden 200, 0 enlaces rotos. PageSpeed móvil (Madrid): rendimiento 100, LCP 1,4 s, CLS 0. |

## Validación SERP (19-11-2026, Chrome de escritorio, no incógnito móvil)

| Búsqueda | Top 3 | Imágenes arriba | Resumen IA |
|---|---|---|---|
| calendario laboral 2027 madrid | madrid.es, calendarios.ideal.es, comunidad.madrid | Sí | No |
| calendario laboral 2027 alcorcon | calendarios.ideal.es, calendarioslaborales.com, micalendariolaboral.com | Sí | No |
| festivos 2027 getafe | calendarios.ideal.es, viajessantamona.com, facebook.com | Sí | No |
| calendario laboral 2027 andalucia | calendarios.ideal.es, juntadeandalucia.es, csif.es | Sí | No |
| calendario escolar 2026-2027 castilla y leon | educa.jcyl.es, stecyl.net, facebook.com | Sí | No |
| puentes 2027 madrid | madrid.es, calendarios.ideal.es, comunidad.madrid | Sí | No |
| calendario 2027 mexico con dias festivos para imprimir | Sin lectura (la página no cargó a tiempo) | | |

Lectura: el rival programático es **calendarios.ideal.es** (sale en las 6). En municipios aparecen Facebook y sitios pequeños: hueco real en la cola larga. Falta medir volúmenes (Ahrefs gratis) y Trends a 5 años.

## Estructura

```
data/es/festivos-2027.json   datos oficiales (BOE) + notas Canarias y Arán
data/es/regiones.json        nombre, slug, vecinas y colores de cada comunidad
plantillas/entrada.html      plantilla de la entrada (placeholders {var})
scripts/boe_festivos.py      prueba de fuente: lee el XML del BOE y compara
scripts/generar.py           genera HTML, PNG, PDF, fichas de datos y queue.csv
scripts/chequeos.py          criterios de aceptación automatizables
scripts/sitio.py             arma docs/: páginas completas, sitemap, robots y 404
scripts/verificar_publicado.py  enlaces 200 + PageSpeed móvil de lo publicado
blogger/tema.xml             plantilla del sitio (sin fechas, autor ni etiquetas)
blogger/paginas/*.html       Acerca, Metodología, Privacidad, Contacto, Aviso legal
docs/                        GitHub Pages: imágenes PNG/PDF y config.json
fonts/                       Anton y Fira Sans (licencia OFL) para las imágenes
```

## Mapa de variables de la plantilla

| Variable | Origen |
|---|---|
| `{anio}` `{region}` `{total}` | ficha de la URL |
| `{respuesta}` `{subrespuesta}` | frase determinista con total, nacionales, autonómicos, locales y festivos entre semana |
| `{franja}` | colores de la comunidad (regiones.json) |
| `{img_png}` `{img_pdf}` `{img_alt}` | GitHub Pages `/docs/img/` |
| `{laborables_anio}` | lunes a viernes menos festivos entre semana |
| `{filas_festivos}` `{nota_region}` | BOE + notas (islas de Canarias, Arán) |
| `{lista_puentes}` | bloques de 3+ días libres y días puente calculados |
| `{diferencias}` | festivos distintos frente a 3 comunidades vecinas |
| `{filas_meses}` | laborables y festivos entre semana por mes |
| `{faq_html}` `{jsonld}` | 3 preguntas visibles + FAQPage + Dataset |
| `{enlaces_vecinos}` | 7 enlaces (España + 6 vecinas); el índice enlaza las 19 |
| `{fuente_url}` `{fuente_titulo}` `{fuente_boe}` | BOE |
| `{datos_js}` | fechas, nombres y tipos para la herramienta (respaldo local si config.json cae) |
| `{sitio}` `{template_version}` | config.json / generador |

Los enlaces internos salen como `@@URL:slug@@`. El publicador los cambia por la URL real; si la vecina aún no existe deja solo el texto (nunca un enlace roto) y vuelve a enlazar cuando se publica.

## SEO metadata (ejemplos)

| | Índice | Hija |
|---|---|---|
| Título | Calendario laboral 2027 en España: festivos nacionales y por comunidad | Calendario laboral 2027 Castilla-La Mancha: festivos y puentes |
| Meta descripción | Los 8 festivos nacionales comunes de 2027 y los de cada comunidad, con calendario para imprimir en PNG y PDF y calculadora de días laborables. | Castilla-La Mancha tiene 12 festivos en 2027 sin contar los locales. Calendario para imprimir, puentes y calculadora de días laborables. |
| Slug | calendario-laboral-2027-espana | calendario-laboral-2027-castilla-la-mancha |

El año va en el título desde los datos (`anio`): al generar 2028 cambia solo.

## queue.csv

`slug, titulo, meta_descripcion, tipo, seccion, anio, region, prioridad, template_version, estado (pendiente/publicado/actualizar/error), clave_duplicado, url_publicada, post_id, intentos, ultimo_error, fecha_publicacion, enlaces_pendientes`

## Cómo funciona

1. `publicar-sitio.yml` corre cada día (y a mano con "Run workflow"): pruebas, genera las páginas, pasa los chequeos y publica las siguientes URLs de `queue.csv` en `docs/`.
2. GitHub Pages despliega `docs/` sola en uno o dos minutos.
3. `prueba-fuente.yml` revisa cada lunes que el BOE siga diciendo lo mismo; si cambia, falla y avisa por correo.
4. `verificar.yml` mide enlaces y PageSpeed móvil de las URLs publicadas.

Para cambiar al dominio propio: compra `calendariohoy.com`, ponlo en Settings > Pages > Custom domain y cambia `sitio` y `assets` en `config.json`. GitHub redirige las URLs viejas.

## Pendiente de tu parte (solo cuando quieras)

- Search Console: añade la propiedad de prefijo de URL `https://davarooo.github.io/calendarios/`, verifícala con el archivo HTML que da Google (súbelo a `docs/` o pásamelo) y envía `sitemap.xml`.
- AdSense pide un dominio propio: no acepta `github.io`. Se conecta al comprar el dominio.

## Plan de medición (cada lunes)

Los umbrales de Imágenes, CTR y RPM son iniciales, sin datos propios todavía: se ajustan tras 4 semanas de tráfico real.

| Dónde | Qué mirar | Decisión |
|---|---|---|
| Search Console > Páginas | % de URLs indexadas | Semana 4: más del 60 % e impresiones subiendo → Fase 2. Menos del 40 % → parar y mejorar valor. |
| Search Console > Rendimiento > Imágenes | Impresiones y clics en Google Imágenes | Si Imágenes trae menos del 30 % de los clics, revisar alt, nombre de archivo y tamaño de la imagen. |
| Search Console > Rendimiento | CTR por página | CTR menor del 2 % con posición media de 1 a 10 → reescribir título y descripción. |
| Bing Webmaster | Páginas rastreadas e indexadas | Si Bing indexa y Google no, el problema es valor o calidad, no técnica. |
| AdSense | RPM de página e impresiones por visita | RPM menor de 2 € en noviembre o diciembre → revisar posición de anuncios, nunca junto a la herramienta. |
| informes/verificacion.json | URLs con LCP mayor de 2,5 s o enlaces rotos | Cualquier fallo bloquea la publicación de nuevas URLs hasta corregirlo. |
| Semana 8 | URLs sin indexar | Fusionar con su vecina o marcar noindex. |

## Nota sobre Blogger

Se probó Blogger (calendario-hoy.blogspot.com). Publicar desde la nube exigía credenciales OAuth, así que el sitio pasó a GitHub Pages. La carpeta `blogger/` guarda el tema y las páginas de confianza por si se vuelve a usar. El blog redirige al sitio nuevo: la portada a la portada y cada `/p/<pagina>.html` a `/<pagina>/`.
