"""
`AnthropicBackend` -- v1's one implemented backend (R-ENDPOINT-003).

Dispatches via the `claude` CLI's non-interactive mode rather than a
from-scratch API client (D45/D46). Credential resolution is a plain
process-environment lookup of `ANTHROPIC_API_KEY` (VAR-ANTHROPIC-API-KEY)
-- the same variable the CLI itself already reads by default, so no
second, separately-provisioned secret and no vault/secrets-manager
indirection (D18/D20). The credential is never read into a string this
module constructs a log line or error message from (R-ENDPOINT-005); it
reaches the `claude` process only via the inherited environment.

No retry-with-backoff and no unbounded wait (R-ENDPOINT-004): the CLI
invocation is bounded by a client-side subprocess timeout, and a failure
is reported exactly once as a structured `model_call_error`, never an
internal attempt loop.
"""

import os
import subprocess

# Client-side bound enforcing R-ENDPOINT-004's "no unbounded wait"
# guarantee -- the `claude` CLI itself does not promise one, so this
# backend imposes its own.
_TIMEOUT_SECONDS = 120

_ERROR_CATEGORIES = ("network", "auth", "rate_limit", "timeout")


class AnthropicBackend:
    """
    Callable backend: `backend(prompt, model, **params) -> (text, error)`,
    exactly one of which is populated. `**params` is forwarded untouched
    as CLI flags -- this component does not interpret or validate them;
    a param the CLI rejects surfaces as a `model_call_error`, same as any
    other backend failure.
    """

    name = "anthropic"

    def __call__(self, prompt, model, **params):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return None, {
                "category": "auth",
                "message": "ANTHROPIC_API_KEY is not set in the environment.",
            }

        cmd = ["claude", "--print", "--model", model]
        for key, value in params.items():
            cmd.append(f"--{str(key).replace('_', '-')}")
            cmd.append(str(value))

        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return None, {
                "category": "timeout",
                "message": (
                    f"claude CLI did not respond within {_TIMEOUT_SECONDS}s."
                ),
            }
        except FileNotFoundError:
            return None, {
                "category": "network",
                "message": "claude CLI is not available on this system.",
            }
        except OSError:
            return None, {
                "category": "network",
                "message": "Failed to invoke the claude CLI.",
            }

        if result.returncode == 0:
            return result.stdout, None

        return None, self._classify_failure(result.returncode, result.stderr)

    @staticmethod
    def _classify_failure(returncode, stderr):
        """
        Normalize a nonzero CLI exit into one of R-ENDPOINT-004's four
        categories. The message is deliberately generic -- never the raw
        vendor/CLI stderr text, which could itself echo back request
        details -- satisfying R-ENDPOINT-005's credential boundary by
        construction rather than by scrubbing.
        """
        lowered = (stderr or "").lower()

        if "rate limit" in lowered or "429" in lowered:
            category = "rate_limit"
        elif any(
            marker in lowered
            for marker in ("auth", "401", "403", "api key", "api-key")
        ):
            category = "auth"
        elif "timeout" in lowered or "timed out" in lowered:
            category = "timeout"
        else:
            category = "network"

        return {
            "category": category,
            "message": f"claude CLI exited with status {returncode}.",
        }