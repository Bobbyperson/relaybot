global function BTBInit

array <entity> playersWantingToBalance
table <string, float> lastMatchStats
table <string, int> timePlayed  // player uid, time they have played
table <string, string> nemeses
table <string, string> partyInvites // Invitee, inviter
table <string, array <string> > parties // Party leader, array of members
table <string, int> partyStrenghtTimer
array <entity> chosenNemesis // players who have chose a nemesis
table <entity, float> lastmoved

enum eAntiAfkPlayerState {
    ACTIVE
    SUSPICIOUS
    AFK
}

int differenceMax = 1
int waitTime = 4
float suggestionLimit = 1.5
float activeLimit = 1.6
float stompLimit = 2.0
float voteFraction = 0.45
float relativeScoreDifference = 1.0
float suggestionTimer = 10.0
int afkThresold = 5
int afkTime = 70
int shuffle = 1
int grace = 6
bool highlight = true
bool recentBalancing = true

int rebalancedHasOccurred = 0
int waitedTime = 0
int matchElapsed = 0
int subtleRebalancePermitted = 0
int teamsBuilt = 0 // This is used to prevent team rebuild in round based modes

float accumulatedSuggestionImbalance = 0.0
float accumulatedStompImbalance = 0.0
float accumulatedActiveImbalance = 0.0

const SHUFFLE_RANDOMNESS = 0.075


void function BTBInit(){

    foreach (entity player in GetPlayerArray()){
        AddPlayerCallbacks( player )
    }

    AddCallback_OnClientConnected( AddPlayerCallbacks )
    AddCallback_OnClientDisconnected( DeletePlayerRecords )
    AddCallback_OnPlayerRespawned( Moved )

    if( IsFFAGame() ){
        print("[BTB] BetterTeamBalance is running, but server is on an FFA gamemode - ONLY AFK KICK WILL WORK")
        thread BTBFallbackModeThread()
        return
    }

    foreach( player in GetPlayerArray() ){
        NSCreateStatusMessageOnPlayer( player, "BTB", "Waiting for players....", "btbstatus"  )
    }

    lastMatchStats["average"] <- 0.6666

    differenceMax = GetConVarInt( "btb_difference_max" )
    waitTime = GetConVarInt( "btb_wait_time" )
    suggestionLimit = GetConVarFloat( "btb_suggestion_limit" )
    stompLimit = GetConVarFloat( "btb_stomp_limit" )
    activeLimit = GetConVarFloat( "btb_active_limit" )
    voteFraction = GetConVarFloat( "btb_vote_fraction" )
    afkThresold = GetConVarInt( "btb_afk_threshold" )
    afkTime = GetConVarInt( "btb_afk_time" )
    shuffle = GetConVarInt( "btb_shuffle" )
    grace = GetConVarInt( "btb_grace_time" )
    highlight = GetConVarBool("btb_party_highlight")
    recentBalancing = GetConVarBool("btb_recent_balancing")

#if FSCC_ENABLED
    FSCC_CommandStruct command
    command.m_UsageUser = "teambalance"
    command.m_Description = "Vote for teams and scores to be rebalanced."
    command.m_Group = "BTB"
    command.m_Abbreviations = [ "tb", "tbal" ]
    command.Callback = BTB_BalanceVote
    FSCC_RegisterCommand( "teambalance", command )

    command.m_UsageUser = "party"
    command.m_Description = "%H%Pparty <partial/full-name> %Tsends an invite. If they accept, BTB will keep you on the same team."
    command.m_Group = "BTB"
    command.m_Abbreviations = [ "friend", "ally", "party", "par" ]
    command.Callback = BTB_Party
    if( GetConVarBool( "btb_party" ) )
        FSCC_RegisterCommand( "party", command )

    command.m_UsageUser = "nemesis"
    command.m_Description = "%H%Pnemesis <partial/full-name> %Tmakes someone your nemesis! BTB will keep you on opposite teams."
    command.m_Group = "BTB"
    command.m_Abbreviations = [ "foe", "nemesis", "enemy" ]
    command.Callback = BTB_Enemy
    if( GetConVarBool( "btb_nemesis" ) )
        FSCC_RegisterCommand( "nemesis", command )

    command.m_UsageUser = "switch"
    command.m_Description = "%H%switch %Toh my god fine you can have a switch command"
    command.m_Group = "BTB"
    command.m_Abbreviations = [ "s", "sw" ]
    command.Callback = BTB_Switch
    FSCC_RegisterCommand( "switch", command )

    command.m_UsageUser = "stats"
    command.m_Description = "%H%stats %Tcheck your stats for this server"
    command.m_Group = "ATS"
    command.m_Abbreviations = [ "stat" ]
    command.Callback = BTB_Stats
    FSCC_RegisterCommand( "stats", command )

    print("[BTB] FSU is installed! Running BetterTeamBalance with chat command features enabled.")

    AddCallback_OnClientDisconnected( RemoveCouplings )
    AddCallback_OnPlayerRespawned( InformPlayer )
    if( highlight ){
        AddCallback_OnPilotBecomesTitan( RefreshPartyHighlight )
        AddCallback_OnTitanBecomesPilot( RefreshPartyHighlight )
    }

#else
    print("[BTB] BetterTeamBalance is running. FSU is not installed, chat command related features will be unavailable.")
#endif

    AddCallback_OnPlayerKilled( OnDeathBalance )
    AddCallback_OnClientConnected( HandleJoiningPlayer )
    AddCallback_OnClientDisconnected( DeletePlayTime )
    AddCallback_GameStateEnter( eGameState.Playing, Playing)
    AddCallback_GameStateEnter( eGameState.Prematch, Prematch)
    AddCallback_GameStateEnter( eGameState.Postmatch, Postmatch)
    BTBToneInit()
}


void function Playing(){
    thread BTBThread()
}

void function DeletePlayTime( entity player ){
    if (player.GetUID() in timePlayed){
        delete timePlayed[player.GetUID()]
    }
}

// Saves parties and ranks for use in the next match
void function Postmatch(){
    if (rebalancedHasOccurred == 1){
        print("[BTB] There was a mid match rebalance, the round ended with scores: " + GameRules_GetTeamScore(TEAM_IMC) + "/" + GameRules_GetTeamScore(TEAM_MILITIA) )
    }
    else {
        print("[BTB] A mid match rebalance was not triggered, the round ended with scores: " + GameRules_GetTeamScore(TEAM_IMC) + "/" + GameRules_GetTeamScore(TEAM_MILITIA) )
    }

    print("[BTB] Saving player details to convar.....")

    string ranklist = ""
    string rankvaluelist = ""
    foreach( entity player in GetPlayerArray() ){
        if (ranklist == ""){
            ranklist = player.GetUID()
            rankvaluelist = CalculatePlayerRank(player).tostring()
        }
        else{
            ranklist += "," + player.GetUID()
            rankvaluelist += "," + CalculatePlayerRank(player).tostring()
        }
    }

#if FSCC_ENABLED
    string partiesList = ""
    foreach( key, value in parties ){
        string party = ""
        foreach( string partyMember in value )
            if (party == "")
                party = partyMember
            else
                party += "-" + partyMember
        if( partiesList == "" )
            partiesList = party
        else
            partiesList += "," + party
    }

    string nemesesList = ""
    foreach( key, value in nemeses )
        if (nemesesList == "")
            nemesesList = key+"-"+value
        else
            nemesesList += "," + key+"-"+value

    SetConVarString( "party_list", partiesList )
    SetConVarString( "nemesis_list", nemesesList )
#endif

    SetConVarString( "uid_list", ranklist )
    SetConVarString( "rank_list", rankvaluelist )
    print("[BTB] DONE")
}


// Loads the player rank table and parties, and appends any newcomers that joined in the interrim
void function Prematch(){
    if (GetPlayerArray().len() > 0 && GetConVarString( "uid_list" ) != "" && teamsBuilt == 0){
        print("[BTB] Pulling player ranks and shuffling....")
        array <string> previusMatchUID = split( GetConVarString( "uid_list" ), "," )
        array <string> previusMatchRankValue = split( GetConVarString( "rank_list" ), "," )
    #if FSCC_ENABLED
        array <string> previusMatchParties = split( GetConVarString( "party_list" ), "," )
        array <string> previusMatchNemeses = split( GetConVarString( "nemesis_list" ), "," )
    #endif

        // Rebuild player skill array discarding any players no longer on the server
        float averageValue = 0
        for(int i = 0; i < previusMatchUID.len(); i++){
            float rankValue = previusMatchRankValue[i].tofloat() * RandomFloatRange( 1.0 - SHUFFLE_RANDOMNESS, 1.0 )
            lastMatchStats[previusMatchUID[i]] <- rankValue
            averageValue += rankValue

            foreach( entity player in GetPlayerArray() ){
                if ( previusMatchUID[i] == player.GetUID() ){
                    print("[BTB] Staying player: " + player.GetPlayerName() + " / " + rankValue)
                }
            }
        }

        if (lastMatchStats.len() > 2)
            lastMatchStats["average"] <- averageValue / lastMatchStats.len()

        // Add any new players who joined
        foreach( entity player in GetPlayerArray() ){
            if ( previusMatchUID.find( player.GetUID() ) == -1 ){
                float toneKD = BTBGetToneKD(player)
                if( toneKD == 0.0 )
                    print("[BTB] Joining player: " + player.GetPlayerName() )
                else{
                    lastMatchStats[player.GetUID()] <- toneKD * lastMatchStats["average"]
                    print("[BTB] Joining player: " + player.GetPlayerName() + " / " + lastMatchStats[player.GetUID()] + " (ToneAPI estimate)" )
                }
            }
        }

    #if FSCC_ENABLED
        // Rebuild parties
        foreach( entity player in GetPlayerArray() ){
            foreach( string party in previusMatchParties){
                if( split( party, "-")[0] == player.GetPlayerName() ){
                    string members = ""
                    parties[player.GetPlayerName()] <- []
                    foreach( partyMember in split( party, "-") )
                        foreach( p in GetPlayerArray() )
                            if( p.GetPlayerName() == partyMember ){
                                if( members == "" )
                                    members = p.GetPlayerName()
                                else
                                    members += ", " + p.GetPlayerName()
                                parties[player.GetPlayerName()].append( p.GetPlayerName() )
                            }
                    if( parties[player.GetPlayerName()].len() > 1 )
                        print( "[BTB] Staying party: " + members )
                    else
                        delete parties[player.GetPlayerName()]
                }
            }

            // Rebuild nemeses
            foreach( string nemesisPair in previusMatchNemeses){
                if( split( nemesisPair, "-")[0] == player.GetPlayerName() ){
                    foreach( p in GetPlayerArray() )
                        if( p.GetPlayerName() == split( nemesisPair, "-")[1] ){
                            nemeses[player.GetPlayerName()] <- p.GetPlayerName()
                            print( "[BTB] Staying nemesis pair: " + player.GetPlayerName() + " and " + p.GetPlayerName() )
                        }
                }
            }
        }
    #endif

        if (shuffle == 1)
            ExecuteStatsBalance()
    }
    else if( abs(GetPlayerArrayOfTeam(TEAM_IMC).len()-GetPlayerArrayOfTeam(TEAM_MILITIA).len()) > differenceMax ){
        waitedTime = waitTime
    }
    teamsBuilt = 1
}

// void function GetKDFromToneAPI( entity player ){
//     https://tone.sleepycat.date/v1/client/players/{playerId}
//     NSHttpRequest(request, responseCapture, onFailure)
// }

// Check if the match is close to ending
bool function IsMatchEnding(){
    int scoreLimit = ( GameMode_GetScoreLimit( "aitdm" )*0.8 ).tointeger()
    int timeLeft = GameTime_TimeLeftSeconds()

    int scoreImc = GameRules_GetTeamScore(TEAM_IMC)
    int scoreMil = GameRules_GetTeamScore(TEAM_MILITIA)

    if( scoreImc > scoreLimit || scoreMil > scoreLimit || timeLeft < 180 )
        return true

    return false
}

// Calculate a players ranking score
float function CalculatePlayerRank( entity player ){

    // If match is still starting, use korates from previous match if available
    if( matchElapsed < grace ){
        if (player.GetUID() in lastMatchStats)
            return lastMatchStats[player.GetUID()]
        else
            return lastMatchStats["average"]
    }

    float deaths = player.GetPlayerGameStat(PGS_DEATHS).tofloat()
    float kills = player.GetPlayerGameStat(PGS_KILLS).tofloat()
    float objective = 0.0
    float time = 1.0
    if( player.GetUID() in timePlayed )
        time = timePlayed[player.GetUID()].tofloat() / 6.0
    float korate
    float deathrate

    if (GAMETYPE == "aitdm")
        kills = player.GetPlayerGameStat(PGS_ASSAULT_SCORE).tofloat() / 5
    if (GAMETYPE == "cp"){
        objective = player.GetPlayerGameStat(PGS_ASSAULT_SCORE).tofloat() / 200
        objective += player.GetPlayerGameStat(PGS_DEFENSE_SCORE).tofloat() / 300
        kills *= 0.75
    }
    if (GAMETYPE == "fw"){
        objective = player.GetPlayerGameStat(PGS_DEFENSE_SCORE).tofloat() / 200
        objective += player.GetPlayerGameStat(PGS_ASSAULT_SCORE).tofloat() / 1500
        kills *= 0.75
    }
    if (GAMETYPE == "ttdm" || GAMETYPE == "lts"){
        objective = player.GetPlayerGameStat(PGS_ASSAULT_SCORE).tofloat() / 10000
        kills *= 0.25
    }
    if (GAMETYPE == "at"){
        objective = player.GetPlayerGameStat(PGS_ASSAULT_SCORE).tofloat() / 75
        kills *= 0.25
    }

    if (kills + objective == 0)
        korate = 0.5 / time
    else
        korate = (kills + objective) / time

    if (deaths == 0)
        deathrate = ( 0.5 / time ) / 2
    else
        deathrate = ( deaths / time ) / 2

    // Consider previous match or ToneAPI stats depending on how long player has been playing
    float weight
    try{
        weight = timePlayed[player.GetUID()].tofloat() / 30
    }catch(exception){
        weight = 1.0
    }
    if( weight < 1.0 && player.GetUID() in lastMatchStats ){
        float rankValue = korate - deathrate
        float oldValue
        if (player.GetUID() in lastMatchStats)
            oldValue = lastMatchStats[player.GetUID()]
        else
            oldValue = lastMatchStats["average"]

        return (rankValue * weight ) + ( oldValue * ( 1.0 - weight ) )
    }

    return korate - deathrate
}

// Calculate the strength of a team
float function CalculateTeamStrength( int team ){
    float teamStrength = 0.0
    foreach(entity player in GetPlayerArrayOfTeam(team) ){
        teamStrength += CalculatePlayerRank( player )
    }
    if( GetPlayerArrayOfTeam(team).len() == GetPlayerArrayOfTeam(GetOtherTeam(team)).len()+1 )
        teamStrength -= lastMatchStats["average"]/2.2
    return teamStrength
}

// Calculate what the strength of a team would be, if the player were to be removed, and replacement added instead
float function CalculateTeamStrengtWithout( entity player, entity replacement ){
    float teamStrength = CalculatePlayerRank( replacement )
    int team = player.GetTeam()
    foreach(entity teamMember in GetPlayerArrayOfTeam( team ) ){
        if(teamMember != player)
            teamStrength += CalculatePlayerRank( teamMember )
    }
    if( GetPlayerArrayOfTeam(team).len() == GetPlayerArrayOfTeam(GetOtherTeam(team)).len()+1 )
        teamStrength -= lastMatchStats["average"]/2.2
    return teamStrength
}

// Execute best possible swap with another player to improve team balance
void function ExecuteBestPossibleSwap( entity teamMember, bool forced = false, string inform = "none" ){
    float strengthDifference = fabs(CalculateTeamStrength( TEAM_MILITIA ) - CalculateTeamStrength( TEAM_IMC ))

    // Find best possible other swap
    float lastStrengthDifference = 100
    entity opponentToSwap
    foreach( entity player in GetPlayerArrayOfTeam(GetOtherTeam(teamMember.GetTeam())) ){
        float newStrengthDifference = fabs(CalculateTeamStrengtWithout( player, teamMember ) - CalculateTeamStrengtWithout( teamMember, player ))
    #if FSCC_ENABLED
        if ( lastStrengthDifference > newStrengthDifference && IsSwapAllowed( player, teamMember ) ){
            opponentToSwap = player
            lastStrengthDifference = newStrengthDifference
        }
    #else
        if ( lastStrengthDifference > newStrengthDifference ){
            opponentToSwap = player
            lastStrengthDifference = newStrengthDifference
        }
    #endif
    }

    // Execute the swap if it meets requirements, or if it is forced
    if( strengthDifference > lastStrengthDifference && opponentToSwap != null || forced && opponentToSwap != null ){
        SetTeam( teamMember, GetOtherTeam( teamMember.GetTeam() ) )
        SetTeam( opponentToSwap, GetOtherTeam( opponentToSwap.GetTeam() ) )

        // Inform players about the reason for their switch
        if( GetGameState() == eGameState.Playing ){
            if( inform == "party" ){
            #if FSCC_ENABLED
                FSU_PrivateChatMessage( teamMember, "%FYour team has been switched to unite you with your party!")
                FSU_PrivateChatMessage( opponentToSwap, "%FYour team has been switched to allow a party to play together!")
            #else
                Chat_ServerPrivateMessage( teamMember, "Your team has been switched to unite you with your party!", false)
                Chat_ServerPrivateMessage( opponentToSwap, "%FYour team has been switched to allow a party to play together!", false)
            #endif
                NSSendPopUpMessageToPlayer( teamMember, "Your team has been switched!" )
                NSSendPopUpMessageToPlayer( opponentToSwap, "Your team has been switched!" )
            }
            if( inform == "nemesis" ){
            #if FSCC_ENABLED
                FSU_PrivateChatMessage( teamMember, "%FYour team has been switched to pit you against your nemesis!")
                FSU_PrivateChatMessage( opponentToSwap, "%FYour team has been switched to allow two nemeses to fight it out!")
            #else
                Chat_ServerPrivateMessage( teamMember, "Your team has been switched to pit you against your nemesis!", false)
                Chat_ServerPrivateMessage( opponentToSwap, "%FYour team has been switched to allow two nemeses to fight it out!", false)
            #endif
                NSSendPopUpMessageToPlayer( teamMember, "Your team has been switched!" )
                NSSendPopUpMessageToPlayer( opponentToSwap, "Your team has been switched!" )
            }
        }
    }
}

// Execute insidious mode balancing, always executes during first 80 seconds of a match
void function OnDeathBalance( entity victim, entity attacker, var damageInfo ){
    if (subtleRebalancePermitted == 1 || matchElapsed < grace ){
        float strengthDifference = fabs(CalculateTeamStrength( TEAM_MILITIA ) - CalculateTeamStrength( TEAM_IMC ))

        array <entity> deadOpposingPlayers
        foreach(entity player in GetPlayerArrayOfTeam(GetOtherTeam(victim.GetTeam())) ){
            if( !IsAlive(player) )
               deadOpposingPlayers.append(player)
        }

        float lastStrengthDifference = 100
        entity opponentToSwap
        foreach(entity player in deadOpposingPlayers){
            float newStrengthDifference = fabs(CalculateTeamStrengtWithout( player, victim ) - CalculateTeamStrengtWithout( victim, player ))
        #if FSCC_ENABLED
            if ( lastStrengthDifference > newStrengthDifference && IsSwapAllowed( victim, player ) ){
                opponentToSwap = player
                lastStrengthDifference = newStrengthDifference
            }
        #else
            if ( lastStrengthDifference > newStrengthDifference ){
                opponentToSwap = player
                lastStrengthDifference = newStrengthDifference
            }
        #endif
        }

        float swapImprovement = strengthDifference - lastStrengthDifference

        if( opponentToSwap != null && strengthDifference > lastStrengthDifference && activeLimit < swapImprovement || opponentToSwap != null && lastMatchStats["average"]/2.2 < swapImprovement && strengthDifference > lastStrengthDifference && matchElapsed < grace ){
            SetTeam( victim, GetOtherTeam( victim.GetTeam() ) )
            SetTeam( opponentToSwap, GetOtherTeam( opponentToSwap.GetTeam() ) )
            subtleRebalancePermitted = 0
            if( accumulatedStompImbalance >= 7 )
                accumulatedStompImbalance -= 7
            print("[BTB] Team balance has been improved by switching the teams of " + victim.GetPlayerName() + " and " + opponentToSwap.GetPlayerName() + ".")

            if( matchElapsed < grace ){
                foreach( player in GetPlayerArray() )
                    NSEditStatusMessageOnPlayer( player, "BTB", "Players changed, adjusting teams....", "btbstatus"  )
                #if FSCC_ENABLED
                    FSU_PrivateChatMessage( victim, "%FYour team has been switched due to team balance re-adjustment! Teams are not yet locked.")
                #else
                    Chat_ServerPrivateMessage( victim, "Your team has been switched due to team balance re-adjustment! Teams are not yet locked.", false)
                #endif
                    NSSendPopUpMessageToPlayer( victim, "Your team has been switched!" )
            }
        }
    }
    thread PlayerCountAutobalance(victim)
}

// Check if playercount balancing is needed on death, always executes during first 40 seconds of a match
void function PlayerCountAutobalance( entity victim ){
    wait 0.5
    if( IsValid(victim) && waitedTime >= waitTime && matchElapsed < grace || GetPlayerArrayOfTeam(TEAM_IMC).len() == 0 || GetPlayerArrayOfTeam(TEAM_MILITIA).len() == 0){
        if ( differenceMax == 0 || IsFFAGame() || GetPlayerArray().len() == 1 || abs(GetPlayerArrayOfTeam(TEAM_IMC).len() - GetPlayerArrayOfTeam(TEAM_MILITIA).len()) <= differenceMax || GameTime_TimeLeftSeconds() < 60 ){
            return
        }

        // Compare victims teams size
        if ( GetPlayerArrayOfTeam(victim.GetTeam()).len() < GetPlayerArrayOfTeam(GetOtherTeam(victim.GetTeam())).len() ){
            return
        }

        if (GetPlayerArray().len() > 5) {

            float currentStrengthDifference = fabs( CalculateTeamStrength( TEAM_MILITIA ) - CalculateTeamStrength( TEAM_IMC) )
            float victimTeamStrengthWithoutVictim = CalculateTeamStrength( victim.GetTeam() ) - CalculatePlayerRank( victim )
            float opposingTeamStreanthWithVictim = CalculateTeamStrength( GetOtherTeam(victim.GetTeam()) ) + CalculatePlayerRank( victim )
            float potentialStrengthDifference = fabs(opposingTeamStreanthWithVictim-victimTeamStrengthWithoutVictim)

            //Interrupt if swap would make teams worse, or if party/nemesis conditions forbid it
        #if FSCC_ENABLED
            if( !IsSwapAllowed( victim ) )
                return
        #endif
            if( potentialStrengthDifference > currentStrengthDifference && GetPlayerArrayOfTeam(TEAM_IMC).len() != 0 && GetPlayerArrayOfTeam(TEAM_MILITIA).len() != 0 )
                return
        }
        // Passed checks, balance the teams
        print("[BTB] The team of " + victim.GetPlayerName() + " has been switched")
        SetTeam( victim, GetOtherTeam( victim.GetTeam() ) )
    #if FSCC_ENABLED
        FSU_PrivateChatMessage( victim, "%FYour team has been switched to equalize team sizes!")
    #else
        Chat_ServerPrivateMessage( victim, "Your team has been switched to equalize team sizes!", false)
    #endif
        NSSendPopUpMessageToPlayer( victim, "Your team has been switched!" )
        waitedTime = 1
    }
}


#if FSCC_ENABLED

void function RemoveCouplings( entity player ){
    string name = player.GetPlayerName()
    if( IsPlayerInParty(name) )
        DisbandLeaveParty( name )
    RemoveNemesis( name )
}

entity function PlayerFromName( string playerName ){
    foreach( player in GetPlayerArray() ){
        if( playerName == player.GetPlayerName() )
            return player
    }
    return null
}

void function RefreshPartyHighlight( entity player, entity titan ){
    if( IsPlayerInParty( player.GetPlayerName() ) && highlight ){
        Highlight_SetFriendlyHighlight( player, "hunted_friendly" )
        if ( player.GetPetTitan() != null )
            Highlight_SetFriendlyHighlight( player.GetPetTitan(), "hunted_friendly" )
    }
}

void function InformPlayer( entity player ){
    if( IsPlayerInParty(player.GetPlayerName()) && highlight )
        Highlight_SetFriendlyHighlight( player, "hunted_friendly" )

    if( RandomIntRange( 0, 6 ) != 6 || matchElapsed > 12 )
        return

    if( GetConVarBool( "btb_nemesis" ) && GetConVarBool( "btb_party" ) )
        NSSendInfoMessageToPlayer(player, FSU_FormatString( "Playing with a friend? Use the %Pparty and %Pnemesis commands to stay on the same/opposite team!") )
    else if( GetConVarBool( "btb_nemesis" ) )
        NSSendInfoMessageToPlayer(player, FSU_FormatString( "Playing with a friend? Use the %Pnemesis command to stay on the opposite team!") )
    else if( GetConVarBool( "btb_party" ) )
        NSSendInfoMessageToPlayer(player, FSU_FormatString( "Playing with a friend? Use the %Pparty command to stay on the same team!") )
}

// Leave party and nemesis pair on disconnect
void function RemoveNemesis( string playerName ){
    if( GetNemesis( playerName ) != "" )
        if( playerName in nemeses )
            delete nemeses[playerName]
        else
            delete nemeses[GetNemesis(playerName)]
}

// Simulate assembling a full team in addition to party members, if not possible to create a balanced team, party is too strong
bool function IsPartyTooStrong( entity player, entity newMember = null ){
    float partyStrength = 0.0
    int partySize = 2
    array <float> playerStrengths
    foreach( p in GetPlayerArray() )
        if( !IsPlayerInParty( p.GetPlayerName() ) && p != newMember && p != player )
            playerStrengths.append( CalculatePlayerRank( p ) )
    playerStrengths.sort()

    if( IsPlayerInParty( player.GetPlayerName() ) ){
        partySize = GetParty( player.GetPlayerName() ).len()

        foreach( p in GetParty( player.GetPlayerName() ) )
            partyStrength += CalculatePlayerRank( PlayerFromName(p) )

        if( newMember != null ){
            partyStrength += CalculatePlayerRank( newMember )
            partySize += 1
        }
    }
    else{
        partyStrength = CalculatePlayerRank( player ) + CalculatePlayerRank( newMember )
    }

    for(int i = 0; i < (playerStrengths.len()/2)-partySize ; i++)
        partyStrength += playerStrengths[i]

    if( partyStrength > (lastMatchStats["average"]*(playerStrengths.len().tofloat()*0.475)))
        return true
    return false
}

// Check if one or two players are legal to swap in terms of friend/enemy conditions
bool function IsSwapAllowed( entity player, entity opponentToSwap = null ){
    // When checking a swap between two players, make sure the other one is allowed to be swapped, too
    if( opponentToSwap != null && !IsSwapAllowed( opponentToSwap ) )
        return false
    string playerName = player.GetPlayerName()
    string opponentName
    if( opponentToSwap != null )
        opponentName = opponentToSwap.GetPlayerName()

    if( IsPlayerInParty( playerName ) ){
        string leaderName = GetParty( playerName )[0]
        int playersTeam = player.GetTeam()
        int membersOnTeam = 0
        int membersOnOther = 0
        int otherPartiesMembersOnTeam = 0
        int otherPartiesMembersOnOther = 0

        foreach( leader, memberArray in parties ){
            if( leader == leaderName ){
                foreach( member in memberArray ){
                    if( member == opponentName ) // If the other player is a party member, then swap is pointless, and hence illegal
                        return false
                    if( PlayerFromName(member).GetTeam() == playersTeam )
                        membersOnTeam++
                    else
                        membersOnOther++
                }
            }
            else{
                foreach( member in memberArray ){
                    if( PlayerFromName(member).GetTeam() == playersTeam )
                        otherPartiesMembersOnTeam++
                    else
                        otherPartiesMembersOnOther++
                }
            }
        }

        // If most party members are on the current team, then the swap is illegal, unless there is already too many members of another party
        if( membersOnTeam - otherPartiesMembersOnTeam > membersOnOther - otherPartiesMembersOnOther )
            return false
    }

    // Illegal if swapping either would put them with their nemesis (but legal if these two are each other's nemeses)
    if( GetNemesis( playerName ) != "" && GetNemesis( playerName ) != opponentName || GetNemesis( opponentName ) != "" && GetNemesis( opponentName ) != playerName )
        return false
    return true
}

bool function IsPlayerInParty( string playerName ){
    foreach( key, array <string> value in parties )
        foreach( partyMember in value )
            if( partyMember == playerName )
                return true
    return false
}

// Return the party of a player as array
array <string> function GetParty( string playerName ){
    foreach( key, array <string> value in parties )
        foreach( string partyMember in value )
            if( partyMember == playerName )
                return parties[key]
    return []
}

// Returns the nemesis of a player, if they have one
string function GetNemesis( string playerName ){
    foreach( key, value in nemeses){
        if( playerName == key)
            return value
        if( playerName == value )
            return key
    }
    return ""
}

void function DisplayPartyStatus( entity player ){
    if( IsPlayerInParty( player.GetPlayerName() ) ){
        string members = ""
        foreach( memberName in GetParty( player.GetPlayerName() ) )
            if( members == "" )
                members = memberName + "'s party: %H" + memberName
            else
                members += "%T, %H" + memberName
        FSU_PrivateChatMessage(player, members)
        FSU_PrivateChatMessage(player, "Use %H%Pparty disband %Tto leave the party, or disband it, if you are the leader.")
        return
    }
    else{
        FSU_PrivateChatMessage(player, "%EYou are not a member of a party!")
        FSU_PrivateChatMessage(player, "Use %H%Pparty partial/full-name> %Tto invite someone to form a party with you.")
        return
    }
}

void function AddPlayerToParty( string playerName, string inviterName ){
    entity player = PlayerFromName( playerName )
    entity inviter = PlayerFromName( inviterName )

    if( IsPartyTooStrong( inviter, player ) ){
        FSU_PrivateChatMessage(inviter, "%H" + playerName + " %Ewas unable to accept your invite, the resulting party would be too strong!")
        FSU_PrivateChatMessage(inviter, "You can try again later, if the players on the server, or their stats, change.")
        FSU_PrivateChatMessage(player, "%EFailed to accept party invite from %H" + inviterName + "%E, the resulting party would be too strong!" )
        FSU_PrivateChatMessage(player, "You can try again later, if the players on the server, or their stats, change.")
        return
    }

    if( inviterName in parties ){
        foreach( memberName in parties[inviterName] ){
            entity p = PlayerFromName( memberName )
            FSU_PrivateChatMessage(p, "%H" + playerName + "%T has joined the party!.")
            NSSendLargeMessageToPlayer( p, "New Party Member!", playerName + " has joined the party!", 8, "rui/callsigns/callsign_105_col")
            EmitSoundOnEntityOnlyToPlayer( p, p, "UI_CTF_3P_TeamGrabFlag" )
            DisplayPartyStatus( p )

        }
        parties[inviterName].append( playerName )
    }
    else{
        parties[inviterName] <- [ inviterName, playerName ]
        NSSendLargeMessageToPlayer( inviter, "New Party Member!", playerName + " has joined the party!", 8, "rui/callsigns/callsign_105_col")
        EmitSoundOnEntityOnlyToPlayer( inviter, inviter, "UI_CTF_3P_TeamGrabFlag" )
        if( highlight )
            Highlight_SetFriendlyHighlight( inviter, "hunted_friendly" )
    }

    // Undo nemeses
    if( GetNemesis( playerName ) == inviterName )
        if( playerName in nemeses )
            delete nemeses[playerName]
        else
            delete nemeses[GetNemesis( playerName )]

    NSSendLargeMessageToPlayer( player, "You Joined the Party!", "You accepted " + inviterName + "'s invitation to their party!", 8, "rui/callsigns/callsign_105_col")
    EmitSoundOnEntityOnlyToPlayer( player, player, "UI_CTF_3P_TeamGrabFlag" )

    FSU_PrivateChatMessage( player, "%SYou have accepted the party invite from %H" + inviterName + "%S!" )
    DisplayPartyStatus( player )
    FSU_PrivateChatMessage( inviter, "%H" + playerName + " %Shas accepted your party invite!" )
    if( highlight )
        Highlight_SetFriendlyHighlight( player, "hunted_friendly" )
    delete partyInvites[playerName]
    UniteParties()

    print( "[BTB] " + playerName + " has joined " + inviterName + "'s party" )
}

void function DisbandLeaveParty( string playerName ){
    if( playerName in parties || GetParty( playerName ).len() == 2 ){
        array <string> party = GetParty( playerName )
        foreach( name in party ){
            entity p = PlayerFromName( name )
            if( p == null )
                continue
            FSU_PrivateChatMessage( p, "%H" + playerName + "'s %Eparty, which you were in, has been disbanded!")
            NSSendLargeMessageToPlayer( p, "Party Disbanded!", playerName + "'s party, which you were in, has been disbanded!", 8, "rui/callsigns/callsign_34_col")
            EmitSoundOnEntityOnlyToPlayer( p, p, "UI_CTF_3P_EnemyGrabFlag" )
            if( highlight )
                Highlight_ClearFriendlyHighlight( p )
        }

        print( "[BTB] " + party[0] + "'s party disbanded" )
        delete parties[party[0]]

        return
    }
    else{
        print( "[BTB] " + playerName + " left " + GetParty( playerName )[0] + "'s party" )
        foreach( name in GetParty( playerName ) ){
            entity p = PlayerFromName( name )
            entity player = PlayerFromName( playerName )
            if( p != player && p != null ){
                FSU_PrivateChatMessage( p, "%H" + playerName + "%E has left the party!")
                NSSendLargeMessageToPlayer( p, "Party Member Left!", playerName + " has left the party!", 8, "rui/callsigns/callsign_34_col")
                EmitSoundOnEntityOnlyToPlayer( p, p, "UI_CTF_3P_EnemyGrabFlag" )
            }
            else if( p != null && p == player && GetParty( playerName ).find( playerName ) > -1){
                FSU_PrivateChatMessage(player, "%SYou left " + GetParty( playerName )[0] + "'s party!")
                GetParty( playerName ).remove( GetParty( playerName ).find( playerName ) )
                if( highlight )
                    Highlight_ClearFriendlyHighlight( p )
            }
        }
        return
    }
}

// Unite parties in the most efficient way possible
void function UniteParties(){
    foreach( string leaderName, array <string> value in parties ){
        entity leader = PlayerFromName( leaderName )
        foreach( string partyMemberName in value ){
            entity partyMember = PlayerFromName( partyMemberName )
            if( partyMember == null || leader.GetTeam() == partyMember.GetTeam() )
                continue
            if( leader.GetTeam() != partyMember.GetTeam() && 0 != abs(GetPlayerArrayOfTeam(TEAM_IMC).len()-GetPlayerArrayOfTeam(TEAM_MILITIA).len()) ){
                if( GetPlayerArrayOfTeam(leader.GetTeam()).len() > GetPlayerArrayOfTeam(partyMember.GetTeam()).len() ){
                    SetTeam( leader, partyMember.GetTeam() )
                    FSU_PrivateChatMessage( leader, "%FYour team has been switched to unite you with your party!")
                    NSSendPopUpMessageToPlayer( leader, "Your team has been switched!" )
                }
                else{
                    SetTeam( partyMember, leader.GetTeam() )
                    FSU_PrivateChatMessage( partyMember, "%FYour team has been switched to unite you with your party!")
                    NSSendPopUpMessageToPlayer( partyMember, "Your team has been switched!" )
                }
            }
            if( leader.GetTeam() != partyMember.GetTeam() )
                ExecuteBestPossibleSwap( leader, false, "party" )
            if( leader.GetTeam() != partyMember.GetTeam() )
                ExecuteBestPossibleSwap( partyMember, false, "party" )
            if( leader.GetTeam() != partyMember.GetTeam() && fabs(CalculatePlayerRank(leader)-lastMatchStats["average"]) < fabs(CalculatePlayerRank(partyMember)-lastMatchStats["average"]) )
                ExecuteBestPossibleSwap( leader, true, "party" )
            else if( leader.GetTeam() != partyMember.GetTeam() )
                ExecuteBestPossibleSwap( partyMember, true, "party" )
            if( leader.GetTeam() != partyMember.GetTeam() )
                ExecuteBestPossibleSwap( leader, true, "party" )
            if( leader.GetTeam() != partyMember.GetTeam() )
                ExecuteBestPossibleSwap( partyMember, true, "party" )
            if( leader.GetTeam() != partyMember.GetTeam() )
                print("[BTB] Uh Oh, UniteParties ran, but failed to unite all party members")
        }
    }
}

// Split nemeses in the most efficient way possible
void function SplitNemeses(){
    foreach( string n1, string n2 in nemeses ){
        entity key = PlayerFromName( n1 )
        entity value = PlayerFromName( n2 )
        if( key == null || value == null || key.GetTeam() != value.GetTeam() )
            continue
        if( key.GetTeam() == value.GetTeam() && 0 != abs(GetPlayerArrayOfTeam(TEAM_IMC).len()-GetPlayerArrayOfTeam(TEAM_MILITIA).len()) ){
            if( GetPlayerArrayOfTeam(key.GetTeam()).len() > GetPlayerArrayOfTeam(GetOtherTeam(key.GetTeam())).len() ){
                SetTeam( key, GetOtherTeam(key.GetTeam()) )
                FSU_PrivateChatMessage( key, "%FYour team has been switched to pit you against your nemesis!")
                NSSendPopUpMessageToPlayer( key, "Your team has been switched!" )
            }
        }
        if( key.GetTeam() == value.GetTeam() )
            ExecuteBestPossibleSwap( key, false, "nemesis" )
        if( key.GetTeam() == value.GetTeam() )
            ExecuteBestPossibleSwap( value, false, "nemesis" )
        if( key.GetTeam() == value.GetTeam() && fabs(CalculatePlayerRank(key)-lastMatchStats["average"]) < fabs(CalculatePlayerRank(value)-lastMatchStats["average"]) )
            ExecuteBestPossibleSwap( key, true, "nemesis" )
        else if( key.GetTeam() == value.GetTeam() )
            ExecuteBestPossibleSwap( value, true, "nemesis" )
        if( key.GetTeam() == value.GetTeam() )
            ExecuteBestPossibleSwap( key, true, "nemesis" )
        if( key.GetTeam() == value.GetTeam() )
            ExecuteBestPossibleSwap( value, true, "nemesis" )
        if( key.GetTeam() == value.GetTeam() )
            print("[BTB] Uh Oh, SplitNemeses ran, but failed to split all nemesis pairs")
    }
}

void function BTB_Party ( entity player, array < string > args ){

    // Display party status
	if(args.len() == 0){
        DisplayPartyStatus( player )
        return
	}

	// Accept party invite
	if( args[0] == "accept" || args[0] == "yes" || args[0] == "y" || args[0] == "join" ){
        if( player.GetPlayerName() in partyInvites ){
            AddPlayerToParty( player.GetPlayerName(), partyInvites[player.GetPlayerName()] )
            return
        }
        else{
            FSU_PrivateChatMessage(player, "%EYou have no pending party invite!")
            return
        }
	}

    //Disband or leave a party
    if( args[0] == "disband" || args[0] == "leave" || args[0] == "exit" || args[0] == "reset" ){
        if( IsPlayerInParty( player.GetPlayerName() ) ){
            DisbandLeaveParty( player.GetPlayerName() )
            return
        }
        else{
            FSU_PrivateChatMessage(player, "%EYou are not in a party!")
            return
        }
	}

    entity target
    foreach( entity p in GetPlayerArray() ){
        if( p.GetPlayerName() == args[0] )
            target = p
    }
    if(target == null){
        foreach( entity p in GetPlayerArray() ) {
            if( p.GetPlayerName().tolower().find( args[0].tolower() ) != null ) {
                if( target != null ){
                    FSU_PrivateChatMessage(player, "%EMore than one matching player! %TWrite a bit more of their name.")
                    return
                }
                target = p
            }
        }
    }
    if(target == null){
        FSU_PrivateChatMessage( player, "%H\"" + args[0] + "\"%E couldn't be found!" )
        return
    }
    else{
        if( target == player ){
            FSU_PrivateChatMessage(player, "%EYou cannot party invite yourself!")
            return
        }
        // Check if player is allowed to invite party members
        if( IsPlayerInParty( player.GetPlayerName() ) && !( player.GetPlayerName() in parties ) ){
            FSU_PrivateChatMessage(player, "%EYou cannot send invites! %TYou are not the party leader.")
            return
        }
        // Check if target is already in party
        if( IsPlayerInParty( target.GetPlayerName() ) ){
            FSU_PrivateChatMessage( player, "%H" + target.GetPlayerName() + "%E is already in a party!" )
            return
        }
        // Check if the resulting party would bee too strong
        if( IsPartyTooStrong( player, target ) ){
            FSU_PrivateChatMessage( player, "%EParty invite failed, the resulting party would be too strong!" )
            FSU_PrivateChatMessage( player, "You can try again later, if the players on the server, or their stats, change.")
            return
        }
        // Send invite, make friends, profit :D
        if( target.GetPlayerName() in partyInvites ){
            partyInvites[target.GetPlayerName()] = player.GetPlayerName()
        }
        else{
            partyInvites[target.GetPlayerName()] <- player.GetPlayerName()
        }
        FSU_PrivateChatMessage( player, "%H" + target.GetPlayerName() + "%S has been sent a party invite!" )
        FSU_PrivateChatMessage( target, "%H" + player.GetPlayerName() + "%T has invited you to party up! Use %H%Pparty accept %T to join their party." )
        NSSendLargeMessageToPlayer( target, "Party Invite!", player.GetPlayerName() + " has invited you to party up! Use '!party accept' to join their party.", 8, "rui/callsigns/callsign_39_col")
        EmitSoundOnEntityOnlyToPlayer( target, target, "UI_CTF_3P_TeamGrabFlag" )
    }
}

// Set someone as your nemesis
void function BTB_Enemy ( entity player, array < string > args ){
    if(args.len() == 0){
        if( GetNemesis( player.GetPlayerName() ) != "" )
            FSU_PrivateChatMessage( player, "%E" + GetNemesis( player.GetPlayerName() ) + "%T is your current nemesis!" )
        else
            FSU_PrivateChatMessage( player, "%EYou do not have a nemesis." )
        return
    }
    if(args[0] == "peace" || args[0] == "cancel" || args[0] == "none" ){
        if( player.GetPlayerName() in nemeses ){
            FSU_PrivateChatMessage( player, "%H" + nemeses[player.GetPlayerName()] + "%S is no longer your nemesis!" )
            delete nemeses[player.GetPlayerName()]
            return
        }
    }

    entity target
    foreach( entity p in GetPlayerArray() ){
        if( p.GetPlayerName() == args[0] )
            target = p
    }
    if(target == null){
        foreach( entity p in GetPlayerArray() ) {
            if( p.GetPlayerName().tolower().find( args[0].tolower() ) != null ) {
                if( target != null ){
                    FSU_PrivateChatMessage(player, "%EMore than one matching player! %TWrite a bit more of their name.")
                    return
                }
                target = p
            }
        }
    }
    if(target == null){
        FSU_PrivateChatMessage( player, "%H\"" + args[0] + "\"%E couldn't be found!" )
        return
    }
    else{
        if( target == player ){
            FSU_PrivateChatMessage(player, "%EYou cannot be your own nemesis!")
            return
        }
        foreach( p in chosenNemesis )
            if( p == player ){
                FSU_PrivateChatMessage( player, "%EYou have already chosen a nemesis during this match." )
                return
            }

        // Make sure player isnt trying to make a party member their nemesis
        if( IsPlayerInParty( player.GetPlayerName() ) )
            foreach( name in GetParty( player.GetPlayerName() ) )
                if( PlayerFromName( name ) == target ){
                    FSU_PrivateChatMessage( player, "%EA member of your party cannot be your nemesis." )
                    return
                }

        // Make nemeses
        if( player.GetPlayerName() in nemeses ){
            FSU_PrivateChatMessage( player, "%EYou already had a nemesis! %H" + target.GetPlayerName() + "%S is now your nemesis instead!" )
            FSU_PrivateChatMessage( player, "%TYou can only choose one nemesis at a time." )
            nemeses[player.GetPlayerName()] = target.GetPlayerName()
        }
        else{
            nemeses[player.GetPlayerName()] <- target.GetPlayerName()
            FSU_PrivateChatMessage( player, "%E" + target.GetPlayerName() + "%S is now your nemesis!" )
        }
        FSU_PrivateChatMessage( target, "%H" + player.GetPlayerName() + "%E has made you their nemesis!" )
        NSSendLargeMessageToPlayer( target, "You Have a Nemesis!", player.GetPlayerName() + " has made you their nemesis!", 8, "rui/callsigns/callsign_53_col")
        NSSendLargeMessageToPlayer( player, "You Have a Nemesis!", "You have marked " + player.GetPlayerName() + " as your nemesis!", 8, "rui/callsigns/callsign_53_col")
        EmitSoundOnEntityOnlyToPlayer( player, player, "pilot_collectible_pickup" )
        EmitSoundOnEntityOnlyToPlayer( target, target, "pilot_collectible_pickup" )
        SplitNemeses()
        chosenNemesis.append( player )
    }
}

// Count votes for !balance, and activate, when enough have voted for it
void function BTB_BalanceVote ( entity player, array < string > args ){
    if ( GetMapName() == "mp_lobby" ){

        FSU_PrivateChatMessage( player, "%ECan't balance in lobby")
        return
    }

    if ( GetGameState() != eGameState.Playing ){
        FSU_PrivateChatMessage( player, "%ECan't balance in this game state")
        return
    }

    if ( rebalancedHasOccurred + 180 > GetUnixTimestamp() ){
        FSU_PrivateChatMessage( player, "%ETeams have been balanced to recently! Please wait a few minutes before rebalancing again.")
        return
    }

    if ( GetPlayerArray().len() < 3 ){
        FSU_PrivateChatMessage( player, "%ENot enough players for a good rebalance!")
        return
    }

    if ( matchElapsed < 14 ){
        FSU_PrivateChatMessage( player, "%EIt is too soon for a team rebalance!")
        return
    }

    if ( playersWantingToBalance.find( player ) != -1 ){
        FSU_PrivateChatMessage( player, "%EYou have already voted!")
        return
    }

    int required_players = int ( GetPlayerArray().len() * voteFraction )
    if ( required_players == 0 ){
        required_players = 1
    }

    if ( playersWantingToBalance.len() == 0 ){
        thread VoteHUD()
    }

    playersWantingToBalance.append( player )
    FSU_PrivateChatMessage( player, "%SYou voted to rebalance teams!")

    if ( playersWantingToBalance.len() >= required_players ){
        print("[BTB] Team skill balancing triggered by vote")
        ExecuteStatsBalance()
        rebalancedHasOccurred = GetUnixTimestamp()
    }
}

void function VoteHUD(){
    int timer = GetConVarInt("btb_vote_duration")
    int nextUpdate = timer
    int lastVotes = playersWantingToBalance.len()

    // Announce the starting of a vote
    if(GetConVarBool("FSV_ENABLE_RUI")){
        foreach ( entity player in GetPlayerArray() ){
            NSSendAnnouncementMessageToPlayer( player, "TEAM REBALANCE VOTE STARTED", "Use '!tb' in chat to add your vote.", <1,0,0>, 0, 1 )
        }
        wait 1
        foreach ( entity player in GetPlayerArray() ){
            NSCreateStatusMessageOnPlayer( player, "", playersWantingToBalance.len() + "/" + int(GetPlayerArray().len()*voteFraction) + " have voted to rebalance teams", "teambalance"  )
        }
    }
    if(GetConVarBool("FSV_ENABLE_CHATUI")){
        FSU_ChatBroadcast( "%H"+FSV_TimerToMinutesAndSeconds(timer)+"%N - " + "A vote to rebalance teams has begun! Use %H%Ptb %Nto vote. %T" + int(GetPlayerArray().len()*voteFraction) + " votes will be needed." )
    }

    while(timer > 0 && playersWantingToBalance.len() < int(GetPlayerArray().len()*voteFraction)){
        if(timer == nextUpdate){
            int minutes = int(floor(timer / 60))
            string seconds = string(timer - (minutes * 60))
            if (timer - (minutes * 60) < 10){
                seconds = "0"+seconds
            }
            if(GetConVarBool("FSV_ENABLE_RUI")){
                foreach (entity player in GetPlayerArray()) {
                    NSEditStatusMessageOnPlayer( player, FSV_TimerToMinutesAndSeconds(timer), playersWantingToBalance.len() + "/" + int(GetPlayerArray().len()*voteFraction) + " have voted to rebalance teams", "teambalance" )
                }
            }
            if(GetConVarBool("FSV_ENABLE_CHATUI") && playersWantingToBalance.len() != lastVotes){
                FSU_ChatBroadcast( "%H"+FSV_TimerToMinutesAndSeconds(timer)+"%H - " + playersWantingToBalance.len() + "/" + int(GetPlayerArray().len()*voteFraction) + "%N have voted to rebalance teams and scores. %T Use %H%Ptb %Tto vote." )
                lastVotes = playersWantingToBalance.len()
            }
            nextUpdate -= 5
        }
        timer -= 1
        wait 1
    }

    if(GetConVarBool("FSV_ENABLE_RUI")){
        if(playersWantingToBalance.len() >= int(GetPlayerArray().len()*voteFraction)){
            foreach ( entity player in GetPlayerArray() ){
                NSSendAnnouncementMessageToPlayer( player, "TEAMS HAVE BEEN REBALANCED", "Teams and scores have been rebalanced by vote!", <1,0,0>, 0, 1 )
            }
            wait 0.1
            foreach ( entity player in GetPlayerArray() ){
                NSEditStatusMessageOnPlayer( player, "PASS", "Teams and have been rebalanced!", "teambalance" )
            }
        }
        else{
            foreach (entity player in GetPlayerArray()) {
                NSEditStatusMessageOnPlayer( player, "FAIL", "Not enough votes to rebalance teams!", "teambalance" )
            }
        }
    }
    if (GetConVarBool("FSV_ENABLE_CHATUI") ){
        if(playersWantingToBalance.len() >= int(GetPlayerArray().len()*voteFraction)){
            FSU_ChatBroadcast("Final vote received! %STeams have been rebalanced!")
        }
        else{
            FSU_ChatBroadcast("%EThe vote to rebalance teams has failed! %NNot enough votes.")
        }
    }

    playersWantingToBalance.clear()
    wait 10
    foreach ( entity player in GetPlayerArray() ){
        NSDeleteStatusMessageOnPlayer( player, "teambalance" )
    }
}

#endif

// Execute balanced team rebuild
void function ExecuteStatsBalance(){

    // First make sure playercounts are leveled
    while( abs(GetPlayerArrayOfTeam(TEAM_IMC).len() - GetPlayerArrayOfTeam(TEAM_MILITIA).len()) > 1 ){
        if( GetPlayerArrayOfTeam(TEAM_IMC).len() > GetPlayerArrayOfTeam(TEAM_MILITIA).len() )
            SetTeam( GetPlayerArrayOfTeam( TEAM_IMC )[0], TEAM_MILITIA )
        else
            SetTeam( GetPlayerArrayOfTeam( TEAM_MILITIA )[0], TEAM_IMC )
    }

    subtleRebalancePermitted = 0
    float currentStrengthDifference = fabs( CalculateTeamStrength(TEAM_IMC) - CalculateTeamStrength(TEAM_MILITIA) )
    float improvement = 1
    int pass = 0

    print( "[BTB] Initial team strength difference: " + currentStrengthDifference )

    // Compare every player against every other player, swapping teams whenever it results in improved balance
    while( pass < 6 && improvement != 0){
        pass++

        foreach(player in GetPlayerArray())
            ExecuteBestPossibleSwap( player )

        improvement = currentStrengthDifference - (fabs( CalculateTeamStrength(TEAM_IMC) - CalculateTeamStrength(TEAM_MILITIA) ))

        currentStrengthDifference = fabs( CalculateTeamStrength(TEAM_IMC) - CalculateTeamStrength(TEAM_MILITIA) )

        print( "[BTB] PASS " + pass + " - Team strength difference improved by " + improvement + " to: " + currentStrengthDifference )
    }

    print( "[BTB] No further improvement possible. Achieved a team strength difference of: " + currentStrengthDifference)
    // Initial team build complete

#if FSCC_ENABLED
    // Double check that parties have stayed together and nemeses apart
    SplitNemeses()
    UniteParties()
    float afterFriendEnemy = fabs( CalculateTeamStrength(TEAM_IMC) - CalculateTeamStrength(TEAM_MILITIA) )
    if( currentStrengthDifference != afterFriendEnemy )
        print( "[BTB] Uh oh, parties had to be united and nemeses split, final strength difference is: " + afterFriendEnemy)
#endif

    //Redistribute scores
    if ( GetGameState() == eGameState.Playing ){
        if (GAMETYPE == "tdm" || GAMETYPE == "ps" || GAMETYPE == "aitdm" || GAMETYPE == "ttdm" || GAMETYPE == "at"){
            AddTeamScore( TEAM_IMC, -GameRules_GetTeamScore(TEAM_IMC))
            AddTeamScore( TEAM_MILITIA, -GameRules_GetTeamScore(TEAM_MILITIA))

            // Loop through each player, adding up their scores for their teams
            foreach (entity player in GetPlayerArray()){
                if (GAMETYPE == "tdm" || GAMETYPE == "ps" || GAMETYPE == "ttdm"){
                    AddTeamScore( player.GetTeam(), player.GetPlayerGameStat(PGS_KILLS))
                }
                else if (GAMETYPE == "aitdm" || GAMETYPE == "at"){
                    AddTeamScore( player.GetTeam(), player.GetPlayerGameStat(PGS_ASSAULT_SCORE))

                    //Scale team score to account for a missing player if teams are uneven
                    int imcPlayers = GetPlayerArrayOfTeam(TEAM_IMC).len()
                    int militiaPlayers = GetPlayerArrayOfTeam(TEAM_MILITIA).len()
                    if (imcPlayers > 0 && militiaPlayers > 0){
                        if (imcPlayers > militiaPlayers){
                            AddTeamScore( TEAM_MILITIA, GameRules_GetTeamScore(TEAM_MILITIA) * (((militiaPlayers + 1) / imcPlayers) - 1 ) )
                        }
                        else if (militiaPlayers > imcPlayers){
                            AddTeamScore( TEAM_IMC, GameRules_GetTeamScore(TEAM_IMC) * (((imcPlayers + 1) / imcPlayers) - 1 ) )
                        }
                    }
                }
            }
        }
        // If not one of the supported game modes, simply level the scores, rounding down
        else {
            int totalScore = int ( 0.5 * (GameRules_GetTeamScore(TEAM_IMC) + GameRules_GetTeamScore(TEAM_MILITIA)))
            AddTeamScore( TEAM_IMC, totalScore - GameRules_GetTeamScore(TEAM_IMC))
            AddTeamScore( TEAM_MILITIA, totalScore - GameRules_GetTeamScore(TEAM_MILITIA))
        }
    }
}

void function HandleJoiningPlayer( entity player ){
    timePlayed[player.GetUID()] <- 0
    float toneKD = BTBGetToneKD( player )
    if( toneKD != 0.0 )
        lastMatchStats[player.GetPlayerName()] <- toneKD * lastMatchStats["average"]

    if (!IsFFAGame()){
        int playerTeamScore = GameRules_GetTeamScore( player.GetTeam() )
        int otherTeamScore = GameRules_GetTeamScore( GetOtherTeam(player.GetTeam()) )
        int playerTeam = GetPlayerArrayOfTeam(player.GetTeam()).len() - 1
        int otherTeam = GetPlayerArrayOfTeam(GetOtherTeam(player.GetTeam())).len()

        if (playerTeamScore >= otherTeamScore && playerTeam >= otherTeam)
            SetTeam(player, GetOtherTeam(player.GetTeam()))
        else if(playerTeam > otherTeam)
            SetTeam(player, GetOtherTeam(player.GetTeam()))

        if( GetGameState() == eGameState.Prematch ){
            NSCreateStatusMessageOnPlayer( player, "BTB", "Waiting for players....", "btbstatus"  )
            return
        }
        else if( matchElapsed < grace )
            NSCreateStatusMessageOnPlayer( player, "BTB", "Teams have been balanced", "btbstatus"  )

        if( GetGameState() == eGameState.Playing && recentBalancing ){
            if( playerTeam+1 == otherTeam )
                BalanceRecentlyJoined( player )
            thread JoiningPlayerHUD( player )
        }
    }
}

void function JoiningPlayerHUD( entity player ){
    NSCreateStatusMessageOnPlayer( player, "BTB", "Welcome! Your team may change...", "btbjoining"  )
    wait 70
    if(IsValid(player))
        NSEditStatusMessageOnPlayer( player, "BTB", "Your team is now locked!", "btbjoining"  )
    else
        return
    wait 20
    if(IsValid(player))
        NSDeleteStatusMessageOnPlayer( player, "btbjoining"  )
}

void function BalanceRecentlyJoined(entity player){
    float strengthDifference = fabs(CalculateTeamStrength( TEAM_MILITIA ) - CalculateTeamStrength( TEAM_IMC ))

    array <entity> recentPlayers
    foreach(entity p in GetPlayerArrayOfTeam(GetOtherTeam(player.GetTeam())) ){
        if( timePlayed[p.GetUID()] < 7)
            recentPlayers.append(p)
    }

    float lastStrengthDifference = 100
    entity opponentToSwap
    foreach(entity p in recentPlayers){
        float newStrengthDifference = fabs(CalculateTeamStrengtWithout( p, player ) - CalculateTeamStrengtWithout( player, p ))
    #if FSCC_ENABLED
        if ( lastStrengthDifference > newStrengthDifference && IsSwapAllowed( player, p ) ){
            opponentToSwap = p
            lastStrengthDifference = newStrengthDifference
        }
    #else
        if ( lastStrengthDifference > newStrengthDifference ){
            opponentToSwap = p
            lastStrengthDifference = newStrengthDifference
        }
    #endif
    }

    if( strengthDifference > lastStrengthDifference && opponentToSwap != null ){
        SetTeam( player, GetOtherTeam( player.GetTeam() ) )
        SetTeam( opponentToSwap, GetOtherTeam( opponentToSwap.GetTeam() ) )
        print("[BTB] " + opponentToSwap.GetPlayerName() + "'s team has been switched to better place " + player.GetPlayerName() + ".")

    #if FSCC_ENABLED
        FSU_PrivateChatMessage( opponentToSwap, "%FYour team has been switched to place a joining player onto the best team for them. Your team is not yet locked.")
    #else
        Chat_ServerPrivateMessage( opponentToSwap, "Your team has been switched to place a joining player onto the best team for them. Your team is not yet locked.", false)
    #endif
        NSSendPopUpMessageToPlayer( opponentToSwap, "Your team has been switched!" )
    }
}

// Main thread
void function BTBThread(){
    float previousStrengthDifference = 0.0
    int previousAbsoluteScoreDifference = 0

    wait 1

#if FSCC_ENABLED
    foreach( player in GetPlayerArray() ){
        if( IsPlayerInParty( player.GetPlayerName() ) )
            DisplayPartyStatus( player )
        if( GetNemesis( player.GetPlayerName() ) != "" )
            FSU_PrivateChatMessage( player, "You have a nemesis: %E" + GetNemesis( player.GetPlayerName() ) )
    }
#endif

    wait 3
    foreach( player in GetPlayerArray() ){
        NSEditStatusMessageOnPlayer( player, "BTB", "Teams have been balanced", "btbstatus"  )
    }

    wait 6
    while ( GetGameState() == eGameState.Playing ){

        if( matchElapsed == grace )
            foreach( player in GetPlayerArray() )
                NSEditStatusMessageOnPlayer( player, "BTB", "Teams are now locked", "btbstatus"  )
        else if( matchElapsed == grace+6 )
            foreach( player in GetPlayerArray() )
                NSDeleteStatusMessageOnPlayer( player, "btbstatus" )

        // Increment player time played counters
        foreach(entity player in GetPlayerArray())
            if(player.GetUID() in timePlayed )
                timePlayed[player.GetUID()] += 1
            else
                timePlayed[player.GetUID()] <- 1

        // Check for player count imbalance
        if (differenceMax != 0 && GetPlayerArray().len() > 1){
            int difference = abs(GetPlayerArrayOfTeam(TEAM_IMC).len() - GetPlayerArrayOfTeam(TEAM_MILITIA).len())

            if (difference > differenceMax)
                waitedTime += difference - differenceMax
            else{
                waitedTime = 0
            }

            // If on team is empty, move a player over immediately
            if( GetPlayerArrayOfTeam(TEAM_IMC).len() == 0 || GetPlayerArrayOfTeam(TEAM_MILITIA).len() == 0 ){
                if( IsAlive( GetPlayerArray()[0] ) )
                    GetPlayerArray()[0].Die()
                SetTeam(GetPlayerArray()[0], GetOtherTeam(GetPlayerArray()[0].GetTeam()))
            }
        }

        // Check for team skill imbalance
        if (suggestionLimit != 0 || stompLimit != 0 || activeLimit != 0){

            int imcScore = GameRules_GetTeamScore(TEAM_IMC)
            int militiaScore = GameRules_GetTeamScore(TEAM_MILITIA)
            int absoluteScoreDifference = abs( imcScore - militiaScore )

            float imcTeamStrength = CalculateTeamStrength(TEAM_IMC)
            float milTeamStrength = CalculateTeamStrength(TEAM_MILITIA)
            float strengthDifference = fabs( imcTeamStrength - milTeamStrength )

            // Calculate the relative difference of the score between teams
            if (militiaScore > imcScore)
                relativeScoreDifference = 1.0 * militiaScore / imcScore
            else
                relativeScoreDifference = 1.0 * imcScore / militiaScore


            // Determine whether the team in the lead is also the stronger team
            bool leadTeamIsStronger = false
            if( imcScore > militiaScore && imcTeamStrength > milTeamStrength || militiaScore > imcScore && milTeamStrength > imcTeamStrength)
                leadTeamIsStronger = true

            // Determine whether the leading team is snowballing
            bool isMatchSnowballing = false
            if( strengthDifference >= previousStrengthDifference || absoluteScoreDifference >= previousAbsoluteScoreDifference)
                isMatchSnowballing = true

            previousStrengthDifference = strengthDifference
            previousAbsoluteScoreDifference = absoluteScoreDifference

//             print("[BTBDEBUG] Team strength difference: " + strengthDifference)
//             print("[BTBDEBUG] Absolute score difference: " + absoluteScoreDifference)
//             print("[BTBDEBUG] Is lead team stronger: " + leadTeamIsStronger)

            //General requirement switch
            if (matchElapsed > 14 && absoluteScoreDifference > 50 && rebalancedHasOccurred == 0 && !IsMatchEnding() && GetPlayerArray().len() > 3){

            #if FSCC_ENABLED
                // Strength check parties, and auto-disband them if needed
                foreach( leader, memberArray in parties ){
                    if( IsPartyTooStrong( PlayerFromName( leader ) ) ){
                        if( leader in partyStrenghtTimer )
                            partyStrenghtTimer[leader] += 1
                        else
                            partyStrenghtTimer[leader] <- 1
                        if( partyStrenghtTimer[leader] == 12 )
                            foreach( member in memberArray )
                                FSU_PrivateChatMessage( PlayerFromName( member ), "%ETHIS PARTY IS TOO STRONG, AND IS RISKING AUTOMATIC DISBAND" )
                        if( partyStrenghtTimer[leader] > 30 ){
                            foreach( member in memberArray )
                                FSU_PrivateChatMessage( PlayerFromName( member ), "%EYOUR PARTY IS TOO STRONG, AND HAS BEEN AUTO-DIBANDED" )
                            DisbandLeaveParty( leader )
                        }
                    }
                }

                // Suggestion switch
                if ( suggestionLimit != 0 ){

                    // Accrue a value if above the treshold, decay when below
                    if ( leadTeamIsStronger && isMatchSnowballing && relativeScoreDifference > suggestionLimit && strengthDifference > suggestionLimit || leadTeamIsStronger && isMatchSnowballing && absoluteScoreDifference > suggestionLimit*100 && strengthDifference > suggestionLimit ){
                        accumulatedSuggestionImbalance += 1.0 + (absoluteScoreDifference.tofloat() / 100 )
                        print("[BTB] Accumulating suggestion imbalance/threshold: " + accumulatedSuggestionImbalance + " / " + suggestionTimer)
                    }
                    else{
                        accumulatedSuggestionImbalance -= 0.5
                        if (accumulatedSuggestionImbalance < 0){
                            accumulatedSuggestionImbalance = 0
                            suggestionTimer = 10.0
                        }
                        else
                            print("[BTB] Decaying suggestion imbalance/threshold: " + accumulatedSuggestionImbalance + " / " + suggestionTimer)
                    }

                    // Activate suggestion for rebalance when accrued enough value, set a new treshold when to suggest again
                    if (accumulatedSuggestionImbalance > suggestionTimer){
                        print("[BTB] Match is uneven, suggesting rebalance")
                        FSU_ChatBroadcast( "Looks like this match is uneven, if you'd like to rebalance the teams and their scores, use %H%Pteambalance%N.")
                        suggestionTimer += suggestionTimer * 2
                    }
                }
            #endif

                // Check for team strength imbalance
                if ( activeLimit != 0 && subtleRebalancePermitted == 0){
                    // Accrue a value if above the treshold, decay when below
                    if ( leadTeamIsStronger && isMatchSnowballing && relativeScoreDifference > activeLimit && strengthDifference > activeLimit || leadTeamIsStronger && absoluteScoreDifference > activeLimit*100 && strengthDifference > activeLimit ){
                        accumulatedActiveImbalance += 1.0 + ( absoluteScoreDifference.tofloat() / 100 )
                        print("[BTB] Accumulating active imbalance/threshold: " + accumulatedActiveImbalance + " / 12")
                    }
                    else{
                        accumulatedActiveImbalance -= 0.5
                        if (accumulatedActiveImbalance < 0)
                            accumulatedActiveImbalance = 0
                        else
                            print("[BTB] Decaying active imbalance/threshold: " + accumulatedActiveImbalance + " / 12")
                    }

                    // When enough value accrued allow insidious/active rebalancing
                    if (accumulatedActiveImbalance > 12){
                        print("[BTB] Active/Insidious rebalancing has been triggered! Looking for candidates.")
                        subtleRebalancePermitted = 1
                        accumulatedActiveImbalance = 0
                    }
                }

                // Forced rebalance switch
                if ( stompLimit != 0 ){
                    // Accrue a value if above the treshold, decay when below
                    if ( leadTeamIsStronger && isMatchSnowballing && relativeScoreDifference > stompLimit && strengthDifference > stompLimit || leadTeamIsStronger && isMatchSnowballing && absoluteScoreDifference > stompLimit*120 && strengthDifference > stompLimit ){
                        accumulatedStompImbalance += 1.0 + (absoluteScoreDifference.tofloat() / 120 )
                        print("[BTB] Accumulating stomp imbalance/threshold: " + accumulatedStompImbalance + " / 16")
                    }
                    else{
                        accumulatedStompImbalance -= 0.5
                        if (accumulatedStompImbalance < 0)
                            accumulatedStompImbalance = 0
                        else
                            print("[BTB] Decaying stomp imbalance/threshold: " + accumulatedStompImbalance + " / 16")
                    }

                    // Activate forced rebalance when accrued enough value
                    if (accumulatedStompImbalance > 16 && matchElapsed > 16){
                        print("[BTB] Match is very uneven, forcing rebalance")
                    #if FSCC_ENABLED
                        FSU_ChatBroadcast( "%EVery uneven match detected! %NTeams and scores have been automatically rebalanced.")
                    #else
                        Chat_ServerBroadcast( "\x1b[38;5;203mVery uneven match detected! \x1b[0mTeams and scores have been automatically rebalanced." )
                    #endif
                        foreach( entity player in GetPlayerArray()){
                            NSSendAnnouncementMessageToPlayer( player, "TEAMS HAVE BEEN AUTO-REBALANCED!", "Detected a very uneven match! Scores have also been leveled.", <1,0,0>, 0, 1 )
                        }
                        ExecuteStatsBalance()
                        rebalancedHasOccurred = 1
                    }
                }
            }
            else{
                if (accumulatedSuggestionImbalance > 0){
                    accumulatedSuggestionImbalance -= 0.5
                    if (accumulatedSuggestionImbalance < 0){
                        accumulatedSuggestionImbalance = 0
                        suggestionTimer = 10.0
                    }
                    else
                        print("[BTB] Decaying suggestion imbalance/threshold: " + accumulatedSuggestionImbalance + " / " + suggestionTimer)
                }
                if (accumulatedActiveImbalance > 0){
                    accumulatedActiveImbalance -= 0.5
                    if (accumulatedActiveImbalance < 0)
                        accumulatedActiveImbalance = 0
                    else
                        print("[BTB] Decaying active imbalance/threshold: " + accumulatedActiveImbalance + " / 12")
                }
                if (accumulatedStompImbalance > 0){
                    accumulatedStompImbalance -= 0.5
                    if (accumulatedStompImbalance < 0)
                        accumulatedStompImbalance = 0
                    else
                        print("[BTB] Decaying stomp imbalance/threshold: " + accumulatedStompImbalance + " / 16")
                }
            }
        }

        // Check for AFK players
        if (afkThresold != 0 && GetPlayerArray().len() > afkThresold){
            foreach (entity player in GetPlayerArray()){

                // Remove data if player has left match
                if ( !player.IsPlayer() ){
                    DeletePlayerRecords( player )
                    break
                }

            #if FSA_ENABLED
                // Ignore if player is FSU admin
                if (FSA_IsAdmin(player))
                    break
            #endif

                // Warn or kick player
                switch (GetAfkState(player)){
                    case eAntiAfkPlayerState.SUSPICIOUS:
                    #if FSCC_ENABLED
                        FSU_PrivateChatMessage( player, "%EYou will soon be kicked for being AFK! MOVE!!!")
                    #else
                        Chat_ServerPrivateMessage( player, "\x1b[38;5;203mYou will soon be kicked for being AFK! MOVE!!!", false)
                    #endif
                        NSSendPopUpMessageToPlayer( player, "YOU ARE AFK! MOVE!!!")
                        print("[BTB] AFK player has been warned")
                        break

                    case eAntiAfkPlayerState.AFK:
                        print("[BTB] AFK player kicked: " + player.GetPlayerName() + " - " + player.GetUID())
                        NSDisconnectPlayer(player, "You were disconnected due to being AFK")
                        break
                }
            }
        }
        matchElapsed += 1
        wait 10
    }
}

// FFA Fallback thread
void function BTBFallbackModeThread(){
    wait 10
    while (true){
        wait 10

        // Check for AFK players
        if (afkThresold != 0 && GetPlayerArray().len() > afkThresold){
            foreach (entity player in GetPlayerArray()){

                // Remove data if player has left match
                if ( !player.IsPlayer() ){
                    DeletePlayerRecords( player )
                    break
                }

            #if FSA_ENABLED
                // Ignore if player is FSU admin
                if (FSA_IsAdmin(player))
                    break
            #endif

                // Warn or kick player
                switch (GetAfkState(player)){
                    case eAntiAfkPlayerState.SUSPICIOUS:
                    #if FSCC_ENABLED
                        FSU_PrivateChatMessage( player, "%EYou will soon be kicked for being AFK! MOVE!!!")
                    #else
                        Chat_ServerPrivateMessage( player, "\x1b[38;5;203mYou will soon be kicked for being AFK! MOVE!!!", false)
                    #endif
                        NSSendPopUpMessageToPlayer( player, "YOU ARE AFK! MOVE!!!")
                        print("[BTB] AFK player has been warned")
                        break

                    case eAntiAfkPlayerState.AFK:
                        print("[BTB] AFK player kicked: " + player.GetPlayerName() + " - " + player.GetUID())
                        ServerCommand("kickid "+ player.GetUID())
                        break
                }
            }
        }
    }
}

int function GetAfkState( entity player ){
    float localgrace = afkTime * 1.0
    float warn = afkTime * 0.43
    if ( player in lastmoved){
        float lastmove = lastmoved[ player ]
        if (Time() > lastmove + (localgrace - warn)){

            if (Time() > lastmove + localgrace){
                return eAntiAfkPlayerState.AFK
            }
            return eAntiAfkPlayerState.SUSPICIOUS
        }
    }
    return eAntiAfkPlayerState.ACTIVE
}

void function Moved( entity player ){
    lastmoved[ player ] <- Time()
}

bool function bMoved( entity player ){
    Moved( player )
    return true
}

void function AddPlayerCallbacks( entity player ){
    AddPlayerPressedForwardCallback( player, bMoved )
    AddPlayerPressedBackCallback( player, bMoved )
    AddPlayerPressedLeftCallback( player, bMoved )
    AddPlayerPressedRightCallback( player, bMoved )
    AddPlayerMovementEventCallback( player, ePlayerMovementEvents.JUMP, Moved )
    AddPlayerMovementEventCallback( player, ePlayerMovementEvents.DODGE, Moved )
    AddPlayerMovementEventCallback( player, ePlayerMovementEvents.LEAVE_GROUND, Moved )
    AddPlayerMovementEventCallback( player, ePlayerMovementEvents.TOUCH_GROUND, Moved )
    AddPlayerMovementEventCallback( player, ePlayerMovementEvents.MANTLE, Moved )
    AddPlayerMovementEventCallback( player, ePlayerMovementEvents.BEGIN_WALLRUN, Moved )
    AddPlayerMovementEventCallback( player, ePlayerMovementEvents.END_WALLRUN, Moved )
    AddPlayerMovementEventCallback( player, ePlayerMovementEvents.BEGIN_WALLHANG, Moved )
    AddPlayerMovementEventCallback( player, ePlayerMovementEvents.END_WALLHANG, Moved )
}

void function DeletePlayerRecords( entity player ){
    if (player in lastmoved){
        delete lastmoved[ player ]
    }
}

void function BTB_Switch( entity player, array < string > args ){
    int imcPlayers = GetPlayerArrayOfTeam(TEAM_IMC).len()
    int militiaPlayers = GetPlayerArrayOfTeam(TEAM_MILITIA).len()

    if (imcPlayers < militiaPlayers){
        SetTeam( player, TEAM_IMC )
    }
    else if (militiaPlayers < imcPlayers){
        SetTeam( player, TEAM_MILITIA )
    }
    FSU_PrivateChatMessage( player, "%EYour team has been switched to whichever team had less players." )
}

void function BTB_Stats( entity player, array < string > args ){
    HttpRequest request = { ... }
    request.method = HttpRequestMethod.GET
    request.url = toneurl + "/get?player=" + player.GetUID() + "&server=v3x"

    void functionref( HttpRequestResponse ) OnSuccess = void function ( HttpRequestResponse response )
    {
        try{
            table decoded
            foreach( uid, tab in DecodeJSON(response.body) )
                decoded = expect table(tab)

            if(response.statusCode == 200 && decoded.len() != 0 ){
                string user = expect string(decoded["username"])
                int kills = expect int(decoded["kills"])
                int deaths = expect int(decoded["deaths"])
                int playtime = expect int(decoded["playtime"])
                float kd = kills / deaths
                float playtimeHours = playtime / 60.0 / 60.0
                int formattedPlaytime = playtimeHours.tointeger()
                int killstreak = expect int(decoded["killstreak"])
                FSU_PrivateChatMessage( player, "\nKills: " + kills + "\nDeaths: " + deaths + "\nPlaytime: " + formattedPlaytime + " hours\nK/D: " + kd + "\nKillstreak: " + killstreak )
                toneKDs[user] <- kd
            }else{
                FSU_PrivateChatMessage( player, "Failed to get stats, the tracker might be down. Sorry." )
                print("[BTB][Tone API] Tone API unavailable, or does not have stats for this player")
                print("[BTB][Tone API] " + response.body )
            }
        }catch(exception){
            FSU_PrivateChatMessage( player, "Failed to get stats, the tracker might be down. Sorry." )
            print("[BTB][Tone API] Failed to decode Tone API response")
            return
        }
    }

    void functionref( HttpRequestFailure ) OnFailure = void function ( HttpRequestFailure failure )
    {
        FSU_PrivateChatMessage( player, "Failed to get stats, the tracker might be down. Sorry." )
        print("[BTB][Tone API] Tone API unavailable, or does not have stats for this player")
        print("[BTB][Tone API] " + failure.errorMessage )
    }

    NSHttpRequest(request, OnSuccess, OnFailure)
}