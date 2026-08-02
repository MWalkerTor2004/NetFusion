import os
import shutil
import json
import sys
import pty
import socket
import getopt
import threading
import subprocess
import select
import psutil as p  # Used to look for any open/running ports incase of a improper shutdown

# define global variables
listen = False
bind = False
upload = False
port_cleaing = False
message = False
quiet = False
stream = False
execute = ''
target = ''
upload_destination = ''
port = 0
listen_host = ''
mode = ''
client_name = ''
server_name = ''

# A Notice to inform users to use this tool responsibly
def notice():
    print('''
This is a personal project that anyone is welcome to use, study, and contribute to in order to learn more about programming, networking, and defensive security concepts, including red team tools and techniques.

This tool is intended for educational and authorized testing purposes only.

Only use this tool on systems, networks, and devices that you own or have explicit permission to test.
Do not use this tool for unauthorized access, malicious activity, or any illegal purpose.
Always comply with applicable laws, regulations, and organizational policies.

By using this tool, you acknowledge that you are solely responsible for your actions. The author assumes no liability for any misuse of this software or for any damages resulting from its use.''')

# Displays all commands/flags and show examples of use
def usage():
    notice()
    print('''NetFusion
        Usage: nf.py -t target_host -p port
        -b --bind               - Initialize a bind shell
        -e --execute=file_to_run   - Execute the given file upon connection
        -F --force-freeing         - Force freeing of the socket after closing
        -h --help                  - Display commands and examples of commands to run
        -l --listen                - Listen on [host]:[port] for incoming connections
        -L --listen-host=ip        - Bind the listener to a specific IP address
        -m --message               - Sets up a messaging tunnel between the Client and Server
        -q --quiet                 - Run commands quietly i.e running a bind shell so the server does not display information
        -r --reverse               - (WIP DO NOT USE YET) use the script as a simple reverse shell
        -s --stream                - Use this for a pure pipeline similar to NetCat. Needed when using the FIFO pipeline command
        -t --target_host           - Select a specific target host
        -u --upload=destination    - Upload a file upon connection
------------------------------------------------------------------------------------------
General usage Examples:
          nf.py -h
          nf.py -F -p 5555
          nf.py -p 5555 -l -L 0.0.0.0
          nf.py -p 5555 -l -m
          nf.py -l -p 5555 -s
          nf.py -t 192.168.1.100 -p 5555 -l -b
          nf.py -t 192.168.1.100 -p 5555 -l -u=c:\\target.exe
          nf.py -t 192.168.1.100 -p 5555 -l -e=calc.exe or -e=\'cat /etc/passwd\'
          echo 'ABCDEFGHI' |./nf.py -t 192.168.11.12 -p 135
-------------------------------------------------------------------------------------------
General Notes:
            If errors show up from exsiting from a connection do not be alarmed that will happen currently working on making the script not do that.''')
    sys.exit(0)

class Linuxshell:
    def __init__(self):
        self.shell = None
        self.running = False

        shell = os.environ.get('SHELL')

        if not shell or not os.path.exists(shell):
            shell = None

        shell = (
            os.environ.get('SHELL')
            or shutil.which('bash')
            or shutil.which('sh')
            or '/bin/sh'
        )

        try:
            self.shell = subprocess.Popen(
                [
                    shell
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
        except FileNotFoundError:
            raise RuntimeError(f' [*] Shell not found: {shell}...')

        self.running = True

    def read_loop(self, client_socket):
        while self.running:
            output = self.shell.stdout.read(1)

            if output:
                client_socket.sendall(output.encode('utf-8', errors='ignore'))

    def write(self, data):
        if self.running:
            self.shell.stdin.write(data)
            self.shell.stdin.flush()

    def close(self):
        self.running = False

        if self.shell:
            self.shell.terminate()

# class MacShell:
#     def __init__(self):
#         shell = os.environ.get('SHELL')
#         if not shell or not os.path.exists(shell):
#             shell = (
#                 shutil.which('zsh')
#                 or shutil.which('bash')
#                 or shutil.which('sh')
#                 or '/bin/sh'
#             )

class ShellSession:
    def __init__(self):
        self.shell = None
        self.running = False

        shell = os.environ.get('COMSPEC')

        if not shell or not os.path.exists(shell):
            shell = (
                shutil.which('pwsh.exe')
                or shutil.which('powershell.exe')
                or shutil.which('cmd.exe')
                or shutil.which('cmd')
                or r'C:\Windows\System32\cmd.exe'
            )

        self.shell = subprocess.Popen(
            [
                shell
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        self.running = True

    def read_loop(self, client_socket):
        while self.running:
            output = self.shell.stdout.read(1)

            if output:
                client_socket.sendall(output.encode('utf-8', errors='ignore'))

    def write(self, data):
        if self.running:
            self.shell.stdin.write(data)
            self.shell.stdin.flush()

    def close(self):
        self.running = False

        if self.shell:
            self.shell.terminate()

def is_port_in_use(port):
    global port_cleaing

    try:
        if port_cleaing:
            for conn in p.net_connections():
                if conn.laddr.port == port:
                    user_input = input(f' [*] Port {port} is in use by PID {conn.pid}.\n [*] Do you want to terminate the process using this port? (y/n): ')

                    while user_input.lower() not in ['y', 'n']:
                        user_input = input('\n [*] Invalid input. Please enter either y or n: ')

                    if user_input.lower() == 'y':
                        try:
                            p.Process(conn.pid).terminate()
                            print(f'\n [*] Successfully terminated process with PID {conn.pid}.')

                        except Exception as e:
                            print(f'\n [*] Failed to terminate process with PID {conn.pid}. Error: {e}')
                            return True
                        
                    elif user_input.lower() == 'n':
                        print(f'\n [*] Process with PID {conn.pid} is still using port {port}. Exiting program.')
                        return True
                    
            return False
        
        else:
            pass  # Do nothing, just check if the port is in use

    except Exception as e:
        print(f' [*] Error checking port usage: {e}')
        return True
    
    port_cleaing = False  # Reset the port_cleaing flag after checking

def server_end(client_socket):
    global upload
    global execute
    global bind
    global message
    global stream
    global mode
    global server_name

    client_socket.sendall((f'{mode} \n').encode())

    if len(upload_destination):
        file_buffer = b''

        while True:
            data = client_socket.recv(1024)

            if not data:
                break

            else:
                file_buffer += data

        try:
            file_descriptor = open(upload_destination, 'wb')
            file_descriptor.write(file_buffer)
            file_descriptor.close()
            client_socket.send(('Successfully saved file to %s\r\n' % upload_destination).encode())
        except:
            client_socket.send(('Failed to save file to %s\r\n' % upload_destination).encode())

    # if len(execute):
    #     output = ShellSession(execute)

    #     client_socket.sendall(output)

    if bind:
        if sys.platform.startswith('win'):
            shell = ShellSession()
        elif sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
            shell = Linuxshell()

        threading.Thread(target=shell.read_loop, args=(client_socket,), daemon=True).start()

        while True:
            data = client_socket.recv(1024)

            if not data:
                break

            shell.write(data.decode('utf-8', errors='ignore'))
            
    elif message:
        server_name_choice = input('\n [*] Do you want to set a username  (y or n): ')

        while server_name_choice.lower() not in ('y', 'n'):
            server_name_choice = input('\n [*] Invalid input please type either y or n: ')

        if server_name_choice.lower() == 'y':
            server_name = input('\n [*] What is your temp username: ')
        else:
            server_name = 'Server'

        client_socket.sendall(json.dumps({'name': server_name}).encode('utf-8') + b'\n')
        client_info = json.loads(client_socket.recv(1024).decode())
        client_uname = client_info['name']

        def recv_msg():
            while True:
                data = client_socket.recv(1024)
                if not data:
                    print('\n [*] Client disconnected...')
                    break

                text = data.decode().rstrip('\r\n')
                sys.stdout.write(f'\n{client_uname}: {text}\n<{server_name}:#>')

        def send_msg():
            print(' [*] To disconnect type either: quit/exit/shutdown')
            while True:
                msg = input(f'<{server_name}:#> ')

                client_socket.sendall((f'{msg} \n').encode())

                if msg.strip().lower() in ('quit', 'exit', 'shutdown'):
                    print('\n [*] Disconnecting...')
                    client_socket.close()
                    continue

        recv_thread = threading.Thread(target=recv_msg)
        send_thread = threading.Thread(target=send_msg)

        recv_thread.start()
        send_thread.start()

        recv_thread.join()
        send_thread.join()

        client_socket.close()

    elif stream:
        def send_stream():
            while True:
                data = sys.stdin.buffer.read(4096)

                if not data:
                    break

                client_socket.sendall(data)

        threading.Thread(target=send_stream, daemon=True).start()

        while True:
            data = client_socket.recv(1024)

            if not data:
                break

            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()

def server_loop():
    global target
    global port
    global listen_host
    global mode

    bind_host = listen_host or target or '0.0.0.0'

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.settimeout(1.0)
    
    try:
        server.bind((bind_host, port))
    except OSError as e:
        if getattr(e, 'errno', None) == 98:
            print(f' [*] Port {port} is already in use.\n ')

            if port_cleaing:
                cleaned = is_port_in_use(port)

                if cleaned:
                    try:
                        server.bind((bind_host, port))
                        print(f' [*] Redound successfull... Bound to {bind_host}:{port}...')
                    except OSError:
                        print(' [*] Port unavailable...')
                        return
        else:
            print(f' [*] Use -F to free a port or use a differen port...')
            sys.exit(0)

    server.listen(5)
    try:
        print(f' [*] Listening on {bind_host}:{port}')

        while True:
            try:
                client_socket, addr = server.accept()
            except socket.timeout:
                continue
            except KeyboardInterrupt:
                raise

            print(f''' -----------------------------------------------------------------------------------------
 [*] Connection established from {addr[0]} On listener port: {port}
 [*] You can now interact with the client.\n [*] Client IP: {addr[0]} \n [*] Client Temporary Port: {addr[1]} ''')
            client_thread = threading.Thread(target=server_end, args=(client_socket,))
            client_thread.daemon = True
            client_thread.start()
    except KeyboardInterrupt:
        print(f'\n [*] KeyboardInterrupt received. Exiting...')
    finally:
        try:
            server.close()
        except Exception:
            pass
    sys.exit(0)

def client_end(buffer):
    global stream
    global client_name

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    stop_event = threading.Event()

    client.connect((target, port))
    server_mode = client.recv(1024).decode().strip()
    print(f' [*] Server mode: {server_mode}')

    if server_mode == 'message':
        run_message = True
        run_bind = False
        run_stream = False

    elif server_mode == 'bind':
        run_bind = True
        run_message = False
        run_stream = False

    elif server_mode == 'stream':
        run_stream = True
        run_message = False
        run_bind = False

    else:
        run_message = False
        run_bind = False
        run_stream = False

    def receive_loop():           
        while not stop_event.is_set():
            try:
                data = client.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break

            if not data:
                try:
                    client.close()
                    sys.exit()
                except OSError:
                    pass
                client.close()
                break 

            if run_message:
                text = data.decode().rstrip('\r\n')
                sys.stdout.write(f'\n{server_uname}: {text}\n<{client_name}:#>')

            elif run_bind:
                sys.stdout.write(data.decode(errors='ignore'))
                sys.stdout.flush()

    def send_msg():
        while True:
            msg = input(f'<{client_name}:#> ')
            client.sendall((msg + '\n').encode())

            if msg.strip().lower() in ('quit', 'exit', 'shutdown'):
                print(' [*] Diconnecting...')
                client.close()
                return

    try:
        print(f' [*] To disconnect type either: quit/exit/shutdown')

        if run_message:
            client_name_choice = input('\n [*] Do you want to set a username (y or n): ')
            while client_name_choice.lower() not in ('y', 'n'):
                client_name_choice = input('\n [*] Invalide input please type either y or n: ')
    
            if client_name_choice.lower() == 'y':
                client_name = input('\n [*] Set your username: ')
            else:
                client_name = 'Client'

            handshake = json.loads(client.recv(1024).decode())

            server_uname = handshake['name']
            client.sendall(json.dumps({'name': client_name}).encode('utf-8') + b'\n')

            client.settimeout(0.2)

            print(f' [*] Connect to Server on  {target}:{port}')
            send_thread = threading.Thread(target=send_msg)
            recv_thread = threading.Thread(target=receive_loop)

            send_thread.start()
            recv_thread.start()

            send_thread.join()
            recv_thread.join()
            return

        elif run_bind:

            def shell_receive():
                while True:
                    try:
                        data = client.recv(4096)

                        if not data:
                            break

                        print(data.decode(errors="ignore"),end="")
                    except OSError:
                        break

            recv_thread = threading.Thread(target=shell_receive, daemon=True)

            recv_thread.start()

            while True:
                try:
                    command = input()

                    if command.lower() in ('quit', 'exit', 'shutdown'):
                        break

                    client.sendall(
                        (command + "\n").encode()
                    )

                except KeyboardInterrupt:
                    print(f'\n [*] KeyboardInterrupt received. Exiting...')
                    continue

        elif run_stream:
            def stream_receive():
                while True:
                    try:
                        data = client.recv(4096)

                        if not data:
                            break

                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()
                    except OSError:
                        break
                    
            def stream_send():
                if buffer:
                    client.sendall(buffer.encode())

                while True:
                    try:
                        data = sys.stdin.buffer.readline()

                        if not data:
                            break

                        client.sendall(data)
                    except KeyboardInterrupt:
                        continue

            recv_thread = threading.Thread(target=stream_receive, daemon=True)
            send_thread = threading.Thread(target=stream_send, daemon=True)

            recv_thread.start()
            send_thread.start()

            recv_thread.join()
            send_thread.join()

    except Exception as e:
        print(f'[*] Exception! Exiting: Error: {e}')
    except KeyboardInterrupt as e:
        print(f'\n [*] KeyboardInterrupt received. Exiting...')
        client.close()

    finally:
        stop_event.set()
        client.close()
        sys.exit()

def main():
    global listen
    global port
    global execute
    global bind
    global upload_destination
    global target
    global port_cleaing
    global reverse
    global stream
    global listen_host
    global message
    global mode
    global client_name
    global server_name

    if not len(sys.argv[1:]):
        usage()
    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            'hle:t:p:bFrsL:m',
            [
                'help',
                'listen',
                'execute',
                'target',
                'port',
                'bind',
                'upload',
                'force-freeing',
                'reverse',
                'stream',
                'listen-host=',
                'message',
            ],
        )
    except getopt.GetoptError as err:
        print(str(err))
        usage()
    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
        elif o in ('-b', '--bind'):
            bind = True
            mode = 'bind'
        elif o in ('-e', '--execute'):
            execute = a
        elif o in ('-F', '--force-freeing'):
            port_cleaing = True
        elif o in ('-l', '--listen'):
            listen = True
        elif o in ('-L', '--listen-host'):
            listen_host = a
            listen = True
        elif o in ('-m', '--message'):
            message = True
            mode = 'message'
        elif o in ('-r', '--reverse'):
            reverse = True
            mode = 'reverse'
        elif o in ('-p', '--port'):
            port = int(a)
        elif o in ('-s', '--stream'):
            stream = True
            mode = 'stream'
        elif o in ('-t', '--target'):
            target = a
        elif o in ('-u', '--upload'):
            upload_destination = a
        else:
            assert False, 'Unhandled Option'

    if not listen and len(target) and port > 0:
        if sys.stdin.isatty():
            buffer = ''

        else:
            buffer = sys.stdin.read()

        client_end(buffer)

    if listen:
        server_loop()

if __name__ == '__main__':
    main()