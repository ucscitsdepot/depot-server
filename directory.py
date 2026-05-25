import base64
import re

import requests

_session = requests.Session()


def lookup_cruzid(name: str) -> str | None:
    r = _session.get("https://campusdirectory.ucsc.edu/cd_simple")
    csrf_name = re.search(r"name='CSRFName' value='([^']+)'", r.text)
    csrf_token = re.search(r"name='CSRFToken' value='([^']+)'", r.text)
    if not csrf_name or not csrf_token:
        return None

    r2 = _session.post(
        "https://campusdirectory.ucsc.edu/cd_simple",
        data={
            "CSRFName": csrf_name.group(1),
            "CSRFToken": csrf_token.group(1),
            "keyword": name,
            "Action": "Find",
            "affiliation": "All",
        },
    )

    # Only trust the result if exactly one record matched
    if "1  record matched" not in r2.text:
        return None

    b64 = re.search(r"Base64\.decode\('([^']+)'\)", r2.text)
    if not b64:
        return None

    decoded = base64.b64decode(b64.group(1)).decode()
    match = re.search(r"mailto:([^@]+)@ucsc\.edu", decoded)
    return match.group(1) if match else None
