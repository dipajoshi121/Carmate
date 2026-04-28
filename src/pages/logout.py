"""Sign out and return to the home page."""
import sys
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from ui_helpers import perform_logout

st.set_page_config(page_title="Carmate - Log out", page_icon="", layout="centered")

perform_logout()
st.switch_page("home.py")
