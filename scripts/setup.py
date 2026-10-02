"""Prepare isolated local credentials and synthetic Keycloak identities."""
from pathlib import Path
import json
import secrets

root = Path(__file__).resolve().parents[1]
env_file = root / ".env"
if not env_file.exists():
    env_file.write_text(
        f"DB_PASSWORD={secrets.token_urlsafe(32)}\n"
        f"KC_ADMIN_PASSWORD={secrets.token_urlsafe(32)}\n"
        f"LAB_USER_PASSWORD={secrets.token_urlsafe(24)}\n",
        encoding="utf-8",
    )
values = dict(line.split("=", 1) for line in env_file.read_text().splitlines() if "=" in line)
roles = {"alice": ["admin", "reader", "writer"], "bob": ["reader", "writer"], "guest": []}
realm = {
    "realm": "banking-lab", "enabled": True, "sslRequired": "none",
    "registrationAllowed": False, "resetPasswordAllowed": False,
    "roles": {"realm": [{"name": name} for name in ("admin", "reader", "writer")]},
    "clients": [{
        "clientId": "banking-lab", "enabled": True, "publicClient": True,
        "standardFlowEnabled": True, "directAccessGrantsEnabled": True,
        "redirectUris": ["http://localhost:19080/*"],
        "protocol": "openid-connect",
        "protocolMappers": [{
            "name": "banking-audience", "protocol": "openid-connect",
            "protocolMapper": "oidc-audience-mapper",
            "config": {"included.client.audience": "banking-lab", "access.token.claim": "true", "id.token.claim": "false"},
        }],
    }],
    "users": [{
        "username": name, "enabled": True, "emailVerified": True,
        "firstName": name.title(), "lastName": "Synthetic",
        "email": f"{name}@example.invalid", "realmRoles": assigned,
        "credentials": [{"type": "password", "value": values["LAB_USER_PASSWORD"], "temporary": False}],
    } for name, assigned in roles.items()],
}
destination = root / "artifacts" / "keycloak"
destination.mkdir(parents=True, exist_ok=True)
(destination / "realm.json").write_text(json.dumps(realm, indent=2), encoding="utf-8")
print("Local configuration ready; credentials kept in ignored .env and artifacts/.")
