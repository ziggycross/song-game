from datetime import datetime, timedelta

import pandas as pd
import regex as re
import streamlit as st
from streamlit import session_state as state

from connections import MongoDBConnection, SpotifyConnection

# SESSION VARIABLES
max_lives = 3
correct_answer_score = 100
genres_modifier = 0.25
decades_modifier = 0.1

# - game state
if "state" not in state: state.state = "waiting"
if "score" not in state: state.score = 0
if "lives" not in state: state.lives = max_lives

# - game settings
if "genres" not in state: state.genres = None
if "decades" not in state: state.decades = ["70", "80", "90", "00", "10"]
if "data" not in state: state.data = None

# - leaderboard settings
if "name" not in state: state.name = ""
if "submitted" not in state: state.submitted = True

# FUNCTIONS
def check(guess, correct):
    if guess == correct:
        st.toast("Correct!")
        state.score += correct_answer_score
    
    elif state.lives > 1:
        st.toast("Incorrect!")
        state.lives -= 1
    
    else:
        st.balloons()
        state.state = "game_over"

year_format = lambda d: f"{19 if int(d[0]) > 5 else 20}{d}s"
decade_regex = r"(\d{2})[sS]"

# CONNECTIONS
musicgen = st.experimental_connection(
    "mongodb",
    type=MongoDBConnection,
    database="musicgen"
    )

sp = st.experimental_connection(
    "spotify",
    type=SpotifyConnection
    )

# GAME INTERFACE
st.title("🎸 Streamlit Song Game ⚡")
"""
Test your music knowledge in this song challenge!
"""

st.divider()

match state.state:
    
    case "waiting":
        
        # Retrieve available charts
        charts = musicgen.aggregate(
            "musicgen", 
            [{"$group": {"_id": {"chart_name": "$chart_name", "am_genre": "$am_genre"}}}],
            ttl=None
            )
        charts = pd.DataFrame(list(charts.index))
        charts["decade"] = charts["chart_name"].str.extract(decade_regex)
        
        all_decades = sorted(charts["decade"].unique(), key = year_format)

        # Layout
        presets, custom = st.columns(2)

        # Get most popular modes from leaderboard
        with presets:
            top_modes = musicgen.aggregate(
                "leaderboard", [
                    {"$group": {"_id": "$mode", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                    {"$limit": 10}
                ], ttl=100).reset_index()

            # TODO: Make options clickable to copy settings
            st.markdown(f"### Most popular:  \n"+"  \n".join([f"- {mode} *({count} plays)*" for i, (mode, count) in top_modes.iterrows()]))

        # Allow customisation of gamemode
        with custom:
            # Get year range
            start_year, end_year = st.select_slider(
                "Decades",
                options=all_decades,
                value=(state.decades[0], state.decades[-1]),
                format_func=year_format
                )
            selected_decades = all_decades[all_decades.index(start_year): all_decades.index(end_year)+1]

            # Get genres available in those years
            available_genres = charts.loc[charts["decade"].isin(selected_decades)]["am_genre"].unique().tolist()
            available_genres.sort()

            # Genre selection
            if state.genres:
                state.genres = [g for g in state.genres if g in available_genres]
            selected_genres = st.multiselect("Genres", sorted(available_genres), default=state.genres)

            st.markdown("Our dataset contains over 8000 songs! We recommend selecting just a few genres from a decade that you're familiar with.")

            st.divider()

            name = st.text_input("Leaderboard name", placeholder="Leave blank to play anonymously", value=state.name)

        st.divider()

        if st.button("New game", type="primary", disabled=not selected_genres, use_container_width=True):        
            
            # Select rows from charts
            filtered_charts = charts.loc[(charts["am_genre"].isin(selected_genres)) & (charts["decade"].isin(selected_decades))]

            # Get song data for selection
            data = musicgen.query(
                "musicgen",
                filter={"chart_name": {"$in": list(filtered_charts["chart_name"])}},
                projection={"song": 1, "artist": 1, "chart_name": 1, "id": 1},
                ttl=None
                )
            
            # Save settings to state
            state.decades = selected_decades
            state.genres = selected_genres
            state.data = data

            state.state = "playing"
            state.score = 0
            state.lives = max_lives
            
            state.name = name.strip()
            state.submitted = False
            
            st.experimental_rerun()

    case "playing":
        
        # Select three rows
        selection = state.data.sample(3)
        
        # Select correct answer from sample
        song = selection["song"][0]
        song_id = selection["id"][0]
        answer = selection["artist"][0]

        # Get name and IDs for all options
        artists = selection[["artist", "id"]].sample(frac=1)
        
        question_box = st.empty()
        with question_box.container():
            st.subheader(f"Score = {state.score}")

            lives_bar = st.progress(state.lives/max_lives, f"Lives = {state.lives}")

            st.divider()

            st.text(f"Who wrote '{song}'?")

            preview = sp.get_song_preview(song_id)
            if preview:
                st.audio(preview, format="audio/mp3")
            else:
                st.markdown("*(No preview available for this track)*")
            
            # Options for artists
            columns = st.columns(3)
            for i, (artist, track_id) in artists.reset_index(drop=True).iterrows():
                artist_id = sp.get_song_artist(track_id)
                artist_image = sp.get_artist_image(artist_id, quality=3)

                with columns[i]:
                    st.image(artist_image)
                    st.button(artist, key=state.score+i+1, on_click=check, use_container_width=True, args=(artist, answer))

    case "game_over":
        
        # Create title for game mode (decade and genre settings)
        mode = f"""{" + ".join(state.genres)} from {" to ".join(map(year_format, [state.decades[0], state.decades[-1]]))}"""
        
        # Calculate bonuses and final score
        base_score = state.score

        genres_multiplier = genres_modifier*len(state.genres)
        genres_bonus = int(base_score*genres_multiplier)
        
        decades_multiplier = decades_modifier*len(state.decades)
        decades_bonus = int(base_score*decades_multiplier)

        final_score = base_score+genres_bonus+decades_bonus
        
        st.markdown(
            f"""
            # Final score: {final_score}

            *{mode}*
            
            **Base score:** `{base_score}`  
            
            **Genres multiplier:** `{1+genres_multiplier}x`  
            **Genres bonues:** `{genres_bonus}`  
            
            **Decades multiplier:** `{1+decades_multiplier}x`  
            **Decades bonues:** `{decades_bonus}`  

            """)
        
        st.divider()

        # Send score to leaderboard
        if state.name and not state.submitted:
            state.submitted = True
            musicgen.insert("leaderboard", {
                "name": state.name,
                "score": final_score,
                "mode": mode,
                "time": datetime.now()
                })
        
        # Leaderboard tabs
        lb_mode, lb_personal, lb_weekly, lb_all = st.tabs([mode, "Personal", "Weekly", "All"])

        # Leaderboard matching current settings
        with lb_mode:

            try:
                leaderboard = musicgen.aggregate(
                    "leaderboard", [
                        {"$match": {"mode": mode}},
                        {"$sort": {"score": -1}},
                        {"$limit": 15},
                        {"$project": {"name": 1, "score": 1}}
                    ], ttl=100).reset_index(drop=True)
                leaderboard = list(leaderboard.iterrows())
            except KeyError:
                leaderboard = []
    
            st.markdown(f"## Leaderboard for '{mode}'")
            leaderboard_cols = st.columns(3)
            for i in range(3):
                with leaderboard_cols[i]:
                    st.markdown("\n".join([
                        f"{i+1}. **{name}**  \nScore: {score}"
                        for i, (name, score)
                        in leaderboard[5*i:5*(i+1)]
                        ]))
        
        # Leadboard matching current username
        with lb_personal:

            try:
                leaderboard = musicgen.aggregate(
                    "leaderboard", [
                        {"$match": {"name": state.name}},
                        {"$sort": {"score": -1}},
                        {"$limit": 15},
                        {"$project": {"score": 1, "mode": 1}}
                    ], ttl=100).reset_index(drop=True)
                leaderboard = list(leaderboard.iterrows())
            except KeyError:
                leaderboard = []
            
            st.markdown(f"## Overall leaderboard")
            leaderboard_cols = st.columns(3)
            for i in range(3):
                with leaderboard_cols[i]:
                    st.markdown("\n".join([
                        f"{i+1}. **Score: {score}**  \n*{mode}*"
                        for i, (score, mode)
                        in leaderboard[5*i:5*(i+1)]
                        ]))
                    
        # Leaderboard showing the last 7 days
        with lb_weekly:

            try:
                leaderboard = musicgen.aggregate(
                    "leaderboard", [
                        {"$match": {"time": {"$gte": datetime.now() - timedelta(days=7)}}},
                        {"$sort": {"score": -1}},
                        {"$limit": 15},
                        {"$project": {"name": 1, "score": 1, "mode": 1}}
                    ], ttl=100).reset_index(drop=True)
                leaderboard = list(leaderboard.iterrows())
            except KeyError:
                leaderboard = []
            
            st.markdown(f"## Overall leaderboard")
            leaderboard_cols = st.columns(3)
            for i in range(3):
                with leaderboard_cols[i]:
                    st.markdown("\n".join([
                        f"{i+1}. **{name}**  \n*{mode}*  \nScore: {score}"
                        for i, (name, score, mode)
                        in leaderboard[5*i:5*(i+1)]
                        ]))
        
        # Leaderboard showing all time
        with lb_all:

            leaderboard = musicgen.aggregate(
                "leaderboard", [
                    {"$sort": {"score": -1}},
                    {"$limit": 15},
                    {"$project": {"name": 1, "score": 1, "mode": 1}}
                ], ttl=100).reset_index(drop=True)
            leaderboard = list(leaderboard.iterrows())
            
            st.markdown(f"## Overall leaderboard")
            leaderboard_cols = st.columns(3)
            for i in range(3):
                with leaderboard_cols[i]:
                    st.markdown("\n".join([
                        f"{i+1}. **{name}**  \n*{mode}*  \nScore: {score}"
                        for i, (name, score, mode)
                        in leaderboard[5*i:5*(i+1)]
                        ]))
        
        st.divider()

        if st.button("Play again", type="primary", use_container_width=True):
            state.state = "waiting"
            st.experimental_rerun()
