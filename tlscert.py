"""Lokalna certifikacna autorita (CA) a certifikat servera pre HTTPS - len standardna kniznica Pythonu.

iPhone povoli ukladanie viacerych suborov naraz (menu Zdielat) iba cez HTTPS. Na to si
pouzivatel raz nainstaluje certifikat CA. CA ma obmedzenie mien (Name Constraints):
smie vydavat certifikaty len pre sukromne IP adresy a localhost, takze ani odcudzeny
kluc CA sa neda zneuzit na podvrhnutie cudzich webov (banka, Google...).
"""
import base64
import datetime
import hashlib
import ipaddress
import json
import math
import secrets

# Siete, pre ktore smie CA vydat certifikat (domace siete, hotspot, link-local, loopback).
PERMITTED_NETS = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10",
                  "169.254.0.0/16", "127.0.0.0/8"]
CA_DAYS = 3650
LEAF_DAYS = 800  # iOS prijme certifikat servera s platnostou najviac 825 dni


# --- RSA -------------------------------------------------------------------
_SMALL_PRIMES = [p for p in range(3, 2000) if all(p % d for d in range(2, int(p ** 0.5) + 1))]


def _probable_prime(n, rounds=40):
    for p in _SMALL_PRIMES:
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for _ in range(rounds):
        x = pow(secrets.randbelow(n - 3) + 2, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _prime(bits):
    while True:
        # najvyssie dva bity nastavene -> sucin dvoch prvocisel ma presne 2*bits bitov
        c = secrets.randbits(bits) | (3 << (bits - 2)) | 1
        if _probable_prime(c):
            return c


def gen_key(bits=2048, e=65537):
    while True:
        p, q = _prime(bits // 2), _prime(bits // 2)
        phi = (p - 1) * (q - 1)
        if p != q and math.gcd(e, phi) == 1:
            return {"n": p * q, "e": e, "d": pow(e, -1, phi), "p": p, "q": q}


_SHA256_INFO = bytes.fromhex("3031300d060960864801650304020105000420")


def _sign(key, data):
    """RSASSA-PKCS1-v1_5 so SHA-256."""
    n, d, p, q = key["n"], key["d"], key["p"], key["q"]
    k = (n.bit_length() + 7) // 8
    t = _SHA256_INFO + hashlib.sha256(data).digest()
    m = int.from_bytes(b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t, "big")
    m1, m2 = pow(m, d % (p - 1), p), pow(m, d % (q - 1), q)
    s = m2 + (pow(q, -1, p) * (m1 - m2) % p) * q
    if pow(s, key["e"], n) != m:  # kontrola chyby vypoctu
        raise ValueError("RSA podpis zlyhal")
    return s.to_bytes(k, "big")


# --- DER -------------------------------------------------------------------
def _tlv(tag, content):
    n = len(content)
    if n < 0x80:
        length = bytes([n])
    else:
        b = n.to_bytes((n.bit_length() + 7) // 8, "big")
        length = bytes([0x80 | len(b)]) + b
    return bytes([tag]) + length + content


def _seq(*items):
    return _tlv(0x30, b"".join(items))


def _int(v):
    return _tlv(0x02, v.to_bytes(v.bit_length() // 8 + 1, "big"))


def _oid(dotted):
    parts = [int(x) for x in dotted.split(".")]
    out = bytes([40 * parts[0] + parts[1]])
    for p in parts[2:]:
        enc = [p & 0x7F]
        p >>= 7
        while p:
            enc.append(0x80 | (p & 0x7F))
            p >>= 7
        out += bytes(reversed(enc))
    return _tlv(0x06, out)


def _bits(b, unused=0):
    return _tlv(0x03, bytes([unused]) + b)


def _time(dt):
    if dt.year < 2050:
        return _tlv(0x17, dt.strftime("%y%m%d%H%M%SZ").encode())
    return _tlv(0x18, dt.strftime("%Y%m%d%H%M%SZ").encode())


def _name(cn):
    attr = lambda oid, val: _tlv(0x31, _seq(_oid(oid), _tlv(0x0C, val.encode())))
    return _seq(attr("2.5.4.10", "FileDrop"), attr("2.5.4.3", cn))


def _ext(oid, value, critical=False):
    return _seq(_oid(oid), _tlv(0x01, b"\xff") if critical else b"", _tlv(0x04, value))


def _pubkey_der(key):
    return _seq(_int(key["n"]), _int(key["e"]))


def _key_id(key):
    return hashlib.sha1(_pubkey_der(key)).digest()


_SIG_ALG = _seq(_oid("1.2.840.113549.1.1.11"), b"\x05\x00")  # sha256WithRSAEncryption


def _cert(subject, issuer, key, signer, days, exts):
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    spki = _seq(_seq(_oid("1.2.840.113549.1.1.1"), b"\x05\x00"), _bits(_pubkey_der(key)))
    tbs = _seq(_tlv(0xA0, _int(2)), _int(secrets.randbits(127) | 1), _SIG_ALG, issuer,
               _seq(_time(now - datetime.timedelta(days=1)), _time(now + datetime.timedelta(days=days))),
               subject, spki, _tlv(0xA3, _seq(*exts)))
    return _seq(tbs, _SIG_ALG, _bits(_sign(signer, tbs)))


def make_ca(key, label):
    subtrees = [_seq(_tlv(0x87, ipaddress.ip_network(net).network_address.packed
                          + ipaddress.ip_network(net).netmask.packed)) for net in PERMITTED_NETS]
    subtrees.append(_seq(_tlv(0x82, b"localhost")))
    exts = [
        _ext("2.5.29.19", _seq(_tlv(0x01, b"\xff")), critical=True),           # CA:TRUE
        _ext("2.5.29.15", _bits(b"\x06", 1), critical=True),                    # keyCertSign, cRLSign
        _ext("2.5.29.30", _seq(_tlv(0xA0, b"".join(subtrees))), critical=True),  # Name Constraints
        _ext("2.5.29.14", _tlv(0x04, _key_id(key))),                            # Subject Key Identifier
    ]
    name = _name(f"FileDrop Local CA ({label})")
    return _cert(name, name, key, key, CA_DAYS, exts)


def make_leaf(key, ca_key, ca_label, ips):
    san = b"".join(_tlv(0x87, ipaddress.ip_address(ip).packed) for ip in ips) + _tlv(0x82, b"localhost")
    exts = [
        _ext("2.5.29.19", _seq()),                                              # CA:FALSE
        _ext("2.5.29.15", _bits(b"\xa0", 5), critical=True),                    # digitalSignature, keyEncipherment
        _ext("2.5.29.37", _seq(_oid("1.3.6.1.5.5.7.3.1"))),                     # serverAuth
        _ext("2.5.29.17", _seq(san)),                                           # Subject Alternative Name
        _ext("2.5.29.14", _tlv(0x04, _key_id(key))),
        _ext("2.5.29.35", _seq(_tlv(0x80, _key_id(ca_key)))),                   # Authority Key Identifier
    ]
    return _cert(_name("localhost"), _name(f"FileDrop Local CA ({ca_label})"), key, ca_key, LEAF_DAYS, exts)


# --- PEM a ulozenie --------------------------------------------------------
def _pem(label, der):
    b = base64.b64encode(der).decode()
    return f"-----BEGIN {label}-----\n" + "\n".join(b[i:i + 64] for i in range(0, len(b), 64)) + f"\n-----END {label}-----\n"


def _key_pem(k):
    n, e, d, p, q = k["n"], k["e"], k["d"], k["p"], k["q"]
    der = _seq(_int(0), _int(n), _int(e), _int(d), _int(p), _int(q),
               _int(d % (p - 1)), _int(d % (q - 1)), _int(pow(q, -1, p)))
    return _pem("RSA PRIVATE KEY", der)


def _key_from_pem(text):
    der = base64.b64decode("".join(line for line in text.splitlines() if "-----" not in line))
    ints, i = [], 0
    i += 2 if der[1] < 0x80 else 2 + (der[1] & 0x7F)  # preskoc hlavicku SEQUENCE
    while i < len(der):
        ln, i = der[i + 1], i + 2
        if ln & 0x80:
            nb = ln & 0x7F
            ln, i = int.from_bytes(der[i:i + nb], "big"), i + nb
        ints.append(int.from_bytes(der[i:i + ln], "big"))
        i += ln
    _, n, e, d, p, q = ints[:6]
    return {"n": n, "e": e, "d": d, "p": p, "q": q}


def _private_ips(ips):
    nets = [ipaddress.ip_network(n) for n in PERMITTED_NETS]
    return sorted({ip for ip in ips if any(ipaddress.ip_address(ip) in net for net in nets)} | {"127.0.0.1"})


def ensure(folder, ips, label):
    """Vytvori/obnovi CA a certifikat servera. Vrati (cesta k certifikatu, cesta ku klucu, CA v DER)."""
    folder.mkdir(parents=True, exist_ok=True)
    ca_crt, ca_key_f = folder / "ca.crt", folder / "ca.key"
    srv_crt, srv_key_f, meta_f = folder / "server.crt", folder / "server.key", folder / "server.json"

    ca_label_f = folder / "ca.label"
    if ca_crt.exists() and ca_key_f.exists() and ca_label_f.exists():
        ca_key = _key_from_pem(ca_key_f.read_text())
        ca_label = ca_label_f.read_text(encoding="utf-8")
    else:
        print("  Vytváram certifikát pre HTTPS (raz, pár sekúnd)…")
        ca_key, ca_label = gen_key(), label
        ca_key_f.write_text(_key_pem(ca_key))
        ca_crt.write_text(_pem("CERTIFICATE", make_ca(ca_key, ca_label)))
        ca_label_f.write_text(ca_label, encoding="utf-8")
        meta_f.unlink(missing_ok=True)
    ca_der = base64.b64decode("".join(l for l in ca_crt.read_text().splitlines() if "-----" not in l))
    ca_fp = hashlib.sha256(ca_der).hexdigest()

    want = _private_ips(ips)
    meta = json.loads(meta_f.read_text()) if meta_f.exists() else {}
    expires = meta.get("expires", 0)
    fresh = (meta.get("ips") == want and meta.get("ca") == ca_fp and srv_crt.exists() and srv_key_f.exists()
             and expires - datetime.datetime.now().timestamp() > 30 * 86400)
    if not fresh:
        key = gen_key()
        srv_key_f.write_text(_key_pem(key))
        srv_crt.write_text(_pem("CERTIFICATE", make_leaf(key, ca_key, ca_label, want)))
        meta_f.write_text(json.dumps({"ips": want, "ca": ca_fp,
                                      "expires": datetime.datetime.now().timestamp() + (LEAF_DAYS - 1) * 86400}))
    return srv_crt, srv_key_f, ca_der
