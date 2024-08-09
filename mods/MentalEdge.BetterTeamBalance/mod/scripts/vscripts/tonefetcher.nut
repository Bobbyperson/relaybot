global function BTBToneInit
global function BTBGetToneKD

table <string, float> toneKDs
array <string> previusMatchUID
string toneurl
bool toneEnabled = false

void function BTBToneInit(){
    toneurl = GetConVarString( "btb_tone_url" )
    toneEnabled = GetConVarBool( "btb_tone" )

    if( toneEnabled ){
        previusMatchUID = split( GetConVarString( "uid_list" ), "," )
        AddCallback_OnClientConnecting( CheckPlayer )
    }
}

float function BTBGetToneKD( entity player ){
    if( player.GetPlayerName() in toneKDs ){
        return toneKDs[player.GetPlayerName()]
    }

    return 0.0
}

void function CheckPlayer( entity player ){

    // Only get the stats of new players
    foreach( uid in previusMatchUID )
        if( uid == player.GetUID() )
            return

    print("[BTB][Tone API] Attempting to get stats for " + player.GetPlayerName() )
    SaveToneKD( player.GetUID() )
}

void function SaveToneKD(string uid){

    HttpRequest request = { ... }
    request.method = HttpRequestMethod.GET
    request.url = toneurl + "/get?player=" + uid

    void functionref( HttpRequestResponse ) OnSuccess = void function ( HttpRequestResponse response )
    {
        try{
            table decoded
            foreach( uid, tab in DecodeJSON(response.body) )
                decoded = expect table(tab)

            if(response.statusCode == 200 && decoded.len() != 0 ){
                string user = expect string(decoded["username"])
                float kd = expect int(decoded["kills"]).tofloat() / expect int(decoded["deaths"]).tofloat()
                print("[BTB][Tone API] Succesfully grabbed stats for " + user + ": " + kd )
                toneKDs[user] <- kd
            }else{
                print("[BTB][Tone API] Tone API unavailable, or does not have stats for this player")
                print("[BTB][Tone API] " + response.body )
            }
        }catch(exception){
            print("[BTB][Tone API] Failed to decode Tone API response")
            return
        }
    }

    void functionref( HttpRequestFailure ) OnFailure = void function ( HttpRequestFailure failure )
    {
        print("[BTB][Tone API] Tone API unavailable, or does not have stats for this player")
        print("[BTB][Tone API] " + failure.errorMessage )
    }

    NSHttpRequest(request, OnSuccess, OnFailure)
}
