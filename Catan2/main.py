import sys
from PyQt5.QtWidgets import QApplication
from client.loginwindow import LoginWindow

def main():
    app = QApplication(sys.argv)
    window = LoginWindow()  # Normal window, user can maximize manually
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()