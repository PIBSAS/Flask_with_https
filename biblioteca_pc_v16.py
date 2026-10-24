""" DOCS:
    PyMuPDF[pymupdf]: https://pymupdf.readthedocs.io/en/latest/
    Pillow       : https://pillow.readthedocs.io/en/latest/
    Flask        : https://flask.palletsprojects.com/en/latest/
    Requiere     : https://aka.ms/vc14/vc_redist.x64.exe
"""
import io, json, mimetypes, os, re, socket, subprocess, sys, threading, time, webbrowser, shutil, zipfile, argparse, uuid
import urllib.request
from urllib.parse import quote, unquote

######### Instalación de dependencias #########
def is_dependencies_installed():
    """
    Verifica si las dependencias están instaladas.
    Si alguna falta, la instala automáticamente.

    :return: None
    """
    packages = ["flask", "Pillow", "PyMuPDF"]
    for package in packages:
        try:
            subprocess.check_output([sys.executable, "-m", "pip", "show", package])
        except subprocess.CalledProcessError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-cache-dir", package])

is_dependencies_installed()
#########################################################

######### Argumentos de línea de comandos #########

def parse_arguments():
    """
    Parsea los argumentos de línea de comandos.
    
    :return: Objeto con los argumentos parseados
    """
    parser = argparse.ArgumentParser(
        description='Generador de carátulas de PDFs',
        epilog='''
Ejemplos de uso:
  python archivo.py              # Usa formato WEBP (por defecto)
  python archivo.py -f png       # Usa formato PNG
  python archivo.py -f webp      # Usa formato WEBP (explícito)
  python archivo.py -h           # Muestra esta ayuda
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-f', '--formato', 
                        choices=['webp', 'png'], 
                        default='webp',
                        help='Formato de salida para las carátulas (webp o png)')
    return parser, parser.parse_args()

parser, args = parse_arguments()

if len(sys.argv) == 1:
    print("No se especificaron argumentos. Mostrando ayuda:\n")
    parser.print_help()
    print("\nEjecutando con valores por defecto...\n")

FORMATO_CARATULA = args.formato
#########################################################
######### Third Party Libraries #########
from https.sechttps import https
import pymupdf
from PIL import Image, ImageDraw, ImageFont, ImageFile
from flask import Flask, render_template_string, send_file, send_from_directory, request

mimetypes.add_type('image/webp', '.webp')
mimetypes.add_type('image/png', '.png')

Image.MAX_IMAGE_PIXELS = 200_000_000
ImageFile.LOAD_TRUNCATED_IMAGES = True

BASE_DIRECTORY = os.getcwd()
basename = os.path.basename(BASE_DIRECTORY)
BASE_PATH = f'/{basename}' if basename else ""  # si estás en raíz, queda ""

STATIC_FOLDER = os.path.join(os.getcwd(), 'static')
PDFJS_FOLDER = os.path.join(STATIC_FOLDER, "pdfjs")
os.makedirs(STATIC_FOLDER, exist_ok=True)

########################################################

######### Funciones Helpers / Misc #########

def open_browser_when_ready(host, port):
    """
    Abre el navegador web apuntando a la URL del servidor Flask
    solo cuando el servidor esté listo para recibir conexiones.

    :param host: Dirección del host donde corre Flask.
    :type host: str
    :param port: Puerto donde corre Flask.
    :type port: int
    """
    url = f"https://{host}:{port}{BASE_PATH}/"
    
    while True:
        try:
            with socket.create_connection((host, port), timeout=1):
                break
        except OSError:
            time.sleep(0.5)
    webbrowser.open_new(url)


#########################################################

######### Funciones para los PDFs #########
                         
def orden_natural(s):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]

def buscar_pdfs_recursivo(base_dir):
    """
    Busca PDFs recursivamente en un directorio, ignorando la carpeta 'static'.

    :param base_dir: Directorio base donde buscar los PDFs.
    :type base_dir: str
    :return: Lista de tuplas (ruta_completa, carpeta_relativa, nombre_archivo).
    :rtype: list[tuple[str, str, str]]
    """
    pdfs = []
    
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs 
                  if d != 'static'
                  and not d.startswith('.')]
        
        dirs.sort(key=orden_natural)
        
        files.sort(key=orden_natural)
        
        for f in files:
            if f.lower().endswith(".pdf"):
                ruta_pdf = os.path.join(root, f)
                carpeta_relativa = os.path.relpath(root, base_dir)
                carpeta_relativa = '.' if carpeta_relativa == '.' else carpeta_relativa.replace('\\', '/')   
                pdfs.append((ruta_pdf, carpeta_relativa, f))
    pdfs.sort(key=lambda x: (orden_natural(x[1]), orden_natural(x[2])))
    return pdfs


def eliminar_metadatos(ruta_pdf, nombre_base):
    """
    Elimina los metadatos de un PDF, dejando únicamente el título como nombre_base.

    :param ruta_pdf: Ruta al archivo PDF.
    :type ruta_pdf: str
    :param nombre_base: Nombre base que se usará como título del PDF.
    :type nombre_base: str
    :return: True si se modificaron los metadatos, False si ya estaban limpios.
    :rtype: bool
    """
    try:
        pdf = pymupdf.open(ruta_pdf)
        metadata_actual = pdf.metadata or {}
                
        empty_metadata = {
            "title": nombre_base,
            "author": "",
            "subject": "",
            "keywords": "",
            "creator": "",
            "producer": "",
            "creationDate": "",
            "modDate": ""
        }

        ya_limpio = all(
            metadata_actual.get(clave, "") in ("", nombre_base if clave == "title" else "")
            for clave in empty_metadata
        )

        if ya_limpio:
            print(f"Metadatos ya estaban limpios: {os.path.basename(ruta_pdf)}")
            pdf.close()
            return False
        else:
            pdf.set_metadata(empty_metadata)
            temp_path = ruta_pdf + ".tmp"
            pdf.save(temp_path, garbage=4, deflate=True)
            pdf.close()

            os.remove(ruta_pdf)
            shutil.move(temp_path, ruta_pdf)
            print(f"Metadatos eliminados: {os.path.basename(ruta_pdf)}")
            return True

    except Exception as e:
        error_msg = str(e)
        if "xref" in error_msg or "format error" in error_msg:
            print(f"PDF corrupto (no se pueden modificar metadatos): {os.path.basename(ruta_pdf)}")
        else:
            print(f"Error al eliminar metadatos de {os.path.basename(ruta_pdf)}: {e}")
        return False

def extraer_caratulas_y_redimensionar(directorio, salida, ancho_deseado, alto_deseado, formato='webp'):
    """
    Extrae las carátulas de los PDFs y las redimensiona a un tamaño fijo (WEBP).

    :param directorio: Ruta al directorio con los PDFs.
    :type directorio: str
    :param salida: Ruta al directorio de salida para las carátulas.
    :type salida: str
    :param ancho_deseado: Ancho deseado en píxeles.
    :type ancho_deseado: int
    :param alto_deseado: Alto deseado en píxeles.
    :type alto_deseado: int
    :param formato: Formato de salida ('webp' o 'png').
    :type formato: str
    """
    if not os.path.exists(salida):
        os.makedirs(salida)
        
    pdf_files = buscar_pdfs_recursivo(directorio)
    print(f"\nSe encontraron {len(pdf_files)} archivos PDF en todas las subcarpetas...\n")
    print(f"Formato de salida: {formato.upper()}\n")
    
    pdfs_exitosos = 0
    pdfs_con_error = 0
    
    for ruta_pdf, carpeta, archivo in pdf_files:
        base = os.path.splitext(archivo)[0]
        if carpeta == ".":
            salida_subcarpeta = salida
        else:
            salida_subcarpeta = os.path.join(salida, carpeta)

        os.makedirs(salida_subcarpeta, exist_ok=True)
        
        ruta_caratula = os.path.join(salida_subcarpeta, base + f".{formato}")
        if os.path.exists(ruta_caratula):
            print(f"Carátula ya existe, se omite: {ruta_caratula}")
            continue
        
        try:
            eliminar_metadatos(ruta_pdf, base)
            with pymupdf.open(ruta_pdf) as doc:
                pagina = doc[0]
                pix = pagina.get_pixmap(matrix=pymupdf.Matrix(300 / 72, 300 / 72))
                img_bytes = pix.tobytes("png")
                imagen_pil = Image.open(io.BytesIO(img_bytes))
                imagen_redimensionada = imagen_pil.resize(
                    (ancho_deseado, alto_deseado),Image.LANCZOS
                )
                if formato.lower() == 'png':
                    imagen_redimensionada.save(ruta_caratula, "PNG", lossless=True)
                else:
                    imagen_redimensionada.save(ruta_caratula, "WEBP", lossless=True)
                print(f"Carátula extraída y redimensionada: {ruta_caratula}")
                pdfs_exitosos += 1
                
        except Exception as e_pymupdf:
            print(f"Error procesando {archivo}: {e_pymupdf}")
            pdfs_con_error += 1


#########################################################

######### Funciones para los assets #########

def crear_logo_pdf(ruta_salida='logo.webp', tamaño=(1024, 1024)):
    """
    Crea un logo PDF en formato WEBP con fondo rojo y texto "PDF" en blanco.

    :param ruta_salida: Ruta de salida del logo.
    :type ruta_salida: str
    :param tamaño: Tupla con (ancho, alto) de la imagen.
    :type tamaño: tuple[int, int]
    """
    fondo_rojo = (220, 20, 60)
    texto_blanco = (255, 255, 255)
    img = Image.new("RGB", tamaño, fondo_rojo)
    draw = ImageDraw.Draw(img)
    texto = "PDF"
    padding = int(tamaño[0] * 0.1)
    fuente_size = int(tamaño[1] * 0.8)
    while fuente_size > 1:
        try:
            fuente = ImageFont.truetype("arialbd.ttf", size=int(tamaño[1] * 0.4))
        except:
            fuente = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), texto, font=fuente)
        texto_ancho = bbox[2] - bbox[0]
        texto_alto = bbox[3] - bbox[1]
        if texto_ancho <= tamaño[0] - 2*padding and texto_alto <= tamaño[1] - 2*padding:
                break
        fuente_size -= 1
    posicion = ((tamaño[0] - texto_ancho) // 2, (tamaño[1] - texto_alto) // 2)
    draw.text(posicion, texto, fill=texto_blanco, font=fuente)

    img.save(ruta_salida, "WEBP")
    print(f"Logo PDF creado: {ruta_salida}")


def convertir_a_ico(entrada='logo.webp', salida='favicon.ico', tamaño=(512, 512)):
    """
    Crea un archivo favicon.ico a partir de una imagen de entrada.

    :param entrada: Ruta de la imagen de entrada (generalmente logo.webp).
    :type entrada: str
    :param salida: Ruta del archivo ICO de salida.
    :type salida: str
    :param tamaño: Tupla (ancho, alto) del favicon.
    :type tamaño: tuple[int, int]
    """
    img = Image.open(entrada).convert("RGBA")
    img = img.resize(tamaño, Image.LANCZOS)
    img.save(salida, format='ICO')
    print(f"Favicon creado: {salida}")


#########################################################

######### Servidor Flask #########

app = Flask(__name__, static_folder=STATIC_FOLDER, static_url_path='/static')

FAVICON_PATH = os.path.join(STATIC_FOLDER, 'favicon.ico')

@app.route('/favicon.ico')
@app.route('/<path:path>/favicon.ico')
def favicon(path=None):
    return send_from_directory(STATIC_FOLDER, 'favicon.ico')

@app.route(f'{BASE_PATH}/')
def serve_index():
    pdf_files = buscar_pdfs_recursivo(BASE_DIRECTORY)
    lista_para_html = []
    
    for ruta, carpeta, archivo in pdf_files:
        carpeta_codificada = quote(carpeta.replace('\\', '/')) if carpeta != "." else "."
        archivo_codificado = quote(archivo)
        lista_para_html.append((carpeta_codificada, archivo_codificado, archivo))
    html_content = generate_html(lista_para_html, BASE_PATH, FORMATO_CARATULA)
    return render_template_string(html_content)


@app.route(f'{BASE_PATH}/<path:subpath>')
def serve_cover(subpath):
    subpath = unquote(subpath)
    ruta_completa = os.path.join(BASE_DIRECTORY, subpath)
    
    if os.path.exists(ruta_completa):
        if subpath.endswith('.webp'):
            mimetype = 'image/webp'
        elif subpath.endswith('.png'):
            mimetype = 'image/png'
        elif subpath.endswith('.pdf'):
            mimetype = 'application/pdf'
        else:
            mimetype = None
        
        return send_file(ruta_completa, mimetype=mimetype)
    else:
        return "Archivo no encontrado", 404

@app.route('/cerrar-servidor', methods=['POST'])
def cerrar_servidor():
    """Cierra el servidor SOLO si es un cierre real, no un refresh."""
    
    # Verificar headers para intentar distinguir
    #cache_control = request.headers.get('Cache-Control', '')
    #pragma = request.headers.get('Pragma', '')
    token = request.form.get('token', '')
    session_token = app.config.get('SESSION_TOKEN', '')
    # Los refreshes suelen tener ciertos headers
    #if 'max-age=0' in cache_control or 'no-cache' in cache_control or pragma == 'no-cache':
     #   print("Posible refresh detectado - NO cerrar servidor")
      #  return "OK (refresh ignorado)", 200
    if token and session_token and token != session_token:
        print("Token no coincide - Posible refresh - NO cerrar servidor")
        return "OK (refresh ignorado)", 200
    
    cache_control = request.headers.get('Cache-Control', '')
    pragma = request.headers.get('Pragma', '')
    
    if 'max-age=0' in cache_control or 'no-cache' in cache_control or pragma == 'no-cache':
        print("Posible refresh detectado (headers de caché) - NO cerrar servidor")
        return "OK (refresh ignorado)", 200
    
    print("Cierre real detectado - Cerrando servidor...")
    
    # Dar tiempo para responder
    time.sleep(0.5)
    
    # Cerrar en un thread separado
    def shutdown():
        time.sleep(1)
        os._exit(0)
    
    threading.Thread(target=shutdown, daemon=True).start()
    
    return "OK", 200


#########################################################

######### Generador del HTML #########

def generate_html(pdf_files, base_path, formato='webp'):
    """
    Genera el contenido HTML del índice con miniaturas y títulos de PDFs.

    :param pdf_files: Lista de tuplas con información de los PDFs
                      en formato (carpeta, archivo_codificado, nombre_original).
    :type pdf_files: list[tuple[str, str, str]]
    :param base_path: Ruta base de la aplicación para construir URLs.
    :type base_path: str
    :param formato: Formato de las imagenes ('webp' o 'png').
    :type formato: str
    :return: Contenido HTML generado como string.
    :rtype: str
    """
    from collections import defaultdict
    pdfs_por_carpeta = defaultdict(list)

    for carpeta, archivo, nombre_original in pdf_files:
        pdfs_por_carpeta[carpeta].append((archivo, nombre_original))
    
    folder_name = os.path.basename(os.getcwd())
    
    session_token = str(uuid.uuid4())
    app.config['SESSION_TOKEN'] = session_token
    
    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{folder_name}</title>
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
    <!-- <link rel="manifest" href="/static/site.webmanifest"> -->
    <style>
        html, body {{
            margin: 0;
            padding: 0;
            height: 100%;
            overflow-x: hidden;
            font-family: Arial, sans-serif;
        }}
        
        #fondo {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
        }}
        
        #logo {{
            margin: 20px auto;
            width: 256px;
            height: auto;
            text-align: center;
            border-radius: 30px;
            overflow: hidden;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }}
        
        #logo img {{
            display: block;
            width: 100%;
            height: auto;
        }}
        
        .pdfs-container {{
            display: grid;
            gap: 20px;
            justify-items: center;
            padding: 20px;
        }}

        .pdfs-container.few-1 {{ grid-template-columns: 1fr; max-width: 400px; margin: 0 auto; }}
        .pdfs-container.few-2 {{ grid-template-columns: repeat(2, 1fr); max-width: 700px; margin: 0 auto; }}
        .pdfs-container:not(.few-1):not(.few-2) {{ grid-template-columns: repeat(3, 1fr); max-width: 100%; margin: 0 auto; }}


        .pdf-container {{
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            background: #fff;
            transition: transform 0.2s;
            width: 100%;      /* llena la celda del grid */
            max-width: 332px; /* el ancho de la miniatura */
        }}
        
        .pdf-container:hover {{
            transform: scale(1.05);
        }}
        
        .pdf-thumbnail {{
            width: 100%;
            height: auto;
            cursor: pointer;
            display: block;
        }}

        .pdf-row {{
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
        }}

        .pdf-row-few {{
            justify-content: center;
        }}
        
        .pdf-title {{
            text-align:center;
            font-size: 14px;
            font-weight: bold;
            color: #333;
            margin-top: 5px;
            margin-bottom: 10px;
            box-sizing: border-box;
        }}
        
        @media (max-width: 768px) {{
            #pdfs-container {{
                grid-template-columns: 1fr 1fr;
            }}
        }}
        
        @media (max-width: 480px) {{
            #pdfs-container {{
                grid-template-columns: 1fr;
            }}
        }}
        
        footer {{
            text-align: center;
            margin-top: 30px;
            padding: 15px 0;
            color: #555;
            font-size: 12px;
        }}
        
        footer img {{
            max-width: 50px;
            margin-bottom: 5px;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }}

        footer p {{
            margin: 0;
            font-size: 12px;
            color: #555;
        }}
        .btn-cerrar {{
            margin-top: 10px;
            padding: 8px 20px;
            background: #dc3545;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            transition: background 0.3s;
        }}
        
        .btn-cerrar:hover {{
            background: #c82333;
        }}
        h2 {{
            background-color: rgba(255, 255, 255, 0.8);
            color: #333;
            text-align: center;
            padding: 10px 0;
            margin: 20px 40px;
            border-radius: 10px;
            width: calc(100% - 80px);
            box-sizing: border-box;                     
        }}
        
        #modal-visor {{
            display: none;
            position: fixed;
            top:0; left:0;
            width:100%; height:100%;
            background-color: rgba(0,0,0,0.8);
            z-index: 9999;
        }}
        
        #modal-visor iframe {{
            width:100%; height:100%;
            display:block;
            border:none;
        }}
        
        #modal-visor .cerrar {{
            position:absolute; top:50px; right:10px;
            font-size:30px; color:green;
            cursor:pointer;
            z-index: 10000;
        }}
    </style>
    
    <div id="fondo"></div>
    <script>
    const fondo = document.getElementById('fondo');
    let hue = 0;
    function animateBackground() {{
        hue = (hue + 0.5) % 360;
        fondo.style.background = `linear-gradient(135deg, hsl(${{hue}}, 70%, 80%), hsl(${{(hue+60)%360}}, 70%, 80%))`;
        requestAnimationFrame(animateBackground);
    }}
    animateBackground();
    const SESSION_TOKEN = '{session_token}';
    window.addEventListener('pagehide', function(e) {{
        const data = new URLSearchParams();
        data.append('token', SESSION_TOKEN);
        navigator.sendBeacon('/cerrar-servidor', data);
    }});
    
    // Función para cerrar servidor manualmente
    function cerrarServidor() {{
        if (confirm('¿Seguro que quieres cerrar el servidor?')) {{
            fetch('/cerrar-servidor', {{ 
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/x-www-form-urlencoded',
                }},
                body: new URLSearchParams({{'token': SESSION_TOKEN}}),
                keepalive: true
            }}).then(() => {{
                window.close();
            }}).catch(() => {{
                window.close();
            }});
        }}
    }}
</script>
    <!-- <script>
    if ('serviceWorker' in navigator) {{
      window.addEventListener('load', function() {{
        navigator.serviceWorker.register("/service-worker.js").then(function(registration) {{
          console.log('ServiceWorker registration successful with scope: ', registration.scope);
        }}, function(err) {{
          console.log('ServiceWorker registration failed: ', err);
        }});
      }});
    }}
  </script>
  <script>
    function abrirPDF(pdf) {{
        const modal = document.getElementById('modal-visor');
        const iframe = document.getElementById('visor-pdf');
        iframe.src = `static/pdfjs/web/viewer.html?file=${{encodeURIComponent(pdf)}}`;
        modal.style.display = 'block';
    }}
    function cerrarModal() {{
        const modal = document.getElementById('modal-visor');
        const iframe = document.getElementById('visor-pdf');
        iframe.src = '';
        modal.style.display = 'none';
    }} 
</script> -->

</head>
<body>
    <div id="logo">
        <img src="/static/logo.webp" alt="{folder_name}">
    </div>
"""
    for carpeta, archivos in pdfs_por_carpeta.items():
        titulo = "En Raíz" if carpeta == "." else carpeta
        titulo = unquote(titulo)
        html_content += f"<h2>{titulo}</h2>\n"
        clase = ""
        if len(archivos) == 1:
            clase = "few-1"
        elif len(archivos) == 2:
            clase = "few-2"

        html_content += f'<div class="pdfs-container {clase}">\n'

        for archivo_codificado, nombre_original in archivos:
            base = os.path.splitext(nombre_original)[0]
            nombre_sin_extension = os.path.splitext(archivo_codificado)[0]
            
            if carpeta == ".":
                ruta_miniatura = f"{base_path}/{nombre_sin_extension}.{formato}"
                ruta_pdf = f"{base_path}/{archivo_codificado}"
            else:
                ruta_miniatura = f"{base_path}/{carpeta}/{nombre_sin_extension}.{formato}"
                ruta_pdf = f"{base_path}/{carpeta}/{archivo_codificado}"
                
            html_content += f"""
        <div class="pdf-container">
            <!-- Para PC agregamos un anchor href y comento onclick--> 
            <a href="{ruta_pdf}" target="_blank">
                <!--<img src="{ruta_miniatura}" class="pdf-thumbnail" alt="{base}" onclick="abrirPDF('{ruta_pdf}')">-->
                <img src="{ruta_miniatura}" class="pdf-thumbnail" alt="{base}">
            </a>
            <p class="pdf-title">{base}</p>
        </div>
"""
        html_content += "</div>\n"
    
    html_content += f"""
    <div id="modal-visor">
        <span class="cerrar" onclick="cerrarModal()">&times;</span>
        <iframe id="visor-pdf"></iframe>
    </div>
    <footer>
        <img src="/static/logo.webp" alt="{folder_name}">
        <p>© 2026 PDF Web App</p>
        <button class="btn-cerrar" onclick="cerrarServidor()">⏻ Cerrar servidor</button>
    </footer>
</body>
</html>
"""
    return html_content

logo_path = os.path.join(STATIC_FOLDER, 'logo.webp')
favicon_path = os.path.join(STATIC_FOLDER, 'favicon.ico')

if not os.path.exists(logo_path):
    crear_logo_pdf()
    shutil.move('logo.webp', logo_path)

if not os.path.exists(favicon_path):
    convertir_a_ico(entrada=logo_path, salida='favicon.ico')
    shutil.move('favicon.ico', favicon_path)

port = 443
extraer_caratulas_y_redimensionar("./", "./", 332, 443, FORMATO_CARATULA)

#########################################################

######### Main #########

if __name__ == '__main__':
    # Silenciar warning de servidor de desarrollo de Flask NO SIRVE
    import warnings
    warnings.filterwarnings("ignore", message="WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.")
    browser_host, ssl_context = https()
    # Thread que abre navegador solo cuando Flask esté listo
    threading.Thread(target=open_browser_when_ready, args=(browser_host, port), daemon=True).start() 
    # Ejecutar Flask en el puerto 443 escuchando en todas las interfaces (0.0.0.0)
    app.run(debug=False, host='0.0.0.0', port=port, use_reloader=False, ssl_context=ssl_context)
