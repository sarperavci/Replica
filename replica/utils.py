from __future__ import annotations
import re
from typing import Dict, Iterable, List
from urllib.parse import urlparse


def escape_regex(s: str) -> str:
    return re.escape(s)


def perform_text_replacements(text: str, replacements: Dict[str, str], incoming_host: str) -> str:
    result = text
    for from_str, to_str in replacements.items():
        if not from_str or to_str is None:
            continue
        if to_str == "MY_HOST":
            to_str = incoming_host
        pat = re.compile(escape_regex(from_str), re.IGNORECASE)
        result = pat.sub(to_str, result)
    return result


def is_static_file(path: str, static_extensions: List[str]) -> bool:
    parsed_path = urlparse(path).path
    return any(parsed_path.lower().endswith(ext) for ext in static_extensions)


def sanitize_request_headers(headers: Dict[str, str], my_origin: str, my_host: str, target_origin: str) -> Dict[str, str]:
    remove_patterns = [
        re.compile(r"^cf-", re.IGNORECASE),
        re.compile(r"^cdn-loop$", re.IGNORECASE),
        re.compile(r"^x-forwarded-", re.IGNORECASE),
        re.compile(r"^x-real-ip$", re.IGNORECASE),
        re.compile(r"^via$", re.IGNORECASE),
        re.compile(r"^x-amzn-", re.IGNORECASE),
        re.compile(r"^x-request-id$", re.IGNORECASE),
    ]

    sanitized: Dict[str, str] = {}

    my_origin_re = re.compile(escape_regex(my_origin), re.IGNORECASE)
    my_host_re = re.compile(escape_regex(my_host), re.IGNORECASE)

    for name, value in headers.items():
        if any(p.match(name) for p in remove_patterns):
            continue
        if isinstance(value, str):
            value = my_origin_re.sub(target_origin, value)
            value = my_host_re.sub(target_origin.split("//")[-1].split("/")[0], value)
        sanitized[name] = value
    return sanitized


def sanitize_response_headers(headers: Dict[str, str], target_origin: str, target_host: str, my_origin: str, my_host: str) -> Dict[str, str]:
    remove_patterns = [
        re.compile(r"^cf-", re.IGNORECASE),
        re.compile(r"^cdn-loop$", re.IGNORECASE),
        re.compile(r"^x-forwarded-", re.IGNORECASE),
        re.compile(r"^cf-ray$", re.IGNORECASE),
        re.compile(r"^cf-visitor$", re.IGNORECASE),
        re.compile(r"^cf-cache-status$", re.IGNORECASE),
        re.compile(r"^via$", re.IGNORECASE),
    ]

    sanitized: Dict[str, str] = {}

    target_origin_re = re.compile(escape_regex(target_origin), re.IGNORECASE)
    target_host_re = re.compile(escape_regex(target_host), re.IGNORECASE)

    for name, value in headers.items():
        if any(p.match(name) for p in remove_patterns):
            continue
        if isinstance(value, str):
            value = target_origin_re.sub(my_origin, value)
            value = target_host_re.sub(my_host, value)
            if name.lower() == "set-cookie" and "Domain=" in value:
                value = re.sub(f"Domain={escape_regex(target_host)}", f"Domain={my_host}", value, flags=re.IGNORECASE)
        sanitized[name] = value

    # Remove or adjust headers that break proxies
    sanitized.pop("content-security-policy", None)
    sanitized.pop("content-security-policy-report-only", None)
    sanitized.pop("clear-site-data", None)
    sanitized.pop("content-length", None)
    sanitized.pop("transfer-encoding", None)
    sanitized.pop("content-encoding", None)

    return sanitized
