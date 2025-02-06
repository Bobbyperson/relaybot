from rcon.source import rcon
from config import servers


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
        for s in servers:
            try:
                await rcon(
                    command,
                    host=s.ip,
                    port=self.rcon_port,
                    passwd=self.rcon_password,
                    frag_threshold=0,
                )
            except Exception:
                pass
