"""
Atividade: Comunicação Cliente-Servidor com Sockets TCP
Arquivo: servidor.py

Descrição
---------
Servidor TCP concorrente que atende múltiplos clientes simultaneamente.
Cada conexão aceita é entregue a uma thread própria (daemon), de modo que
um cliente lento ou que fique com a conexão aberta não bloqueia os demais.

Protocolo
---------
- Codificação: texto UTF-8.
- Uma mensagem por linha: o caractere '\\n' é o delimitador de mensagens.
  Isso é necessário porque o TCP entrega um FLUXO CONTÍNUO de bytes, sem
  marcar onde uma mensagem termina e a próxima começa. O '\\n' é a marca
  que o cliente e o servidor usam para saber onde cortar cada mensagem.
- Formato de cada linha enviada pelo cliente: "COMANDO [argumento]".
  O nome do comando não diferencia maiúsculas de minúsculas.

Comandos suportados:
    TIME              -> "Hora atual: HH:MM:SS"
    STATUS            -> "Servidor ativo e aguardando conexões
                           (clientes conectados: N, tempo ativo: Xs)"
    ECHO <mensagem>   -> devolve exatamente <mensagem>
    EXIT              -> "Conexão encerrada" e a conexão é fechada

Forma de uso
------------
    python servidor.py [porta]

Se a porta não for informada, é usada a porta padrão (5000).
Todos os eventos são exibidos no terminal e também gravados no arquivo
de log definido em ARQUIVO_LOG (servidor.log).
"""

import socket
import sys
import threading
import time
from datetime import datetime

# Força stdout/stderr em UTF-8: no Windows, a saída padrão costuma usar a
# codepage do console (ex.: cp1252/cp850), o que corrompe os acentos das
# mensagens em português. reconfigure() está disponível desde o Python 3.7.
for _fluxo in (sys.stdout, sys.stderr):
    if hasattr(_fluxo, "reconfigure"):
        _fluxo.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# Constantes de configuração do servidor
# ---------------------------------------------------------------------------
HOST = "0.0.0.0"          # escuta em todas as interfaces de rede da máquina
PORTA_PADRAO = 5000
ARQUIVO_LOG = "servidor.log"
TAMANHO_FILA_ESPERA = 5   # backlog do listen(): conexões pendentes de accept()

# ---------------------------------------------------------------------------
# Estado global compartilhado entre as threads dos clientes.
# Como várias threads podem alterar essas variáveis ao mesmo tempo, o acesso
# a elas é protegido por um lock (trava_estado) para evitar condição de
# corrida (duas threads incrementando/decrementando o contador ao mesmo
# tempo e "perdendo" uma atualização).
# ---------------------------------------------------------------------------
clientes_conectados = 0
horario_inicio = time.monotonic()
trava_estado = threading.Lock()

# Lock específico para serializar a escrita no arquivo de log, evitando que
# duas threads escrevam linhas intercaladas/corrompidas no mesmo arquivo.
trava_log = threading.Lock()


def registrar(msg: str) -> None:
    """Imprime uma mensagem no terminal e a grava em ARQUIVO_LOG.

    Cada linha do log é prefixada com a data e hora no formato
    [AAAA-MM-DD HH:MM:SS]. A escrita no arquivo é protegida por lock porque
    várias threads (uma por cliente) podem chamar esta função ao mesmo tempo.
    """
    carimbo = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{carimbo}] {msg}"
    print(linha)
    with trava_log:
        try:
            with open(ARQUIVO_LOG, "a", encoding="utf-8") as arquivo:
                arquivo.write(linha + "\n")
        except OSError as erro:
            # Se não for possível gravar o log (ex.: disco cheio, sem
            # permissão), o servidor continua funcionando normalmente;
            # apenas avisamos no terminal.
            print(f"[AVISO] Não foi possível gravar no log: {erro}")


def processar_comando(mensagem: str):
    """Interpreta uma linha de comando recebida do cliente.

    Recebe a mensagem já sem o '\\n' final e devolve uma tupla
    (resposta, encerrar), em que:
        - resposta: texto (sem '\\n') a ser enviado de volta ao cliente;
        - encerrar: True se, após enviar a resposta, a conexão deve ser
          fechada pelo servidor (caso do comando EXIT).
    """
    linha = mensagem.strip()

    if linha == "":
        return "ERRO: comando vazio", False

    # Separa o comando do restante da linha (o argumento), permitindo que o
    # argumento do ECHO contenha espaços.
    partes = linha.split(maxsplit=1)
    comando = partes[0].upper()
    argumento = partes[1] if len(partes) > 1 else ""

    if comando == "TIME":
        hora_atual = datetime.now().strftime("%H:%M:%S")
        return f"Hora atual: {hora_atual}", False

    if comando == "STATUS":
        with trava_estado:
            n_clientes = clientes_conectados
            tempo_ativo = int(time.monotonic() - horario_inicio)
        return (
            f"Servidor ativo e aguardando conexões "
            f"(clientes conectados: {n_clientes}, tempo ativo: {tempo_ativo}s)"
        ), False

    if comando == "ECHO":
        if argumento == "":
            return "ERRO: ECHO exige um texto. Uso: ECHO <mensagem>", False
        return argumento, False

    if comando == "EXIT":
        return "Conexão encerrada", True

    return (
        f"ERRO: comando desconhecido '{partes[0]}'. "
        f"Comandos válidos: TIME, STATUS, ECHO <texto>, EXIT"
    ), False


def atender_cliente(conexao: socket.socket, endereco) -> None:
    """Função executada em uma thread própria para cada cliente aceito.

    Lê comandos linha a linha (o '\\n' delimita cada mensagem), processa
    cada um com processar_comando() e envia a resposta de volta.
    """
    global clientes_conectados

    ip_porta = f"{endereco[0]}:{endereco[1]}"

    with trava_estado:
        clientes_conectados += 1

    registrar(f"Cliente conectado ({ip_porta})")

    arquivo_conexao = None
    try:
        # makefile() transforma o socket em um objeto "tipo arquivo" que
        # permite usar readline(), já tratando a decodificação UTF-8 e a
        # busca pelo delimitador '\n' de cada mensagem — sem isso, seria
        # necessário implementar manualmente a montagem de linhas a partir
        # dos pedaços de bytes que chegam pela rede.
        arquivo_conexao = conexao.makefile("r", encoding="utf-8")

        while True:
            try:
                linha = arquivo_conexao.readline()
            except UnicodeDecodeError:
                # O cliente enviou bytes que não formam texto UTF-8 válido.
                registrar(f"Erro de decodificação UTF-8 ({ip_porta})")
                break

            # readline() devolve string vazia quando o outro lado fechou a
            # conexão (fim de fluxo) — ou seja, o cliente encerrou sem EXIT.
            if linha == "":
                registrar(f"Cliente desconectou sem enviar EXIT ({ip_porta})")
                break

            mensagem = linha.rstrip("\n").rstrip("\r")
            registrar(f"Comando recebido: {mensagem!r} ({ip_porta})")

            resposta, encerrar = processar_comando(mensagem)

            try:
                # O '\n' na resposta é o delimitador que o cliente usa para
                # saber que a mensagem terminou.
                conexao.sendall((resposta + "\n").encode("utf-8"))
            except (ConnectionResetError, BrokenPipeError):
                registrar(f"Falha ao enviar resposta, cliente desconectado ({ip_porta})")
                break

            registrar(f"Resposta enviada: {resposta!r} ({ip_porta})")

            if encerrar:
                break

    except ConnectionResetError:
        # O cliente encerrou a conexão de forma abrupta (ex.: fechou o
        # processo, queda de rede) enquanto o servidor tentava ler dele.
        registrar(f"Conexão redefinida pelo cliente ({ip_porta})")
    except BrokenPipeError:
        registrar(f"Conexão interrompida (broken pipe) ({ip_porta})")
    except OSError as erro:
        registrar(f"Erro de socket com o cliente {ip_porta}: {erro}")
    finally:
        # O socket do cliente é sempre fechado aqui, independentemente de
        # como o laço acima terminou (EXIT, erro ou desconexão abrupta).
        if arquivo_conexao is not None:
            arquivo_conexao.close()
        conexao.close()
        with trava_estado:
            clientes_conectados -= 1
        registrar(f"Conexão encerrada. ({ip_porta})")


def ler_porta_da_linha_de_comando() -> int:
    """Lê a porta a partir de sys.argv, usando PORTA_PADRAO se omitida."""
    if len(sys.argv) < 2:
        return PORTA_PADRAO
    try:
        porta = int(sys.argv[1])
    except ValueError:
        print(f"Porta inválida: '{sys.argv[1]}'. Usando porta padrão {PORTA_PADRAO}.")
        return PORTA_PADRAO
    return porta


def main() -> None:
    global horario_inicio

    porta = ler_porta_da_linha_de_comando()

    # AF_INET: família de endereços IPv4. SOCK_STREAM: socket TCP orientado
    # a conexão e a fluxo de bytes confiável.
    socket_servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # SO_REUSEADDR permite reiniciar o servidor rapidamente na mesma porta,
    # sem esperar o sistema liberar a porta que ficou em estado TIME_WAIT
    # após uma execução anterior.
    socket_servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        # bind associa o socket ao endereço/porta local em que o servidor
        # vai escutar por conexões.
        socket_servidor.bind((HOST, porta))
    except OSError as erro:
        print(f"ERRO: não foi possível iniciar o servidor na porta {porta}.")
        print(f"Detalhe: {erro}")
        print("Dica: a porta pode já estar em uso; tente outra porta.")
        socket_servidor.close()
        sys.exit(1)

    # listen coloca o socket em modo passivo, pronto para aceitar conexões.
    # O parâmetro é o tamanho da fila de conexões que aguardam accept().
    socket_servidor.listen(TAMANHO_FILA_ESPERA)

    horario_inicio = time.monotonic()
    registrar(f"Servidor iniciado na porta {porta}")

    try:
        while True:
            # accept() bloqueia até que um cliente se conecte; devolve um
            # NOVO socket exclusivo para essa conexão, mais o endereço do
            # cliente. O socket_servidor continua livre para aceitar outros.
            conexao, endereco = socket_servidor.accept()

            # Cada cliente é atendido em uma thread própria, marcada como
            # daemon para que não impeça o processo de terminar caso o
            # programa principal precise encerrar (ex.: erro fatal).
            thread_cliente = threading.Thread(
                target=atender_cliente,
                args=(conexao, endereco),
                daemon=True,
            )
            thread_cliente.start()

    except KeyboardInterrupt:
        # Ctrl+C no terminal do servidor: encerramento solicitado pelo
        # usuário, não é um erro.
        registrar("Servidor interrompido pelo usuário (Ctrl+C).")
    finally:
        socket_servidor.close()
        registrar("Servidor finalizado.")


if __name__ == "__main__":
    main()
