#!/usr/bin/env python3
"""Launch marbles by MJD, or run its portable installation smoke check."""
import multiprocessing
import sys


def main():
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from marbledesk.studio.branding import APP_NAME, icon_path
    from marbledesk.studio.window import StudioWindow

    application = QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setApplicationDisplayName(APP_NAME)
    application.setOrganizationName('MJD')
    application.setWindowIcon(QIcon(str(icon_path())))
    window = StudioWindow()
    window.show()
    if '--smoke-test' in sys.argv:
        from marbledesk.studio.smoke import run_smoke
        return run_smoke(application, window)
    return application.exec()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    try:
        exit_code = main()
    except Exception:
        import os
        from pathlib import Path
        import traceback
        report = traceback.format_exc()
        output = os.environ.get('MARBLE_SMOKE_OUTPUT')
        if output:
            destination = Path(output)
            destination.mkdir(parents=True, exist_ok=True)
            (destination / 'startup-error.txt').write_text(report, encoding='utf-8')
        elif sys.stderr is not None:
            sys.stderr.write(report)
        exit_code = 1
    sys.exit(exit_code)
