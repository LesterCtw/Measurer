import os
import sys

import pytest
from PySide6.QtWidgets import QApplication


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    return app
