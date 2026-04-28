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
        from db import list_businesses_with_ratings, list_reviews_for_business, DatabaseError

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
                address = (row.get("address") or "").strip()
                cnt = int(row.get("review_count") or 0)
                avg = row.get("avg_rating")
                with st.container(border=True):
                    st.markdown(f"**{name}**")
                    if address:
                        st.caption(address)
                    if cnt > 0 and avg is not None:
                        avg_f = float(avg)
                        stars = min(5, max(1, int(round(avg_f))))
                        st.markdown("**" + "★" * stars + "☆" * (5 - stars) + f"** ({avg_f:.2f} / 5)")
                        st.caption(f"Based on **{cnt}** review(s).")
                        show_reviews = st.checkbox(
                            f"View reviews ({cnt})",
                            key=f"show_reviews_{row.get('id')}",
                        )
                        if show_reviews:
                            reviews = list_reviews_for_business(str(row.get("id")), limit=50)
                            if not reviews:
                                st.caption("No review details found.")
                            else:
                                for rv in reviews:
                                    rating = int(rv.get("rating") or 0)
                                    rv_stars = "★" * max(0, min(5, rating)) + "☆" * max(0, 5 - rating)
                                    reviewer = (rv.get("reviewer_name") or "").strip() or "Customer"
                                    created_at = rv.get("created_at")
                                    created_s = (
                                        created_at.isoformat()
                                        if hasattr(created_at, "isoformat")
                                        else str(created_at) if created_at else ""
                                    )
                                    with st.container(border=True):
                                        st.markdown(f"**{rv_stars} ({rating}/5)**")
                                        st.caption(f"By {reviewer}" + (f" • {created_s}" if created_s else ""))
                                        comment = (rv.get("comment") or "").strip()
                                        if comment:
                                            st.write(comment)
                                        else:
                                            st.caption("No written comment.")
                                        provider_response = (rv.get("provider_response") or "").strip()
                                        if provider_response:
                                            st.info("Business response: " + provider_response)
                    else:
                        st.caption("No reviews yet.")

render_footer_bug_panel()
