import { useState } from "react";
import { RepoSubmit } from "./components/RepoSubmit";
import { ChatView } from "./components/ChatView";

interface ActiveRepo {
  id: string;
  name: string;
  url: string;
}

function App() {
  const [activeRepo, setActiveRepo] = useState<ActiveRepo | null>(null);

  return (
    <div className="app-container">
      <header className="app-header">
        <h1 className="app-title">AI Software Engineering Assistant</h1>
        <p className="app-subtitle">
          Análise e chat inteligente sobre código-fonte com RAG e Embeddings
        </p>
      </header>

      {activeRepo ? (
        <ChatView
          repoId={activeRepo.id}
          repoName={activeRepo.name}
          githubUrl={activeRepo.url}
          onBack={() => setActiveRepo(null)}
        />
      ) : (
        <RepoSubmit onReady={(repo) => setActiveRepo(repo)} />
      )}
    </div>
  );
}

export default App;
