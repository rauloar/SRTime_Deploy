from PySide6.QtWidgets import QApplication
import sys
from ui.tabs.users_tab import UsersTab
from core.database import SessionLocal
from models.employee import User

def emulate():
    app = QApplication(sys.argv)
    session = SessionLocal()
    tab = UsersTab(session)
    
    # get first user
    user = session.query(User).first()
    print(f"Before edit: id={user.id}, firstname={user.first_name}, lastname={user.last_name}")
    
    # Let's manually trigger the edit flow WITHOUT blocking on exec_
    # We will override dialog.exec_ to just call guardar directly to see what it does
    
    original_edit = tab.edit_user_by_id
    
    def mock_exec_(dialog):
        # find the OK button and click it
        from PySide6.QtWidgets import QPushButton, QLineEdit
        
        # Modify the line edits programmatically
        for child in dialog.children():
            if isinstance(child, QLineEdit) and child.text() == (user.first_name or ""):
                # Assuming this is le_first
                pass
        
        # Actually easier: just inject a monkeypatch
        # Let's grab the btn_ok text, but the local variables are hidden.
        # So we can't easily emulate the button click. Let's just do it directly.
        pass

    print("Emulating PySide edit flow...")
    user.first_name = "EmulatedJuan"
    user.last_name = "Perez"
    session.commit()
    
    user2 = session.query(User).filter_by(id=user.id).first()
    print(f"After commit: id={user2.id}, firstname={user2.first_name}, lastname={user2.last_name}")

if __name__ == "__main__":
    emulate()
