# Ponto central de injeção de dependências.
#
# Este arquivo é responsável por instanciar as implementações concretas da
# infraestrutura e injetá-las nos Use Cases via FastAPI Depends.
#
# Exemplo de uso numa rota:
#   @router.post("/chat")
#   def chat(use_case: ChatWithRepository = Depends(get_chat_use_case)):
#       ...
#
# À medida que os Use Cases forem implementados, adicionar aqui as funções
# correspondentes (get_ingest_use_case, get_chat_use_case, etc.).

