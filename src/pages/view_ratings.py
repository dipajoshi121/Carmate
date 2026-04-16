import os
import traceback
from pathlib import Path

import streamlit as st

from ui_helpers import log_bug, render_footer_bug_panel

st.set_page_config(page_title="Carmate - View ratings", page_icon="", layout="centered")

BASE_DIR = Path(__file__).resolve().parent
CSS_PATH = BASE_DIR / "resources" / "carmate.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

st.title("View ratings")
st.write(
    "Average ratings from completed service requests. Each completed job can receive one customer review."
)

if not os.environ.get("DATABASE_URL"):
    st.warning("Set **DATABASE_URL** to load ratings from the database.")
else:
    try:
        from db import list_businesses_with_ratings, DatabaseError

        rows = list_businesses_with_ratings()
    except DatabaseError as e:
        st.error(str(e))
        rows = []
        log_bug("view ratings DB", str(e))
    except Exception:
        st.error("Could not load ratings.")
        log_bug("view ratings", traceback.format_exc())
        rows = []
    else:
        if not rows:
            st.info("No business profiles found yet.")
        else:
            for row in rows:
                name = (row.get("full_name") or "").strip() or (row.get("email") or "Shop")
                cnt = int(row.get("review_count") or 0)
                avg = row.get("avg_rating")
                with st.container(border=True):
                    st.markdown(f"**{name}**")
                    if cnt > 0 and avg is not None:
                        avg_f = float(avg)
                        stars = min(5, max(1, int(round(avg_f))))
                        st.markdown("**" + "★" * stars + "☆" * (5 - stars) + f"** ({avg_f:.2f} / 5)")
                        st.caption(f"Based on **{cnt}** review(s).")
                    else:
                        st.caption("No reviews yet.")

render_footer_bug_panel()
