"""
Atividade: Comunicação Cliente-Servidor com Sockets TCP
Arquivo: cliente.py

Descrição
---------
Cliente TCP interativo. Conecta-se ao servidor, lê comandos digitados pelo
usuário no terminal, envia cada um ao servidor e exibe a resposta recebida.

Protocolo
---------
- Codificação: texto UTF-8.
- Uma mensagem por linha: o caractere '\\n' é o delimitador de mensagens,
  necessário porque o TCP entrega um fluxo contínuo de bytes sem marcar
  onde uma mensagem termina.
- Formato de cada linha enviada ao servidor: "COMANDO [argumento]".

Comandos aceitos pelo servidor: TIME, STATUS, ECHO <mensagem>, EXIT.

Forma de uso
------------
    python cliente.py [ip] [porta]

Se omitidos, os padrões são 127.0.0.1 (IP) e 5000 (porta).
Para conectar a um servidor em outra máquina da rede, informe o IP dessa
máquina, por exemplo: python cliente.py 192.168.0.10 5000
"""

import socket
import sys

# Força stdout/stderr em UTF-8: no Windows, a saída padrão costuma usar a
# codepage do console (ex.: cp1252/cp850), o que corrompe os acentos das
# mensagens em português. reconfigure() está disponível desde o Python 3.7.
for _fluxo in (sys.stdout, sys.stderr):
    if hasattr(_fluxo, "reconfigure"):
        _fluxo.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# Constantes de configuração do cliente
# ---------------------------------------------------------------------------
IP_PADRAO = "127.0.0.1"
PORTA_PADRAO = 5000
TIMEOUT_CONEXAO_SEGUNDOS = 5.0


def ler_ip_e_porta():
    """Lê IP e porta da linha de comando, usando os padrões se omitidos."""
    ip = sys.argv[1] if len(sys.argv) > 1 else IP_PADRAO

    if len(sys.argv) > 2:
        try:
            porta = int(sys.argv[2])
        except ValueError:
            print(f"Porta inválida: '{sys.argv[2]}'. Usando porta padrão {PORTA_PADRAO}.")
            porta = PORTA_PADRAO
    else:
        porta = PORTA_PADRAO

    return ip, porta


def enviar_comando(conexao, arquivo_conexao, comando: str):
    """Envia um comando ao servidor e lê a resposta correspondente.

    O '\\n' ao final do comando é o delimitador que marca o fim da mensagem
    para o servidor. A resposta é lida com readline(), que devolve tudo até
    o próximo '\\n' (ou string vazia se o servidor fechou a conexão).
    """
    conexao.sendall((comando + "\n").encode("utf-8"))
    resposta = arquivo_conexao.readline()
    return resposta


def main() -> None:
    ip, porta = ler_ip_e_porta()

    print("Conectando ao servidor...")
    try:
        # socket.create_connection já resolve o endereço e conecta em uma
        # única chamada; o timeout evita que o cliente fique bloqueado
        # indefinidamente caso o servidor esteja fora do ar ou inacessível.
        conexao = socket.create_connection((ip, porta), timeout=TIMEOUT_CONEXAO_SEGUNDOS)
    except (ConnectionRefusedError, socket.timeout, OSError) as erro:
        print(f"Não foi possível conectar a {ip}:{porta}.")
        print(f"Detalhe: {erro}")
        print("Verifique se o servidor está em execução e se o IP/porta estão corretos.")
        sys.exit(1)

    # Depois de conectado, removemos o timeout: a partir daqui o cliente
    # pode aguardar indefinidamente a digitação do usuário e as respostas
    # do servidor, sem risco de timeout durante o uso normal.
    conexao.settimeout(None)

    print(f"Conectado a {ip}:{porta}.")

    # makefile() permite ler as respostas do servidor linha a linha,
    # respeitando o delimitador '\n' do protocolo.
    arquivo_conexao = conexao.makefile("r", encoding="utf-8")

    try:
        while True:
            try:
                comando = input("Digite um comando: ")
            except EOFError:
                # Ctrl+D (ou Ctrl+Z no Windows): encerra educadamente,
                # avisando o servidor com EXIT antes de sair.
                print("\nEncerrando (EOF)...")
                try:
                    enviar_comando(conexao, arquivo_conexao, "EXIT")
                except OSError:
                    pass
                break

            # Linhas vazias (Enter sem digitar nada) são simplesmente
            # ignoradas, sem serem enviadas ao servidor.
            if comando.strip() == "":
                continue

            try:
                resposta = enviar_comando(conexao, arquivo_conexao, comando)
            except (ConnectionResetError, BrokenPipeError, OSError) as erro:
                print(f"Conexão com o servidor perdida: {erro}")
                break

            # readline() vazio indica que o servidor fechou a conexão do
            # lado dele (fim de fluxo), sem que o cliente tenha enviado EXIT.
            if resposta == "":
                print("O servidor encerrou a conexão.")
                break

            resposta = resposta.rstrip("\n").rstrip("\r")
            print(f"Resposta do servidor: {resposta}")

            if comando.strip().upper() == "EXIT":
                break

    except KeyboardInterrupt:
        # Ctrl+C: avisa o servidor com EXIT antes de encerrar o cliente.
        print("\nInterrompido pelo usuário (Ctrl+C). Enviando EXIT...")
        try:
            enviar_comando(conexao, arquivo_conexao, "EXIT")
        except OSError:
            pass
    finally:
        arquivo_conexao.close()
        conexao.close()
        print("Conexão finalizada.")


if __name__ == "__main__":
    main()
