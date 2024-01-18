import sys
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *


def window():
    app = QApplication(sys.argv)
    win = QWidget()
    fbox = QFormLayout()
    win.setLayout(fbox)

    # 第一行
    l1 = QLabel("Name")
    nm = QLineEdit()
    fbox.addRow(l1, nm)

    # 第二行，包含一个子布局QVBoxLayout
    vbox = QVBoxLayout()
    l2 = QLabel("Address")
    add1 = QLineEdit()
    add2 = QLineEdit()
    vbox.addWidget(add1)
    vbox.addWidget(add2)
    fbox.addRow(l2, vbox)

    # 第三行，包含一个子布局QHBoxLayout
    hbox = QHBoxLayout()
    r1 = QRadioButton("Male")
    r2 = QRadioButton("Female")
    hbox.addWidget(r1)
    hbox.addWidget(r2)
    hbox.addStretch()
    fbox.addRow(QLabel("sex"), hbox)

    fbox.addRow(QPushButton("Submit"), QPushButton("Cancel"))

    win.setWindowTitle("PyQt")
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    window()
