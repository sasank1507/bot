import React, { useState, useEffect, useRef } from 'react';
import 'bootstrap/dist/css/bootstrap.min.css';
import '../App.css';
import Markdown from 'react-markdown';

const Chatbot = () => {
  const [messages, setMessages] = useState([
    { from: "bot", text: "Hello! How can I assist you today?", agentMode: "normal" }
  ]);

  const [input, setInput] = useState("");
  const [isBotTyping, setIsBotTyping] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [userName, setUserName] = useState("");
  const [userContact, setUserContact] = useState("");
  const [showPopup, setShowPopup] = useState(false);
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [emailBody, setEmailBody] = useState("");
  const [isEditingFields, setIsEditingFields] = useState(false);
  const [isEditingSummary, setIsEditingSummary] = useState(false);
  const [showEmailSentPopup, setShowEmailSentPopup] = useState(false);
  const [personalityMode, setPersonalityMode] = useState("normal");
  const messagesEndRef = useRef(null);
  const agentIcons = {
    "normal": "👤",
    "naruto": "🔥",
    "witty": "😎"
  };


  useEffect(() => {
    const id = crypto.randomUUID ? crypto.randomUUID() : 'session_' + Date.now() + '_' + Math.random();
    setSessionId(id);
    console.log("Session ID for this page load:", id);
  }, []);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const convertLinks = (text) => {
    return text.replace(/(https?:\/\/[^\s]+|(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,})/g, (match) => {
      const url = match.startsWith('http') ? match : `https://${match}`;
      return `[${match}](${url})`;
    });
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || !sessionId) return;

    const userMsg = { from: "user", text: input };
    setMessages(prev => [...prev, userMsg]);
    setIsBotTyping(true);

    const nameMatch = input.match(/(?:my name is|i'm|i am|this is|name is|name:|name-)\s+([A-Z][a-zA-Z\-']{1,40})/i);
    if (nameMatch) {
      setUserName(nameMatch[1]);
    }

    const contactPattern = /(\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b|(?:\+?1?\d{9,15}))/;
    const contactMatch = input.match(contactPattern);
    if (contactMatch) {
      setUserContact(contactMatch[0]);
    }

    const query = input;
    setInput("");

    try {
      const response = await fetch("http://localhost:8000/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          query, 
          session_id: sessionId,
          personality_mode: personalityMode
        })
      });

      const data = await response.json();
      setMessages(prev => [...prev, { from: "bot", text: data.answer, agentMode: data.agent_mode || personalityMode }]);
    } catch (error) {
      setMessages(prev => [...prev, {
        from: "bot",
        text: "Error: Unable to reach the server.",
        agentMode: personalityMode
      }]);
    } finally {
      setIsBotTyping(false);
    }
  };

  const handleSummary = async () => {
    try {
      const response = await fetch("http://localhost:8081/process_and_email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          messages: messages.map(m => m.text),
          user_name: userName || null,
          user_contact: userContact || null
        })
      });

      const data = await response.json();
      const emailText = data.email;

      const subjectMatch = emailText.match(/Subject:\s*(.*)/);
      const toMatch = emailText.match(/To:\s*(.*)/);

      setSubject(subjectMatch ? subjectMatch[1].trim() : "");
      setTo(toMatch ? toMatch[1].trim() : "");
      let body = "";
      const splitBody = emailText.split("Dear Team,");
      if (splitBody.length > 1) {
        body = "Dear Team,\n" + splitBody[1].trim();
      }

      setEmailBody(body);
      setShowPopup(true);
      setShowEmailSentPopup(true);

      setTimeout(() => setShowEmailSentPopup(false), 2000);
    } catch (err) {
      alert("Error fetching summary");
    }
  };

  const closePopup = () => {
    setShowPopup(false);
    setIsEditingFields(false);
    setIsEditingSummary(false);
  };

  const handleModeChange = (mode) => {
    setPersonalityMode(mode);

  };

  // Define background colors for each mode
  const getBackgroundColor = (mode) => {
    switch (mode) {
      case 'naruto':
        return '#fff3cd'; // Light yellow/orange
      case 'witty':
        return '#d1ecf1'; // Light blue/green
      default:
        return '#f8f9fa'; // Light gray (default bg-light)
    }
  };

  return (
    <div className="container-fluid vh-100 d-flex justify-content-center align-items-center bg-white">
      <div className="row w-100 shadow-lg rounded main-container">
        <div className="col-lg-3 col-md-4 col-12 sidebar d-flex flex-column align-items-center justify-content-center text-center p-3">
          <div className="d-flex flex-column w-100 mb-4">
            <h6 className="text-uppercase text-muted mb-2" style={{ letterSpacing: '1px' }}>
              Agent Modes
            </h6>
            <div className="d-flex flex-column gap-2">
              <button
                type="button"
                className={`btn btn-lg w-100 rounded-pill d-flex align-items-center justify-content-center ${
                  personalityMode === "normal" ? "btn-info text-white" : "btn-outline-secondary"
                }`}
                onClick={() => handleModeChange("normal")}
                title="Normal mode - Professional"
              >
                <span style={{ fontSize: "1.4rem", marginRight: "8px" }}>👤</span>
                <span>Normal</span>
              </button>

              <button
                type="button"
                className={`btn btn-lg w-100 rounded-pill d-flex align-items-center justify-content-center ${
                  personalityMode === "naruto" ? "btn-warning text-dark" : "btn-outline-warning"
                }`}
                onClick={() => handleModeChange("naruto")}
                title="Naruto mode - Enthusiastic"
              >
                <span style={{ fontSize: "1.4rem", marginRight: "8px" }}>🔥</span>
                <span>Naruto</span>
              </button>

              <button
                type="button"
                className={`btn btn-lg w-100 rounded-pill d-flex align-items-center justify-content-center ${
                  personalityMode === "witty" ? "btn-success text-white" : "btn-outline-success"
                }`}
                onClick={() => handleModeChange("witty")}
                title="Witty mode - Humorous"
              >
                <span style={{ fontSize: "1.4rem", marginRight: "8px" }}>😎</span>
                <span>Witty</span>
              </button>
            </div>
          </div>

          <h3 className="h5 mb-3 text-dark">How Argano Can Help You</h3>
          <p className="sidebar-text text-dark small mb-3">
            Argano empowers businesses through digital transformation, intelligent automation, and optimized operations.
          </p>
          <a
            href="https://argano.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="btn argano-btn"
            aria-label="Visit Argano website"
          >
            Visit Argano
          </a>
        </div>

        <div className="col-lg-9 col-md-8 col-12 chat-container d-flex flex-column bg-light">
          <div 
            className="messages-container d-flex flex-column gap-3 p-3 overflow-auto flex-grow-1"
            style={{ backgroundColor: getBackgroundColor(personalityMode) }}
          >
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`p-2 rounded shadow-sm message-bubble position-relative ${
                  msg.from === "bot"
                    ? "bot-msg align-self-start bg-light border mt-3"  // Added mt-3 for slight downward shift
                    : "user-msg align-self-end text-black"
                }`}
                style={msg.from === "bot" ? { borderLeft: `4px solid ${msg.agentMode === 'naruto' ? '#ffc107' : msg.agentMode === 'witty' ? '#28a745' : '#0d6efd'}`} : {} }
              >
                {msg.from === "bot" && msg.agentMode && (
                  <div className="mode-label position-absolute top-0 start-0 bg-secondary px-1 py-2 rounded-end shadow-sm text-center" style={{ fontSize: '0.7rem', fontWeight: 'bold', zIndex: 1, writingMode: 'vertical-rl', textOrientation: 'mixed', width: '20px', left: '-20px' }}>
                    {agentIcons[msg.agentMode]} AGENT
                  </div>
                )}
                <Markdown>{convertLinks(msg.text)}</Markdown>
              </div>
            ))}

            {isBotTyping && (
              <div className="typing-indicator d-inline-flex align-self-start p-1 rounded border bg-light">
                <div className="typing-dots d-flex gap-1">
                  <span className="bg-secondary rounded-circle"></span>
                  <span className="bg-secondary rounded-circle"></span>
                  <span className="bg-secondary rounded-circle"></span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          <form onSubmit={handleSend} className="input-container d-flex gap-2 p-3 bg-white border-top position-sticky bottom-0">
            <input
              type="text"
              className="form-control flex-grow-1 rounded-pill border-secondary bg-light"
              placeholder="Type a message... "
              value={input}
              onChange={e => setInput(e.target.value)}
            />

            <button type="submit" className="btn btn-primary rounded-pill px-3">
              Send
            </button>

            <button type="button" className="btn btn-primary rounded-pill px-3" onClick={handleSummary}>
              Draft
            </button>
          </form>
        </div>
      </div>

      {showPopup && (
        <div className="modal fade show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
          <div className="modal-dialog modal-fullscreen">
            <div className="modal-content d-flex flex-column h-100">
              <div className="modal-header">
                <h5 className="modal-title">Email Draft</h5>
                <button type="button" className="btn-close" onClick={closePopup}></button>
              </div>

              <div className="modal-body d-flex flex-column gap-4 p-4 overflow-auto">
                <div className="email-fields bg-light p-3 rounded border">
                  <div className="d-flex justify-content-between align-items-center mb-3">
                    <h6>Email Details</h6>
                    <button
                      className="btn btn-outline-primary btn-sm"
                      onClick={() => setIsEditingFields(!isEditingFields)}
                    >
                      {isEditingFields ? "Save" : "Edit"}
                    </button>
                  </div>

                  <div className="row g-3">
                    <div className="col-md-6">
                      <label className="form-label">To</label>
                      <input
                        type="email"
                        className="form-control"
                        value={to}
                        onChange={e => setTo(e.target.value)}
                        disabled={!isEditingFields}
                      />
                    </div>

                    <div className="col-md-6">
                      <label className="form-label">Subject</label>
                      <input
                        type="text"
                        className="form-control"
                        value={subject}
                        onChange={e => setSubject(e.target.value)}
                        disabled={!isEditingFields}
                      />
                    </div>
                  </div>
                </div>

                <div className="summary-block bg-light p-3 rounded border">
                  <div className="d-flex justify-content-between align-items-center mb-3">
                    <h6>Email Body</h6>
                    <button
                      className="btn btn-outline-primary btn-sm"
                      onClick={() => setIsEditingSummary(!isEditingSummary)}
                    >
                      {isEditingSummary ? "Save" : "Edit"}
                    </button>
                  </div>

                  {isEditingSummary ? (
                    <textarea
                      className="form-control"
                      rows="10"
                      value={emailBody}
                      onChange={e => setEmailBody(e.target.value)}
                    />
                  ) : (
                    <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{emailBody}</pre>
                  )}
                </div>
              </div>

              <div className="modal-footer">
                <button className="btn btn-secondary" onClick={closePopup}>Close</button>
                <button className="btn btn-primary">Send Email</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showEmailSentPopup && (
        <div className="modal fade show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }} tabIndex="-1">
          <div className="modal-dialog modal-dialog-centered">
            <div className="modal-content border-0 shadow-lg email-sent-popup" style={{ borderRadius: '20px', background: 'linear-gradient(135deg, #28a745, #20c997)', boxShadow: '0 10px 30px rgba(0,0,0,0.3)', animation: 'popupFadeIn 0.5s ease-out' }}>
              <div className="modal-body text-center p-5" style={{ animation: 'contentSlideUp 0.6s ease-out 0.2s both' }}>
                <div className="mb-4" style={{ animation: 'iconBounce 1s ease-out 0.4s both' }}>
                  <svg className="bi bi-check-circle-fill email-sent-icon" width="100" height="100" fill="currentColor" viewBox="0 0 16 16" style={{ filter: 'drop-shadow(0 0 15px rgba(255,255,255,0.7))', animation: 'iconGlow 2s ease-in-out infinite alternate' }}>
                    <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zm-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/>
                  </svg>
                </div>
                <h4 className="mb-3 email-sent-title" style={{ fontWeight: 'bold', textShadow: '0 3px 6px rgba(0,0,0,0.4)', animation: 'textFadeIn 0.8s ease-out 0.6s both' }}>Draft Ready!</h4>
                <p className="mb-0 email-sent-subtitle" style={{ fontSize: '1.1rem', textShadow: '0 2px 4px rgba(0,0,0,0.3)', animation: 'textFadeIn 1s ease-out 0.8s both' }}>Your chat summary has been prepared.</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Chatbot;