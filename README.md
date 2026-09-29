# Comunicação Cliente-Servidor com Sockets TCP

Projeto acadêmico em **Python 3**, usando apenas a **biblioteca padrão**
(`socket`, `threading`, `datetime`, `time`, `sys`), que implementa um servidor
TCP concorrente e um cliente interativo, trocando comandos texto simples
delimitados por `'\n'`.

## Descrição

O servidor aceita múltiplas conexões simultâneas, atendendo cada uma em uma
thread própria. O cliente se conecta, envia comandos digitados pelo usuário e
exibe as respostas do servidor. Todos os eventos do servidor (conexões,
comandos, respostas, desconexões) são registrados no terminal e em um arquivo
de log (`servidor.log`).

## Arquivos

| Arquivo         | Descrição                                              |
|-----------------|---------------------------------------------------------|
| `servidor.py`   | Servidor TCP concorrente (multithread)                  |
| `cliente.py`    | Cliente TCP interativo                                   |
| `RELATORIO.md`  | Relatório da atividade (lógica, protocolo, testes)       |
| `README.md`     | Este arquivo                                             |
| `servidor.log`  | Gerado em tempo de execução pelo servidor (não versionar)|

## Requisitos

- Python 3 (testado com Python 3.14), sem dependências externas.

## Como executar

### Em dois terminais na mesma máquina

**Terminal 1 — servidor:**

```bash
python servidor.py            # usa a porta padrão 5000
# ou
python servidor.py 5001       # especifica outra porta
```

**Terminal 2 — cliente:**

```bash
python cliente.py                      # conecta em 127.0.0.1:5000
# ou
python cliente.py 127.0.0.1 5001       # especifica IP e porta
```

### Pela rede (máquinas diferentes)

1. Na máquina que vai rodar o servidor, descubra o IP local (ex.: `ipconfig`
   no Windows ou `ip addr` no Linux) — por exemplo `192.168.0.10`.
2. Nessa máquina, rode o servidor normalmente:
   ```bash
   python servidor.py 5000
   ```
3. Em outra máquina da mesma rede, rode o cliente apontando para esse IP:
   ```bash
   python cliente.py 192.168.0.10 5000
   ```
4. Certifique-se de que o firewall da máquina do servidor permite conexões de
   entrada na porta escolhida.

### Encerrando

- No cliente: digite `EXIT`, ou pressione `Ctrl+C`/`Ctrl+D` (o cliente envia
  `EXIT` automaticamente antes de sair).
- No servidor: pressione `Ctrl+C` no terminal onde ele está rodando.

## Protocolo e comandos

Mensagens em texto UTF-8, uma por linha (`'\n'` como delimitador, necessário
porque o TCP é um fluxo de bytes sem limites de mensagem). Formato:
`COMANDO [argumento]` (comando não diferencia maiúsculas de minúsculas).

| Comando          | Resposta                                                                          |
|------------------|-------------------------------------------------------------------------------------|
| `TIME`           | `Hora atual: HH:MM:SS`                                                              |
| `STATUS`         | `Servidor ativo e aguardando conexões (clientes conectados: N, tempo ativo: Xs)`     |
| `ECHO <mensagem>`| Devolve exatamente `<mensagem>`                                                     |
| `EXIT`           | `Conexão encerrada` e a conexão é fechada                                           |
| *(vazio)*        | `ERRO: comando vazio`                                                               |
| desconhecido     | `ERRO: comando desconhecido 'X'. Comandos válidos: TIME, STATUS, ECHO <texto>, EXIT` |

## Desafios implementados

- **Multithread:** atendimento simultâneo de múltiplos clientes, cada um em
  sua própria thread daemon, com contador de clientes protegido por
  `threading.Lock`.
- **Logs em arquivo:** todos os eventos relevantes são gravados em
  `servidor.log` com data e hora (`[AAAA-MM-DD HH:MM:SS]`), além de exibidos no
  terminal.
- **Validação de comandos:** tratamento de comando vazio, argumento ausente no
  `ECHO`, comando desconhecido, e tratamento robusto de erros de rede
  (desconexão abrupta, `ConnectionResetError`, `BrokenPipeError`,
  `UnicodeDecodeError`, porta em uso, `Ctrl+C`).

Detalhes da implementação e um exemplo real de execução estão em
[`RELATORIO.md`](RELATORIO.md).
