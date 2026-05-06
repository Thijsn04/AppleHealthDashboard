from __future__ import annotations

import os
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def generate_weekly_summary(df: pd.DataFrame, adf: pd.DataFrame, wdf: pd.DataFrame) -> str:
    """
    Generates a weekly health summary using Gemini.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        return "⚠️ Gemini API Key not configured. Please set `GEMINI_API_KEY` in your `.env` file to enable AI summaries."

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')

        # Prepare context
        # 1. Recent Stats
        recent_adf = adf.tail(7) if not adf.empty else pd.DataFrame()
        recent_wdf = wdf.tail(5) if not wdf.empty else pd.DataFrame()
        
        context = "Summarize the following health data for the past week. Be encouraging and highlight patterns.\n\n"
        
        if not recent_adf.empty:
            context += "Daily Stats (last 7 days):\n"
            context += recent_adf[["day", "active_energy_burned_kcal", "steps"]].to_string() + "\n\n"
            
        if not recent_wdf.empty:
            context += "Recent Workouts:\n"
            context += recent_wdf[["start_at", "workout_type", "duration_min"]].to_string() + "\n\n"

        prompt = f"""
        You are a supportive, data-driven personal health coach. 
        Analyze the following data from my Apple Health export and provide a concise (3-4 paragraph) weekly summary.
        Include:
        1. A "Headline" for the week.
        2. Highlights of activity trends.
        3. One actionable tip for next week based on the data.
        
        Data:
        {context}
        """

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ Error generating AI summary: {str(e)}"
