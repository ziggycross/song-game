from connections import MongoDBConnection, SpotifyConnection
import streamlit as st
import pandas as pd

import regex as re

# SESSION VARIABLES
max_lives = 3

if "state" not in st.session_state: st.session_state.state = "waiting"
if "score" not in st.session_state: st.session_state.score = 0
if "lives" not in st.session_state: st.session_state.lives = max_lives

if "data" not in st.session_state: st.session_state.data = None

# FUNCTIONS
def check(guess, correct):
    if guess == correct:
        st.toast("Correct!")
        st.session_state.score += 1
    
    elif st.session_state.lives > 1:
        st.toast("Incorrect!")
        st.session_state.lives -= 1
    
    else:
        st.balloons()
        st.session_state.state = "game_over"

year_format = lambda d: f"{19 if int(d[0]) > 5 else 20}{d}"
decade_regex = re.compile(r"(\d{2}[sS])")

# DATABASE
musicgen = st.experimental_connection(
    "mongodb",
    type=MongoDBConnection,
    database="musicgen"
    )

charts = musicgen.distinct("musicgen", "chart_name")
genres = musicgen.distinct("musicgen", "am_genre")

decades = sorted({re.search(decade_regex, chart).group(0)
    for chart
    in charts
    },
    key = year_format
    )

# GAME INTERFACE
st.title("Streamlit Song Challenge")
"""
Test your music knowledge in this song challenge!
"""

st.divider()

if st.session_state.state == "waiting":
    with st.form(key="settings"):
        selected_decades = st.select_slider("Decades", options=decades, value=("70s", "10s"), format_func=year_format)
        selected_genres = st.multiselect("Genres", genres)
        "Our dataset contains over 8000 songs! We recommend selecting just a few genres from a decade that you're familiar with."

        if st.form_submit_button("New game", type="primary", use_container_width=True):

            decade_charts = [
                chart
                for chart
                in charts
                if re.search(decade_regex, chart).group(0) in selected_decades
                ]
            
            try:
                data = musicgen.query(
                    "musicgen",
                    filter={"chart_name": {"$in": decade_charts}, "am_genre": {"$in": selected_genres}},
                    projection={"song": 1, "artist": 1, "chart_name": 1, "id": 1}
                    )
            except KeyError:
                data = None
            
            if data is not None:
                st.toast(f"Found {data.shape[0]} songs!")
                st.session_state.data = data

                st.session_state.state = "playing"
                st.session_state.score = 0
                st.session_state.lives = max_lives
                
                st.experimental_rerun()
            else:
                st.toast(f"Error: No playlists found for {selected_decades} & {selected_genres}")

                

elif st.session_state.state == "playing":
    question_box = st.empty()
    lives = st.session_state.lives
    score = st.session_state.score

    selection = st.session_state.data.sample(3)

    song = selection["song"][0]
    answer = selection["artist"][0]
    artists = selection["artist"].sample(frac=1)

    with question_box.container():
        st.subheader(f"Score = {score}")

        lives_bar = st.progress(lives/max_lives, f"Lives = {lives}")

        st.text(f"Who wrote '{song}'?")
        
        columns = st.columns(3)
        with columns[0]:
            st.button(artists[0], key=score+1, on_click=check, use_container_width=True, args=(artists[0], answer))
        with columns[1]:
            st.button(artists[1], key=score+2, on_click=check, use_container_width=True, args=(artists[1], answer))
        with columns[2]:
            st.button(artists[2], key=score+3, on_click=check, use_container_width=True, args=(artists[2], answer))

elif st.session_state.state == "game_over":
    st.title(f"You scored {st.session_state.score}")

    if st.button("Play again", type="primary", use_container_width=True):
        st.session_state.state = "waiting"
        st.experimental_rerun()
