"""Jazz Jackrabbit 1 DOS level editor package."""

__all__ = ["main"]


def main(argv=None):
    from .app import main as app_main

    return app_main(argv)

