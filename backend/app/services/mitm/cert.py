"""Root CA + per-host leaf certificates."""

from __future__ import annotations

import datetime
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from app.services.mitm.paths import CA_CERT, CA_KEY, cert_files_exist


def generate_root_ca(force: bool = False) -> Path:
    """Write rootCA.crt / rootCA.key. Skip if both exist unless force."""
    if cert_files_exist() and not force:
        return CA_CERT

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "9Router MITM Root CA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "9Router"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    CA_KEY.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    CA_CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return CA_CERT


def _load_ca() -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    cert = x509.load_pem_x509_certificate(CA_CERT.read_bytes())
    key = serialization.load_pem_private_key(CA_KEY.read_bytes(), password=None)
    return cert, key  # type: ignore[return-value]


def generate_leaf_cert(hostname: str) -> tuple[bytes, bytes]:
    """Return (cert_pem, key_pem) signed by the Root CA."""
    if not cert_files_exist():
        generate_root_ca()
    ca_cert, ca_key = _load_ca()
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.datetime.now(datetime.timezone.utc)
    san: list[x509.GeneralName] = [x509.DNSName(hostname)]
    try:
        san.append(x509.IPAddress(ipaddress.ip_address(hostname)))
    except ValueError:
        pass
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        ]))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return cert_pem, key_pem
