import base64
import hashlib
import hmac
import json
import time


class OAuthError(Exception):
    pass


class OAuthFlow:
    """State for one in-progress sign-in.

    Our pods are stateless, so the whole flow object rides along in the
    session cookie between /auth/login and /auth/callback.
    """

    def __init__(self, client_id, client_secret, redirect_uri, scopes, state,
                 next_url="/", debug_note=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = list(scopes)
        self.state = state
        self.next_url = next_url
        self.created_at = int(time.time())
        self.debug_note = debug_note

    def exchange_code(self, code):
        """Validate an authorization code from the IdP and return the user."""
        try:
            payload_b64, sig = code.split(".", 1)
            payload = base64.urlsafe_b64decode(payload_b64 + "==")
        except ValueError as exc:
            raise OAuthError("malformed code") from exc

        expected = sign_code(self.client_secret, payload)
        if not hmac.compare_digest(sig, expected):
            raise OAuthError("bad code signature")

        userinfo = json.loads(payload)
        if userinfo.get("aud") != self.client_id:
            raise OAuthError("code issued to another client")
        if time.time() - userinfo.get("iat", 0) > 300:
            raise OAuthError("code expired")
        return userinfo


def sign_code(client_secret, payload):
    return hmac.new(client_secret.encode(), payload, hashlib.sha256).hexdigest()


def issue_code(client_id, client_secret, email, name):
    payload = json.dumps({
        "aud": client_id,
        "email": email,
        "name": name,
        "iat": int(time.time()),
    }).encode()
    payload_b64 = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"{payload_b64}.{sign_code(client_secret, payload)}"
