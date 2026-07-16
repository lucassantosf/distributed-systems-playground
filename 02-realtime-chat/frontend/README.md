# Frontend

Interface do chat em tempo real construída com React e TypeScript. Conecta ao backend via WebSocket e renderiza mensagens, presença de usuários e indicadores de sistema em tempo real.

## Estrutura

```text
frontend/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── public/
│   ├── favicon.svg
│   └── icons.svg
└── src/
    ├── main.tsx                     # Ponto de entrada React
    ├── routes/
    │   └── index.tsx                # Rotas: / → Home, /chat → Chat
    ├── pages/
    │   ├── Home/
    │   │   └── Home.tsx             # Tela de entrada (username + room)
    │   └── Chat/
    │       └── Chat.tsx             # Tela principal do chat
    ├── features/
    │   └── chat/
    │       └── components/
    │           ├── MessageInput.tsx  # Campo de texto + botão enviar
    │           ├── MessageItem.tsx   # Renderização de uma mensagem
    │           └── MessageList.tsx   # Lista de mensagens
    ├── components/
    │   ├── Button/
    │   │   └── Button.tsx           # Botão reutilizável
    │   └── Input/
    │       └── Input.tsx            # Campo de input reutilizável
    ├── types/
    │   ├── chat.ts                  # JoinChatFormData
    │   └── message.ts               # Message
    └── styles/
        └── global.css               # Estilos globais da aplicação
```

## Páginas

### Home (`/`)
Formulário de entrada com campos **Username** e **Room**. Suporta Enter para submeter. Valida que ambos os campos estejam preenchidos antes de permitir o join.

### Chat (`/chat`)
Tela principal do chat. Responsável por:
- Conexão WebSocket com o backend
- Envio e recebimento de mensagens em tempo real
- Exibição de usuários online
- Indicadores de joined/left
- Reconexão automática com backoff exponencial
- Auto-scroll na lista de mensagens
- Banner de status de conexão (conectando / reconectando / desconectado)

## Componentes

| Componente | Responsabilidade |
|------------|-----------------|
| `MessageInput` | Campo de texto + botão enviar. Emite `onSendMessage` ao submeter. |
| `MessageItem` | Renderiza uma mensagem. Diferencia mensagens próprias (cor azul, alinhada à direita), de outros usuários e do sistema (centralizada, cinza). |
| `MessageList` | Lista iterando sobre `MessageItem`. |
| `Button` | Botão reutilizável com estados `disabled` e `type`. |
| `Input` | Campo de input reutilizável com label e placeholder. |

## Conexão WebSocket

A conexão é gerenciada dentro de `Chat.tsx` via `useEffect`:

1. **Conexão**: `ws://{host}:8000/ws/{room}/{username}`
2. **Mensagens recebidas**:
   - `Active users: ...` → atualiza lista de online
   - `{"type": "ping"}` → responde com `{"type": "pong"}`
   - `{user}: {text}` → adiciona à lista de mensagens
3. **Reconexão**: backoff exponencial (3s, 6s, 12s...) com máximo de 10 tentativas
4. **Cleanup**: fecha o WebSocket ao desmontar o componente

## Mensagens do sistema

Mensagens com `username === "System"` são renderizadas de forma diferente:
- Centralizadas
- Sem header (username/timestamp)
- Cor cinza (`#9ca3af`)
- Fonte menor

Exemplos: `Lucas joined`, `Lucas left`

## Convenções

- Componentes em **PascalCase** (`MessageItem.tsx`)
- Hooks com prefixo `use` (`useChat.ts`)
- Types em minúsculo relacionados ao domínio (`chat.ts`, `message.ts`)
- Componentes reutilizáveis em `components/`
- Componentes específicos de feature em `features/<feature>/`
- Comunicação com APIs e WebSockets em `services/`

## Comandos

```bash
# Instalar dependências
npm install

# Rodar em modo de desenvolvimento (hot reload)
npm run dev

# Build para produção
npm run build

# Lint
npm run lint
```

## Configuração

O frontend roda na porta **5173** (padrão do Vite). O backend é esperado na porta **8000**.

Para alterar, modificar `vite.config.ts` e o `docker-compose.yml`.
