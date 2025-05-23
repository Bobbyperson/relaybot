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
        iplist = []
        for i in range(18, 30, 1):
            iplist.append(f"172.{i}.0.2")
        for ip in iplist:
            try:
                await rcon(
                    command,
                    host=ip,
                    port=self.rcon_port,
                    passwd=self.rcon_password,
                    timeout=1,
                )
            except Exception:
                pass
