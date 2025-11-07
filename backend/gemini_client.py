"""DEPRECATED shim.

The legacy `gemini_client` implementation was removed in favor of using a
container-based Llama server and the new `llm_client` module. Keep this file
only to avoid import-time failures in older deployments.
"""

raise ImportError("gemini_client has been removed; use backend.llm_client and run a llama server container.")
