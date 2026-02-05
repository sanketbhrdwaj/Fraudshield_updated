import streamlit as st
import re
import csv
import os
from datetime import datetime
import pandas as pd

from model_utils import ml_predict, keyword_risk_score
from honeypot_bot import honeypot_reply



# ================== LLM CONFIG (OLLAMA) ==================
LLM_MODEL = "phi3:mini"   # or "mistral", "phi3", etc.


# =================================================
# =============== APP CONFIG ======================
# =================================================

st.set_page_config(
    page_title="FraudShield AI",
    page_icon="🚨",
    layout="centered"
)

import json


DB_DIR = "database"
DB_FILE = os.path.join(DB_DIR, "honeypot_db.json")
os.makedirs(DB_DIR, exist_ok=True)

def load_db():
    if not os.path.exists(DB_FILE):
        return []

    if os.path.getsize(DB_FILE) == 0:
        return []

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def save_to_db(entry):
    data = load_db()
    data.append(entry)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)



# =================================================
# =============== CONTINUOUS LEARNING =============
# =================================================

LOG_DIR = "learning_logs"
os.makedirs(LOG_DIR, exist_ok=True)

def save_chat_for_learning(chat_history):
    path = os.path.join(LOG_DIR, "honeypot_chats.csv")
    write_header = not os.path.exists(path)

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["role", "message"])
        for role, msg in chat_history:
            writer.writerow([role, msg])

# =================================================
# =============== SESSION STATE ===================
# =================================================

defaults = {
    "honeypot_active": False,
    "chat_history": [],
    "detected_words": [],
    "interaction_log": [],
    "fraud_stats": {
        "UPI IDs": 0,
        "Bank Mentions": 0,
        "Scam Links": 0,
        "Phone Numbers": 0
    }
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# =================================================
# =============== HEADER ==========================
# =================================================

st.markdown("""
<h1 style='text-align:center;'>🚨 FraudShield AI</h1>
<h4 style='text-align:center;color:gray;'>
Silent Scam Detection + AI Honeypot System
</h4>
<hr>
""", unsafe_allow_html=True)

# =================================================
# =============== MESSAGE INPUT ===================
# =================================================

st.markdown("## 📩 Incoming Message")

message = st.text_area(
    "Paste the received SMS / WhatsApp / chat message",
    height=120
)

def clean_text(text):
    text = text.lower()
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"\d+", "", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()

# =================================================
# =============== DETECTION =======================
# =================================================

if st.button("🔍 Process Message") and message:
    # Reset previous conversation
    st.session_state.pop("conversation_id", None)
    st.session_state.honeypot_active = False
    st.session_state.chat_history = []
    st.session_state.detected_words = []

    clean = clean_text(message)
    keyword_score, detected = keyword_risk_score(clean)

    # 🔴 ONLY trigger honeypot if scam words are present
    if detected:
        st.session_state.honeypot_active = True
        st.session_state.detected_words = detected
        st.success(
            f"🚨 Scam keywords detected: {', '.join(detected)}. Honeypot engaged."
        )
    else:
        st.info("✅ No scam keywords detected. Message ignored.")

# =================================================
# =============== FRAUD INTELLIGENCE ==============
# =================================================

def extract_entities(text):
    return {
        "upi": re.findall(r'\b[\w.-]+@upi\b', text),
        "links": re.findall(r'https?://\S+', text),
        "phones": re.findall(r'\b\d{10}\b', text),
        "bank": re.findall(r'\baccount\b|\bkyc\b|\bifsc\b', text, re.IGNORECASE)
    }

def extract_patterns(chat_history):
    combined = " ".join(m.lower() for _, m in chat_history)
    patterns = []

    if "dear winner" in combined:
        patterns.append("Generic greeting")
    if "fee" in combined and ("won" in combined or "prize" in combined):
        patterns.append("Fee before reward")
    if "urgent" in combined or "act fast" in combined:
        patterns.append("Urgency pressure")

    return patterns

# =================================================
# =============== AI HONEYPOT =====================
# =================================================

if st.session_state.honeypot_active:
    st.markdown("## 🤖 AI Honeypot Chatbot")
    st.info("Victim bot is safely engaging the sender.")

    scammer_msg = st.text_input("🧑‍💼 Scammer Message")

    if scammer_msg:
        step = len(st.session_state.chat_history)

        typing = st.empty()
        typing.info("🤖 Victim is typing...")

        bot_reply = honeypot_reply(
            scammer_msg,
            st.session_state.detected_words,
            step,
            model_name=LLM_MODEL
            )

        typing.empty()

        # save chat
        st.session_state.chat_history.extend([
            ("Scammer", scammer_msg),
            ("Victim Bot", bot_reply)
        ])


        db_entry = {
            "conversation_id": st.session_state.get(
                "conversation_id",
                datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            ),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scammer_message": scammer_msg,
        "victim_reply": bot_reply,
        "detected_keywords": st.session_state.detected_words,
        "confidence_level": len(st.session_state.detected_words) * 15 + step * 5
        }

        st.session_state["conversation_id"] = db_entry["conversation_id"]
        save_to_db(db_entry)


        save_chat_for_learning(st.session_state.chat_history)

        st.session_state.interaction_log.append({
            "Time": datetime.now().strftime("%H:%M:%S"),
            "Scammer": scammer_msg,
            "Bot": bot_reply
        })

        # update fraud stats
        entities = extract_entities(" ".join([m for _, m in st.session_state.chat_history]))
        st.session_state.fraud_stats["UPI IDs"] += len(entities["upi"])
        st.session_state.fraud_stats["Scam Links"] += len(entities["links"])
        st.session_state.fraud_stats["Phone Numbers"] += len(entities["phones"])
        st.session_state.fraud_stats["Bank Mentions"] += len(entities["bank"])

    # ---- Conversation ----
    for role, msg in st.session_state.chat_history:
        st.markdown(f"**{role}:** {msg}")

    # ---- Patterns ----
    patterns = extract_patterns(st.session_state.chat_history)
    if patterns:
        st.markdown("## 🧠 Fraud Patterns Learned")
        for p in patterns:
            st.write(f"• {p}")

# =================================================
# =============== DASHBOARD =======================
# =================================================

st.markdown("## 📊 Fraud Intelligence Dashboard")

c1, c2 = st.columns(2)
c3, c4 = st.columns(2)

c1.metric("💳 Fake UPI IDs", st.session_state.fraud_stats["UPI IDs"])
c2.metric("🏦 Bank Mentions", st.session_state.fraud_stats["Bank Mentions"])
c3.metric("🔗 Scam Links", st.session_state.fraud_stats["Scam Links"])
c4.metric("📞 Phone Numbers", st.session_state.fraud_stats["Phone Numbers"])

# =================================================
# =============== INTERACTION LOG =================
# =================================================

if st.session_state.interaction_log:
    st.markdown("## 🕘 Honeypot Interaction Log")
    df = pd.DataFrame(st.session_state.interaction_log)
    st.dataframe(df, use_container_width=True)

# =================================================
# =============== FOOTER ==========================
# =================================================

st.markdown("""
<hr>
<p style='text-align:center;color:gray;font-size:14px;'>
FraudShield AI | AI-Powered Honeypot Scam Defense 🇮🇳
</p>
""", unsafe_allow_html=True)
