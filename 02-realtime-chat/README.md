


# TODO List 

## Epic 1 — Fundação [OK]

    Objetivo:

    Ter toda a infraestrutura funcionando.

    ### Card 1 [OK]

    Criar estrutura inicial do projeto

    Entregável

    Backend
    Frontend
    Docker Compose

    ### Card 2 [OK]

    Subir ambiente Docker

    Serviços:

    FastAPI
    PostgreSQL
    Redis

    Validação

    Tudo sobe sem erros.

    ### Card 3 [OK]

    Configurar banco de dados

    Criar conexão.

    Validação

    Aplicação conecta ao PostgreSQL.

## Epic 2 — Primeira Interface [OK]

    Objetivo:

    Ter uma interface mínima. 

    ### Card 4 [OK]

    Criar tela inicial

    Campos:

    Username
    Room

    Botão:

    Join Chat

    Validação

    Usuário entra na sala.


    ### Card 5 [OK]

    Criar tela de conversa

    Elementos:

    Lista de mensagens
    Campo de texto
    Botão enviar

    Sem WebSocket ainda.

    Só layout.

## Epic 3 — Primeiro WebSocket [OK]

    Objetivo:

    Conseguir conectar. 

    ### Card 6 [OK]

    Criar endpoint WebSocket

    Validação

    Frontend conecta.

    ### Card 7 [OK]

    Manter usuários conectados

    Criar Connection Manager.

    Validação

    Servidor conhece os clientes ativos.

    ### Card 8 [OK]

    Enviar mensagem para o servidor

    Fluxo

    Frontend

    ↓

    WebSocket

    ↓

    FastAPI

    Validação

    Mensagem chega ao backend.

## Epic 4 — Broadcast [OK]

    Objetivo:

    Primeiro chat funcionando.

    ### Card 9 [OK]

    Enviar mensagem para todos

    Fluxo

    Cliente

    ↓

    Servidor

    ↓

    Todos recebem

    Validação

    Abrir duas abas.

    Enviar mensagem.

    As duas recebem.

    ### Card 10 [OK]

    Adicionar username

    Mensagem:

    Lucas:

    Hello!

    Validação

    Cada usuário aparece identificado.

    ### Card 11 [OK]

    Criar salas

    Exemplo:

    general

    python

    backend

    Validação

    Cada sala recebe apenas suas mensagens.

## Epic 5 — Persistência [*]

    Objetivo:

    Guardar histórico.

    ### Card 12 [*]

    Criar entidade Message

    Campos:

    id

    room

    username

    content

    created_at

    ### Card 13 [*]

    Salvar mensagens

    Validação

    Toda mensagem enviada vai para o banco.


    ### Card 14 [*]

    Carregar histórico

    Fluxo

    Entrou na sala.

    ↓

    Busca mensagens antigas.

    Validação

    Histórico aparece.

## Epic 6 — Redis Pub/Sub [*]

    Objetivo:

    Entender por que Redis existe.


    ### Card 15 [*]

    Publicar mensagens no Redis

    Fluxo

    FastAPI

    ↓

    Redis Channel

    Validação

    Mensagem publicada.

    ### Card 16 [*]

    Consumir mensagens do Redis

    Fluxo

    Redis

    ↓

    Chat Server

    ↓

    WebSocket

    Validação

    Mensagens chegam através do Pub/Sub.

    Neste momento você entende que o WebSocket não precisa conversar diretamente entre instâncias.

## Epic 7 — Presença Online [*]

    Objetivo:

    Saber quem está conectado.

    ### Card 17 [*]

    Mostrar usuários online

    Validação

    Entrou.

    ↓

    Lista atualiza.

    Saiu.

    ↓

    Lista atualiza.

    ### Card 18 [*]

    Detectar desconexão

    Validação

    Fechar aba remove usuário.

## Epic 8 — Melhorias do Chat [*]

    Objetivo:

    Deixar parecido com um chat real.

    ### Card 19 [*]

    Indicador de entrada e saída

    Mensagens:

    Lucas joined

    Lucas left

    ### Card 20 [*]

    Timestamp das mensagens

    Formato:

    14:32

    ### Card 21 [*]

    Auto-scroll

    Nova mensagem.

    ↓

    Tela acompanha.

    ### Card 22 [*]

    Diferenciar mensagens próprias

    Exemplo:

    Direita
    Cor diferente


## Epic 9 — Robustez [*]

    Objetivo:

    Pensar como sistema distribuído.

    ### Card 23 [*]

    Reconectar automaticamente

    Se WebSocket cair.

    ↓

    Reconecta.


    ### Card 24 [*]

    Heartbeat/Ping

    Servidor verifica clientes ativos.


### Card 25 [*]

Remover conexões inválidas

Validação

Servidor limpa conexões mortas.

Projeto Final

Quando tudo estiver pronto, o fluxo será:

Usuário abre aplicação

↓

Escolhe username

↓

Escolhe sala

↓

Conecta via WebSocket

↓

Servidor registra conexão

↓

Mensagem enviada

↓

Persistida no PostgreSQL

↓

Publicada no Redis

↓

Recebida por todos da sala

↓

Frontend atualiza em tempo real
O que você aprenderá (sem perceber)

Esse projeto parece um "chat", mas na verdade ele ensina vários conceitos fundamentais:

✅ WebSockets e comunicação full-duplex.
✅ Gerenciamento de conexões persistentes.
✅ Broadcast de mensagens.
✅ Salas (rooms) e isolamento de comunicação.
✅ Persistência de histórico.
✅ Redis Pub/Sub como mecanismo de distribuição.
✅ Diferença entre comunicação síncrona (HTTP) e assíncrona (WebSocket).
✅ Reconexão, heartbeat e limpeza de conexões inativas.
✅ Separação entre interface e backend em uma aplicação em tempo real.