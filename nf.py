from logging import config
import os
import shutil
import json
import sys
import pty
import socket
import getopt
import select
import threading
import subprocess
import platform
import time
import psutil as p  # Used to look for any open/running ports incase of a improper shutdown

if os.name != 'nt':
    import termios
    import tty

# Setting protocol handlers for NetFusion
nfp = b'NF/1'
nfch = b'NF/1 CLIENT\n'
max_handshake_size = 64
handshake_timeout = 2.0

# define variables in a class to avoid using global variables The only global needed is prompt which is used in the nf_input function to display the prompt to the user
class NetFusionConfig():
    def __init__(self):
        self.terminal_busy = threading.Event()
        self.listen = False
        self.listener_thread = None
        self.listener_stop = threading.Event()
        self.listener_running = False
        self.listener_is_active = False
        self.bind = False
        self.upload = False
        self.port_clearing = False
        self.message = False
        self.quiet = False
        self.stream = False
        self.prompt = 'netfusion >'
        self.execute = ''
        self.target = ''
        self.upload_destination = ''
        self.port = 0
        self.listen_host = ''
        self.mode = ''
        self.client_name = ''
        self.server_name = ''
        self.protocol = ''
        self.protocol_timeout = handshake_timeout
        self.run_message = False
        self.run_bind = False
        self.run_stream = False

def start_session(config):
    if config.listen and not config.mode:
        print(' [*] No mode specified.')
        return

    if config.listen:
        server_loop(config, config.listener_stop)

    elif config.target and config.port:
        client_end(config, '')

    else:
        print(' [*] No target or port specified.')

def nf_input():
    return input(f'netfusion {os.getcwd()} > ')


def slow_print(text, delay=0.03):
    for line in text.splitlines():
        print(line)
        time.sleep(delay)

def startup():
    notice = '''\n
This is a personal project that anyone is welcome to use, study, and contribute to in order to learn more about programming, networking, and defensive security concepts, including red team tools and techniques.

This tool is intended for educational and authorized testing purposes only.

Only use this tool on systems, networks, and devices that you own or have explicit permission to test.
Do not use this tool for unauthorized access, malicious activity, or any illegal purpose.
Always comply with applicable laws, regulations, and organizational policies.

By using this tool, you acknowledge that you are solely responsible for your actions. The author assumes no liability for any misuse of this software or for any damages resulting from its use.\n\n'''

    slow_print(notice, delay=0.03)


    steps = [
        'Loading configuration...',
        'Initializing networking...',
        'Loading shell handlers...',
        'Preparing transport layer...',
        'Starting Fusion Core...'
    ]

    for step in steps:
        print(f' [+] {step}')
        time.sleep(0.15)

    print()

    banner()

def banner():
    hostname = socket.gethostname()

    cpu = p.cpu_count()

    banner_text = rf'''
                             ███╗   ██╗███████╗████████╗
                             ████╗  ██║██╔════╝╚══██╔══╝
                             ██╔██╗ ██║█████╗     ██║
                             ██║╚██╗██║██╔══╝     ██║
                             ██║ ╚████║███████╗   ██║
                             ╚═╝  ╚═══╝╚══════╝   ╚═╝

                               ███████╗██╗   ██╗███████╗██╗ ██████╗ ███╗   ██╗
                               ██╔════╝██║   ██║██╔════╝██║██╔═══██╗████╗  ██║
                               █████╗  ██║   ██║███████╗██║██║   ██║██╔██╗ ██║
                               ██╔══╝  ██║   ██║╚════██║██║██║   ██║██║╚██╗██║
                               ██║     ╚██████╔╝███████║██║╚██████╔╝██║ ╚████║
                               ╚═╝      ╚═════╝ ╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝

   Version       2.0.0
   Python        {platform.python_version()}
   Platform      {platform.system()} {platform.release()}
   Hostname      {hostname}
   PID           {os.getpid()}
   Threads       {threading.active_count()}
   Runtime       {platform.python_implementation()}
   CPU Cores     {cpu}
   Status        Ready

   ───────────────────────────────────────────────────────────

   ✔ Connection Handler
   ✔ Bind Shell
   ✔ Interactive Messaging
   ✔ TCP Stream Pipeline
   ✔ Cross-Platform Shell

   ───────────────────────────────────────────────────────────
'''
    slow_print(banner_text, delay=0.03)

def nf_console(config):
    while True:
        try:
            while config.terminal_busy.is_set():
                time.sleep(0.1)
                continue

            command_line = nf_input().strip()

            if not command_line:
                continue

            command = command_line.split()

            if command[0].lower() == 'help':
                help = '''
You can run one of commands like ls -la, pwd, and whoami without using the shell command
-----------------------------------------------------------------------------------------
Available commands:
  help                    Show this help message
  clear                   Clear the console screen
  info                    Show information about the current session
  connect <host> <port>   Connect to a target host and port
  quit/exit/shutdown      Exit the program
  message <port>          Start a messaging session with a target host and port
  bind <port>             Start a bind shell on a target host and port
  stream <port>           Start a TCP stream pipeline with a target host and port
  listen <port>           Start a listener on a target host and port
  shell                   Starts a mock terminal type exit to return back to NetFusion
-----------------------------------------------------------------------------------------
  '''

                slow_print(help, delay=0.03)

                usage()
                
            elif command[0].lower()in ('quit', 'exit', 'shutdown'):
                if config.listener_is_active:
                    config.listener_is_active = False
                    if not config.listener_running:
                        print(' [*] Listener is not running...')
                        continue

                    config.listener_stop.set()
                    config.listener_thread.join()

                    print(f' [*] Listener on {config.listen_host}:{config.port} has been stopped...')
                else:
                    print(' [*] Exiting NetFusion...')
                    sys.exit(0)

                print(' [*] Disconnecting NetFusion...')
                sys.exit(0)

            elif command[0].lower() == 'clear':
                os.system('cls' if os.name == 'nt' else 'clear')
                banner()

            elif command[0].lower() == 'shell':
                if os.name == 'nt':
                    print(' [*] Starting Windows shell...')
                else:
                    print(' [*] Starting interactive shell...')

                local_shell()

                print(' [*] Returned to NetFusion')

            elif command[0].lower() == 'info':
                banner()

            elif command[0].lower() == 'connect':
                if len(command) < 3:
                    print(' [!] Usage: connect <host> <port>')
                    continue

                arguments = [
                    '-t', command[1],
                    '-p', command[2]
                ]

                parse_arguments(config, arguments)

                client_end(config, '')

                print(f' [*] Connecting to {config.target}:{config.port}...')

            elif command[0].lower() == 'listen':

                command.pop(0)  # Remove the 'listen' command from the list

                arguments = []

                arguments.append('-l')

                if len(command) > 0:
                    arguments.extend(['-p', command[0]])
                                 
                if not parse_arguments(config, arguments):
                    continue

                if config.listener_running:
                    print(f' [*] Listener is already running on port {config.port}.')

                config.listener_stop.clear()

                config.listener_thread = threading.Thread(target=server_loop, args=(config, config.listener_stop), daemon=True)
                config.listener_thread.start()

                config.listener_running = True
                config.listener_is_active = True

                print(f' \n [*] Listening on port {config.port}... \n [*] To stop the listener, type "quit","exit", or "shutdown" in the console.')

            elif command[0].lower() in ('message', 'bind' , 'stream'):

                arguments = [] 

                mode = command[0].lower()

                if mode == 'message':
                    arguments.append('-m')

                elif mode == 'bind':
                    arguments.append('-b')

                elif mode == 'stream':
                    arguments.append('-s')

                arguments.append('-l')

                if len(command) > 1:
                    arguments.extend(['-p', command[1]])

                if not parse_arguments(config, arguments):
                    continue

                if config.listener_running:
                    print(f' [*] Listener is already running on port {config.port}...')
                    continue

                config.listener_stop.clear()

                config.listener_thread = threading.Thread(target=server_loop, args=(config, config.listener_stop), daemon=True)
                config.listener_thread.start()

                config.listener_running = True
                config.listener_is_active = True

                print(f' \n [*] Listening on port {config.port} in {mode} mode... \n [*] To stop the listener, type "quit","exit", or "shutdown" in the console...')   

            elif command[0].lower() == 'clean':
                if len(command) < 2:
                    print(' [!] Usage: clean <port>')
                    continue

                try:
                    port = int(command[1])

                except ValueError:
                    print(' [!] Invalid port number. Please provide a valid integer.')
                    continue

                cleaned = is_port_in_use(config, port)

                if cleaned:
                    print(f' [*] Port {port} has been cleaned.')
                else:
                    print(f' [*] Port {port} is not in use or could not be cleaned.')

            else:
                local_command(command_line)

        except KeyboardInterrupt:
            print('\n [*] KeyboardInterrupt received. Exiting...')
            sys.exit(0)

# Displays all commands/flags and show examples of use
def usage():
    usage = '''\nNetFusion outside of the tool
------------------------------------------------------------------------------------------    
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
Use outside of the Tool examples:
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
            If errors show up from exsiting from a connection do not be alarmed that will happen currently working on making the script not do that.\n'''

    slow_print(usage, delay=0.05)

class UnixTerminal:
    def __init__(self):
        self.pid = None
        self.master_fd = None
        self.running = False

    def start(self):
        shell = (
            os.environ.get('SHELL')
            or shutil.which('bash')
            or shutil.which('zsh')
            or shutil.which('sh')
            or '/bin/sh'
        )

        self.pid, self.master_fd = pty.fork()

        if self.pid == 0:
            os.execv(shell, [shell])

        self.running = True

    def read_loop(self, client_socket):
        if not self.running or self.master_fd is None:
            return

        while self.running:
            try:
                data = os.read(self.master_fd, 4096)

                if not data:
                    break

                client_socket.sendall(data)

            except OSError:
                break

            except (BrokenPipeError, ConnectionResetError):
                break

        self.running = False

    def write(self, data):
            if not self.running or self.master_fd is None:
                return

            try:
                if isinstance(data, str):
                    data = data.encode()

                os.write(self.master_fd, data)

            except OSError:
                self.running = False

    def close(self):
        if not self.running:
            return

        self.running = False

        try:
            os.close(self.master_fd)

        except OSError:
            pass


def local_shell():
    '''
    This will start a interactive local shell
    
    Unix:
        Uses a PTY so programs believe they are attached to a real terminal
        
    Windows:
        Falls back to th user's normal shell through subproccess
    '''
    print(' [*] Type exit to return to NetFusion')
    if os.name in ('nt'):
        windows_shell = (
            os.environ.get('COMSPEC')
            or shutil.which('pwsh.exe')
            or shutil.which('powershell.exe')
            or shutil.which('cmd.exe')
        )

        if not windows_shell:
            print(' [*] No Windows shell could be found...')
            return

        try:
            subprocess.run([windows_shell])
        except KeyboardInterrupt:
            pass

        return

    terminal = UnixTerminal()
    try:
        terminal.start()
    except Exception as e:
        print(f' [*] Failed to start local shell" {e}')
        return

    stdin_fd = sys.stdin.fileno()

    old_settings = termios.tcgetattr(stdin_fd)

    try:
        #Gives individual keystrokes instead of waiting for Enter
        tty.setraw(stdin_fd)

        while terminal.running:
            readable, _, _ = select.select(
                [stdin_fd, terminal.master_fd],
            [],
            []
            )

            if stdin_fd in readable:
                data = os.read(stdin_fd, 4096)

                if not data:
                    break

                os.write(terminal.master_fd, data)

            if terminal.master_fd in readable:
                try:
                    data = os.read(terminal.master_fd, 4096)

                    if not data:
                        break

                    os.write(sys.stdout.fileno(), data)

                except OSError:
                    break
    except KeyboardInterrupt:
        pass

    finally:
        # Restore the user's terminal
        termios.tcsetattr(
            stdin_fd,
            termios.TCSADRAIN,
            old_settings
        )

        terminal.close()

        print()

def local_command(command_line):
    # Runs a local shell command without leaving NetFusion

    try:
        output = subprocess.run(
            command_line,
            shell = True,
            cwd = os.getcwd(),
            env = os.environ.copy()
        )
    except KeyboardInterrupt:
        print(' [!] Command interrupted...')

    except Exception as e:
        print(f' [!] Failed to exectue command: {e}')

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

def is_port_in_use(config, port):
    try:
        if config.port_clearing:
            for conn in p.net_connections():
                if conn.laddr.port == port:
                    user_input = nf_input(f' [*] Port {port} is in use by PID {conn.pid}.\n [*] Do you want to terminate the process using this port? (y/n): ')

                    while user_input.lower() not in ['y', 'n']:
                        user_input = nf_input('\n [*] Invalid input. Please enter either y or n: ')

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
    
    config.port_clearing = False  # Reset the port_clearing flag after checking

# Send NetFusion protocol ID and negotiated mode 
def send_handshake(client_socket, mode):
    if mode not in ('message', 'bind', 'stream'):
        raise ValueError(f'Invalid NetFusion mode: {mode}')
    
    handshake = f'NF/1 {mode}\n'.encode('ascii')

    client_socket.sendall(handshake)

# Receive/ validate a NetFusion server handshake
def receive_handshake(client_socket):
    buffer = b''
    try:
        while len(buffer) < max_handshake_size:
            data = client_socket.recv(1)

            if not data:
                print(' [!] Server closed the connection during handshake.')
                return None

            buffer += data

            if data == b'\n':
                break

    except ConnectionResetError:
        print(' [!] Connection was reset by the server during handshake.')
        return None

    except BrokenPipeError:
        print(' [!] Broken pipe during handshake.')
        return None

    except OSError as e:
        print(f' [!] Socket error during handshake: {e}')
        return None

    try:
        line = buffer.decode('ascii').strip()
    except UnicodeDecodeError:
        print(' [!] Invalid characters received during handshake.')
        return None

    print(f'Raw handshaek recevied: {line!r}')
    parts = line.split()

    if len(parts) != 2:
        print(f' [!] Invalid NetFusion handshake: {line!r}')
        return None

    protocol, mode = parts

    if protocol != 'NF/1':
        print(f' [!] Unsupported protocol: {protocol}')
        return None

    if mode not in ('message', 'bind', 'stream'):
        print(f' [!] Unsupported NetFusion mode: {mode}')
        return None

    return mode

#Detect whether a connection is NetFusion or raw TCP
def detect_protocol(client_socket, timeout=2.0):
    original_timeout = client_socket.gettimeout()

    buffer = bytearray()

    try:
        client_socket.settimeout(timeout)

        while len(buffer) < max_handshake_size:
            data = client_socket.recv(1)

            if not data:
                break

            buffer.extend(data)

            if not nfch.startswith(bytes(buffer)):
                return 'raw', bytes(buffer)

            if bytes(buffer) == nfch:
                return 'netfusion', b''
            
        return 'raw', bytes(buffer)
    except socket.timeout:
        return 'raw', bytes(buffer)
    except (ConnectionError, BrokenPipeError, OSError):
        return 'raw', bytes(buffer)
    finally:
        client_socket.settimeout(original_timeout)
    

def server_end(client_socket, config, mode):
    send_handshake(client_socket, mode)

    if mode == 'message':
        config.terminal_busy.set()
        try:
            server_name_choice = input('\n [*] Do you want to set a username  (y or n): ')

            while server_name_choice.lower() not in ('y', 'n'):
                server_name_choice = input('\n [*] Invalid input please type either y or n: ')

            if server_name_choice.lower() == 'y':
                config.server_name = input('\n [*] What is your temp username: ')
            else:
                config.server_name = 'Server'

            client_socket.sendall(json.dumps({'name': config.server_name}).encode('utf-8') + b'\n')
            client_info = json.loads(client_socket.recv(1024).decode())
            client_uname = client_info['name']

            def recv_msg():
                while True:
                    data = client_socket.recv(1024)
                    if not data:
                        print('\n [*] Client disconnected...', flush=True)
                        return

                    text = data.decode().rstrip('\r\n')
                    sys.stdout.write(f'\n{client_uname}: {text}\n<{config.server_name}:#>')
                    sys.stdout.flush()

            def send_msg():
                print(' [*] To disconnect type either: quit/exit/shutdown')

                while True:
                    msg = input(f'<{config.server_name}:#> ')

                    client_socket.sendall((f'{msg} \n').encode())

                    if msg.strip().lower() in ('quit', 'exit', 'shutdown'):
                        print('\n [*] Disconnecting...')
                        client_socket.close()
                        return

            recv_thread = threading.Thread(target=recv_msg)
            send_thread = threading.Thread(target=send_msg)

            recv_thread.start()
            send_thread.start()

            recv_thread.join()
            send_thread.join()
        finally:
            config.terminal_busy.clear()
            client_socket.close()

    elif len(config.upload_destination):
        file_buffer = b''

        while True:
            data = client_socket.recv(1024)

            if not data:
                break

            else:
                file_buffer += data

        try:
            file_descriptor = open(config.upload_destination, 'wb')
            file_descriptor.write(file_buffer)
            file_descriptor.close()
            client_socket.send(('Successfully saved file to %s\r\n' % config.upload_destination).encode())
        except:
            client_socket.send(('Failed to save file to %s\r\n' % config.upload_destination).encode())

    # if len(execute):
    #     output = ShellSession(execute)

    #     client_socket.sendall(output)

    elif mode == 'bind':
        if sys.platform.startswith('win'):
            shell = ShellSession()
        elif sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
            shell = UnixTerminal()
        else:
            print(f' [*] Unsupported platform: {sys.platform}')
            client_socket.close()
            return

        try:
            shell.start()

            reader = threading.Thread(target=shell.read_loop, args=(client_socket,), daemon=True)

            reader.start()

            while shell.running:
                data = client_socket.recv(1024)

                if not data:
                    break

                shell.write(data.decode('utf-8', errors='ignore'))
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass

        finally:
            shell.close()
            client_socket.close()

    elif mode == 'stream':
        def stream_receive():
            try:
                while True:
                    data = client_socket.recv(4096)

                    if not data:
                        break

                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
            except (ConnectionResetError, BrokenPipeError, OSError):
                pass

        def stream_send():
            try:
                while True:
                    data = sys.stdin.buffer.read(4096)

                    if not data:
                        break

                    client_socket.sendall(data)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

        receive_threat = threading.Thread(target=stream_receive, daemon=True)
        send_thread = threading.Thread(target=stream_send, daemon=True)

        receive_threat.start()
        send_thread.start()

        client_socket.close()

#Handle a raw TCP connection
def raw_stream(client_socket, initial_data=b''):
    stop_event = threading.Event()

    def receive_loop():
        try:
            if initial_data:
                sys.stdout.buffer.write(initial_data)
                sys.stdout.buffer.flush()

            while not stop_event.is_set():
                data = client_socket.recv(4096)

                if not data:
                    break

                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()

        except (ConnectionError, BrokenPipeError, OSError):
            pass
        finally:
            stop_event.set()

    def send_loop():
        try:
            while not stop_event.is_set():
                data = sys.stdin.buffer.read(4096)

                if not data:
                    break

                client_socket.sendall(data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            stop_event.set()

    receive_thread = threading.Thread(target=receive_loop, daemon=True)
    send_thread = threading.Thread(target=send_loop, daemon=True)

    receive_thread.start()
    send_thread.start()

    try:
        while not stop_event.is_set():
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()

        try:
            client_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        try:
            client_socket.close()
        except OSError:
            pass

def server_loop(config, stop_event):
    if config.port <= 0:
        print(' [!] Cannot start listener without a valid port.')
        return

    bind_host = config.listen_host or config.target or '0.0.0.0'
    bind_host = config.listen_host or config.target or '0.0.0.0'

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.settimeout(1.0)

    mode = config.mode
    
    try:
        server.bind((bind_host, config.port))
    except OSError as e:
        if getattr(e, 'errno', None) == 98:
            print(f' [*] Port {config.port} is already in use.\n ')

            if config.port_clearing:
                cleaned = is_port_in_use(config, config.port)

                if cleaned:
                    try:
                        server.bind((bind_host, config.port))
                        print(f' [*] Redound successfull... Bound to {bind_host}:{config.port}...')
                    except OSError:
                        print(' [*] Port unavailable...')
                        return
        else:
            print(f' [*] Type clean to free a port or use a differen port...')
            sys.exit(0)

    server.listen(5)
    try:
        print(f' [*] Listening on {bind_host}:{config.port}')

        while not stop_event.is_set():
            try:
                client_socket, addr = server.accept()
            except socket.timeout:
                continue
            except KeyboardInterrupt:
                raise

            print(f''' -----------------------------------------------------------------------------------------
 [*] Connection established from {addr[0]} On listener port: {config.port}
 [*] You can now interact with the client.\n [*] Client IP: {addr[0]} \n [*] Client Temporary Port: {addr[1]} 
 [*] To continue in message mode click enter...''', flush=True)

            protocol, initial_data = detect_protocol(client_socket, timeout=config.protocol_timeout)

            config.protocol = protocol
            print(f' [*] Detected protocol: {protocol}')

            if protocol == 'netfusion':
                print(' [*] NetFusion client detected...')

                client_thread = threading.Thread(target=server_end, args=(client_socket, config, config.mode), daemon=True)
                client_thread.start()
            elif protocol == 'raw':
                print(' [*] Raw TCP connection detected...')

                client_thread = threading.Thread(target=raw_stream, args=(client_socket, initial_data), daemon=True)
                client_thread.start()
            else:
                print(' [*] Non-NetFusion connection detected...')
                client_socket.close()

    except KeyboardInterrupt:
        print(f'\n [*] KeyboardInterrupt received. Exiting...')
        stop_event.set()
    finally:
        config.listener_running = False
        try:
            server.close()
        except Exception:
            pass

        print(f' [*] Listener on {bind_host}:{config.port} has been stopped.')

def client_end(config, buffer):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    stop_event = threading.Event()

    client.connect((config.target, config.port))
    client.sendall(nfch)
    server_mode = receive_handshake(client)
    print(f'Parsed  server mode: {server_mode!r}')

    if server_mode is None:
        print(f' [!] Invalid NetFusion server handshake')
        client.close()
        return
    
    print(f' [*] Server mode: {server_mode}')

    if server_mode == 'message':
        config.run_message = True
        config.run_bind = False
        config.run_stream = False

    elif server_mode == 'bind':
        config.run_bind = True
        config.run_message = False
        config.run_stream = False

    elif server_mode == 'stream':
        config.run_stream = True
        config.run_message = False
        config.run_bind = False

    else:
        config.run_message = False
        config.run_bind = False
        config.run_stream = False

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

            if config.run_message:
                text = data.decode().rstrip('\r\n')
                if text.lower() in ('quit', 'exit', 'shutdown'):
                    print(' [*] Server has disconnected...')
                    client.close()
                    sys.exit()
                else:
                    sys.stdout.write(f'\n{server_uname}: {text}\n<{config.client_name}:#>')
                    sys.stdout.flush()

            elif config.run_bind:
                sys.stdout.write(data.decode(errors='ignore'))
                sys.stdout.flush()

    def send_msg():
        while True:
            msg = input(f'<{config.client_name}:#> ')
            client.sendall((msg + '\n').encode())

            if msg.strip().lower() in ('quit', 'exit', 'shutdown'):
                print(' [*] Diconnecting...')
                client.close()
                return

    print(f' [*] To disconnect type either: quit/exit/shutdown')

    if config.run_message:
        config.client_name_choice = input('\n [*] Do you want to set a username (y or n): ')
        while config.client_name_choice.lower() not in ('y', 'n'):
            config.client_name_choice = input('\n [*] Invalide input please type either y or n: ')

        if config.client_name_choice.lower() == 'y':
            config.client_name = input('\n [*] Set your username: ')
        else:
            config.client_name = 'Client'

        handshake = json.loads(client.recv(1024).decode())

        server_uname = handshake['name']
        client.sendall(json.dumps({'name': config.client_name}).encode('utf-8') + b'\n')

        client.settimeout(0.2)

        print(f' [*] Connect to Server on  {config.target}:{config.port}')
        send_thread = threading.Thread(target=send_msg)
        recv_thread = threading.Thread(target=receive_loop)

        send_thread.start()
        recv_thread.start()

        send_thread.join()
        recv_thread.join()
        return

    elif config.run_bind:

        def shell_receive():
            while True:
                try:
                    data = client.recv(4096)

                    if not data:
                        print('\n[*] Server closed the connection.')
                        break

                    sys.stdout.write(data.decode('utf-8', errors='replace'))
                    sys.stdout.flush()

                except (ConnectionResetError, BrokenPipeError, OSError):
                    break

        recv_thread = threading.Thread(
            target=shell_receive,
            daemon=True
        )
        recv_thread.start()

        try:
            while True:
                command = nf_input().strip()

                if not command:
                    continue

                if command.lower() in ('quit', 'exit', 'shutdown'):
                    print('[*] Disconnecting...')
                    break

                try:
                    client.sendall((command + '\n').encode('utf-8'))
                except (ConnectionResetError, BrokenPipeError, OSError):
                    print('[*] Connection to server was lost.')
                    break

        except KeyboardInterrupt:
            print('\n[*] KeyboardInterrupt received.')

        finally:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            client.close()

    elif config.run_stream:
        def stream_receive():
            try:
                while True:
                    data = client.recv(4096)

                    if not data:
                        break

                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()

            except (ConnectionResetError, BrokenPipeError, OSError):
                pass

        def stream_send():
            try:
                if buffer:
                    if isinstance(buffer, str):
                        buffer_data = buffer.encode()
                    else:
                        buffer_data = buffer

                    client.sendall(buffer_data)

                while True:
                    data = sys.stdin.buffer.read(4096)

                    if not data:
                        break

                    client.sendall(data)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

    recv_thread = threading.Thread(target=stream_receive, daemon=True)
    send_thread = threading.Thread(target=stream_send, daemon=True)

    recv_thread.start()
    send_thread.start()

    try:
        recv_thread.join()
        send_thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            client.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    client.close()

def parse_arguments(config, arguments):
    config.port = 0
    config.listen = False
    config.bind = False
    config.upload = False
    config.port_clearing = False
    config.message = False
    config.quiet = False
    config.stream = False
    config.mode = ''

    try:
        opts, args = getopt.getopt(
            arguments,
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
        return False
    
    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
        elif o in ('-b', '--bind'):
            config.bind = True
            config.mode = 'bind'
        elif o in ('-e', '--execute'):
            config.execute = a
        elif o in ('-F', '--force-freeing'):
            config.port_clearing = True
        elif o in ('-l', '--listen'):
            config.listen = True
        elif o in ('-L', '--listen-host'):
            config.listen_host = a
            config.listen = True
        elif o in ('-m', '--message'):
            config.message = True
            config.mode = 'message'

            if not config.target:
                config.listen = True
        elif o in ('-r', '--reverse'):
            config.reverse = True
            config.mode = 'reverse'
        elif o in ('-p', '--port'):
            try:
                config.port = int(a)
            except ValueError:
                print(' [!] Port number must be a valid integer...')
                return False

            if config.port <= 0:
                print(' [!] Port number cannot be 0...')
                return False

            if config.port > 65535:
                print(' [!] Port number cannot be greater than 65,535...')
                return False
            
        elif o in ('-s', '--stream'):
            config.stream = True
            config.mode = 'stream'
        elif o in ('-t', '--target'):
            config.target = a
        elif o in ('-u', '--upload'):
            config.upload_destination = a

    if config.listen and config.port == 0:
        if config.bind:
            print(' [!] Bind requires a port number between 1 and 65535...')
            print(' [!] Usage: bind <port>')
        elif config.message:
            print(' [!] Message requires a port number between 1 and 65535...')
            print(' [!] Usage: message <port>')
        elif config.stream:
            print(' [!] Stream requires a port number between 1 and 65535...')
            print(' [!] Usage: stream <port>')
        else:
            print(' [!] Listen requires a port number between 1 and 65535...')
            print(' [!] Usage: listen <port>')

        return False

    return True

def main():
    startup()

    config = NetFusionConfig()

    if len(sys.argv) == 1:
        nf_console(config)
        return

    if not parse_arguments(config, sys.argv[1:]):
        return

    start_session(config)


if __name__ == '__main__':
    main()