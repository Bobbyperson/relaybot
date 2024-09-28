from rcon.source import rcon


class Server:
    def __init__(self, name, display_name, relay, ip, key, rcon_password):
        self.name = name
        self.display_name = display_name
        self.relay = relay
        self.ip = ip
        self.key = key
        self.rcon_password = rcon_password

    async def send_command(self, command):
        await rcon(
            command,
            host=self.ip,
            port=7123,
            passwd=self.rcon_password,
            frag_threshold=0,
        )
