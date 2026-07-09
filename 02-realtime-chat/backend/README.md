# Backend

Este backend é simples, mas já foi organizado em pequenas camadas para facilitar a manutenção e a evolução do projeto.

## Estrutura principal

- app/domain: contém os modelos de domínio da aplicação, como a entidade Message.
- app/infrastructure: guarda a infraestrutura técnica, como a conexão com o PostgreSQL e a inicialização do schema do banco.
- app/repositories: concentra o acesso aos dados e as queries relacionadas a mensagens.
- app/services: contém a lógica de aplicação, como salvar uma mensagem e orquestrar a persistência.
- app/main.py: ponto de entrada da aplicação FastAPI, onde as rotas e o WebSocket são definidos.

## Objetivo das camadas

- domain: representar as entidades do negócio de forma simples.
- infrastructure: cuidar de detalhes técnicos externos, como banco de dados.
- repositories: abstrair o acesso ao banco.
- services: centralizar regras de uso da aplicação sem misturar com o framework.

## Observação

A ideia aqui é manter a estrutura enxuta, sem exagerar em abstrações, mas já deixando o projeto preparado para crescer de forma organizada.
