# Deploy público NODO UNAM

Output recomendado para Cloudflare Pages:

- Build command: none
- Output directory: deploy/static

Esta carpeta usa `window.NODO_CONFIG.mode = "static"` y lee datos desde:

`deploy/static/data/workshop/*.json`

Pendiente para producción real:

1. Subir `deploy/static/data/workshop/*.json` a Cloudflare R2.
2. Cambiar `dataBaseUrl` en `deploy/static/index.html` al dominio público de R2.
3. Conectar Cloudflare Pages a GitHub.
4. Mantener Laboratorio semántico desactivado hasta conectar HF Spaces/Worker.
