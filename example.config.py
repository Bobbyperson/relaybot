from server import Server

TOKEN = ""

ban_words = ["fag+ot", "nig+er"]  # automatic ban words
bad_words = [
    "nigg",
    "fag",
    "bundle of sticks",
    "tnd",
    r"f([aeiou*x])\1*g+([aeiou*x])\1*t",
]  # admin warnings

servers = [
    Server(
        "server1",
        "100th attrition server",
        0,
        "127.0.0.1",
        "secretkey1",
        "rconpass1",
        1234,
    ),
    Server(
        "server2",
        "101st attrition server",
        0,
        "127.0.0.1",
        "secretkey2",
        "rconpass2",
        1234,
    ),
    Server(
        "server3",
        "102nd attrition server",
        0,
        "127.0.0.1",
        "secretkey3",
        "rconpass3",
        1234,
    ),
]

tournament_servers = [
    Server(
        "tournament1",
        "awesome tournament server",
        0,
        "127.0.0.1",
        "secretkey1",
        "rconpass1",
        1234,
    ),
]

admin_relay = 0
ban_log = 0
channel_id = 0  # dedicated stats channel id
query = ["server name"]
masterurl = "https://northstar.tf/client/servers"  # don't change this
debug = False
log_channel = 0
bigbrother = 0
bank = "database.sqlite"

# discord ids
admins = []

# northstar ids
admin_uids = []
owner_id = 0
