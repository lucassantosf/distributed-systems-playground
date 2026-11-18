import { useState, useCallback } from "react";
import { Dashboard } from "./components/Dashboard";
import { RepoSubmit } from "./components/RepoSubmit";
import { ChatView } from "./components/ChatView";

type Screen = "dashboard" | "add-repo" | "chat";

interface ActiveRepo {
  id: string;
  name: string;
  url: string;
}

function App() {
  const [screen, setScreen] = useState<Screen>("dashboard");
  const [activeRepo, setActiveRepo] = useState<ActiveRepo | null>(null);
  const [initialConversationId, setInitialConversationId] = useState<string | undefined>(undefined);
  // Incrementar força o Dashboard a recarregar a lista de repos
  const [dashboardRefresh, setDashboardRefresh] = useState(0);

  const goToDashboard = useCallback(() => {
    setScreen("dashboard");
    setActiveRepo(null);
    setInitialConversationId(undefined);
    setDashboardRefresh((n) => n + 1); // força reload da lista
  }, []);

  const goToChat = useCallback(
    (repo: ActiveRepo, conversationId?: string) => {
      setActiveRepo(repo);
      setInitialConversationId(conversationId);
      setScreen("chat");
    },
    []
  );

  const goToAddRepo = useCallback(() => {
    setScreen("add-repo");
  }, []);

  return (
    <div className="app-container">
      <header className="app-header">
        <h1
          className="app-title"
          style={{ cursor: screen !== "dashboard" ? "pointer" : "default" }}
          onClick={screen !== "dashboard" ? goToDashboard : undefined}
          title={screen !== "dashboard" ? "Voltar ao início" : undefined}
        >
          AI Software Engineering Assistant
        </h1>
        <p className="app-subtitle">
          Análise e chat inteligente sobre código-fonte com RAG e Embeddings
        </p>
      </header>

      {screen === "dashboard" && (
        <Dashboard
          onOpenChat={goToChat}
          onAddNew={goToAddRepo}
          refreshTrigger={dashboardRefresh}
        />
      )}

      {screen === "add-repo" && (
        <div>
          <button
            className="btn btn-sm btn-secondary back-btn"
            onClick={goToDashboard}
            style={{ marginBottom: "1rem" }}
          >
            ← Voltar
          </button>
          <RepoSubmit
            onReady={(repo) => {
              setDashboardRefresh((n) => n + 1);
              goToChat(repo);
            }}
          />
        </div>
      )}

      {screen === "chat" && activeRepo && (
        <ChatView
          repoId={activeRepo.id}
          repoName={activeRepo.name}
          githubUrl={activeRepo.url}
          initialConversationId={initialConversationId}
          onBack={goToDashboard}
        />
      )}
    </div>
  );
}

export default App;
