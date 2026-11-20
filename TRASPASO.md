# Traspaso (19 nov 2026, segunda sesión)

Todo el estado, la instalación y el plan de medición están en README.md.

## Pendiente de mí (siguiente sesión)
- Volúmenes (Ahrefs gratis) y Google Trends a 5 años de las frases principales.
- Fuentes de fiestas locales: empezar por Madrid (BOCM) y Murcia (BORM, ya publicado el 27-07-2026).
- Sección 2 (calendario escolar 2027-2028) y sección 3 (calendarios por país).

## Pendiente de ti
- Pasos 1 a 7 de "Instalación" del README.

## Prompt para el chat nuevo
> Sigo el proyecto Calendario Hoy. Adjunto README.md y TRASPASO.md. Resultado de "Prueba de fuente (BOE)": [pega el log]. Primera URL publicada: [enlace]. Continúa con lo pendiente de ti.


## Retomar el 20-11-2026

Hecho el 19-11: Search Console verificado (prefijo davarooo.github.io/calendarios/, sitemap enviado), 44 municipios de Murcia + listado publicado y cotejado contra el BORM.

Pendiente, en este orden:
1. Search Console: pedir indexación de la portada (el 19-11 la cuota diaria estaba agotada).
2. Bing Webmaster: necesita que Juanda apruebe el permiso de importar desde Google.
3. Calendario escolar 2026-2027 (no publicado todavía):
   - Datos verificados contra boletín: data/es/escolar/madrid.json (BOCM 4-6-2026), data/es/escolar/cataluna.json (DOGC 9653).
   - data/es/festivos-2026.json: tabla BOE-A-2025-21667, para los festivos de sept-dic 2026 de cada comunidad.
   - Fuentes localizadas sin leer: C. Valenciana (Resolución 15-6-2026, DOGV 10387, CVE DOGV-C-2026-20810); Murcia (Resolución 8-6-2026, BORM 11-6, modificada 12-7-2026; calendario por municipio en anexo).
   - Andalucía: un calendario por provincia (8 resoluciones de delegación territorial).
   - Falta: plantilla de página escolar y las otras 13 comunidades.
   - Método de lectura de PDF oficiales: pdf.js en una pestaña del propio dominio del boletín y lectura del texto con get_page_text.
