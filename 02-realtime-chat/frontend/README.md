# Frontend Architecture Guidelines

Este projeto adota uma estrutura baseada em **responsabilidade**, onde cada pasta possui um propósito bem definido. A organização deve evoluir conforme a aplicação cresce, evitando complexidade desnecessária e mantendo o código fácil de navegar.

## Estrutura Inicial

```text
frontend/
│
├── public/
│
├── src/
│   ├── assets/
│   ├── components/
│   ├── features/
│   ├── hooks/
│   ├── layouts/
│   ├── pages/
│   ├── routes/
│   ├── services/
│   ├── types/
│   ├── utils/
│   ├── App.tsx
│   └── main.tsx
│
├── package.json
├── vite.config.ts
└── tsconfig.json
```

---

# Diretórios

## `assets/`

Arquivos estáticos da aplicação.

**Exemplos:**

```text
assets/
├── images/
├── icons/
└── logo.svg
```

**Responsabilidade**

* Imagens
* Ícones
* Fontes
* Arquivos estáticos

> Não deve conter nenhuma lógica da aplicação.

---

## `components/`

Componentes reutilizáveis em qualquer parte do sistema.

**Exemplo:**

```text
components/
├── Button/
│   └── Button.tsx
├── Modal/
│   └── Modal.tsx
└── Avatar/
    └── Avatar.tsx
```

Utilize esta pasta apenas quando o componente puder ser reutilizado por múltiplas telas ou funcionalidades.

---

## `features/`

Agrupa tudo que pertence a uma funcionalidade específica da aplicação.

Exemplo para este projeto:

```text
features/
├── chat/
│   ├── components/
│   ├── hooks/
│   └── services/
│
├── auth/
│   ├── components/
│   └── hooks/
│
└── notifications/
```

Esta abordagem mantém cada funcionalidade isolada e evita espalhar arquivos relacionados por toda a aplicação.

---

## `pages/`

Representa as páginas (screens) da aplicação.

**Exemplo:**

```text
pages/
├── Login/
├── Chat/
└── Settings/
```

As páginas devem ser responsáveis por montar os componentes da interface.

Evite concentrar regras de negócio nesta camada.

---

## `layouts/`

Layouts reutilizáveis compartilhados entre páginas.

**Exemplo:**

```text
layouts/
├── MainLayout.tsx
└── AuthLayout.tsx
```

---

## `hooks/`

Hooks customizados reutilizáveis.

**Exemplo:**

```text
hooks/
├── useChat.ts
├── usePresence.ts
└── useWebSocket.ts
```

Caso um hook seja utilizado exclusivamente por uma feature, prefira mantê-lo dentro da própria feature.

---

## `services/`

Responsável pela comunicação com sistemas externos.

**Exemplo inicial:**

```text
services/
└── websocket.ts
```

Possível evolução:

```text
services/
├── api.ts
├── auth.ts
└── websocket.ts
```

Esta camada deve conter:

* Chamadas HTTP
* WebSockets
* Integrações externas

Nunca componentes visuais.

---

## `routes/`

Configuração das rotas da aplicação.

Exemplo:

```text
routes/
└── index.tsx
```

---

## `types/`

Tipos e interfaces compartilhadas.

```text
types/
├── chat.ts
├── user.ts
└── websocket.ts
```

Centralizar os tipos evita duplicação e facilita manutenção.

---

## `utils/`

Funções utilitárias independentes da interface.

**Exemplo:**

```text
utils/
├── constants.ts
├── formatDate.ts
└── generateId.ts
```

Devem ser funções puras e reutilizáveis.

---

# Convenções

## Componentes

Utilizar **PascalCase**.

✅ Correto

```text
Button.tsx
ChatMessage.tsx
UserAvatar.tsx
```

❌ Evitar

```text
button.tsx
chatmessage.tsx
```

---

## Hooks

Sempre iniciar com `use`.

✅

```text
useChat.ts
usePresence.ts
useWebSocket.ts
```

---

## Types

Utilizar nomes em minúsculo relacionados ao domínio.

Exemplo:

```text
chat.ts
user.ts
message.ts
```

---

## Componentes maiores

Quando um componente crescer, criar uma pasta própria.

Exemplo:

```text
Button/
├── Button.tsx
├── Button.module.css
└── index.ts
```

---

# Princípios do Projeto

Este projeto segue algumas regras simples para manter a organização ao longo do tempo.

* Cada arquivo deve possuir uma única responsabilidade.
* Cada pasta deve possuir um único propósito.
* Evite criar novas pastas antes que exista uma necessidade real.
* Componentes reutilizáveis pertencem a `components/`.
* Componentes específicos de uma funcionalidade pertencem a `features/<feature>/`.
* Toda comunicação com APIs e WebSockets deve passar por `services/`.
* Hooks específicos de uma feature podem permanecer dentro dela; hooks reutilizáveis devem ficar em `hooks/`.
* Prefira composição de componentes em vez de componentes excessivamente grandes.
* Organize o projeto para facilitar manutenção, leitura e evolução.

---

# Filosofia

A prioridade deste projeto é **clareza**.

A estrutura deve crescer de forma gradual, acompanhando a evolução da aplicação. Evite antecipar complexidade ou criar camadas que ainda não possuem utilidade.

Sempre que surgir uma nova funcionalidade, pergunte:

* Ela pode reutilizar algo que já existe?
* Ela pertence a uma feature específica?
* Ela mantém a responsabilidade da pasta onde está sendo criada?

Se a resposta for **sim**, provavelmente ela está no lugar certo.
