import { useState, useEffect } from "react";

function App() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hi! I'll help you build your resume. What role are you building a resume for?" }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => {
    let id = localStorage.getItem("resume_session_id");
    if (!id) {
      id = "session-" + Date.now();
      localStorage.setItem("resume_session_id", id);
    }
    return id;
  });
  const [progress, setProgress] = useState({});

  const [optimizing, setOptimizing] = useState(false);
  const [suggestions, setSuggestions] = useState(null);

useEffect(() => {
  const loadConversation = async () => {
    try {
      const response = await fetch("http://127.0.0.1:8000/get-conversation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: "" })
      });
      const data = await response.json();
      if (data.messages && data.messages.length > 0) {
        setMessages(data.messages);
        checkProgress(sessionId);
      }
    } catch (err) {
      console.log("Failed to load conversation:", err);
    }
  };
  loadConversation();
}, []);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: userMessage.content })
      });
      const data = await response.json();
      setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
      checkProgress(sessionId);
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", content: "Error connecting to server." }]);
    } finally {
      setLoading(false);
    }
  };

  const checkProgress = async (currentSessionId) => {
    try {
      const response = await fetch("http://127.0.0.1:8000/generate-resume-data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: currentSessionId, message: "" })
      });
      const data = await response.json();
      if (data && data.resume_data) {
        const d = data.resume_data;
        setProgress({
          personal_info: !!d.personal_info?.full_name && !!d.personal_info?.email,
          target_role: !!d.target_role?.title,
          experience: d.experience?.length > 0,
          education: d.education?.length > 0,
          skills: d.skills?.technical?.length > 0 || d.skills?.soft?.length > 0,
          projects: d.projects?.length > 0,
        });
      }
    } catch (err) {
      console.log("Progress check failed silently:", err);
    }
  };

  const generateResume = async () => {
    setLoading(true);
    try {
      const response = await fetch("http://127.0.0.1:8000/generate-resume-data", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: "" })
      });
      const data = await response.json();
      console.log("Resume data:", data);
      alert("Resume data generated! Check the browser console (F12) to see it.");
    } catch (err) {
      alert("Error generating resume data.");
    } finally {
      setLoading(false);
    }
  };

  const startNewConversation = () => {
    const newId = "session-" + Date.now();
    localStorage.setItem("resume_session_id", newId);
    window.location.reload();
  };

  const optimizeResume = async () => {
    setOptimizing(true);
    try {
      const response = await fetch("http://127.0.0.1:8000/optimize-resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: "" })
      });
      const data = await response.json();
      if (data.error) {
        alert(data.error);
      } else {
        setSuggestions(data);
      }
    } catch (err) {
      alert("Error getting optimization suggestions.");
    } finally {
      setOptimizing(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter") sendMessage();
  };

  return (
    <div style={{ maxWidth: "500px", margin: "40px auto", fontFamily: "sans-serif" }}>
      <h2>Resume Builder Chat</h2>
      <div style={{ fontSize: "13px", marginBottom: "12px", color: "#555" }}>
        Progress: {" "}
        {Object.entries({
          "Personal Info": progress.personal_info,
          "Target Role": progress.target_role,
          "Experience": progress.experience,
          "Education": progress.education,
          "Skills": progress.skills,
          "Projects": progress.projects,
        }).map(([label, done]) => (
          <span key={label} style={{ marginRight: "10px" }}>
            {done ? "✅" : "⬜"} {label}
          </span>
        ))}
      </div>
      <div style={{
        border: "1px solid #ccc",
        borderRadius: "8px",
        height: "400px",
        overflowY: "auto",
        padding: "12px",
        marginBottom: "12px"
      }}>
        {messages.map((msg, i) => (
          <div key={i} style={{
            textAlign: msg.role === "user" ? "right" : "left",
            margin: "8px 0"
          }}>
            <span style={{
              display: "inline-block",
              padding: "8px 12px",
              borderRadius: "12px",
              background: msg.role === "user" ? "#DCF8C6" : "#F1F0F0",
              maxWidth: "80%"
            }}>
              {msg.content}
            </span>
          </div>
        ))}
        {loading && <div>Thinking...</div>}
      </div>

      <div style={{ display: "flex", gap: "8px" }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Type your answer..."
          style={{ flex: 1, padding: "8px" }}
        />
        <button onClick={sendMessage} disabled={loading}>Send</button>
      </div>

      <button onClick={generateResume} style={{ marginTop: "12px", width: "100%" }} disabled={loading}>
        Generate Resume Data
      </button>

      <button onClick={startNewConversation} style={{ marginTop: "8px", width: "100%", background: "#eee", color: "#333", padding: "8px", border: "1px solid #ccc", borderRadius: "4px", cursor: "pointer" }}>
        Start New Conversation
      </button>

      <button onClick={optimizeResume} style={{ marginTop: "8px", width: "100%", background: "#4CAF50", color: "#fff", padding: "8px", border: "none", borderRadius: "4px", cursor: "pointer" }} disabled={optimizing}>
        {optimizing ? "Analyzing..." : "Optimize My Resume"}
      </button>

      {suggestions && (
        <div style={{ marginTop: "16px", padding: "12px", border: "1px solid #ccc", borderRadius: "8px", background: "#f9f9f9", whiteSpace: "pre-wrap", fontSize: "14px" }}>
          <h3>Suggestions for {suggestions.role}</h3>
          <p>{suggestions.suggestions}</p>
          {suggestions.sources_used && suggestions.sources_used.length > 0 && (
            <div style={{ marginTop: "10px", fontSize: "12px", color: "#666" }}>
              Sources: {suggestions.sources_used.map((s, i) => (
                <a key={i} href={s} target="_blank" rel="noreferrer" style={{ display: "block" }}>{s}</a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;