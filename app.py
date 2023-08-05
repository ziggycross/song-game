from connections import MongoDBConnection, SpotifyConnection
import streamlit as st
import pandas as pd

import regex as re

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# SESSION VARIABLES
max_lives = 3
correct_answer_score = 100
genres_modifier = 0.25
decades_modifier = 0.1

if "state" not in st.session_state: st.session_state.state = "waiting"
if "score" not in st.session_state: st.session_state.score = 0
if "lives" not in st.session_state: st.session_state.lives = max_lives

if "genres" not in st.session_state: st.session_state.genres = None
if "genres" not in st.session_state: st.session_state.decades = None
if "data" not in st.session_state: st.session_state.data = None

# FUNCTIONS
def check(guess, correct):
    if guess == correct:
        st.toast("Correct!")
        st.session_state.score += correct_answer_score
    
    elif st.session_state.lives > 1:
        st.toast("Incorrect!")
        st.session_state.lives -= 1
    
    else:
        st.balloons()
        st.session_state.state = "game_over"

year_format = lambda d: f"{19 if int(d[0]) > 5 else 20}{d}s"
decade_regex = re.compile(r"(\d{2})[sS]")

# DATABASE
musicgen = st.experimental_connection(
    "mongodb",
    type=MongoDBConnection,
    database="musicgen"
    )

charts = musicgen.aggregate(
    "musicgen", 
    [
        {"$group": {"_id": {"chart_name": "$chart_name", "am_genre": "$am_genre"}}}
    ]
    )
charts["decade"] = charts["chart_name"].str.extract(r"(\d{2})[sS]")
decades = sorted(charts["decade"].unique(), key = year_format)

# GAME INTERFACE
st.title("🎸 Streamlit Song Game ⚡")
"""
Test your music knowledge in this song challenge!
"""

st.divider()

match st.session_state.state:
    case "waiting":
    
        # Get year range
        start_year, end_year = st.select_slider("Decades", options=decades, value=("70", "10"), format_func=year_format)
        selected_decades = decades[decades.index(start_year): decades.index(end_year)+1]
        # Get genres available in those years
        year_genres = charts.loc[charts["decade"].isin(selected_decades)]["am_genre"].unique()
        if st.session_state.genres is not None:
            st.session_state.genres = [g for g in st.session_state.genres if g in year_genres]
        selected_genres = st.multiselect("Genres", sorted(year_genres), default=st.session_state.genres)
        st.session_state.genres = selected_genres

        filtered_charts = charts.loc[(charts["am_genre"].isin(selected_genres)) & (charts["decade"].isin(selected_decades))]

        st.markdown("Our dataset contains over 8000 songs! We recommend selecting just a few genres from a decade that you're familiar with.")

        if st.button("New game", type="primary", disabled=not selected_genres, use_container_width=True):        
            
            data = musicgen.query(
                "musicgen",
                filter={"chart_name": {"$in": list(filtered_charts["chart_name"])}},
                projection={"song": 1, "artist": 1, "chart_name": 1, "id": 1}
                )
            
            st.toast(f"Found {data.shape[0]} songs!")
            st.session_state.genres = selected_genres
            st.session_state.decades = selected_decades
            st.session_state.data = data

            st.session_state.state = "playing"
            st.session_state.score = 0
            st.session_state.lives = max_lives
            
            st.experimental_rerun()

    case "playing":
        question_box = st.empty()
        lives = st.session_state.lives
        score = st.session_state.score

        selection = st.session_state.data.sample(3)

        song = selection["song"][0]
        song_id = selection["id"][0]
        answer = selection["artist"][0]
        artists = selection[["artist", "id"]].sample(frac=1)

        sp = st.experimental_connection("spotify", SpotifyConnection)

        with question_box.container():
            st.subheader(f"Score = {score}")

            lives_bar = st.progress(lives/max_lives, f"Lives = {lives}")

            st.divider()

            st.text(f"Who wrote '{song}'?")

            preview = sp.get_song_preview(song_id)
            if preview:
                st.audio(sp.get_song_preview(song_id), format="audio/mp3")
            else:
                st.markdown("*(No preview available for this track)*")

            
            columns = st.columns(3)
            for i, (artist, track_id) in artists.reset_index(drop=True).iterrows():
                with columns[i]:
                    artist_id = sp.get_song_artist(track_id)
                    artist_image = sp.get_artist_image(artist_id, quality=3)
                    st.image(artist_image)
                    st.button(artist, key=score+i+1, on_click=check, use_container_width=True, args=(artist, answer))

    case "game_over":
        base_score = st.session_state.score

        genres_multiplier = genres_modifier*len(st.session_state.genres)
        genres_bonus = int(base_score*genres_multiplier)
        
        decades_multiplier = decades_modifier*len(st.session_state.decades)
        decades_bonus = int(base_score*decades_multiplier)

        final_score = base_score+genres_bonus+decades_bonus
        
        st.markdown(
            f"""
            # Final score: {final_score}

            *{" + ".join(st.session_state.genres)} from {" to ".join(map(year_format, [st.session_state.decades[0], st.session_state.decades[-1]]))}*
            
            **Base score:** `{base_score}`  
            
            **Genres multiplier:** `{1+genres_multiplier}x`  
            **Genres bonues:** `{genres_bonus}`  
            
            **Decades multiplier:** `{1+decades_multiplier}x`  
            **Decades bonues:** `{decades_bonus}`  
            """)

        if st.button("Play again", type="primary", use_container_width=True):
            st.session_state.state = "waiting"
            st.experimental_rerun()
