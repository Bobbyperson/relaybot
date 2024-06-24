untyped
global function serverLog

struct {
    string secret
    string url
    string server_identifier
} file

void function serverLog(){
    print("ParseableLogs: Server log init\\\"\"")

    // Playerlist State Logs
    AddCallback_OnClientConnecting(clientConnecting)
    AddCallback_OnClientConnected(clientConnected)
    AddCallback_OnClientDisconnected(clientDisconnected)

    // Gameplay logs
    AddCallback_OnPlayerRespawned(playerRespawned)
    AddCallback_OnPlayerKilled(playerKilled)
    AddCallback_OnRoundEndCleanup(roundEnded)

    // Gamestate logs
	AddCallback_GameStateEnter( eGameState.WaitingForPlayers, gs_waitingForPlayers )
	AddCallback_GameStateEnter( eGameState.PickLoadout, gs_pickingLoadouts )
	AddCallback_GameStateEnter( eGameState.Prematch, gs_prematch )
	AddCallback_GameStateEnter( eGameState.Playing, gs_playing )
	AddCallback_GameStateEnter( eGameState.WinnerDetermined, gs_winnerDetermined )
	AddCallback_GameStateEnter( eGameState.SwitchingSides, gs_switchingSides )
	AddCallback_GameStateEnter( eGameState.SuddenDeath, gs_suddenDeath )
	AddCallback_GameStateEnter( eGameState.Postmatch, gs_postmatch )

    // Chat logs
    AddCallback_OnReceivedSayTextMessage(chatMessage)

    // Regular player location logs
    int playerLocationInterval = GetConVarInt("parsable_player_interval")
    if (playerLocationInterval > 0){
        print("Log: Started JSON log")
        thread playerLogThread(playerLocationInterval)
    }

    file.secret = GetConVarString("api_secret")
    file.url = GetConVarString("api_url")
    file.server_identifier = GetConVarString("server_identifier")
}

// add double quotes to string
string function fmtString(string toFormat){
    return "\"" + toFormat + "\""
}

// Format a string, escaping the quotes inside it.
string function fmtStringSafe(string toFormat){
    toFormat = StringReplace(toFormat, "\"", "§", true, false)
    toFormat = StringReplace(toFormat, "§", "\\\"", true, false)
    return fmtString(toFormat)
}

// string mapping (add double quotes)
string function sMap(string key, string value){
    return fmtString(key) + ":" + fmtString(value)
}

// integer mapping (no formatting needed)
string function iMap(string key, int value){
    return fmtString(key) + ":" + value
}

// float mapping (no formatting needed)
string function fMap(string key, float value){
    return fmtString(key) + ":" + value
}

// raw mapping (no formatting needed)
string function rMap(string key, string value){
    return fmtString(key) + ":" + value
}

// boolean map, string true or false
string function bMap(string key, bool value){
    if (value){
        return fmtString(key) + ":" + "true"
    } else {
        return fmtString(key) + ":" + "false"
    }
    unreachable
}

// join an array of json maps (return val of s/n/bMap ) to a json object
// for anything but top level objects, the first key should be "type" and
// the value should denote the type of object, like player, vector etc.
string function jsonMapJoin(array<string> vals){
    string output_s = "{"
    foreach(idx,value in vals){
        if (output_s == "{"){
            output_s = output_s + value
        } else {
            output_s = output_s +"," + value
        }
    }
    return output_s + "}"
} 

// format a vector as a json object
string function fmtVector(vector vec){
    return jsonMapJoin(
        [
            sMap("type", "vector"),
            fMap("x", vec.x),
            fMap("y", vec.y),
            fMap("z", vec.z),
        ]
    )
}

// format info about a player as a json object
string function fmtPlayer( entity player){
    array<string> json_obj = [
            sMap("type",        "player"),
            sMap("name",        player.GetPlayerName()),
            iMap("playerIndex", player.GetPlayerIndex()),
            iMap("teamId",      player.GetTeam()),
            sMap("uid",         player.GetUID()),
            iMap("ping",        player.GetPlayerGameStat( PGS_PING )),
            iMap("kills",       player.GetPlayerGameStat ( PGS_KILLS )),
            iMap("deaths",      player.GetPlayerGameStat ( PGS_DEATHS )),
            bMap("alive",       IsAlive(player)),
        ]

    if (IsAlive(player)){
        json_obj.append(bMap("titan",       player.IsTitan()))
        json_obj.append(rMap("location",    fmtVector(player.GetOrigin())))
    }

    return jsonMapJoin(json_obj)
}

// subject = a thing to which a action has happened
// verb = any action that could happen to anything in the game
// object = the object to which the subject has done the verb

// log a subject-verb-object log message
void function log_svo( string subject, string verb, string object){
    print("[ParseableLog] " + jsonMapJoin([
        rMap("subject", subject),
        rMap("verb", verb),
        rMap("object", object)
    ]))

	postRequest(jsonMapJoin([
		rMap("subject", subject),
		rMap("verb", verb),
		rMap("object", object),
        rMap("server_identifier", file.server_identifier)
	]))
}

// log a subject-verb log message
void function log_sv( string subject, string verb){
    print("[ParseableLog] " + jsonMapJoin([
        rMap("subject", subject),
        rMap("verb", verb)
    ]))

	postRequest(jsonMapJoin([
		rMap("subject", subject),
		rMap("verb", verb),
        rMap("server_identifier", file.server_identifier)
	]))
}

// log_sv but with string maps
void function log_sv_s( string subject, string verb){
    print("[ParseableLog] " + jsonMapJoin([
        sMap("subject", subject),
        sMap("verb", verb)
    ]))

	postRequest(jsonMapJoin([
		sMap("subject", subject),
		sMap("verb", verb),
        rMap("server_identifier", file.server_identifier)
	]))
}

// logs all players every parsable_player_interval seconds.
void function playerLogThread(int interval) {
    for (;;){
        foreach ( entity player in GetPlayerArray()){
            log_sv(fmtPlayer(player), fmtString("existing"))
        }
        wait interval
    }
}

void function playerKilled( entity victim, entity attacker, var damageInfo ){
    switch(attacker.GetClassName()){
        case"trigger_hurt": // Fall
            log_svo(fmtPlayer(victim), fmtString("diedfrom"), fmtString("fall"))
            return
        case"worldspawn": // Out of Bounds
            log_svo(fmtPlayer(victim), fmtString("diedfrom"), fmtString("out of bounds"))
            return
        case"player":
            log_svo(fmtPlayer(attacker), fmtString("killed"), fmtPlayer(victim))
            return
    }
}

void function playerRespawned( entity client ){
    if (client.IsPlayer()) {
        log_sv(fmtPlayer(client), fmtString("respawned"))
    }
}

void function clientConnecting( entity client ){
    if (client.IsPlayer()){
        log_sv(fmtPlayer(client), fmtString("connecting"))
    }
}

void function clientConnected( entity client ){
    if (client.IsPlayer()){
        log_sv(fmtPlayer(client), fmtString("connected"))
    }
}

void function clientDisconnected( entity client ){
    if (client.IsPlayer()){
        log_sv(fmtPlayer(client), fmtString("disconnected"))
    }
}

void function gs_waitingForPlayers(){
    log_sv_s("gamestate", "waitingForPlayers")
}

void function gs_pickingLoadouts(){
    log_sv_s("gamestate", "pickingLoadouts")
}

void function gs_prematch(){
    log_sv_s("gamestate", "prematch")
}

void function gs_playing(){
    log_sv_s("gamestate", "playing")
}

void function gs_winnerDetermined(){
    log_sv_s("gamestate", "winnerDetermined")
}

void function gs_switchingSides() {
    log_sv_s("gamestate", "switchingSide")
}

void function gs_suddenDeath() {
    log_sv_s("gamestate", "suddenDeath")
}

void function gs_postmatch(){
    log_sv_s("gamestate", "postmatch")
}

void function roundEnded(){
    log_sv_s("round", "ended")
}


ClServer_MessageStruct function chatMessage(ClServer_MessageStruct message)
{
    string msgPart = jsonMapJoin([
        rMap("message", fmtStringSafe(message.message)),
        bMap("team_chat", message.isTeam)
    ])
    log_svo(fmtPlayer(message.player), fmtString("sent"), msgPart)

    return message
}

// POST Http request
void function postRequest( string body )
{
    HttpRequest request
    request.method = HttpRequestMethod.POST
    request.url = file.url
    table<string, array<string> > headers
    headers["authentication"] <- [file.secret]
    request.headers = headers

    request.body = body

    void functionref( HttpRequestResponse ) onSuccess = void function ( HttpRequestResponse response )
    {
        // print("ParseableLogs: POST request success")
    }

	void functionref( HttpRequestFailure ) onFailure = void function ( HttpRequestFailure failure )
	{
        print("ParseableLogs: POST request failed")
	}

    NSHttpRequest( request, onSuccess, onFailure )
}