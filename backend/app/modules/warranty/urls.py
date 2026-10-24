from urllib.parse import quote, urlparse


def _host(value: str) -> str:
    try:
        return (urlparse(value).hostname or "").lower()
    except ValueError:
        return ""


def _is_local(value: str) -> bool:
    return _host(value) in {"127.0.0.1", "localhost", "::1"}


def resolve_warranty_base(configured: str, request_base_url: str) -> str:
    """Resolve the public warranty React base, with a safe same-host fallback for local defaults."""
    value = configured.rstrip("/")
    if _is_local(value):
        return f"{request_base_url.rstrip('/')}/warranty"
    return value


def resolve_qr_base(configured: str | None, request_base_url: str) -> str:
    """Return the stable public resolver base encoded into newly printed QR codes."""
    value = (configured or "").strip().rstrip("/")
    if not value or _is_local(value):
        return request_base_url.rstrip("/")
    return value


def qr_resolver_url(serial: str, configured_qr_base: str | None, request_base_url: str) -> str:
    return f"{resolve_qr_base(configured_qr_base, request_base_url)}/q/{quote(serial, safe='')}"


def dynamic_qr_destination(serial: str, configured_warranty_base: str, template: str | None, request_base_url: str) -> str:
    """Resolve the current destination for a serial. Changing this setting never requires reprinting QR labels."""
    if template and template.strip():
        value = template.strip()
        encoded = quote(serial, safe="")
        return value.replace("{serial}", encoded)
    return f"{resolve_warranty_base(configured_warranty_base, request_base_url)}/{quote(serial, safe='')}"
