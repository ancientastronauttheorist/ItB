GameData = {["save_version"] = 1, ["language"] = 1, ["network"] = 5, ["networkMax"] = 7, ["overflow"] = 0, ["seed"] = 2124055133, ["new_enemies"] = 0, ["new_missions"] = 0, ["new_equip"] = 0, ["difficulty"] = 1, ["new_abilities"] = 0, ["ach_info"] = {["squad"] = "Archive_A", ["trackers"] = {["Detritus_B_2"] = 0, ["Global_Challenge_Power"] = 0, ["Archive_A_1"] = 0, ["Archive_B_2"] = 0, ["Rust_A_2"] = 0, ["Rust_A_3"] = 0, ["Pinnacle_A_3"] = 0, ["Archive_B_1"] = 0, ["Pinnacle_B_3"] = 0, ["Detritus_B_1"] = 0, ["Pinnacle_B_1"] = 0, ["Global_Island_Mechs"] = 0, ["Global_Island_Building"] = 0, ["Squad_Mist_1"] = 0, ["Squad_Bomber_2"] = 0, ["Squad_Spiders_1"] = 0, ["Squad_Mist_2"] = 0, ["Squad_Heat_1"] = 0, ["Squad_Cataclysm_1"] = 0, ["Squad_Cataclysm_2"] = 0, ["Squad_Cataclysm_3"] = 0, },
},


["current"] = {["score"] = 0, ["time"] = 286228.343750, ["kills"] = 0, ["damage"] = 0, ["failures"] = 0, ["difficulty"] = 1, ["victory"] = false, ["squad"] = 0, 
["mechs"] = {"PunchMech", "TankMech", "ArtiMech", },
["colors"] = {0, 0, 0, },
["weapons"] = {"Prime_Punchmech", "", "Brute_Tankmech", "", "Ranged_Artillerymech", "", },
["pilot0"] = {["id"] = "Pilot_Detritus", ["name"] = "Sergei Chavez", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 3, ["exp"] = 2, ["level"] = 0, ["travel"] = 2, ["final"] = 0, ["starting"] = true, ["last_end"] = 2, },
["pilot1"] = {["id"] = "Pilot_Rust", ["name"] = "Peter Nguyen", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 2, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot2"] = {["id"] = "Pilot_Archive", ["name"] = "Nadia Berezin", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 3, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
},
["current_squad"] = 0, }
 

RegionData = {
["sector"] = 0, ["island"] = 3, ["secret"] = false, 
["island0"] = {["corporation"] = "Corp_Grass", ["id"] = 0, ["secured"] = false, },
["island1"] = {["corporation"] = "Corp_Desert", ["id"] = 1, ["secured"] = false, },
["island2"] = {["corporation"] = "Corp_Snow", ["id"] = 2, ["secured"] = false, },
["island3"] = {["corporation"] = "Corp_Factory", ["id"] = 3, ["secured"] = false, },

["turn"] = 0, ["iTower"] = 7, ["quest_tracker"] = 0, ["quest_id"] = 0, ["podRewards"] = {CreateEffect({pilot = "random",cores = 1,}), },


["region0"] = {["mission"] = "Mission2", ["state"] = 0, ["name"] = "The Heap", },

["region1"] = {["mission"] = "Mission5", ["state"] = 0, ["name"] = "Waste Chambers", },

["region2"] = {["mission"] = "Mission6", ["state"] = 0, ["name"] = "Venting Fields", },

["region3"] = {["mission"] = "Mission4", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 1, ["iTeamTurn"] = 1, ["iState"] = 0, ["sMission"] = "Mission4", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_MechHealth_Briefing_CEO_Acid_2", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 3, ["aiDelay"] = 0.000000, ["aiSeed"] = 1339667903, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "any12", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 3 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 79, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 121, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 3 ), ["terrain"] = 0, ["custom"] = "conveyor2.png", },
{["loc"] = Point( 1, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 1, 5 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 88, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_power1", ["people1"] = 87, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 2, 4 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 0, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 3, 0 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 0, },
{["loc"] = Point( 3, 3 ), ["terrain"] = 0, ["custom"] = "conveyor0.png", },
{["loc"] = Point( 3, 4 ), ["terrain"] = 0, ["custom"] = "conveyor0.png", },
{["loc"] = Point( 3, 5 ), ["terrain"] = 0, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 3, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 191, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 5 ), ["terrain"] = 0, ["grapple_targets"] = {2, },
},
{["loc"] = Point( 4, 6 ), ["terrain"] = 1, ["populated"] = 1, ["grappled"] = 1, ["people1"] = 209, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 3 ), ["terrain"] = 0, ["custom"] = "conveyor2.png", },
{["loc"] = Point( 5, 4 ), ["terrain"] = 0, ["custom"] = "conveyor2.png", },
{["loc"] = Point( 5, 7 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 6, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 1 ), ["terrain"] = 1, ["populated"] = 1, ["grappled"] = 1, ["people1"] = 225, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 6, 2 ), ["terrain"] = 0, ["grapple_targets"] = {0, },
},
{["loc"] = Point( 6, 3 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 6, 5 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 6, 6 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 7, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 4 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 4, },
},
["pod"] = Point(4,3), ["spawns"] = {"Jelly_Armor1", "Scorpion1", },
["spawn_ids"] = {794, 795, },
["spawn_points"] = {Point(7,3), Point(7,2), },
["zones"] = {["deployment"] = {Point( 1, 5 ), Point( 1, 4 ), Point( 1, 3 ), Point( 2, 3 ), Point( 2, 4 ), Point( 2, 5 ), Point( 3, 1 ), Point( 3, 2 ), Point( 3, 3 ), Point( 3, 4 ), Point( 3, 5 ), },
["satellite"] = {Point( 1, 4 ), Point( 2, 4 ), Point( 3, 4 ), Point( 4, 4 ), Point( 5, 4 ), Point( 5, 3 ), Point( 4, 3 ), Point( 6, 4 ), },
["enemy"] = {Point( 6, 3 ), Point( 6, 2 ), Point( 7, 2 ), Point( 7, 3 ), Point( 5, 2 ), Point( 5, 3 ), Point( 5, 4 ), Point( 6, 4 ), Point( 6, 5 ), Point( 7, 5 ), Point( 7, 6 ), },
},
["tags"] = {"generic", "any_sector", "mountain", "satellite", },


["pawn1"] = {["type"] = "PunchMech", ["name"] = "", ["id"] = 0, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Prime_Punchmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Detritus", ["name"] = "Sergei Chavez", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 3, ["exp"] = 2, ["level"] = 0, ["travel"] = 2, ["final"] = 0, ["starting"] = true, ["last_end"] = 2, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,2), ["last_location"] = Point(3,2), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 0, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn2"] = {["type"] = "TankMech", ["name"] = "", ["id"] = 1, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Brute_Tankmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Rust", ["name"] = "Peter Nguyen", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 2, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(1,4), ["last_location"] = Point(1,4), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 1, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn3"] = {["type"] = "ArtiMech", ["name"] = "", ["id"] = 2, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Ranged_Artillerymech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Archive", ["name"] = "Nadia Berezin", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 3, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,5), ["last_location"] = Point(3,5), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 2, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn4"] = {["type"] = "Scorpion1", ["name"] = "", ["id"] = 788, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScorpionAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,5), ["last_location"] = Point(4,4), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 5, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 788, ["piTarget"] = Point(4,6), ["piOrigin"] = Point(4,5), ["piQueuedShot"] = Point(4,6), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,6), },


["pawn5"] = {["type"] = "Scorpion1", ["name"] = "", ["id"] = 789, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScorpionAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["bAcid"] = true, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,2), ["last_location"] = Point(6,3), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 5, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 789, ["piTarget"] = Point(6,1), ["piOrigin"] = Point(6,2), ["piQueuedShot"] = Point(6,1), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(6,1), },


["pawn6"] = {["type"] = "Hornet1", ["name"] = "", ["id"] = 790, ["mech"] = false, ["offset"] = 0, ["primary"] = "HornetAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(1,3), ["last_location"] = Point(1,2), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 5, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 790, ["piTarget"] = Point(1,2), ["piOrigin"] = Point(1,3), ["piQueuedShot"] = Point(1,2), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(1,2), },
["pawn_count"] = 6, ["blocked_points"] = {Point(1,3), Point(3,3), Point(3,4), Point(5,3), Point(5,4), Point(6,3), Point(6,6), },
["blocked_type"] = {2, 2, 2, 2, 2, 2, 2, },
},


},
["state"] = 1, ["name"] = "Reprocessing", },

["region4"] = {["mission"] = "Mission3", ["state"] = 0, ["name"] = "Disposal Site C", },

["region5"] = {["mission"] = "Mission7", ["state"] = 0, ["name"] = "Disposal Vault", },

["region6"] = {["mission"] = "Mission1", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission1", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Teleporter_Briefing_CEO_Acid_3", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 1923731333, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "any34", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 1, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 76, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 85, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 66, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 105, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 4 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_bar1", ["people1"] = 74, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 204, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 3, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 216, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 174, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 4, 3 ), ["terrain"] = 3, },
{["loc"] = Point( 4, 4 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 3 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 4 ), ["terrain"] = 3, },
},
["teleports"] = {Point( 1, 3 ), Point( 5, 6 ), Point( 4, 1 ), Point( 1, 5 ), },
["tele_history"] = {-1, -1, -1, -1, },
["spawns"] = {"Firefly1", "Hornet1", "Jelly_Armor1", },
["spawn_ids"] = {791, 792, 793, },
["spawn_points"] = {Point(6,2), Point(5,4), Point(6,4), },
["zones"] = {["satellite"] = {Point( 4, 6 ), Point( 5, 6 ), Point( 5, 5 ), Point( 5, 4 ), Point( 5, 3 ), Point( 5, 2 ), Point( 4, 1 ), Point( 5, 1 ), },
},
["tags"] = {"generic", "any_sector", "water", "satellite", },
["pawn_count"] = 0, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Containment Zone D", },

["region7"] = {["mission"] = "", ["state"] = 2, ["name"] = "Corporate HQ", ["objectives"] = {},
},
["iBattleRegion"] = 3, }
 

GAME = { 
["WeaponDeck"] = { 
[1] = "Prime_Lightning", 
[2] = "Prime_Lasermech", 
[3] = "Prime_ShieldBash", 
[4] = "Prime_Rockmech", 
[5] = "Prime_RightHook", 
[6] = "Prime_RocketPunch", 
[7] = "Prime_Shift", 
[8] = "Prime_Flamethrower", 
[9] = "Prime_Areablast", 
[10] = "Prime_Spear", 
[11] = "Prime_Leap", 
[12] = "Prime_SpinFist", 
[13] = "Prime_Sword", 
[14] = "Prime_Smash", 
[15] = "Brute_Jetmech", 
[16] = "Brute_Mirrorshot", 
[17] = "Brute_PhaseShot", 
[18] = "Brute_Grapple", 
[19] = "Brute_Shrapnel", 
[20] = "Brute_Sniper", 
[21] = "Brute_Shockblast", 
[22] = "Brute_Beetle", 
[23] = "Brute_Unstable", 
[24] = "Brute_Heavyrocket", 
[25] = "Brute_Splitshot", 
[26] = "Brute_Bombrun", 
[27] = "Brute_Sonic", 
[28] = "Ranged_Rockthrow", 
[29] = "Ranged_Defensestrike", 
[30] = "Ranged_Rocket", 
[31] = "Ranged_Ignite", 
[32] = "Ranged_ScatterShot", 
[33] = "Ranged_BackShot", 
[34] = "Ranged_Ice", 
[35] = "Ranged_SmokeBlast", 
[36] = "Ranged_Fireball", 
[37] = "Ranged_RainingVolley", 
[38] = "Ranged_Wide", 
[39] = "Ranged_Dual", 
[40] = "Science_Pullmech", 
[41] = "Science_Gravwell", 
[42] = "Science_Swap", 
[43] = "Science_Repulse", 
[44] = "Science_AcidShot", 
[45] = "Science_Confuse", 
[46] = "Science_SmokeDefense", 
[47] = "Science_FreezeBeam", 
[48] = "Science_LocalShield", 
[49] = "Science_PushBeam", 
[50] = "Support_Boosters", 
[51] = "Support_Smoke", 
[52] = "Support_Refrigerate", 
[53] = "Support_Destruct", 
[54] = "DeploySkill_ShieldTank", 
[55] = "DeploySkill_Tank", 
[56] = "DeploySkill_AcidTank", 
[57] = "DeploySkill_PullTank", 
[58] = "Support_Force", 
[59] = "Support_SmokeDrop", 
[60] = "Support_Repair", 
[61] = "Support_Missiles", 
[62] = "Support_Wind", 
[63] = "Passive_FlameImmune", 
[64] = "Passive_Electric", 
[65] = "Passive_Leech", 
[66] = "Passive_MassRepair", 
[67] = "Passive_Defenses", 
[68] = "Passive_Burrows", 
[69] = "Passive_AutoShields", 
[70] = "Passive_Psions", 
[71] = "Passive_Boosters", 
[72] = "Passive_Medical", 
[73] = "Passive_FriendlyFire", 
[74] = "Passive_ForceAmp", 
[75] = "Passive_CritDefense" 
}, 
["PodWeaponDeck"] = { 
[1] = "Prime_Areablast", 
[2] = "Prime_Spear", 
[3] = "Prime_Leap", 
[4] = "Prime_SpinFist", 
[5] = "Prime_Sword", 
[6] = "Prime_Smash", 
[7] = "Brute_Grapple", 
[8] = "Brute_Sniper", 
[9] = "Brute_Shockblast", 
[10] = "Brute_Beetle", 
[11] = "Brute_Heavyrocket", 
[12] = "Brute_Bombrun", 
[13] = "Brute_Sonic", 
[14] = "Ranged_Ice", 
[15] = "Ranged_SmokeBlast", 
[16] = "Ranged_Fireball", 
[17] = "Ranged_RainingVolley", 
[18] = "Ranged_Dual", 
[19] = "Science_SmokeDefense", 
[20] = "Science_FreezeBeam", 
[21] = "Science_LocalShield", 
[22] = "Science_PushBeam", 
[23] = "Support_Boosters", 
[24] = "Support_Smoke", 
[25] = "Support_Refrigerate", 
[26] = "Support_Destruct", 
[27] = "DeploySkill_ShieldTank", 
[28] = "DeploySkill_Tank", 
[29] = "DeploySkill_AcidTank", 
[30] = "DeploySkill_PullTank", 
[31] = "Support_Force", 
[32] = "Support_SmokeDrop", 
[33] = "Support_Repair", 
[34] = "Support_Missiles", 
[35] = "Support_Wind", 
[36] = "Passive_FlameImmune", 
[37] = "Passive_Electric", 
[38] = "Passive_Leech", 
[39] = "Passive_MassRepair", 
[40] = "Passive_Defenses", 
[41] = "Passive_Burrows", 
[42] = "Passive_AutoShields", 
[43] = "Passive_Psions", 
[44] = "Passive_Boosters", 
[45] = "Passive_Medical", 
[46] = "Passive_FriendlyFire", 
[47] = "Passive_ForceAmp", 
[48] = "Passive_CritDefense" 
}, 
["PilotDeck"] = { 
[1] = "Pilot_Soldier", 
[2] = "Pilot_Youth", 
[3] = "Pilot_Warrior", 
[4] = "Pilot_Aquatic", 
[5] = "Pilot_Medic", 
[6] = "Pilot_Hotshot", 
[7] = "Pilot_Genius", 
[8] = "Pilot_Miner", 
[9] = "Pilot_Recycler", 
[10] = "Pilot_Assassin", 
[11] = "Pilot_Leader", 
[12] = "Pilot_Repairman" 
}, 
["SeenPilots"] = { 
[1] = "Pilot_Detritus", 
[2] = "Pilot_Rust", 
[3] = "Pilot_Archive", 
[4] = "Pilot_Original" 
}, 
["PodDeck"] = { 
[1] = { 
["cores"] = 1 
}, 
[2] = { 
["cores"] = 1 
}, 
[3] = { 
["cores"] = 1 
}, 
[4] = { 
["cores"] = 1, 
["weapon"] = "random" 
}, 
[5] = { 
["cores"] = 1, 
["weapon"] = "random" 
}, 
[6] = { 
["cores"] = 1, 
["weapon"] = "random" 
}, 
[7] = { 
["cores"] = 1, 
["weapon"] = "random" 
}, 
[8] = { 
["cores"] = 1, 
["pilot"] = "random" 
}, 
[9] = { 
["cores"] = 1, 
["pilot"] = "random" 
} 
}, 
["Bosses"] = { 
[1] = "Mission_BeetleBoss", 
[2] = "Mission_HornetBoss", 
[3] = "Mission_SpiderBoss", 
[4] = "Mission_JellyBoss" 
}, 
["Island"] = 4, 
["Missions"] = { 
[1] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 3, 
["curr_weakRatio"] = { 
[1] = 1, 
[2] = 2 
}, 
["curr_upgradeRatio"] = { 
[1] = 0, 
[2] = 2 
}, 
["upgrade_streak"] = 0, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Firefly"] = 1, 
["Hornet"] = 1, 
["Jelly_Armor"] = 1 
} 
}, 
["AssetId"] = "Str_Bar", 
["AssetLoc"] = Point( 2, 4 ), 
["ID"] = "Mission_Teleporter", 
["VoiceEvents"] = { 
}, 
["LiveEnvironment"] = { 
}, 
["BonusObjs"] = { 
[1] = 6, 
[2] = 1 
} 
}, 
[2] = { 
["ID"] = "Mission_AcidTank", 
["BonusObjs"] = { 
} 
}, 
[3] = { 
["ID"] = "Mission_Power", 
["BonusObjs"] = { 
[1] = 3 
}, 
["DiffMod"] = 2 
}, 
[4] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 5, 
["curr_weakRatio"] = { 
[1] = 0, 
[2] = 0 
}, 
["curr_upgradeRatio"] = { 
[1] = 0, 
[2] = 0 
}, 
["upgrade_streak"] = 0, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Jelly_Armor"] = 1, 
["Scorpion"] = 3, 
["Hornet"] = 1 
} 
}, 
["AssetId"] = "Str_Power", 
["BonusObjs"] = { 
[1] = 4, 
[2] = 1 
}, 
["AssetLoc"] = Point( 2, 1 ), 
["ID"] = "Mission_BeltRandom", 
["VoiceEvents"] = { 
}, 
["LiveEnvironment"] = { 
["Belts"] = { 
[1] = Point( 1, 3 ), 
[2] = Point( 3, 3 ), 
[3] = Point( 3, 4 ), 
[4] = Point( 5, 4 ), 
[5] = Point( 5, 3 ), 
[6] = Point( 6, 3 ), 
[7] = Point( 6, 6 ) 
}, 
["BeltsDir"] = { 
[1] = 2, 
[2] = 0, 
[3] = 0, 
[4] = 2, 
[5] = 2, 
[6] = 3, 
[7] = 3 
} 
}, 
["PowerStart"] = 5 
}, 
[5] = { 
["ID"] = "Mission_Disposal", 
["BonusObjs"] = { 
[1] = 1 
}, 
["DiffMod"] = 2, 
["AssetId"] = "Str_Battery" 
}, 
[6] = { 
["ID"] = "Mission_Acid", 
["BonusObjs"] = { 
[1] = 3, 
[2] = 1 
}, 
["AssetId"] = "Str_Power" 
}, 
[7] = { 
["ID"] = "Mission_Belt", 
["BonusObjs"] = { 
[1] = 4 
}, 
["DiffMod"] = 1 
}, 
[8] = { 
["ID"] = "Mission_JellyBoss", 
["BonusObjs"] = { 
[1] = 1 
}, 
["AssetId"] = "Str_Tower" 
} 
}, 
["Enemies"] = { 
[1] = { 
[1] = "Firefly", 
[2] = "Leaper", 
[3] = "Hornet", 
[4] = "Jelly_Health", 
[5] = "Blobber", 
[6] = "Crab", 
["island"] = 1 
}, 
[2] = { 
[1] = "Scarab", 
[2] = "Scorpion", 
[3] = "Firefly", 
[4] = "Jelly_Regen", 
[5] = "Burrower", 
[6] = "Beetle", 
["island"] = 2 
}, 
[3] = { 
[1] = "Hornet", 
[2] = "Scarab", 
[3] = "Leaper", 
[4] = "Jelly_Explode", 
[5] = "Centipede", 
[6] = "Digger", 
["island"] = 3 
}, 
[4] = { 
[1] = "Scorpion", 
[2] = "Hornet", 
[3] = "Firefly", 
[4] = "Jelly_Armor", 
[5] = "Spider", 
[6] = "Digger", 
["island"] = 4 
} 
} 
}

 

SquadData = {
["money"] = 0, ["cores"] = 0, ["bIsFavor"] = false, ["repairs"] = 0, ["CorpReward"] = {CreateEffect({weapon = "Support_Blizzard",}), CreateEffect({skill1 = "Reactor",skill2 = "Grid",pilot = "Pilot_Original",}), CreateEffect({power = 2,}), },
["RewardClaimed"] = false, 
["skip_pawns"] = true, 

["storage_size"] = 3, ["CorpStore"] = {CreateEffect({weapon = "Science_FireBeam",money = -2,}), CreateEffect({weapon = "Science_Shield",money = -2,}), CreateEffect({stock = 0,}), CreateEffect({stock = 0,}), CreateEffect({money = -3,stock = -1,cores = 1,}), CreateEffect({money = -1,power = 1,stock = -1,}), },
["island_store_count"] = 0, ["store_undo_size"] = 0, }
 

