"""demimove-ui

Usage:
    dmv-ui [-d <dir>] [-c <file>] [-v...] [-q] [-h]

Options:
    -c, --config=<file>  Specify a config file to load.
    -d, --dir=<dir>      Specify a directory to load.
    -v                   Logging verbosity level, up to -vvv.
    -q, --quiet          Do not print logging messages to console.
    -h,  --help          Show this help text and exit.
    --version            Show the current demimove-ui version.
"""
# TODO: ConfigParser
import sys

from PyQt4 import QtGui, QtCore, uic

import reporting


try:
    from docopt import docopt
except ImportError:
    print "ImportError: Please install docopt to use the CLI."


class DemiMoveGUI(QtGui.QMainWindow):

    def __init__(self, parent=None):

        super(DemiMoveGUI, self).__init__(parent)
        uic.loadUi("demimove.ui", self)

        self.setWindowIcon(QtGui.QIcon("icon.png"))
        self.mainsplitter.setStretchFactor(0, 0)
        self.mainsplitter.setStretchFactor(1, 2)

        self.create_dirtree()
        self.create_browsertree()
        log.info("demimove initialized.")


    def create_dirtree(self):
        # Passing self as arg/parent here to avoid QTimer errors.
        self.dirmodel = QtGui.QFileSystemModel(self)
        self.dirmodel.setRootPath("")
        self.dirmodel.setFilter(QtCore.QDir.AllDirs | QtCore.QDir.Hidden |
                                QtCore.QDir.NoDotAndDotDot)
        self.dirmodel.fileRenamed.connect(self.on_rootchange)
        self.dirmodel.rootPathChanged.connect(self.on_rootchange)
        self.dirmodel.directoryLoaded.connect(self.on_rootchange)

        self.dirtree.setModel(self.dirmodel)
        self.dirtree.setColumnHidden(1, True)
        self.dirtree.setColumnHidden(2, True)
        self.dirtree.setColumnHidden(3, True)


    def create_browsertree(self):
        self.browsermodel = QtGui.QFileSystemModel(self)
        self.browsermodel.setRootPath("")
        self.browsermodel.setFilter(QtCore.QDir.Dirs | QtCore.QDir.Files |
                                    QtCore.QDir.NoDotAndDotDot |
                                    QtCore.QDir.Hidden)

        self.browsertree.setModel(self.browsermodel)

    def on_rootchange(self, *args):
        print self.sender()


def main():
    "Main entry point for demimove."
    app = QtGui.QApplication(sys.argv)
    app.setApplicationName("demimove")
#     app.setStyle("plastique")
    gui = DemiMoveGUI()
    gui.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    log = reporting.create_logger()

    try:
        args = docopt(__doc__, version="0.1")
        reporting.configure_logger(log, args["-v"], args["--quiet"])
    except NameError:
        reporting.configure_logger(log, loglevel=2, quiet=False)
        log.error("Please install docopt to use the CLI.")

    main()