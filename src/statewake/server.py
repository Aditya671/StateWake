"""Dependency-free, bounded HTTP adapter for StateWake verification."""

from __future__ import annotations

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingParameterType=false
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, cast
from wsgiref.simple_server import make_server
from wsgiref.types import StartResponse, WSGIApplication, WSGIEnvironment

from . import __version__
from .public_api import load_evidence_chain, verify_evidence_chain
from .services.reliability_proof_bundle_service import verify_reliability_proof_bundle


@dataclass(frozen=True, slots=True)
class VerificationServiceConfig:
    """Explicit security boundary for the WSGI verification adapter."""

    artifact_roots: tuple[Path, ...] = ()
    max_request_bytes: int = 1_048_576
    read_only: bool = True
    require_https: bool = True
    allow_insecure_http: bool = False

    def __post_init__(self) -> None:
        """Validate and normalize the instance after initialization."""
        if self.max_request_bytes <= 0:
            raise ValueError("max_request_bytes must be positive")
        if not self.read_only:
            raise ValueError("the verification adapter is read-only")
        if self.allow_insecure_http:
            object.__setattr__(self, "require_https", False)
        roots = tuple(path.resolve() for path in self.artifact_roots)
        object.__setattr__(self, "artifact_roots", roots)

    @classmethod
    def from_environment(cls) -> VerificationServiceConfig:
        """Build HTTP verification configuration from environment variables."""
        raw_roots = os.environ.get("STATEWAKE_VERIFICATION_ARTIFACT_ROOTS", "")
        roots = tuple(
            Path(item) for item in raw_roots.split(os.pathsep) if item.strip()
        )
        allow_insecure = os.environ.get(
            "STATEWAKE_ALLOW_INSECURE_HTTP", "0"
        ).lower() in {"1", "true", "yes"}
        return cls(artifact_roots=roots, allow_insecure_http=allow_insecure)

    def resolve_allowed(self, value: str) -> Path:
        """Resolve one client path only when it is contained by an allowed root."""
        candidate = Path(value).resolve()
        for root in self.artifact_roots:
            try:
                candidate.relative_to(root)
                return candidate
            except ValueError:
                continue
        raise PermissionError("artifact path is outside configured verification roots")


def _json_response(
    start_response: StartResponse,
    status: str,
    payload: dict[str, Any],
) -> list[bytes]:
    """Build a JSON HTTP response for the supplied payload."""
    body = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
    start_response(
        status,
        [("Content-Type", "application/json"), ("Content-Length", str(len(body)))],
    )
    return [body]


def _error(
    start_response: StartResponse,
    status: str,
    code: str,
    message: str,
) -> list[bytes]:
    """Build a JSON HTTP error response for the supplied message."""
    return _json_response(
        start_response, status, {"error": {"code": code, "message": message}}
    )


def create_application(
    config: VerificationServiceConfig | None = None,
) -> WSGIApplication:
    """Create a bounded WSGI verification application."""
    cfg = config or VerificationServiceConfig.from_environment()

    def application(
        environ: WSGIEnvironment,
        start_response: StartResponse,
    ) -> list[bytes]:
        """Handle one WSGI verification request."""
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/")
        if method == "GET" and path == "/health":
            return _json_response(
                start_response, "200 OK", {"status": "ok", "version": __version__}
            )
        if method == "GET" and path == "/v1/version":
            return _json_response(start_response, "200 OK", {"version": __version__})
        if method != "POST" or path not in {"/v1/evidence/verify", "/v1/proof/verify"}:
            return _error(start_response, "404 Not Found", "NOT_FOUND", "not found")
        if (
            cfg.require_https
            and environ.get("wsgi.url_scheme", "http").lower() != "https"
        ):
            return _error(
                start_response,
                "400 Bad Request",
                "HTTPS_REQUIRED",
                "HTTPS is required for verification requests",
            )
        if not cfg.artifact_roots:
            return _error(
                start_response,
                "503 Service Unavailable",
                "VERIFICATION_ROOTS_UNCONFIGURED",
                "verification artifact roots are not configured",
            )

        try:
            raw_length = environ.get("CONTENT_LENGTH")
            if raw_length is None:
                return _error(
                    start_response,
                    "411 Length Required",
                    "CONTENT_LENGTH_REQUIRED",
                    "Content-Length is required",
                )
            length = int(raw_length)
            if length < 0 or length > cfg.max_request_bytes:
                return _error(
                    start_response,
                    "413 Request Entity Too Large",
                    "REQUEST_TOO_LARGE",
                    "request body exceeds configured maximum",
                )
            stream = cast(BinaryIO, environ["wsgi.input"])
            raw = stream.read(length)
            if len(raw) != length:
                return _error(
                    start_response,
                    "400 Bad Request",
                    "INCOMPLETE_BODY",
                    "request body is incomplete",
                )
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("request body must be a JSON object")

            if path == "/v1/evidence/verify":
                chain_path = cfg.resolve_allowed(str(payload["chain_path"]))  # type: ignore
                evidence_root = cfg.resolve_allowed(str(payload["evidence_root"]))  # type: ignore
                chain = load_evidence_chain(chain_path)
                verify_evidence_chain(chain, root=evidence_root)
                return _json_response(
                    start_response,
                    "200 OK",
                    {
                        "verified": True,
                        "chain_id": chain.chain_id,
                        "digest": chain.digest(),
                    },
                )

            bundle_path = cfg.resolve_allowed(str(payload["bundle_path"]))
            report, descriptor = verify_reliability_proof_bundle(bundle_path)
            status = "200 OK" if report.verified else "422 Unprocessable Entity"
            return _json_response(
                start_response,
                status,
                {
                    "verified": report.verified,
                    "bundle_type": descriptor.bundle_type,
                    "subject_id": descriptor.subject_id,
                    "attestation_id": descriptor.attestation_id,
                    "checks": list(report.checks),
                    "failures": list(report.failures),
                },
            )
        except PermissionError:
            return _error(
                start_response,
                "403 Forbidden",
                "PATH_OUTSIDE_ROOT",
                "artifact path is outside configured verification roots",
            )
        except FileNotFoundError:
            return _error(
                start_response,
                "404 Not Found",
                "ARTIFACT_NOT_FOUND",
                "referenced verification artifact was not found",
            )
        except json.JSONDecodeError:
            return _error(
                start_response,
                "400 Bad Request",
                "INVALID_JSON",
                "request body is not valid JSON",
            )
        except (KeyError, TypeError, ValueError):
            return _error(
                start_response,
                "422 Unprocessable Entity",
                "INVALID_REQUEST",
                "verification request is invalid",
            )
        except OSError:
            return _error(
                start_response,
                "422 Unprocessable Entity",
                "ARTIFACT_UNREADABLE",
                "referenced verification artifact could not be read",
            )

    return application


application = create_application()
app = application


def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    """Run the local WSGI verification adapter."""
    with make_server(host, port, application) as httpd:
        print(
            f"StateWake {__version__} verification adapter listening on http://{host}:{port} (configure a TLS-terminating host for HTTPS)"
        )
        httpd.serve_forever()


if __name__ == "__main__":
    serve()
