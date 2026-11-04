import { useEffect, useState } from "react";

function App() {
  const [status, setStatus] = useState<string>("...");

  useEffect(() => {
    fetch("/api/health")
      .then((res) => res.json())
      .then((data) => setStatus(data.status))
      .catch(() => setStatus("erro ao conectar com o backend"));
  }, []);

  return (
    <div>
      <h1>AI Software Engineering Assistant</h1>
      <p>Backend status: {status}</p>
    </div>
  );
}

export default App;

