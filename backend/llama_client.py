"""DEPRECATED shim.

The legacy `llama_client` implementation was removed in favor of a container
based llama.cpp HTTP server and the new `llm_client` module. Keep this file
only to avoid import-time failures in older deployments.
"""

raise ImportError("llama_client has been removed; use backend.llm_client and run a llama server container.")
