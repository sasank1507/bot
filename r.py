from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request
from pydantic import BaseModel
import os
import re
import math
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chat_models import init_chat_model
import google.generativeai as genai


load_dotenv()
PDF_DIR = "./sample_files"     
PERSIST_DIR = "./db"       
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)



session_memory: Dict[str, Dict[str, Any]] = {}

all_docs = []
for fname in os.listdir(PDF_DIR):
    if fname.lower().endswith(".pdf"):
        path = os.path.join(PDF_DIR, fname)
        loader = PyPDFLoader(path)
        pages = loader.load()
        for p in pages:
            p.metadata["source"] = fname
        all_docs.extend(pages)

embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)

if not os.path.exists(PERSIST_DIR):
    print("Creating new Chroma DB...")
    docs = text_splitter.split_documents(all_docs)

    for i, d in enumerate(docs):
        d.metadata.setdefault("chunk_id", f"chunk_{i}")
    db = Chroma.from_documents(docs, embeddings, persist_directory=PERSIST_DIR)
    db.persist()
else:
    print("Using existing Chroma DB...")
    db = Chroma(persist_directory=PERSIST_DIR, embedding_function=embeddings)


llm = init_chat_model(
    model="gemini-2.5-flash",       
    model_provider="openai",         
    api_key=GOOGLE_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai" 
)


def is_person_name(name: str) -> bool:
    prompt = f"""You are a strict name validator.

Input: "{name}"

Task: Decide if this is a reasonable human name (person name), not a verb,
adjective, common noun, or phrase.

Answer with EXACTLY one word: "yes" or "no"."""
    try:
        resp = llm.invoke(prompt)
        text = resp.content.strip().lower()
        return text == "yes"
    except Exception as e:
        print("Name validation error:", e)
        return False

def extract_name(text: str) -> str:
    patterns = [
        r"\bmy name is\s+([A-Z][a-zA-Z\-']{1,40})\b",
        r"\bI[' ]?am\s+([A-Z][a-zA-Z\-']{1,40})\b",
        r"\bI'm\s+([A-Z][a-zA-Z\-']{1,40})\b",
        r"\bthis is\s+([A-Z][a-zA-Z\-']{1,40})\b",
        r"\bname is\s+([A-Z][a-zA-Z\-']{1,40})\b",
        r"\bname-\s+([A-Z][a-zA-Z\-']{1,40})\b",
        r"\bname:\s+([A-Z][a-zA-Z\-']{1,40})\b",
        r"\bmyself\s+([A-Z][a-zA-Z\-']{1,40})\b",
        r"\bname -\s+([A-Z][a-zA-Z\-']{1,40})\b",
        r"\bname :\s+([A-Z][a-zA-Z\-']{1,40})\b",
        r"\bname-\s*([A-Z][a-zA-Z\-']{1,40})\b",
        r"\bname:\s*([A-Z][a-zA-Z\-']{1,40})\b"
    ]
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            correct_name=name.capitalize()
            if is_person_name(correct_name):
                return correct_name
    return None

def estimate_tokens_from_text(text: str) -> int:

    if not text:
        return 0
    return math.ceil(len(text) / 4)

def client_key_from_request(req: Request, session_id: str = None) -> str:

    if session_id:
        return session_id
    client_host = req.client.host if req.client else "unknown"
    return client_host

def fetch_top_chunks(query: str, k: int = 3):

    try:
        results = db.similarity_search_with_score(query, k=k)
    except Exception as e:
        print("Error in similarity search:", e)
        results = []
    return results


personalities={
    "naruto": {
        "role": "A determined ninja consultant inspired by Naruto",
        "tone": "enthusiastic, motivational, uses anime references",
        "traits": ["persistent", "optimistic", "team-player", "energetic"],
        "background": "Former ninja turned tech consultant, never gives up",
        "quirks": ["Never quit attitude!", "believes in the power of teamwork", 
                   "Uses fire/ninja metaphors"],
        "examples": [
            "Just like in my ninja days, we don't give up until the mission is complete!",
            "Your business transformation journey is like training to become a better ninja - consistency wins!",
            "Let's channel that ninja energy and level up your enterprise! 🔥"
        ]
    },
    "witty": {
        "role": "A clever tech consultant with sharp humor",
        "tone": "witty, sarcastic, playful but professional",
        "traits": ["intelligent", "humorous", "quick-thinking", "engaging"],
        "background": "Brilliant consultant who believes tech should be fun",
        "quirks": ["makes tech jokes", "uses clever analogies", "light sarcasm"],
        "examples": [
            "Ah, you want to modernize? Bold move. Even clouds need a good upgrade! ☁️",
            "SAP integration? That's our specialty - we make ERP look easy.",
            "Your cloud setup is about to get a serious glow-up!"
        ]
    }
}



def inject_personality(answer: str, user_input: str = "",personality_mode: str = "normal") -> str:
    if personality_mode == "normal" or personality_mode not in personalities:
        return answer
    
    persona = personalities[personality_mode]
    
    prompt = f"""You are {persona['role']}.
    Your tone: {persona['tone']}
    Your traits: {', '.join(persona['traits'])}
    Your background: {persona['background']}
    Your quirks/habits: {', '.join(persona['quirks'])}

    User asked: "{user_input}"
    Your answer: "{answer}"

    Rewrite the answer to match your persona while keeping all the technical information intact.
    Make it engaging and memorable, but stay professional and on-brand for Argano.
    Keep it concise - don't add more than 1-2 sentences of personality flair."""
        
    try:
        response = llm.invoke(prompt)
        return response.content.strip()
    except Exception as e:
        print(f"Personality injection error: {e}")
        ans=answer
    return ans

def build_system_prompt(context_chunks: List[str]) -> str:
    chunk_summary = "\n\n".join(context_chunks) if context_chunks else ""
    prompt = f"""
You are a polite, professional virtual receptionist (company assistant) for our company.



Behavior rules (VERY IMPORTANT):
- Use only the information provided in the "Context" section below to answer customer questions about the company.
- If the user's question is outside the company materials, or the context does not contain the necessary facts, reply exactly:
  "I don't have specific information about that in my current knowledge base. However, this is something our team can help you with! Would you like me to connect you with someone who can provide more detailed information? Please share your name and contact, and click Draft to get in touch with our team."
- Do NOT invent facts. If uncertain, say you don't have that information in the documents.
- Keep answers concise, factual, and helpful.
- If the user introduced their name earlier in the session, greet them by name only when it is naturally required but not for every answer.
- Give related emails from the documents if required or asked.

Context:
{chunk_summary}

Respond naturally and use the context above.
"""
    return prompt

def company_rag_response(query: str, client_key: str) -> Dict[str, Any]:
    results = fetch_top_chunks(query, k=3)

    used_chunks = []
    context_texts = []

    print("\nRetrieved Chunks\n")
    for i, item in enumerate(results, start=1):
        if isinstance(item, tuple) and len(item) == 2:
            doc, score = item
        else:
            doc = item[0] if item else None
            score = None

        chunk_id = doc.metadata.get("chunk_id", f"chunk_{i}") if doc else f"chunk_{i}"
        preview = (doc.page_content[:300] + "...") if doc else ""

        print(f"--- Chunk {i} ---")
        print(f"Chunk ID: {chunk_id}")
        print(f"Score: {score}")
        print(f"Source: {doc.metadata.get('source') if doc else None}")

        used_chunks.append({
            "chunk_id": chunk_id,
            "score": score,
            "source": doc.metadata.get("source") if doc else None,
            "preview": preview,
        })

        if doc:
            context_texts.append(doc.page_content)

    system_prompt = build_system_prompt(context_texts)
    sess = session_memory.get(client_key, {})
    user_name = sess.get("name")

    if user_name:
        system_prompt += f"\n\nSession user name: {user_name}\n"

    final_input = f"{system_prompt}\n\nUser question: {query}\n\nAnswer:"

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        token_count_response = model.count_tokens(final_input)
        prompt_tokens = token_count_response.total_tokens
        
        response = llm.invoke(final_input)
        text = getattr(response, "content", None) or str(response)

        completion_tokens = estimate_tokens_from_text(text)
        total_tokens = prompt_tokens + completion_tokens

        print("\n===== Token Usage =====")
        print(f"Prompt Tokens: {prompt_tokens}")
        print(f"Completion Tokens: {completion_tokens}")
        print(f"Total Tokens: {total_tokens}\n")
            
    except Exception as e:
        print(f"LLM Error: {str(e)}\n")
        return {
            "answer": "Error: LLM invocation failed.",
            "tokens": 0,
            "used_chunks": used_chunks,
            "llm_error": str(e)
        }

    return {
        "answer": text,
        "tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "used_chunks": used_chunks,
    }


def is_relevant_to_company(query: str, threshold_high: float = 1.1, threshold_low: float = 1.7) -> tuple:

    try:
        results = db.similarity_search_with_score(query, k=1)
    except Exception as e:
        print("similarity check error:", e)
        return 'not_relevant', None
    
    if not results:
        return 'not_relevant', None
    
    first = results[0]
    if isinstance(first, tuple) and len(first) == 2:
        _, score = first
        try:
            if score < threshold_low:
                return 'highly_relevant', score
            elif score < threshold_high:
                return 'somewhat_relevant', score
            else:
                return 'not_relevant', score
        except Exception:
            return 'not_relevant', score
    return 'not_relevant', None

def is_acknowledgment(user_input: str) -> bool:
    prompt = f"""Determine if this user message is an acknowledgment, confirmation, or agreement or a compliment(like okay, got it, thanks, understood,thats impressive,nice,good etc).
    
User message: "{user_input}"

Respond with ONLY "yes" or "no"."""
    
    try:
        response = llm.invoke(prompt)
        result = response.text.strip().lower()
        return "yes" in result
    except Exception as e:
        print(f"Error in acknowledgment check: {e}")
        return False

def classify_intent_and_extract(user_input: str, client_key: str) -> dict:
    stored_name = session_memory.get(client_key, {}).get("name")
    
    prompt = f"""
    Analyze the user's message.
    User Input: "{user_input}"
    Context: User Name is "{stored_name}" if known.

    Classify into ONE category:
    1. GREETING_ONLY: User is ONLY greeting (e.g. "Hello","Hi", "Hey", "Wassup") or even they are identify themselves. No questions asked.
    2. QUESTION: User is asking for information, even if they say hi or name first (e.g., "Hi, what is AWS?", "Tell me about services").
    
    If GREETING_ONLY, generate a warm greeting response and if they just identified themselves just greet by name(nice to meet you)but dont offer any services.
    If QUESTION, return "RAG_REQUIRED".

    Output JSON format:
    {{
        "intent": "GREETING_ONLY" | "QUESTION",
        "response_text": "your generated response if greeting, else null"
    }}
    """
    try:
        response = llm.invoke(prompt)
        text = response.content.strip()
        

        if text.startswith("```"):
            text = text.split('\n', 1)[1]
        if text.endswith("```"):
            text = text.rsplit('\n', 1)[0]
        
        text = text.strip()
        
        import json
        result = json.loads(text)
        
        return result
    except Exception as e:
        print(f"[ERROR] Intent parsing failed: {e}")
        print(f"[ERROR] Returning fallback QUESTION\n")
        return {"intent": "QUESTION", "response_text": None}

app = FastAPI(title="Company Receptionist RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryIn(BaseModel):
    query: str
    session_id: Optional[str] = None
    personality_mode: str = "normal" 


@app.post("/ask")
async def ask_api(data: QueryIn, request: Request):
    user_input = data.query.strip()
    client_key = client_key_from_request(request, data.session_id)
    personality_mode = data.personality_mode
    name = extract_name(user_input)
    if name:
        session_memory.setdefault(client_key, {})["name"] = name
    contact_pattern = r"(\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b|(?:\+?1?\d{9,15}))"
    contact_match = re.search(contact_pattern, user_input)
    if contact_match:
        contact = contact_match.group(0)
        session_memory.setdefault(client_key, {})["contact"] = contact
        return {
            "answer": "Got it! Please click **Draft** when you're ready to send."
        }
    result = classify_intent_and_extract(user_input, client_key)
    intent = result.get("intent")
    llm_response = result.get("response_text")

    if intent == "GREETING_ONLY":
        final_answer = inject_personality(llm_response, user_input, personality_mode)
        print(f"\nAgent: Greeting Agent\n")
        return {"answer": final_answer, "agent_type": "greeting"}
    
    '''if name and not re.search(r'(\?|help|tell|what|how|can|do|you|service|offer|about)', user_input, flags=re.I):
        return {
            "answer": f"Nice to meet you, {name}!"
        }
    '''
    if is_acknowledgment(user_input):
        stored_name = session_memory.get(client_key, {}).get("name")
        if stored_name:
            answer = f"Great! I'm here to help you, {stored_name}. What would you like to know about Argano's services?"
        else:
            answer = "Great! I'm here to help you. What would you like to know about Argano's services?"
        persona_answer=inject_personality(answer,user_input,personality_mode)
        print(f"\nAgent: Acknowledgment Handler\n")
        return {
                "answer": persona_answer,
                "word_count": len(answer.split())
            }
    
    relevance_type, top_score = is_relevant_to_company(user_input)
    
    if relevance_type == 'highly_relevant':
        rag_resp = company_rag_response(user_input, client_key)
        rag_answer = rag_resp["answer"]
        persona_answer=inject_personality(rag_answer,user_input,personality_mode)
        print(f"\nAgent: RAG Agent\n")
        rag_resp["answer"]=persona_answer
        rag_resp["word_count"] = len(rag_answer.split())
        rag_resp["top_score"] = top_score
        
        
        return rag_resp
    
    elif relevance_type == 'somewhat_relevant':
        answer = (
            "I don't have specific information about that in my current knowledge base. "
            "However, this is something our team can definitely help you with! "
            "Please share your name and contact number, and click **Draft** to get in touch with someone who can assist."
        )
        persona_answer=inject_personality(answer,user_input,personality_mode)
        print(f"\nAgent: Out-of-scope Handler (Related)\nAnswer: {answer}\n")
        return {
            "answer": persona_answer,
            "top_score": top_score,
            "word_count": len(answer.split())
        }
    
    else:
        answer = "I can only answer questions related to our company's services and offerings. How else can I assist you?"
        print(f"\nAgent: Out-of-scope Handler (Unrelated)\nAnswer: {answer}\n")
        return {
            "answer": answer,
            "top_score": top_score,
            "word_count": len(answer.split())
        }

