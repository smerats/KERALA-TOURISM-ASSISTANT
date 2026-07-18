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
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

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

def is_valid_email_format(email):
    """Basic email format validation."""
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def generate_otp():
    """Generate a 6-digit OTP."""
    return str(random.randint(100000, 999999))

def send_otp_email(recipient_email, otp):
    """Send OTP to the given email via Gmail SMTP. Returns (success, message)."""
    try:
        sender_email = str(st.secrets["SENDER_EMAIL"]).strip()
        sender_password = str(st.secrets["SENDER_APP_PASSWORD"]).replace(" ", "").strip()
    except Exception:
        return False, "Email service not configured. Please add SENDER_EMAIL and SENDER_APP_PASSWORD to secrets."

    subject = f"Your Verification Code: {otp}"
    body = f"""Hello,

Your verification code for Kerala Tourism Assistant is: {otp}

This code is valid for 10 minutes. Please do not share it with anyone.

Thank you,
Kerala Tourism Assistant Team
"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr(("Kerala Tourism Assistant", sender_email))
    msg["To"] = recipient_email

    html_body = f"""\
<html>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #334155;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f8fafc; padding: 40px 20px;">
    <tr>
      <td align="center">
        <table width="100%" style="max-width: 480px; background-color: #ffffff; border-radius: 16px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 20px rgba(17, 153, 142, 0.05);">
          <!-- Brand Top Accent -->
          <tr>
            <td height="6" style="background: linear-gradient(90deg, #11998e, #38ef7d);"></td>
          </tr>
          <!-- Body Content -->
          <tr>
            <td style="padding: 40px 32px;">
              <h2 style="font-size: 22px; font-weight: 700; color: #11998e; margin: 0 0 6px 0; letter-spacing: -0.5px;">🌴 Kerala Tourism Assistant</h2>
              <p style="font-size: 13px; color: #94a3b8; margin: 0 0 30px 0; text-transform: uppercase; font-weight: 600; letter-spacing: 1px;">Email Verification</p>
              
              <p style="font-size: 15px; line-height: 1.6; margin: 0 0 16px 0; color: #334155;">Hello,</p>
              <p style="font-size: 15px; line-height: 1.6; margin: 0 0 24px 0; color: #334155;">Welcome to Kerala Tourism Assistant! Please use the verification code below to complete your registration:</p>
              
              <!-- OTP Container -->
              <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin: 30px 0;">
                <tr>
                  <td align="center">
                    <div style="display: inline-block; background-color: #f0fdf4; border: 1.5px solid rgba(17, 153, 142, 0.18); padding: 18px 36px; border-radius: 14px;">
                      <span style="font-size: 34px; font-weight: 800; letter-spacing: 8px; color: #11998e; font-family: monospace;">{otp}</span>
                    </div>
                  </td>
                </tr>
              </table>
              
              <p style="font-size: 13px; color: #64748b; line-height: 1.5; margin: 0 0 30px 0; text-align: center;">
                This OTP is valid for <strong>10 minutes</strong>. Please do not share it with anyone.
              </p>
              
              <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 30px 0;">
              
              <p style="font-size: 12px; line-height: 1.6; color: #94a3b8; margin: 0; text-align: center;">
                If you did not request this registration, you can safely ignore this email.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # Try Port 465 SSL first, fallback to Port 587 STARTTLS
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        return True, "OTP sent successfully!"
    except Exception as ssl_err:
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipient_email, msg.as_string())
            return True, "OTP sent successfully!"
        except smtplib.SMTPAuthenticationError:
            return False, "Gmail authentication failed. Please verify 2-Step Verification is ON and a valid 16-character Gmail App Password is configured in secrets."
        except smtplib.SMTPRecipientsRefused:
            return False, "❌ The recipient email address is invalid or refused by server."
        except Exception as err:
            return False, f"Failed to send OTP email: {str(err)}"

def register_user(email, password):
    email_clean = email.strip().lower()
    users = load_users()
    if email_clean in users:
        return False, "Email already registered!"
    users[email_clean] = {
        "password": hash_password(password),
        "sessions": {}
    }
    save_users(users)
    return True, "Registration successful!"

def login_user(email, password):
    email_clean = email.strip().lower()
    users = load_users()
    if email_clean not in users:
        return False, "Email not found!"
    if users[email_clean]["password"] != hash_password(password):
        return False, "Incorrect password!"
    return True, users[email_clean].get("sessions", {})

def save_user_sessions(email, sessions):
    email_clean = email.strip().lower()
    users = load_users()
    if email_clean in users:
        users[email_clean]["sessions"] = sessions
        save_users(users)

def delete_user(email):
    """Permanently delete a user account from storage."""
    email_clean = email.strip().lower()
    users = load_users()
    if email_clean in users:
        del users[email_clean]
        save_users(users)
        return True
    return False

# Initialize auth session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"
# OTP verification state
if "otp_sent" not in st.session_state:
    st.session_state.otp_sent = False
if "otp_code" not in st.session_state:
    st.session_state.otp_code = ""
if "otp_email" not in st.session_state:
    st.session_state.otp_email = ""
if "otp_password" not in st.session_state:
    st.session_state.otp_password = ""
if "otp_timestamp" not in st.session_state:
    st.session_state.otp_timestamp = 0
# Delete account confirmation state
if "confirm_delete" not in st.session_state:
    st.session_state.confirm_delete = False
# Kebab (⋮) menu toggle state — kept for compatibility
if "show_account_menu" not in st.session_state:
    st.session_state.show_account_menu = False
# Settings dialog toggle state
if "show_settings" not in st.session_state:
    st.session_state.show_settings = False

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

# ── Securely load Mistral API key from Streamlit secrets ──
mistral_api_key = st.secrets.get("MISTRAL_API_KEY", "YOUR_MISTRAL_API_KEY")
client = Mistral(
    api_key=mistral_api_key
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
            email_clean = email.strip().lower()
            if not email_clean or not password:
                st.error("Please fill in all fields.")
            else:
                success, result = login_user(email_clean, password)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.user_email = email_clean
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

        # ── STEP 1: Enter details and request OTP ──────────────────────────
        if not st.session_state.otp_sent:
            reg_email = st.text_input("📧 Gmail Address", placeholder="you@gmail.com", key="reg_email")
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                reg_pass = st.text_input("🔒 Password", type="password", placeholder="Create password", key="reg_pass")
            with col_p2:
                reg_confirm = st.text_input("✅ Confirm", type="password", placeholder="Repeat password", key="reg_confirm")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("📨 Send OTP to Mail", use_container_width=True, type="primary"):
                reg_email_clean = reg_email.strip().lower()
                if not reg_email_clean or not reg_pass or not reg_confirm:
                    st.error("Please fill in all fields.")
                elif not is_valid_email_format(reg_email_clean):
                    st.error("❌ Invalid email format. Please enter a valid email address (e.g. you@gmail.com).")
                elif len(reg_pass) < 6:
                    st.error("Password must be at least 6 characters.")
                elif reg_pass != reg_confirm:
                    st.error("Passwords do not match!")
                else:
                    # Check if already registered
                    existing_users = load_users()
                    if reg_email_clean in existing_users:
                        st.error("❌ This email is already registered! Please login.")
                    else:
                        with st.spinner("Sending OTP to your email..."):
                            otp = generate_otp()
                            sent, send_msg = send_otp_email(reg_email_clean, otp)
                        if sent:
                            st.session_state.otp_sent = True
                            st.session_state.otp_code = otp
                            st.session_state.otp_email = reg_email_clean
                            st.session_state.otp_password = reg_pass
                            st.session_state.otp_timestamp = time.time()
                            st.success(f"✅ OTP sent to **{reg_email_clean}**! Check your inbox (and spam folder).")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(send_msg)

        # ── STEP 2: Enter OTP to verify and complete registration ──────────
        else:
            st.info(f"📬 An OTP has been sent to **{st.session_state.otp_email}**. Enter it below to verify your email.")
            entered_otp = st.text_input("🔢 Enter OTP", placeholder="6-digit code", key="entered_otp", max_chars=6)
            st.markdown("<br>", unsafe_allow_html=True)

            col_verify, col_resend = st.columns(2)
            with col_verify:
                if st.button("✅ Verify & Create Account", use_container_width=True, type="primary"):
                    if not entered_otp:
                        st.error("Please enter the OTP.")
                    elif time.time() - st.session_state.otp_timestamp > 600:
                        st.error("⏰ OTP has expired (10 minutes). Please request a new one.")
                        st.session_state.otp_sent = False
                        st.rerun()
                    elif entered_otp.strip() != st.session_state.otp_code:
                        st.error("❌ Incorrect OTP. Please try again.")
                    else:
                        success, msg = register_user(
                            st.session_state.otp_email,
                            st.session_state.otp_password
                        )
                        if success:
                            # Reset OTP state
                            st.session_state.otp_sent = False
                            st.session_state.otp_code = ""
                            st.session_state.otp_email = ""
                            st.session_state.otp_password = ""
                            st.session_state.otp_timestamp = 0
                            st.success("🎉 Account created successfully! Please login.")
                            st.session_state.auth_mode = "login"
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(msg)
            with col_resend:
                if st.button("🔄 Resend OTP", use_container_width=True):
                    with st.spinner("Resending OTP..."):
                        otp = generate_otp()
                        sent, send_msg = send_otp_email(st.session_state.otp_email, otp)
                    if sent:
                        st.session_state.otp_code = otp
                        st.session_state.otp_timestamp = time.time()
                        st.success("✅ New OTP sent! Check your inbox.")
                        st.rerun()
                    else:
                        st.error(send_msg)

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("← Back", use_container_width=True):
                st.session_state.otp_sent = False
                st.session_state.otp_code = ""
                st.rerun()

# Show login page if not authenticated
if not st.session_state.logged_in:
    show_auth_page()
    st.stop()

# -----------------------------
# SETTINGS DIALOG
# -----------------------------
@st.dialog("⚙️ Account Settings")
def settings_dialog():
    # Immediately reset the trigger flag so subsequent unrelated reruns
    # (like sending a chat message or resizing the window) do not reopen the dialog.
    st.session_state.show_settings = False

    st.markdown("""
    <style>
    /* Dialog styling */
    div[data-testid="stDialog"] > div > div {
        border-radius: 20px !important;
        padding: 8px !important;
    }
    div[data-testid="stDialog"] .settings-option {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 14px 18px;
        border-radius: 14px;
        margin-bottom: 10px;
        border: 1px solid rgba(17,153,142,0.15);
        background: rgba(17,153,142,0.04);
        transition: background 0.2s;
        cursor: pointer;
    }
    </style>
    """, unsafe_allow_html=True)

    user_email = st.session_state.get("user_email", "")
    st.markdown(f"""
    <div style='background:linear-gradient(135deg,rgba(17,153,142,0.10),rgba(56,239,125,0.10));
                border-radius:12px;padding:11px 16px;margin-bottom:18px;
                border:1px solid rgba(17,153,142,0.20);'>
        <span style='font-size:0.82rem;color:#11998e;font-weight:700;'>👤 {user_email}</span>
    </div>
    """, unsafe_allow_html=True)
    # ── Main menu or Delete confirmation ───────────────────────────────────
    if not st.session_state.get("confirm_delete", False):

        # Logout
        if st.button("🚪  Logout", use_container_width=True, key="dlg_logout"):
            save_user_sessions(st.session_state.user_email, st.session_state.sessions)
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            st.session_state.sessions = {}
            st.session_state.current_session_id = ""
            st.session_state.intro_shown = False
            st.session_state.auth_mode = "login"
            st.session_state.show_settings = False
            st.rerun()

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        # Login Another Account
        if st.button("🔄  Login Another Account", use_container_width=True, key="dlg_switch"):
            save_user_sessions(st.session_state.user_email, st.session_state.sessions)
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            st.session_state.sessions = {}
            st.session_state.current_session_id = ""
            st.session_state.intro_shown = False
            st.session_state.auth_mode = "login"
            st.session_state.show_settings = False
            st.rerun()

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        # Register New Account
        if st.button("📝  Register New Account", use_container_width=True, key="dlg_register"):
            save_user_sessions(st.session_state.user_email, st.session_state.sessions)
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            st.session_state.sessions = {}
            st.session_state.current_session_id = ""
            st.session_state.intro_shown = False
            st.session_state.auth_mode = "register"
            st.session_state.otp_sent = False
            st.session_state.otp_code = ""
            st.session_state.show_settings = False
            st.rerun()

        st.markdown("""
        <hr style='border:none;border-top:1px solid rgba(231,76,60,0.20);margin:12px 0 10px 0;'>
        """, unsafe_allow_html=True)

        # Delete Account button — shows the actual account email
        if st.button(f"🗑️  Delete '{user_email}'", use_container_width=True, key="dlg_delete"):
            st.session_state.confirm_delete = True
            st.session_state.show_settings = True  # Keep dialog open for confirmation step
            st.rerun()

    else:
        # ── Delete confirmation screen ─────────────────────────────────────
        st.markdown(f"""
        <div style='background:rgba(231,76,60,0.08);border:1px solid rgba(231,76,60,0.28);
                    border-radius:14px;padding:16px;margin-bottom:14px;'>
            <p style='color:#c0392b;font-weight:700;font-size:0.95rem;margin:0 0 6px 0;'>
                ⚠️ Delete Account?
            </p>
            <p style='color:#7f1d1d;font-size:0.82rem;margin:0;line-height:1.5;'>
                You are about to permanently delete<br>
                <strong>{user_email}</strong><br>
                and <strong>all chat history</strong>.<br>
                This action <u>cannot be undone</u>.
            </p>
        </div>
        """, unsafe_allow_html=True)
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("✅ Yes, Delete", use_container_width=True,
                         type="primary", key="dlg_yes"):
                delete_user(user_email)
                st.session_state.logged_in = False
                st.session_state.user_email = ""
                st.session_state.sessions = {}
                st.session_state.current_session_id = ""
                st.session_state.intro_shown = False
                st.session_state.confirm_delete = False
                st.session_state.show_settings = False
                st.rerun()
        with col_no:
            if st.button("❌ Back", use_container_width=True, key="dlg_no"):
                st.session_state.confirm_delete = False
                st.session_state.show_settings = True  # Keep dialog open for main menu
                st.rerun()


# Trigger the dialog once per click
if st.session_state.get("show_settings", False):
    settings_dialog()

# -----------------------------
# SIDEBAR (CHAT HISTORY & NEW CHAT)
# -----------------------------
with st.sidebar:
    st.markdown("### 🌴 Kerala Tourism Assistant")

    # ── Sidebar CSS: just add bottom padding to prevent last chat hiding ──
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] > div:first-child {
        padding-bottom: 72px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Clean email display card ──
    st.markdown(f"""
    <div style='background:linear-gradient(135deg,rgba(17,153,142,0.12),rgba(56,239,125,0.12));
                border-radius:12px;padding:10px 14px;margin-bottom:8px;
                border:1px solid rgba(17,153,142,0.2);'>
        <span style='font-size:0.8rem;color:#11998e;font-weight:600;
                     white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
                     display:block;'>
            👤 {st.session_state.user_email}
        </span>
    </div>
    """, unsafe_allow_html=True)

    # ── New Chat button ──
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

    # Render all sessions with messages (newest first) — sidebar scrolls natively
    sessions_list = list(st.session_state.sessions.items())[::-1]
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

    # Settings button — JS will lift it out of scroll area
    if st.button("⚙️  Settings", key="open_settings", use_container_width=True,
                 help="Account settings — Logout, Switch account, Delete"):
        st.session_state.show_settings = True
        st.session_state.confirm_delete = False
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# JS: Physically move the ⚙️ Settings button OUT of the sidebar scroll area
# and pin it at the bottom of the sidebar — always visible, never scrolled away.
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<script>
(function() {
    var _timer = null;

    function pinSettingsBar() {
        /* Use parent document if in iframe, fallback to current */
        var doc = window.parent.document || document;
        
        /* ── 1. Find the sidebar section ── */
        var section = doc.querySelector('section[data-testid="stSidebar"]');
        if (!section) { setTimeout(pinSettingsBar, 300); return; }

        /* ── 2. Find the Settings button by text ── */
        var allBtns = section.querySelectorAll('button');
        var settingsBtn = null;
        for (var i = 0; i < allBtns.length; i++) {
            if (allBtns[i].innerText && allBtns[i].innerText.indexOf('Settings') !== -1) {
                settingsBtn = allBtns[i];
                break;
            }
        }
        if (!settingsBtn) { setTimeout(pinSettingsBar, 300); return; }

        /* ── 3. Walk up to the block-level container Streamlit wraps it in ── */
        var block = settingsBtn.parentElement;
        while (block && block !== section) {
            if (block.parentElement && block.parentElement === section) break;
            var pp = block.parentElement;
            if (pp && (pp.getAttribute('data-testid') === 'stVerticalBlockBorderWrapper' ||
                       pp.getAttribute('data-testid') === 'stVerticalBlock' ||
                       pp === section.querySelector('[data-testid="stSidebarContent"] > div') ||
                       pp === section.querySelector('[data-testid="stSidebarUserContent"] > div'))) {
                break;
            }
            block = block.parentElement;
        }
        if (!block) return;

        /* ── 4. Ensure CSS styling is injected into the head of the correct document ── */
        var styleId = '_pinned_settings_style';
        var styleEl = doc.getElementById(styleId);
        if (!styleEl) {
            styleEl = doc.createElement('style');
            styleEl.id = styleId;
            styleEl.innerHTML = `
                #_pinned_settings_bar button {
                    width: 100% !important;
                    background: transparent !important;
                    border: 1.5px solid rgba(17,153,142,0.32) !important;
                    color: #11998e !important;
                    font-weight: 600 !important;
                    font-size: 0.86rem !important;
                    border-radius: 10px !important;
                    padding: 9px 12px !important;
                    cursor: pointer !important;
                    font-family: inherit !important;
                    transition: background 0.18s !important;
                    box-shadow: none !important;
                }
                #_pinned_settings_bar button:hover {
                    background: rgba(17,153,142,0.09) !important;
                    border-color: #11998e !important;
                }
            `;
            doc.head.appendChild(styleEl);
        }

        /* ── 5. Get or create the pinned bar container ── */
        var bar = doc.getElementById('_pinned_settings_bar');
        if (!bar) {
            bar = doc.createElement('div');
            bar.id = '_pinned_settings_bar';
        }

        /* ── 6. Style the sidebar section so absolute positioning works ── */
        section.style.position = 'relative';

        /* ── 7. Style the pinned bar ── */
        bar.style.cssText = [
            'position:absolute',
            'bottom:0',
            'left:0',
            'right:0',
            'background:rgba(255,255,255,0.98)',
            'border-top:2px solid rgba(17,153,142,0.20)',
            'padding:10px 16px 14px 16px',
            'z-index:9999',
            'box-shadow:0 -4px 24px rgba(17,153,142,0.10)',
            'backdrop-filter:blur(14px)',
            '-webkit-backdrop-filter:blur(14px)'
        ].join(';');

        /* ── 8. Move block into bar (only if not already there) ── */
        if (!bar.contains(block)) {
            bar.innerHTML = '';
            bar.appendChild(block);
        }

        /* ── 9. Append bar to section (outside the scrollable inner div) ── */
        if (bar.parentElement !== section) {
            section.appendChild(bar);
        }

        /* ── 10. Ensure the scrollable inner div has bottom padding ── */
        var inner = section.querySelector('[data-testid="stSidebarContent"]') ||
                    section.querySelector('> div:first-child');
        if (inner) inner.style.paddingBottom = '72px';
    }

    /* Run immediately and with delays for Streamlit's async render */
    setTimeout(pinSettingsBar, 400);
    setTimeout(pinSettingsBar, 900);
    setTimeout(pinSettingsBar, 1800);

    /* Re-apply after every Streamlit rerender using MutationObserver */
    var mo = new MutationObserver(function() {
        clearTimeout(_timer);
        _timer = setTimeout(pinSettingsBar, 120);
    });
    setTimeout(function() {
        var doc = window.parent.document || document;
        var target = doc.querySelector('section[data-testid="stSidebar"]') || doc.body;
        mo.observe(target, { childList: true, subtree: true });
    }, 500);

    window.addEventListener('resize', pinSettingsBar);
})();
</script>
""", unsafe_allow_html=True)

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
    try:
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        bot_answer = response.choices[0].message.content
    except Exception as e:
        loader_placeholder.empty()
        err_msg = str(e)
        if "401" in err_msg or "Unauthorized" in err_msg:
            st.error("⚠️ **API Key Error:** The Mistral API key has expired or is invalid. Please update your API key in `app.py`.")
        elif "429" in err_msg:
            st.error("⚠️ **Rate Limit:** Too many requests. Please wait a moment and try again.")
        else:
            st.error(f"⚠️ **Error getting response:** {err_msg}")
        # Remove the failed user message from history to keep chat clean
        st.session_state.sessions[current_id]["messages"].pop()
        st.stop()



    # ── Save the bot response to history BEFORE the typewriter animation.
    # This ensures that even if the user switches to another chat during the
    # animation, the full answer is already stored and will be visible on return.
    st.session_state.sessions[current_id]["messages"].append({
        "role": "assistant",
        "content": bot_answer
    })
    # Also persist to file so it survives a full page reload
    save_user_sessions(st.session_state.user_email, st.session_state.sessions)

    # Clear the coconut loader
    loader_placeholder.empty()

    # 🔥 TYPEWRITER ANIMATION (response is already saved above)
    typewriter(bot_answer)

    st.rerun()

    # Testing Git