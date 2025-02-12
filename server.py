from rcon.source import rcon


class Server:
    def __init__(self, name, display_name, relay, ip, key, rcon_password, rcon_port):
        self.name = name
        self.display_name = display_name
        self.relay = relay
        self.ip = ip
        self.key = key
        self.rcon_password = rcon_password
        self.rcon_port = rcon_port

    async def send_command(self, command):
        temp = ["172.18.0.2", "172.19.0.2", "172.20.0.2", "172.21.0.2", "172.22.0.2"]
        for ip in temp:
            try:
                await rcon(
                    command,
                    host=ip,
                    port=self.rcon_port,
                    passwd=self.rcon_password,
                    timeout=1,
                )
            except Exception as e:
                print(e)
