"""Arsenal security platform — command-line interface.

A small, modular CLI that turns Arsenal from a collection of tools into a
cohesive platform: diagnostics (`doctor`), maintenance (`update`), support
bundles (`reportbug`), an AI assistant, workflow orchestration, reporting,
a dashboard and curated profiles.

The package is intentionally dependency-light: the foundation uses only the
Python standard library. Optional features (PDF export, local AI) detect their
extras at runtime and degrade gracefully when they are not installed.
"""

__all__ = ["__version__"]

# Version of the CLI itself (distinct from the Arsenal OS build, which is
# resolved at runtime by ``arsenal_cli.version.os_version``).
__version__ = "0.1.0"
