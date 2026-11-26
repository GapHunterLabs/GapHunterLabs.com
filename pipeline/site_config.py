"""site_config.py -- configuracion compartida por los generadores del sitio.

SITE_URL es la unica fuente de la URL base (sin barra final). Si algun dia
el sitio pasa a un dominio propio, se cambia aqui (y el archivo CNAME);
canonical, og:url, JSON-LD, sitemap, hreflang y fichas salen de esta
constante al volver a correr los generadores.
"""

SITE_URL = "https://gaphunterlabs.com"

# Version of the social-share (Open Graph) images, appended as ?v= to every og:image and twitter:image URL.
# Networks cache the image by URL: bump it whenever pipeline/build_page_og.py or build_og_images.py re-render.
OG_VERSION = "6"
