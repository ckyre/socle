import socket

import pytest

from socle.serve import SAFE_DEFAULTS, dual_stack_socket


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _connect(family, addr, port):
    with socket.socket(family, socket.SOCK_STREAM) as c:
        c.settimeout(2)
        c.connect((addr, port))


def _ipv6_available() -> bool:
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            s.bind(("::1", 0))
        return True
    except OSError:
        return False


def test_dual_stack_accepts_ipv4_and_ipv6():
    if not _ipv6_available():
        pytest.skip("IPv6 indisponible sur cette machine")
    port = _free_port()
    sock = dual_stack_socket("::", port)
    try:
        _connect(socket.AF_INET, "127.0.0.1", port)  # test de santé de Railway
        _connect(socket.AF_INET6, "::1", port)        # réseau privé de Railway
    finally:
        sock.close()


def test_ipv4_only_host():
    port = _free_port()
    sock = dual_stack_socket("0.0.0.0", port)
    try:
        assert sock.family == socket.AF_INET
        _connect(socket.AF_INET, "127.0.0.1", port)
    finally:
        sock.close()


def test_bind_error_closes_socket():
    port = _free_port()
    first = dual_stack_socket("0.0.0.0", port)
    try:
        with pytest.raises(OSError):
            # SO_REUSEADDR ne permet pas deux écoutes actives sur le même port.
            dual_stack_socket("0.0.0.0", port)
    finally:
        first.close()


def test_safe_defaults():
    assert SAFE_DEFAULTS["server_header"] is False
    assert SAFE_DEFAULTS["proxy_headers"] is False
