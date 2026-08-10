-- Inicialização do PostgreSQL
-- Executado automaticamente pelo container na primeira inicialização
-- Um database dedicado por serviço — isolamento de dados sem múltiplos containers

CREATE DATABASE db_producer;
CREATE DATABASE db_billing;
CREATE DATABASE db_analytics;
CREATE DATABASE db_inventory;
CREATE DATABASE db_notification;
