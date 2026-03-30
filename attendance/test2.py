import sys
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QPushButton
from ui.tabs.users_tab import UsersTab
from core.database import SessionLocal
from models.employee import User
from PySide6.QtCore import QTimer
import time

def test():
    app = QApplication(sys.argv)
    session = SessionLocal()
    tab = UsersTab(session)
    
    first_user = session.query(User).filter_by(id=5).first()
    print(f"Targeting User {first_user.id}, FN={first_user.first_name}")
    
    # We will patch QMessageBox to avoid blocking
    from PySide6.QtWidgets import QMessageBox
    QMessageBox.information = lambda *args, **kwargs: None
    QMessageBox.warning = lambda *args, **kwargs: None
    
    def on_dialog_open():
        dialog = app.activeModalWidget()
        if not dialog: dialog = app.activeWindow()
        
        if isinstance(dialog, QDialog):
            line_edits = dialog.findChildren(QLineEdit)
            line_edits[1].setText("TEST_FIRSTNAME")
            line_edits[2].setText("TEST_LASTNAME")
            print(f"I typed TEST_FIRSTNAME. current text()={line_edits[1].text()}")
            
            btns = dialog.findChildren(QPushButton)
            for btn in btns:
                if btn.text() == "Guardar":
                    print("Clicking Guardar...")
                    btn.click()
                    return
            dialog.reject()
            
    QTimer.singleShot(200, on_dialog_open)
    QTimer.singleShot(1000, app.quit)
    
    tab.edit_user_by_id(first_user.id)
    app.exec()
    
    session2 = SessionLocal()
    u2 = session2.query(User).filter_by(id=5).first()
    print(f"After test: User ID {u2.id}, FN={u2.first_name}, LN={u2.last_name}")

if __name__ == "__main__":
    test()
