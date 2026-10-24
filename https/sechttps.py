import ipaddress
import socket
from pathlib import Path
from datetime import datetime, timedelta, timezone
import subprocess, sys

def is_dependencies_installed():
    """
    Verifica si las dependencias están instaladas.
    Si alguna falta, la instala automáticamente.

    :return: None
    """
    packages = ["cryptography"]
    for package in packages:
        try:
            subprocess.check_output([sys.executable, "-m", "pip", "show", package])
        except subprocess.CalledProcessError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-cache-dir", package])

is_dependencies_installed()

from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa


BASE_DIR = Path(__file__).resolve().parent

CA_KEY_FILE = BASE_DIR / "flask-local-ca.key"
CA_CERT_FILE = BASE_DIR / "flask-local-ca.crt"

SERVER_KEY_FILE = BASE_DIR / "flask-local-server.key"
SERVER_CERT_FILE = BASE_DIR / "flask-local-server.crt"

def generar_ca():
    if CA_KEY_FILE.exists() or CA_CERT_FILE.exists():
        print("La CA ya existe.")

        if CA_KEY_FILE.exists():
            print(f"Clave:       {CA_KEY_FILE}")

        if CA_CERT_FILE.exists():
            print(f"Certificado: {CA_CERT_FILE}")

        print()
        print("No se sobrescribirá.")
        return

    print("Generando autoridad certificadora local...")

    # Clave privada de la CA
    ca_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
    )

    # Identidad de la CA
    subject = issuer = x509.Name([
        x509.NameAttribute(
            NameOID.COUNTRY_NAME,
            "AR"
        ),
        x509.NameAttribute(
            NameOID.ORGANIZATION_NAME,
            "Flask PC"
        ),
        x509.NameAttribute(
            NameOID.COMMON_NAME,
            "Flask PC Local CA"
        ),
    ])

    ahora = datetime.now(timezone.utc)

    # Certificado de la CA
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora - timedelta(minutes=5))
        .not_valid_after(ahora + timedelta(days=3650))
        .add_extension(
            x509.BasicConstraints(
                ca=True,
                path_length=None
            ),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                content_commitment=False,
                data_encipherment=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(
            private_key=ca_key,
            algorithm=hashes.SHA256(),
        )
    )

    # Guardar clave privada de la CA
    with open(CA_KEY_FILE, "wb") as f:
        f.write(
            ca_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Guardar certificado público de la CA
    with open(CA_CERT_FILE, "wb") as f:
        f.write(
            ca_cert.public_bytes(
                serialization.Encoding.PEM
            )
        )

    print()
    print("CA creada correctamente.")
    print()
    print(f"Clave privada:")
    print(f"  {CA_KEY_FILE}")
    print()
    print(f"Certificado:")
    print(f"  {CA_CERT_FILE}")
    print()
    print("IMPORTANTE:")
    print("La clave flask-local-ca.key NO debe distribuirse.")
    print("El archivo flask-local-ca.crt sí debe instalarse")
    print("como autoridad certificadora confiable en los dispositivos clientes.")
    """print("PASOS:")
    print("1. Doble click sobre flask-local-ca.crt")
    print("2. Instalar certificado ...")
    print("3. Equipo local")
    print("4. Colocar todos los certificados en el siguiente almacén")
    print("5. Examinar...")
    print("6. Entidades de certificación raíz de confianza")
    print("7. Aceptar")
    print("8. Siguiente")
    print("9. Finalizar")
    print("Repetir para los demaás dispositivos de la red también se debe instalar el flask-local-ca.crt")
    print("En Android es en Ajustes, Seguridad y Privacidad, Mayor seguridad y privacidad")
    print("Encriptacion y credenciales, Instalar un certificado, Certificado de CA")
    print("Instalar de todas formas, elegir el .crt")"""

def asegurar_ca():
    """Comprueba que la CA exista y la genera si falta."""
    if not CA_KEY_FILE.exists() and not CA_CERT_FILE.exists():
        generar_ca()
    elif not CA_KEY_FILE.exists() or not CA_CERT_FILE.exists():
        raise FileNotFoundError(
            "La CA está incompleta.\n"
            f"Clave privada: {CA_KEY_FILE}\n"
            f"Certificado: {CA_CERT_FILE}\n"
            "No se sobreescribirán los archivos existentes."
        )


def obtener_ip_local():
    """Obtiene la IP LAN actual del equipo."""

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        sock.connect(("1.1.1.1", 80))
        return sock.getsockname()[0]

    except OSError:
        return socket.gethostbyname(socket.gethostname())

    finally:
        sock.close()


def cargar_ca():
    """Carga la clave y el certificado de la CA local."""

    if not CA_KEY_FILE.exists():
        raise FileNotFoundError(
            f"No existe la clave de la CA:\n{CA_KEY_FILE}\n\n"
            "Ejecutá generar_ca.py primero."
        )

    if not CA_CERT_FILE.exists():
        raise FileNotFoundError(
            f"No existe el certificado de la CA:\n{CA_CERT_FILE}\n\n"
            "Ejecutá generar_ca.py primero."
        )

    with open(CA_KEY_FILE, "rb") as f:
        ca_key = serialization.load_pem_private_key(
            f.read(),
            password=None
        )

    with open(CA_CERT_FILE, "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(
            f.read()
        )

    return ca_key, ca_cert


def instalar_ca():
    """Instala la CA local en Windows si todavia no es confiable."""

    ca_cert = cargar_ca()[1]
    huella = ca_cert.fingerprint(hashes.SHA1()).hex().upper()

    # Comprobar si ya esta instalada
    for argumentos in (["certutil", "-store", "Root", huella], ["certutil", "-user", "-store", "Root", huella]):
        resultado = subprocess.run(argumentos, capture_output=True, text=True, encoding="mbcs", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)

        if resultado.returncode == 0:
            print("La CA local ya esta instalada en Windows.")
            return

    # Si no existe en ninguno de los almacenes, instalarla para el usuario
    subprocess.run(["certutil", "-user", "-addstore", "Root", str(CA_CERT_FILE)], check=True, capture_output=True, text=True, encoding="mbcs", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)
    print("CA local instalada correctamente en Windows.")

    
def generar_certificado_servidor(ip):
    """Genera un certificado HTTPS firmado por la CA local."""

    ca_key, ca_cert = cargar_ca()

    server_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

    ahora = datetime.now(timezone.utc)

    subject = x509.Name([
        x509.NameAttribute(
            NameOID.ORGANIZATION_NAME,
            "Servidor Flask Local"
        ),
        x509.NameAttribute(
            NameOID.COMMON_NAME,
            ip
        ),
    ])

    san = x509.SubjectAlternativeName([
        x509.IPAddress(ipaddress.ip_address(ip)),
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora - timedelta(minutes=5))
        .not_valid_after(ahora + timedelta(days=30))
        .add_extension(
            san,
            critical=False
        )
        .add_extension(
            x509.BasicConstraints(
                ca=False,
                path_length=None
            ),
            critical=True
        )
        .add_extension(
            x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.SERVER_AUTH
            ]),
            critical=False
        )
        .sign(
            private_key=ca_key,
            algorithm=hashes.SHA256()
        )
    )

    with open(SERVER_KEY_FILE, "wb") as f:
        f.write(
            server_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
        )

    with open(SERVER_CERT_FILE, "wb") as f:
        f.write(
            cert.public_bytes(
                serialization.Encoding.PEM
            )
        )


def certificado_corresponde_a_ip(ip):
    """Comprueba si el certificado actual corresponde a la IP."""

    if not SERVER_CERT_FILE.exists():
        return False

    try:
        with open(SERVER_CERT_FILE, "rb") as f:
            cert = x509.load_pem_x509_certificate(
                f.read()
            )

        san = cert.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        )

        ips = san.value.get_values_for_type(
            x509.IPAddress
        )

        return ipaddress.ip_address(ip) in ips

    except Exception:
        return False


def https():
    """
    Prepara HTTPS para un servidor Flask local.

    Devuelve:
        ip_actual
        ssl_context
    """
    asegurar_ca()
    instalar_ca()
    ip = obtener_ip_local()

    print(f"IP local detectada: {ip}")

    if not certificado_corresponde_a_ip(ip):
        print("Generando certificado HTTPS...")
        generar_certificado_servidor(ip)
    else:
        print("Certificado HTTPS válido para la IP actual.")

    ssl_context = (
        str(SERVER_CERT_FILE),
        str(SERVER_KEY_FILE)
    )

    return ip, ssl_context
