import os
import re
from dotenv import load_dotenv
from llama_index.core import Settings
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import google.generativeai as genai

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

class ChatRequest(BaseModel):
    messages: list[str]
    user_name: Optional[str] = None
    user_contact: Optional[str] = None


Settings.llm = GoogleGenAI(
    model="gemini-2.5-flash",
    temperature=0.2,
)

Settings.embed_model = HuggingFaceEmbedding(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


def summarize_conversation(convo_text):
    prompt = (
        "Summarize the following chat conversation in 4–5 clear sentences. "
        "If any email is mentioned, include it.\n\n"
        f"{convo_text}\n"
    )
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        

        token_count_response = model.count_tokens(prompt)
        prompt_tokens = token_count_response.total_tokens
        
        resp = Settings.llm.complete(prompt)
        summary_text = resp.text.strip()
        

        completion_tokens = len(summary_text.split()) * 1
        total_tokens = prompt_tokens + completion_tokens
        
        print("\n===== Summarization Token Usage =====")
        print(f"Prompt Tokens: {prompt_tokens}")
        print(f"Completion Tokens: {completion_tokens}")
        print(f"Total Tokens: {total_tokens}\n")
        
        return summary_text
    except Exception as e:
        print("Error during summarization:", repr(e))
        return None

def extract_email(text):
    if not text:
        return []

    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    found = re.findall(email_pattern, text)

    unique_emails = []
    seen = set()
    for email in found:
        email_clean = email.rstrip(".") 
        if email_clean not in seen:
            unique_emails.append(email_clean)
            seen.add(email_clean)

    return unique_emails

def detect_topics_llm(convo_text):
    prompt = (
        "Identify the main topics discussed in this conversation. "
        "Return ONLY a comma-separated list of short topic labels."
        "Do not include sentences, explanations, or extra text.\n\n"
        f"{convo_text}\n"
    )

    try:
        resp = Settings.llm.complete(prompt)
        topics_text = resp.text.strip()

        topics = [t.strip() for t in topics_text.split(",") if t.strip()]
        if not topics:
            return ["General Inquiry"]

        return topics

    except Exception as e:
        print("Topic detection error:", repr(e))
        return ["General Inquiry"]



def build_subject(topics):
    if not topics:
        return "User Query Summary"

    if len(topics) == 1:
        return f"{topics[0]} — User Query Summary"

    combined = ", ".join(topics[:-1]) + " & " + topics[-1]
    return f" User Query Summary related to {combined} "

def generate_email(summary, email_list, user_name=None, user_contact=None,subject=None):
    email_to = ", ".join(email_list)
    email_text = f"""
**Email Draft**

Subject: {subject} 
To: {email_to}



Dear Team,
From: {user_name or "Not provided"}  

{summary}

Please proceed with the required assistance.
Contact: {user_contact or "Not provided"}
Warm regards,  
AI Support Bot
"""
    return email_text.strip()

def run(conversation_text, user_name=None, user_contact=None):
    summary = summarize_conversation(conversation_text)

    if summary is None:
        raise RuntimeError("Summarization failed; cannot continue.")


    emails_raw = extract_email(conversation_text) + extract_email(summary)

    final_emails = []
    seen = set()
    for email in emails_raw:
        if email not in seen:
            final_emails.append(email)
            seen.add(email)


    if not final_emails:
        final_emails = ["team@Argano.com"]
    topics = detect_topics_llm(conversation_text)

    
    subject = build_subject(topics)

    return generate_email(summary, final_emails, user_name, user_contact,subject)

@app.post("/process_and_email")
def process_and_email(payload: dict):
    messages = payload.get("messages", [])
    user_name = payload.get("user_name")
    user_contact = payload.get("user_contact")

    conversation_text = "\n".join(messages)

    email_draft = run(conversation_text, user_name, user_contact)

    return {"email": email_draft}
