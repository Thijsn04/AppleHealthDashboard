from __future__ import annotations

import pandas as pd
import streamlit as st
import duckdb
import os

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.web.page_utils import sidebar_nav, page_header

st.set_page_config(
    page_title="Health Chat · Apple Health Dashboard",
    page_icon="🤖",
    layout="wide",
)

page_header("🤖", "Health Chat", "Chat directly with your health data using AI.")

with st.sidebar:
    sidebar_nav(current="Health Chat")
    st.divider()
    api_key = st.text_input("Gemini API Key", type="password", help="Get yours at aistudio.google.com")
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY", "")

db_path = default_db_path()

if not db_path.exists():
    st.warning("No database found. Please import data first.")
    st.stop()

# Initialize chat history
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {"role": "assistant", "content": "Hi! I'm your Health AI. I can analyze your database and answer questions like 'What was my average resting heart rate last month?' or 'How does my sleep correlate with my workouts?'"}
    ]

# Display chat messages
for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

def query_db(query: str) -> pd.DataFrame:
    try:
        con = duckdb.connect(str(db_path))
        try:
            return con.execute(query).df()
        finally:
            con.close()
    except Exception as e:
        return pd.DataFrame({"Error": [str(e)]})

if prompt := st.chat_input("Ask a question about your health data..."):
    # Append user message
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        
    with st.chat_message("assistant"):
        if not api_key:
            st.error("Please enter a Gemini API Key in the sidebar to use the chat.")
            st.session_state.chat_messages.append({"role": "assistant", "content": "Please enter an API key to continue."})
            st.stop()
            
        with st.spinner("Thinking..."):
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                
                # We provide the schema to the LLM
                schema = """
                Table: health_record
                Columns: id, type, source_name, source_version, unit, creation_at, start_at, end_at, value, record_hash
                
                Table: workout
                Columns: id, workout_activity_type, duration_s, duration_unit, total_distance, total_distance_unit, total_energy_kcal, total_energy_unit, source_name, source_version, creation_at, start_at, end_at
                
                Table: activity_summary
                Columns: day, active_energy_burned_kcal, active_energy_burned_goal_kcal, apple_exercise_time_min, apple_exercise_time_goal_min, apple_stand_hours, apple_stand_hours_goal
                """
                
                system_prompt = f"You are an AI assistant analyzing Apple Health data stored in a DuckDB database. The database schema is:\n{schema}\n\nThe user asked: '{prompt}'. Reply ONLY with a valid SQL query (DuckDB) to answer the user's question. Do not use markdown blocks around the query, just return the raw SQL string. Ensure the query is read-only (SELECT)."
                
                model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
                response = model.generate_content(system_prompt)
                
                sql_query = response.text.strip()
                if sql_query.startswith("```sql"):
                    sql_query = sql_query[6:]
                if sql_query.startswith("```"):
                    sql_query = sql_query[3:]
                if sql_query.endswith("```"):
                    sql_query = sql_query[:-3]
                sql_query = sql_query.strip()
                
                st.code(sql_query, language="sql")
                
                df_res = query_db(sql_query)
                st.dataframe(df_res, use_container_width=True)
                
                if "Error" in df_res.columns:
                    answer = f"I tried to run a SQL query, but encountered an error: {df_res['Error'].iloc[0]}"
                else:
                    # Generate a natural language response
                    data_str = df_res.head(20).to_string()
                    nl_prompt = f"The user asked: '{prompt}'. The database returned this data:\n{data_str}\n\nProvide a friendly, concise natural language summary of the answer."
                    nl_response = model.generate_content(nl_prompt)
                    answer = nl_response.text
                
                st.markdown(answer)
                st.session_state.chat_messages.append({"role": "assistant", "content": answer})
                
            except ImportError:
                msg = "The `google-generativeai` package is not installed. Please run `pip install google-generativeai`."
                st.error(msg)
                st.session_state.chat_messages.append({"role": "assistant", "content": msg})
            except Exception as e:
                msg = f"An error occurred: {str(e)}"
                st.error(msg)
                st.session_state.chat_messages.append({"role": "assistant", "content": msg})
