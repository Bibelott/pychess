import tkinter as tk
from multiprocessing import Process
import client
import os
if os.path.exists('server/server.py'):
    from server import server

def join_game(host: str, port: int) -> None:
    client.run(host, port)

def create_game(port: int) -> None:
    with server.Game() as game:
        game.serve(port)

def join(root: tk.Tk, host: str, port: int) -> Process:
    global client_proc
    client_proc = Process(target=join_game, args=[host, port])

    client_proc.start()

    root.destroy()

    return client_proc

def create_and_join(root: tk.Tk, host: str, port: int) -> tuple[Process, Process]:
    global server_proc
    global client_proc
    server_proc = Process(target=create_game, args=[port])
    client_proc = Process(target=join_game, args=[host, port])

    server_proc.start()
    client_proc.start()

    root.destroy()

    return (server_proc, client_proc)

client_proc = None
server_proc = None

if __name__ == '__main__':
    root = tk.Tk()
    root.title("Join a game")

    host_label = tk.Label(root, text="Address:")
    host_label.grid(row = 0, column = 0, sticky='E')

    host = tk.StringVar(root, value='127.0.0.1')

    host_entry = tk.Entry(root, textvariable=host)
    host_entry.grid(row = 0, column = 1)

    port_label = tk.Label(root, text="Port:", justify='right')
    port_label.grid(row = 1, column = 0, sticky='E')

    port = tk.IntVar(root, value=40000)

    port_entry = tk.Entry(root, textvariable=port)
    port_entry.grid(row = 1, column = 1)

    join_but = tk.Button(root, text="Join an existing game", command=lambda: join(root, host.get(), port.get()))
    join_but.grid(row = 2, column = 0)

    create_but = tk.Button(root, text="Create a new game", command=lambda: create_and_join(root, host.get(), port.get()))
    create_but.grid(row = 2, column = 1)

    root.mainloop()

    if client_proc != None:
        client_proc.join()
        client_proc.terminate()
    if server_proc != None:
        server_proc.terminate()