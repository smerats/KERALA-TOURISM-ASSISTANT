import streamlit as st
import pandas as pd
import faiss
import time
import base64
from sentence_transformers import SentenceTransformer
from mistralai.client import Mistral
import re
import hashlib
import json
import os

# -----------------------------
# USER STORAGE FUNCTIONS
# -----------------------------
USERS_FILE = "users_data.json"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(email, password):
    users = load_users()
    if email in users:
        return False, "Email already registered!"
    users[email] = {
        "password": hash_password(password),
        "sessions": {}
    }
    save_users(users)
    return True, "Registration successful!"

def login_user(email, password):
    users = load_users()
    if email not in users:
        return False, "Email not found!"
    if users[email]["password"] != hash_password(password):
        return False, "Incorrect password!"
    return True, users[email].get("sessions", {})

def save_user_sessions(email, sessions):
    users = load_users()
    if email in users:
        users[email]["sessions"] = sessions
        save_users(users)

# Initialize auth session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

# Initialize sessions (only if logged in)
if "sessions" not in st.session_state:
    st.session_state.sessions = {}
if "current_session_id" not in st.session_state:
    initial_id = str(time.time())
    st.session_state.sessions[initial_id] = {
        "title": "New Chat",
        "messages": []
    }
    st.session_state.current_session_id = initial_id

# -----------------------------
# PAGE SETTINGS
# -----------------------------
st.set_page_config(
    page_title="Kerala Tourism Chatbot",
    page_icon="🌴",
    layout="centered"
)

# -----------------------------
# BACKGROUND IMAGE LOADER
# -----------------------------
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return ""

img_base64 = get_base64_image("Kerala.png")
map_base64 = get_base64_image("kerala_map.png")

if img_base64:
    bg_style = f"""
    background-image: linear-gradient(rgba(255, 255, 255, 0.25), rgba(255, 255, 255, 0.32)), url("data:image/png;base64,{img_base64}");
    background-size: cover;
    background-position: center center;
    background-repeat: no-repeat;
    background-attachment: fixed;
    """
else:
    bg_style = "background: #F0F4F4;"

if map_base64:
    sidebar_bg_style = f"""
    background-image: linear-gradient(rgba(255, 255, 255, 0.72), rgba(255, 255, 255, 0.72)), url("data:image/png;base64,{map_base64}") !important;
    background-size: auto 100% !important;
    background-position: center center !important;
    background-repeat: no-repeat !important;
    """
else:
    sidebar_bg_style = "background-color: rgba(255, 255, 255, 0.85) !important;"

# -----------------------------
# PREMIUM UI STYLE
# -----------------------------
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Inter:wght@300;400;500;600&display=swap');

.stApp {{
    {bg_style}
    font-family: 'Inter', sans-serif;
}}

/* Reduce Streamlit's default top padding so content sits higher */
.stMainBlockContainer, .block-container {{
    padding-top: 0.5rem !important;
}}

div.element-container:has(.sticky-header-container) {{
    position: sticky;
    top: 2.875rem;
    z-index: 99;
    background: transparent;
}}

.sticky-header-container {{
    {bg_style}
    text-align: center;
    padding: 4px 0px 14px 0px;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    width: 100%;
}}

.main-header {{
    font-family: 'Outfit', sans-serif;
    background: linear-gradient(135deg, #11998e, #38ef7d);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 800;
    font-size: 2.2rem;
    margin: 0;
    letter-spacing: -0.5px;
    display: inline-block;
    filter: drop-shadow(0px 0px 10px rgba(255, 255, 255, 0.95));
}}

.user-bubble {{
    background: linear-gradient(135deg, #11998e, #38ef7d);
    color: white;
    padding: 14px 18px;
    border-radius: 20px 20px 0px 20px;
    max-width: 75%;
    margin: 10px 0px 10px auto;
    text-align: left;
    box-shadow: 0px 4px 15px rgba(17, 153, 142, 0.25);
    font-family: 'Inter', sans-serif;
    font-size: 0.95rem;
    line-height: 1.4;
}}

.bot-bubble {{
    background: rgba(255, 255, 255, 0.9);
    color: #2c3e50;
    padding: 14px 18px;
    border-radius: 20px 20px 20px 0px;
    max-width: 75%;
    margin: 10px auto 10px 0px;
    text-align: left;
    box-shadow: 0px 4px 15px rgba(0, 0, 0, 0.05);
    font-family: 'Inter', sans-serif;
    font-size: 0.95rem;
    line-height: 1.4;
    border: 1px solid rgba(255, 255, 255, 0.5);
}}

.message-row {{
    display: flex;
    width: 100%;
}}

/* Make the bottom chat input bar container transparent */
[data-testid="stBottom"] {{
    background: transparent !important;
    box-shadow: none !important;
    border-top: none !important;
}}

[data-testid="stBottom"] > div {{
    background: transparent !important;
}}

.stChatInputContainer {{
    background: transparent !important;
    box-shadow: none !important;
    border: none !important;
}}

/* Sidebar customization */
[data-testid="stSidebar"] {{
    {sidebar_bg_style}
    backdrop-filter: blur(10px);
    border-right: 1px solid rgba(0, 0, 0, 0.05);
}}

/* Sidebar primary buttons (Active chat, New Chat) */
[data-testid="stSidebar"] button[kind="primary"] {{
    background: linear-gradient(135deg, #11998e, #38ef7d) !important;
    color: white !important;
    border: none !important;
    font-weight: 500 !important;
    box-shadow: 0px 4px 10px rgba(17, 153, 142, 0.2) !important;
}}

/* Sidebar secondary buttons (Inactive chats) */
[data-testid="stSidebar"] button[kind="secondary"] {{
    background-color: rgba(255, 255, 255, 0.65) !important;
    color: #2c3e50 !important;
    border: 1px solid rgba(0, 0, 0, 0.08) !important;
    font-weight: 400 !important;
}}

/* Style the delete button in the second column */
[data-testid="stSidebar"] div[data-testid="column"]:nth-of-type(2) button,
[data-testid="stSidebar"] div[data-testid="column"]:nth-of-type(2) button[kind="secondary"],
[data-testid="stSidebar"] [data-testid="column"]:nth-child(2) button,
[data-testid="stSidebar"] [data-testid="column"]:nth-child(2) button[kind="secondary"] {{
    background-color: rgba(231, 76, 60, 0.12) !important;
    color: #e74c3c !important;
    border: none !important;
    border-radius: 8px !important;
}}

[data-testid="stSidebar"] div[data-testid="column"]:nth-of-type(2) button:hover,
[data-testid="stSidebar"] div[data-testid="column"]:nth-of-type(2) button[kind="secondary"]:hover,
[data-testid="stSidebar"] [data-testid="column"]:nth-child(2) button:hover,
[data-testid="stSidebar"] [data-testid="column"]:nth-child(2) button[kind="secondary"]:hover {{
    background-color: #e74c3c !important;
    color: white !important;
}}

/* Coconut loader animation */
.loader-backdrop {{
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(240, 245, 245, 0.85);
    backdrop-filter: blur(5px);
    -webkit-backdrop-filter: blur(5px);
    z-index: 999999;
    display: flex;
    justify-content: center;
    align-items: center;
    flex-direction: column;
}}

.coconut-loader {{
    position: relative;
    width: 200px;
    height: 250px;
    display: flex;
    justify-content: center;
    align-items: center;
    flex-direction: column;
}}

.coconut {{
    font-size: 4.5rem;
    position: absolute;
    top: 60px;
}}

.coconut.whole {{
    animation: fall 1.2s cubic-bezier(0.6, -0.28, 0.735, 0.045) infinite;
}}

.coconut.half-left {{
    clip-path: inset(0 50% 0 0);
    animation: split-left 1.2s infinite;
}}

.coconut.half-right {{
    clip-path: inset(0 0 0 50%);
    animation: split-right 1.2s infinite;
}}

.loading-text {{
    position: absolute;
    bottom: 20px;
    font-family: 'Outfit', sans-serif;
    font-weight: 600;
    color: #11998e;
    font-size: 1.1rem;
    letter-spacing: 1px;
    animation: pulse 1.2s infinite;
}}

@keyframes fall {{
    0% {{
        transform: translateY(-150px) rotate(0deg);
        opacity: 1;
    }}
    50% {{
        transform: translateY(0px) rotate(360deg);
        opacity: 1;
    }}
    50.1% {{
        opacity: 0;
    }}
    100% {{
        transform: translateY(0px);
        opacity: 0;
    }}
}}

@keyframes split-left {{
    0%, 50% {{
        transform: translate(0, 0) rotate(0deg);
        opacity: 0;
    }}
    50.1% {{
        opacity: 1;
    }}
    100% {{
        transform: translate(-50px, 30px) rotate(-60deg);
        opacity: 0;
    }}
}}

@keyframes split-right {{
    0%, 50% {{
        transform: translate(0, 0) rotate(0deg);
        opacity: 0;
    }}
    50.1% {{
        opacity: 1;
    }}
    100% {{
        transform: translate(50px, 30px) rotate(60deg);
        opacity: 0;
    }}
}}

@keyframes pulse {{
    0%, 100% {{ opacity: 0.6; }}
    50% {{ opacity: 1; }}
}}

/* Global auto coconut loader — shows on ANY Streamlit rerun */
.global-coconut-loader {{
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(240, 245, 245, 0.85);
    backdrop-filter: blur(5px);
    -webkit-backdrop-filter: blur(5px);
    z-index: 888888;
    justify-content: center;
    align-items: center;
    flex-direction: column;
}}

/* Show global loader whenever Streamlit's Stop button is visible (app is running) */
body:has(button[title="Stop"]) .global-coconut-loader {{
    display: flex;
}}

/* Hide global loader during splash screen (splash has higher z-index) */
body:has(.splash-screen) .global-coconut-loader {{
    display: none;
}}
</style>
""", unsafe_allow_html=True)

# Inject the persistent global coconut loader HTML (CSS controls show/hide)
st.markdown("""
<div class="global-coconut-loader">
    <div class="coconut-loader">
        <div class="coconut whole">🥥</div>
        <div class="coconut half-left">🥥</div>
        <div class="coconut half-right">🥥</div>
        <div class="loading-text">Please wait...</div>
    </div>
</div>
""", unsafe_allow_html=True)

# -----------------------------
# FORMAT MESSAGE FUNCTION
# -----------------------------
def format_message(text):
    # Convert bold **text** to <strong>text</strong>
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    # Convert *italic* to <em>italic</em>
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    # Convert bullet points to list items
    text = re.sub(r'^\s*[\*\-]\s+(.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
    # Convert newlines to <br>
    text = text.replace('\n', '<br>')
    return text

# -----------------------------
# TYPEWRITER FUNCTION
# -----------------------------
def typewriter(text, speed=0.02):
    placeholder = st.empty()
    output = ""

    for char in text:
        output += char
        placeholder.markdown(f"""
        <div class="message-row">
            <div class="bot-bubble">
                {format_message(output)}
            </div>
        </div>
        """, unsafe_allow_html=True)
        time.sleep(speed)

# -----------------------------
# LOAD MISTRAL
# -----------------------------
#client = Mistral(
   # api_key="wb87pSIrDSjKeGZCnZ48ba7D0USHSPHZ")
   
client = Mistral(
    api_key=os.environ["MISTRAL_API_KEY"]
)

# -----------------------------
# LOAD DATA
# -----------------------------
df = pd.read_csv("kerala_tourism_chatbot_dataset.csv.xls")
index = faiss.read_index("tourism_index.faiss")
model = SentenceTransformer("all-MiniLM-L6-v2")

# -----------------------------
# LOGIN / REGISTER PAGE
# -----------------------------
def show_auth_page():
    st.markdown(f"""
    <style>
    .auth-wrapper {{
        min-height: 80vh;
        display: flex;
        align-items: center;
        justify-content: center;
    }}
    .auth-card {{
        background: rgba(255,255,255,0.88);
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        border-radius: 24px;
        padding: 44px 40px 36px 40px;
        box-shadow: 0 20px 60px rgba(17,153,142,0.15);
        border: 1px solid rgba(255,255,255,0.6);
        max-width: 440px;
        width: 100%;
        margin: 0 auto;
    }}
    .auth-logo {{
        text-align: center;
        font-size: 2.8rem;
        margin-bottom: 4px;
    }}
    .auth-title {{
        text-align: center;
        font-family: 'Outfit', sans-serif;
        font-size: 1.7rem;
        font-weight: 800;
        background: linear-gradient(135deg, #11998e, #38ef7d);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0 0 4px 0;
    }}
    .auth-subtitle {{
        text-align: center;
        color: #888;
        font-size: 0.9rem;
        margin-bottom: 28px;
        font-family: 'Inter', sans-serif;
    }}
    .auth-tab-row {{
        display: flex;
        background: rgba(17,153,142,0.08);
        border-radius: 12px;
        padding: 4px;
        margin-bottom: 24px;
    }}
    .auth-tab {{
        flex: 1;
        text-align: center;
        padding: 9px 0;
        border-radius: 9px;
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        font-size: 0.95rem;
        cursor: pointer;
        color: #11998e;
    }}
    .auth-tab.active {{
        background: linear-gradient(135deg, #11998e, #38ef7d);
        color: white;
    }}
    </style>
    <div class="auth-wrapper">
        <div class="auth-card">
            <div class="auth-logo">🌴</div>
            <h1 class="auth-title">Kerala Tourism Assistant</h1>
            <p class="auth-subtitle">God's Own Country — Sign in to explore</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Tab toggle
    col_login, col_register = st.columns(2)
    with col_login:
        if st.button("🔑  Login", use_container_width=True,
                     type="primary" if st.session_state.auth_mode == "login" else "secondary"):
            st.session_state.auth_mode = "login"
            st.rerun()
    with col_register:
        if st.button("📝  Register", use_container_width=True,
                     type="primary" if st.session_state.auth_mode == "register" else "secondary"):
            st.session_state.auth_mode = "register"
            st.rerun()

    st.markdown("---")

    if st.session_state.auth_mode == "login":
        st.markdown("#### Welcome back 👋")
        email = st.text_input("📧 Gmail Address", placeholder="you@gmail.com", key="login_email")
        password = st.text_input("🔒 Password", type="password", placeholder="Enter your password", key="login_pass")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Login →", use_container_width=True, type="primary"):
            if not email or not password:
                st.error("Please fill in all fields.")
            else:
                success, result = login_user(email, password)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.user_email = email
                    # Load the user's saved sessions
                    saved_sessions = result
                    if saved_sessions:
                        st.session_state.sessions = saved_sessions
                        # Set current to most recent session
                        st.session_state.current_session_id = list(saved_sessions.keys())[-1]
                    else:
                        # Fresh user — create initial session
                        initial_id = str(time.time())
                        st.session_state.sessions = {initial_id: {"title": "New Chat", "messages": []}}
                        st.session_state.current_session_id = initial_id
                    st.success(f"Welcome back! Logged in as {email}")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(result)
    else:
        st.markdown("#### Create your account ✨")
        reg_email = st.text_input("📧 Gmail Address", placeholder="you@gmail.com", key="reg_email")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            reg_pass = st.text_input("🔒 Password", type="password", placeholder="Choose password", key="reg_pass")
        with col_p2:
            reg_confirm = st.text_input("✅ Confirm", type="password", placeholder="Repeat password", key="reg_confirm")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Create Account →", use_container_width=True, type="primary"):
            if not reg_email or not reg_pass or not reg_confirm:
                st.error("Please fill in all fields.")
            elif "@" not in reg_email:
                st.error("Please enter a valid email address.")
            elif len(reg_pass) < 6:
                st.error("Password must be at least 6 characters.")
            elif reg_pass != reg_confirm:
                st.error("Passwords do not match!")
            else:
                success, msg = register_user(reg_email, reg_pass)
                if success:
                    st.success("✅ Account created! Please login.")
                    st.session_state.auth_mode = "login"
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(msg)

# Show login page if not authenticated
if not st.session_state.logged_in:
    show_auth_page()
    st.stop()

# -----------------------------
# SIDEBAR (CHAT HISTORY & NEW CHAT)
# -----------------------------
with st.sidebar:
    st.markdown("### 🌴 Kerala Tourism Assistant")
    
    # User info + logout
    st.markdown(f"""
    <div style='background: linear-gradient(135deg,rgba(17,153,142,0.12),rgba(56,239,125,0.12)); 
                border-radius:12px; padding:10px 14px; margin-bottom:8px;
                border: 1px solid rgba(17,153,142,0.2);'>
        <span style='font-size:0.8rem; color:#11998e; font-weight:600;'>👤 {st.session_state.user_email}</span>
    </div>
    """, unsafe_allow_html=True)
    if st.button("🚪 Logout", use_container_width=True):
        # Save sessions before logout
        save_user_sessions(st.session_state.user_email, st.session_state.sessions)
        st.session_state.logged_in = False
        st.session_state.user_email = ""
        st.session_state.sessions = {}
        st.session_state.current_session_id = ""
        st.session_state.intro_shown = False
        st.rerun()
    
    # ➕ New Chat button
    if st.button("💬 New Chat", use_container_width=True, type="primary"):
        new_id = str(time.time())
        st.session_state.sessions[new_id] = {
            "title": "New Chat",
            "messages": []
        }
        st.session_state.current_session_id = new_id
        st.rerun()
        
    st.markdown("---")
    st.markdown("**Recent Chats**")
    
    # Render only sessions that have actual messages (skip empty/unused new chats)
    sessions_list = list(st.session_state.sessions.items())[::-1] # newest first
    for session_id, session_data in sessions_list:
        # Skip sessions with no messages — they are unused "New Chat" placeholders
        if not session_data["messages"]:
            continue
        
        is_active = session_id == st.session_state.current_session_id
        title = session_data["title"]
        
        # Primary for active, secondary for others
        btn_type = "primary" if is_active else "secondary"
        
        col1, col2 = st.columns([0.82, 0.18])
        with col1:
            if st.button(f"💬 {title}", key=f"session_{session_id}", use_container_width=True, type=btn_type):
                st.session_state.current_session_id = session_id
                st.rerun()
        with col2:
            if st.button("🗑️", key=f"delete_{session_id}", use_container_width=True, help="Delete this chat"):
                del st.session_state.sessions[session_id]
                if session_id == st.session_state.current_session_id:
                    remaining = list(st.session_state.sessions.keys())
                    if remaining:
                        st.session_state.current_session_id = remaining[0]
                    else:
                        new_id = str(time.time())
                        st.session_state.sessions[new_id] = {
                            "title": "New Chat",
                            "messages": []
                        }
                        st.session_state.current_session_id = new_id
                st.rerun()

# -----------------------------
# INTRO SPLASH SCREEN
# -----------------------------
if "intro_shown" not in st.session_state:
    st.session_state.intro_shown = False

if not st.session_state.intro_shown:
    st.markdown("""
    <div class="splash-screen">
        <div class="splash-content">
            <h1 class="splash-title">KERALA</h1>
            <p class="splash-subtitle">God's Own Country</p>
        </div>
    </div>
    <style>
    .splash-screen {
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background: #F0F4F4;
        z-index: 10000000;
        display: flex;
        justify-content: center;
        align-items: center;
        animation: fadeOutSplash 3.5s forwards;
    }
    .splash-content {
        text-align: center;
        animation: zoomInSplash 1.8s ease-out;
    }
    .splash-title {
        font-family: 'Outfit', sans-serif;
        font-size: 5rem;
        font-weight: 900;
        letter-spacing: 6px;
        background: linear-gradient(135deg, #11998e, #38ef7d);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .splash-subtitle {
        font-family: 'Inter', sans-serif;
        font-size: 1.4rem;
        color: #555;
        margin-top: 12px;
        letter-spacing: 3px;
        text-transform: uppercase;
        font-weight: 500;
    }
    @keyframes zoomInSplash {
        0% { transform: scale(0.85); opacity: 0; filter: blur(5px); }
        50% { transform: scale(1.03); opacity: 1; filter: blur(0); }
        100% { transform: scale(1); opacity: 1; }
    }
    @keyframes fadeOutSplash {
        0% { opacity: 1; visibility: visible; }
        85% { opacity: 1; }
        100% { opacity: 0; visibility: hidden; pointer-events: none; }
    }
    </style>
    """, unsafe_allow_html=True)
    st.session_state.intro_shown = True

# -----------------------------
# TITLE (STICKY HEADER)
# -----------------------------
st.markdown(
    "<div class='sticky-header-container'><h1 class='main-header'>🌴 Kerala Tourism Assistant</h1></div>",
    unsafe_allow_html=True
)

# -----------------------------
# CHAT HISTORY
# -----------------------------
current_id = st.session_state.current_session_id
messages = st.session_state.sessions[current_id]["messages"]

for message in messages:
    if message["role"] == "user":
        st.markdown(f"""
        <div class="message-row">
            <div class="user-bubble">
                {message["content"]}
            </div>
        </div>
        """, unsafe_allow_html=True)

    else:
        st.markdown(f"""
        <div class="message-row">
            <div class="bot-bubble">
                {format_message(message["content"])}
            </div>
        </div>
        """, unsafe_allow_html=True)

# -----------------------------
# USER INPUT
# -----------------------------
user_question = st.chat_input("Ask About Kerala Tourism")

if user_question:
    current_id = st.session_state.current_session_id
    
    # save user message
    st.session_state.sessions[current_id]["messages"].append({
        "role": "user",
        "content": user_question
    })

    # Update session title if this is the first message
    if st.session_state.sessions[current_id]["title"] == "New Chat":
        st.session_state.sessions[current_id]["title"] = user_question[:25] + ("..." if len(user_question) > 25 else "")

    # Render user bubble immediately so it is visible before/during the typing animation
    st.markdown(f"""
    <div class="message-row">
        <div class="user-bubble">
            {user_question}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Render the custom coconut loader
    loader_placeholder = st.empty()
    loader_placeholder.markdown("""
    <div class="loader-backdrop">
        <div class="coconut-loader">
            <div class="coconut whole">🥥</div>
            <div class="coconut half-left">🥥</div>
            <div class="coconut half-right">🥥</div>
            <div class="loading-text">Cracking the knowledge...</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # embedding search
    query_embedding = model.encode([user_question])
    distances, indices = index.search(query_embedding, 3)

    context = ""
    for idx in indices[0]:
        context += str(df.iloc[idx]["bot_response"]) + "\n"

    prompt = f"""
You are a Kerala tourism assistant.

Context:
{context}

User Question:
{user_question}

Answer naturally using the context.
"""

    # Mistral response
    response = client.chat.complete(
        model="mistral-small-latest",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    bot_answer = response.choices[0].message.content

    # Clear the coconut loader
    loader_placeholder.empty()

    # 🔥 TYPEWRITER ANIMATION
    typewriter(bot_answer)

    # save final response
    st.session_state.sessions[current_id]["messages"].append({
        "role": "assistant",
        "content": bot_answer
    })

    st.rerun()