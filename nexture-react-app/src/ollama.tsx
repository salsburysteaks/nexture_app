import { useState } from "react";

export default function Chat() {
  const [input, setInput] = useState("");
  const [reply, setReply] = useState("");

  async function sendPrompt() {
    const res = await fetch("http://localhost:3001/api/ask", {
        
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: input })
    });

    const data = await res.json();
    setReply(data.reply);
  }

  return (
    <div className="p-6 space-y-4">
      <textarea
        className="resize-none w-full h-32 p-2 bg-slate-800"
        value={input}
        onChange={e => setInput(e.target.value)}
      />
      <button onClick={sendPrompt} className="bg-indigo-600 px-4 py-2 rounded">
        Ask AI
      </button>

      <pre className="bg-slate-900 p-4 rounded whitespace-pre-wrap">
        {reply}
      </pre>
    </div>
  );
}