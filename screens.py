# screens.py

import os
from fastapi import HTTPException

# белый список экранов - контролируем, какие шаблоны можно рендерить
ALLOWED_SCREENS = {"home", "feed", "map", "chat", "profile", "profile_edit", "user_profile_view"}

def safe_screen_template(name: str, SCREENS_TEMPLATES_DIR) -> str:
    if name not in ALLOWED_SCREENS:
        raise HTTPException(status_code=404, detail="screen not allowed")
    tmpl_path = os.path.join(SCREENS_TEMPLATES_DIR, f"{name}.html")
    if not os.path.exists(tmpl_path):
        raise HTTPException(status_code=404, detail="screen template missing")
    return f"screens/{name}.html"