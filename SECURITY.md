# Security

## Reporting

If you believe you have found a **security vulnerability** (for example, unsafe handling of credentials or a way to bypass localhost binding in `audctl serve`), please report it privately to the repository maintainers using GitHub **Security advisories** (repository **Security** tab), if that feature is enabled for the repo.

Do not post exploit details in public issues until maintainers have had time to respond.

## Known design choices

- **`audctl serve`** has **no authentication** by default. It is meant for **127.0.0.1** or trusted networks only. Treat exposure like leaving an unlocked local RPC port.
- If you set **`AUDCTL_HTTP_TOKEN`**, clients must send **`Authorization: Bearer <token>`** for all routes except **`GET /`** and **`GET /health`** (discovery/liveness). **`GET /`** remains unauthenticated by design for local discovery; do not expose the listener to untrusted networks.
- **API credentials** are stored under the user’s XDG state directory; file permissions are tightened on POSIX where possible.
- The **`audible`** PyPI dependency talks to Amazon’s internal-style APIs; supply-chain and dependency updates should be reviewed like any other dependency.
