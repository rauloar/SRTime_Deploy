import sys
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QPushButton
from ui.tabs.users_tab import UsersTab
from core.database import SessionLocal
from models.employee import User
from PySide6.QtCore import QTimer

def test():
    app = QApplication(sys.argv)
    session = SessionLocal()
    tab = UsersTab(session)
    
    # Grab the first user id
    first_user = session.query(User).first()
    original_fn = first_user.first_name
    print(f"Targeting User ID {first_user.id}, Original FN={original_fn}")
    
    # We will trigger edit_user_by_id
    # But to prevent exec_ from blocking forever, we use a single shot timer
    
    def on_dialog_open():
        print("Dialog opened!")
        # Find the active dialog
        dialog = app.activeModalWidget()
        if not dialog:
            dialog = app.activeWindow()
            
        print(f"Active widget: {dialog}")
        if isinstance(dialog, QDialog):
            # Find line edits
            line_edits = dialog.findChildren(QLineEdit)
            if len(line_edits) >= 3:
                le_first = line_edits[1]
                le_last = line_edits[2]
                le_first.setText("TEST_FIRSTNAME")
                le_last.setText("TEST_LASTNAME")
                print("Set text to TEST_FIRSTNAME")
                
                # Find ok button
                btns = dialog.findChildren(QPushButton)
                for btn in btns:
                    if btn.text() == "Guardar":
                        print("Clicking Guardar")
                        btn.click()
                        return
                        
            print("Could not find inputs or save button")
            dialog.reject()
            
    QTimer.singleShot(500, on_dialog_open)
    QTimer.singleShot(2000, app.quit)
    
    tab.edit_user_by_id(first_user.id)
    app.exec()
    
    # Check if DB was updated
    session2 = SessionLocal()
    u2 = session2.query(User).filter_by(id=first_user.id).first()
    print(f"After test: User ID {u2.id}, FN={u2.first_name}, LN={u2.last_name}")

if __name__ == "__main__":
    test()
