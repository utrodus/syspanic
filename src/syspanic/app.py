import argparse
from collections.abc import Sequence

from syspanic import __version__
from syspanic.constants import APP_NAME


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="syspanic",
        description=f"{APP_NAME} — local-only, evidence-cited Linux crash diagnostics.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="use packaged synthetic demo data instead of collecting from this machine",
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    from PySide6.QtWidgets import QApplication

    from syspanic.ui.main_window import MainWindow
    from syspanic.ui.theme import apply_theme

    app = QApplication([])
    apply_theme(app)
    window = MainWindow(demo=args.demo)
    window.show()
    return app.exec()
