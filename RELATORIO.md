# Relatório — Comunicação Cliente-Servidor com Sockets TCP

## 1. Lógica da implementação

**Servidor (`servidor.py`).** Cria um socket `AF_INET`/`SOCK_STREAM` (TCP/IPv4),
ativa `SO_REUSEADDR` para permitir reiniciar rapidamente na mesma porta, faz
`bind()` em `0.0.0.0:<porta>` e `listen()` para aceitar conexões. O laço
principal chama `accept()` repetidamente; cada conexão aceita é entregue a uma
**thread daemon** própria (`atender_cliente`), permitindo que múltiplos
clientes sejam atendidos ao mesmo tempo sem que um bloqueie os outros. Dentro
da thread, `conexao.makefile("r", encoding="utf-8")` transforma o socket em um
objeto de leitura por linhas, e `readline()` entrega uma mensagem completa por
vez. Cada linha é passada para `processar_comando(mensagem)`, uma função pura
que devolve `(resposta, encerrar)` — separando a lógica dos comandos da lógica
de rede. O número de clientes conectados e o horário de início do servidor são
variáveis globais protegidas por `threading.Lock` (`trava_estado`), pois várias
threads podem lê-las/alterá-las ao mesmo tempo. A função `registrar()` imprime
no terminal e grava em `servidor.log`, protegendo a escrita no arquivo com um
segundo lock (`trava_log`) para não intercalar linhas de threads diferentes.

**Cliente (`cliente.py`).** Conecta com `socket.create_connection` usando
timeout de 5s (evita travar se o servidor estiver fora do ar); após conectar,
remove o timeout com `settimeout(None)`. Em um laço, lê comandos digitados com
`input()`, ignora linhas vazias, envia `comando + "\n"` e lê a resposta com
`readline()` via `makefile()`. Ao receber `EXIT` ou uma resposta vazia (servidor
fechou a conexão), o laço termina.

**Tratamento de erros.** O servidor trata: cliente que desconecta sem `EXIT`
(`readline()` retorna string vazia), `ConnectionResetError` e `BrokenPipeError`
(cliente derrubado abruptamente), `UnicodeDecodeError` (bytes inválidos),
`OSError` de bind (porta já em uso, com mensagem amigável) e `KeyboardInterrupt`
(Ctrl+C encerra o servidor de forma limpa). Todo socket é fechado em um bloco
`finally`, garantindo liberação de recursos mesmo em caso de erro. O cliente
trata falha de conexão inicial, `ConnectionResetError`/`BrokenPipeError`
durante o uso, e envia `EXIT` ao servidor antes de sair em `Ctrl+C`
(`KeyboardInterrupt`) ou `Ctrl+D` (`EOFError`).

## 2. Protocolo adotado

O TCP é um **fluxo de bytes** sem limites de mensagem: não existe garantia de
que um `send()` do lado do cliente corresponda a um único `recv()` no servidor
(mensagens podem chegar fragmentadas ou concatenadas). Por isso o protocolo
define o caractere **`'\n'`** como delimitador: cada mensagem é uma linha de
texto UTF-8, e tanto cliente quanto servidor usam `makefile().readline()` para
reconstruir exatamente uma mensagem por vez a partir do fluxo de bytes.

Formato de cada linha: `COMANDO [argumento]` (comando não diferencia maiúsculas
de minúsculas).

| Comando         | Resposta                                                                                  |
|-----------------|--------------------------------------------------------------------------------------------|
| `TIME`          | `Hora atual: HH:MM:SS`                                                                     |
| `STATUS`        | `Servidor ativo e aguardando conexões (clientes conectados: N, tempo ativo: Xs)`            |
| `ECHO <msg>`    | `<msg>` (exatamente o texto informado)                                                      |
| `ECHO` (vazio)  | `ERRO: ECHO exige um texto. Uso: ECHO <mensagem>`                                            |
| `EXIT`          | `Conexão encerrada` (servidor fecha a conexão)                                              |
| *(linha vazia)* | `ERRO: comando vazio`                                                                       |
| comando inválido| `ERRO: comando desconhecido 'X'. Comandos válidos: TIME, STATUS, ECHO <texto>, EXIT`         |

## 3. Exemplo de execução (saída real do teste)

Teste executado com o servidor na porta 5099 e dois clientes simultâneos:

```
printf "TIME\nSTATUS\nECHO teste de mensagem\nABC\nECHO\nEXIT\n" | python cliente.py 127.0.0.1 5099
```

**Saída do cliente:**

```
Conectando ao servidor...
Conectado a 127.0.0.1:5099.
Digite um comando: Resposta do servidor: Hora atual: 19:37:51
Digite um comando: Resposta do servidor: Servidor ativo e aguardando conexões (clientes conectados: 1, tempo ativo: 6s)
Digite um comando: Resposta do servidor: teste de mensagem
Digite um comando: Resposta do servidor: ERRO: comando desconhecido 'ABC'. Comandos válidos: TIME, STATUS, ECHO <texto>, EXIT
Digite um comando: Resposta do servidor: ERRO: ECHO exige um texto. Uso: ECHO <mensagem>
Digite um comando: Resposta do servidor: Conexão encerrada
Conexão finalizada.
```

**Trecho do `servidor.log` (um dos dois clientes atendidos concorrentemente):**

```
[2026-09-29 19:37:44] Servidor iniciado na porta 5099
[2026-09-29 19:37:51] Cliente conectado (127.0.0.1:51511)
[2026-09-29 19:37:51] Comando recebido: 'TIME' (127.0.0.1:51511)
[2026-09-29 19:37:51] Resposta enviada: 'Hora atual: 19:37:51' (127.0.0.1:51511)
[2026-09-29 19:37:51] Comando recebido: 'STATUS' (127.0.0.1:51511)
[2026-09-29 19:37:51] Resposta enviada: 'Servidor ativo e aguardando conexões (clientes conectados: 1, tempo ativo: 6s)' (127.0.0.1:51511)
[2026-09-29 19:37:51] Comando recebido: 'ECHO teste de mensagem' (127.0.0.1:51511)
[2026-09-29 19:37:51] Resposta enviada: 'teste de mensagem' (127.0.0.1:51511)
[2026-09-29 19:37:51] Comando recebido: 'ABC' (127.0.0.1:51511)
[2026-09-29 19:37:51] Resposta enviada: "ERRO: comando desconhecido 'ABC'. Comandos válidos: TIME, STATUS, ECHO <texto>, EXIT" (127.0.0.1:51511)
[2026-09-29 19:37:51] Comando recebido: 'ECHO' (127.0.0.1:51511)
[2026-09-29 19:37:51] Resposta enviada: 'ERRO: ECHO exige um texto. Uso: ECHO <mensagem>' (127.0.0.1:51511)
[2026-09-29 19:37:51] Comando recebido: 'EXIT' (127.0.0.1:51511)
[2026-09-29 19:37:51] Resposta enviada: 'Conexão encerrada' (127.0.0.1:51511)
[2026-09-29 19:37:51] Conexão encerrada. (127.0.0.1:51511)
```

O segundo cliente, conectado alguns milissegundos depois, foi atendido em
paralelo pela sua própria thread, gerando a sequência equivalente de linhas no
mesmo `servidor.log` (endereço `127.0.0.1:51512`), comprovando o atendimento
concorrente. Também foram validados manualmente: comando vazio (`ERRO: comando
vazio`) e o não diferenciar maiúsculas/minúsculas (`time` funciona igual a
`TIME`).

## Desafios implementados

- **Multithread:** cada conexão é atendida por uma thread daemon própria
  (`threading.Thread`), permitindo múltiplos clientes simultâneos; o estado
  compartilhado (contador de clientes) é protegido por `threading.Lock`.
- **Logs em arquivo:** todos os eventos (conexão, comando recebido, resposta
  enviada, desconexão) são gravados em `servidor.log` com data/hora, além de
  exibidos no terminal, com escrita serializada por lock.
- **Validação de comandos:** tratamento de comando vazio, `ECHO` sem argumento,
  comando desconhecido e comando com maiúsculas/minúsculas variadas, além de
  tratamento de erros de rede (desconexão abrupta, `ConnectionResetError`,
  `BrokenPipeError`, `UnicodeDecodeError`, porta em uso e `Ctrl+C`).
