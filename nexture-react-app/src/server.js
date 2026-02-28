import express from "express";
import fetch from "node-fetch";
import cors from "cors";

const app = express();
app.use(express.json());
app.use(cors())

app.post("/api/ask", async (req, res) => {
  const { prompt } = req.body;

  const response = await fetch("http://localhost:11434/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "llama3",
      prompt: prompt,
      stream: false
    })
  });

  if(!response.ok){
    throw new Error(`Ollama API error: ${response.status}`);
  }
  console.log("Getting data")
  const data = await response.json();
  console.log(data)
  console.log("Posting")
  res.json({ reply: data.response || data.output || "No Response"});
});

app.post("/api/analyze", async (req, res) => {
   try {
    const response = await fetch("http://localhost:5002/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req.body)
    });

    const text = await response.text();
    console.log("Raw Python response:", text);
    
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      console.error("Failed to parse JSON from Python");
      data = {};
    }

    res.json({ reply: data });
  } catch (err) {
    console.error("Error calling Python backend:", err);
    res.status(500).json({ error: "Internal server error" });
  }
})


app.listen(3001, () => {
  console.log("Backend running on http://localhost:3001");
});

