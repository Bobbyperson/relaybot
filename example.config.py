TOKEN = ""
ban_words = [r"f([aeiou*x])\1*g+([aeiou*x])\1*t", "nig+er"] # automatic ban words
bad_words = ["nigg", "fag", "bundle of sticks", "tnd"] # admin warnings
class Server: # this might suck
    def __init__(self, name, relay, ip, key):
        self.name = name
        self.relay = relay
        self.ip = ip
        self.key = key
        
servers = [Server("server1", 0, "127.0.0.1", "secretkey1"), Server("server2", 0, "127.0.0.1", "secretkey2"), Server("server3", 0, "127.0.0.1", "secretkey3")]   

admin_relay = 0
ban_log = 0
channel_id = 0  # dedicated stats channel id
query = ["server name"]  
masterurl = "https://northstar.tf/client/servers"  # don't change this
whitelist_folder = "C:\Program Files (x86)\Steam\steamapps\common\Titanfall2\R2Northstar\save_data\Whitelist"
debug = False
log_channel = 0
bigbrother = 0
bank = "database.sqlite"

# discord ids
admins = [
]

#northstar ids
admin_uids = [
]
owner_id = 0