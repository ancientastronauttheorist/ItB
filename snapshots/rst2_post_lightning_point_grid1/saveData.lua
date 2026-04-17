GameData = {["save_version"] = 1, ["language"] = 1, ["network"] = 1, ["networkMax"] = 7, ["overflow"] = 0, ["seed"] = 650047080, ["new_enemies"] = 0, ["new_missions"] = 0, ["new_equip"] = 0, ["difficulty"] = 1, ["new_abilities"] = 0, ["ach_info"] = {["squad"] = "Archive_A", ["trackers"] = {["Detritus_B_2"] = 0, ["Global_Challenge_Power"] = 3, ["Archive_A_1"] = 0, ["Archive_B_2"] = 0, ["Rust_A_2"] = 0, ["Rust_A_3"] = 0, ["Pinnacle_A_3"] = 0, ["Archive_B_1"] = 0, ["Pinnacle_B_3"] = 0, ["Detritus_B_1"] = 0, ["Pinnacle_B_1"] = 0, ["Global_Island_Mechs"] = 0, ["Global_Island_Building"] = 4, ["Squad_Mist_1"] = 0, ["Squad_Bomber_2"] = 0, ["Squad_Spiders_1"] = 0, ["Squad_Mist_2"] = 0, ["Squad_Heat_1"] = 0, ["Squad_Cataclysm_1"] = 0, ["Squad_Cataclysm_2"] = 0, ["Squad_Cataclysm_3"] = 0, },
},


["current"] = {["score"] = 0, ["time"] = 3840212.750000, ["kills"] = 5, ["damage"] = 0, ["failures"] = 0, ["difficulty"] = 1, ["victory"] = false, ["squad"] = 0, 
["mechs"] = {"PunchMech", "TankMech", "ArtiMech", },
["colors"] = {0, 0, 0, },
["weapons"] = {"Prime_Punchmech", "", "Brute_Tankmech", "", "Ranged_Artillerymech", "", },
["pilot0"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Celestine", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 2, ["skill2"] = 1, ["exp"] = 2, ["level"] = 0, ["travel"] = 1, ["final"] = 0, ["starting"] = true, ["last_end"] = 2, },
["pilot1"] = {["id"] = "Pilot_Detritus", ["name"] = "Isla Zhang", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 3, ["exp"] = 1, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot2"] = {["id"] = "Pilot_Rust", ["name"] = "Urbana Smith", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 2, ["exp"] = 7, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
},
["current_squad"] = 0, }
 

RegionData = {
["sector"] = 0, ["island"] = 1, ["secret"] = false, 
["island0"] = {["corporation"] = "Corp_Grass", ["id"] = 0, ["secured"] = false, },
["island1"] = {["corporation"] = "Corp_Desert", ["id"] = 1, ["secured"] = false, },
["island2"] = {["corporation"] = "Corp_Snow", ["id"] = 2, ["secured"] = false, },
["island3"] = {["corporation"] = "Corp_Factory", ["id"] = 3, ["secured"] = false, },

["turn"] = 0, ["iTower"] = 0, ["quest_tracker"] = 0, ["quest_id"] = 0, ["podRewards"] = {},


["region0"] = {["mission"] = "", ["state"] = 2, ["name"] = "Corporate HQ", ["objectives"] = {},
},

["region1"] = {["mission"] = "Mission4", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 4, ["iTeamTurn"] = 1, ["iState"] = 0, ["sMission"] = "Mission4", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Filler_Briefing_CEO_Sand_1", ["podReward"] = CreateEffect({skill1 = "Health",skill2 = "Reactor",pilot = "Pilot_Repairman",cores = 1,}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 0, ["aiState"] = 3, ["aiDelay"] = 0.000000, ["aiSeed"] = 1919696704, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "crosscrack2", ["enemy_kills"] = 5, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 116, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 77, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 4, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 84, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 0, ["smoke"] = 1, ["smoke"] = 1, },
{["loc"] = Point( 2, 5 ), ["terrain"] = 0, ["undo_state"] = {["active"] = true, ["neighbor1"] = {["health"] = 2, ["max_health"] = 2, },
},
},
{["loc"] = Point( 2, 7 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 123, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 2, ["health_max"] = 2, ["health_min"] = 0, ["rubble_type"] = 0, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 2, ["health_max"] = 2, ["health_min"] = 0, ["rubble_type"] = 0, },
{["loc"] = Point( 3, 3 ), ["terrain"] = 7, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 0, ["undo_state"] = {["active"] = true, ["neighbor1"] = {["health"] = 2, ["max_health"] = 2, },
["neighbor2"] = {["health"] = 2, ["max_health"] = 2, },
},
},
{["loc"] = Point( 3, 5 ), ["terrain"] = 0, ["smoke"] = 1, ["smoke"] = 1, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 0, ["undo_state"] = {["active"] = true, ["neighbor0"] = {["health"] = 2, ["max_health"] = 2, },
},
},
{["loc"] = Point( 3, 7 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 232, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 0 ), ["terrain"] = 9, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 0, ["pod"] = 2, },
{["loc"] = Point( 4, 3 ), ["terrain"] = 0, ["undo_state"] = {["active"] = true, ["neighbor1"] = {["health"] = 1, ["max_health"] = 1, },
["neighbor3"] = {["health"] = 3, ["max_health"] = 3, },
},
},
{["loc"] = Point( 4, 6 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 7 ), ["terrain"] = 4, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 5, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 6, 4 ), ["terrain"] = 7, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 9, },
{["loc"] = Point( 7, 5 ), ["terrain"] = 7, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 4, },
},
["pod"] = Point(4,1), ["spawns"] = {},
["spawn_ids"] = {},
["spawn_points"] = {},
["zones"] = {["filler"] = {Point( 5, 4 ), },
},
["tags"] = {"sand", "filler", },


["pawn1"] = {["type"] = "Filler_Pawn", ["name"] = "", ["id"] = 454, ["mech"] = false, ["offset"] = 0, ["primary"] = "Filler_Attack", ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Rust", ["name"] = "Mikayla Waller", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 3, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = false, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 1, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,4), ["last_location"] = Point(5,4), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 454, ["piTarget"] = Point(5,4), ["piOrigin"] = Point(5,4), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,4), },


["pawn2"] = {["type"] = "PunchMech", ["name"] = "", ["id"] = 0, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Prime_Punchmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Celestine", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 2, ["skill2"] = 1, ["exp"] = 2, ["level"] = 0, ["travel"] = 1, ["final"] = 0, ["starting"] = true, ["last_end"] = 2, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 1, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 3, ["max_health"] = 3, },
["undo_ready"] = false, ["undo_point"] = Point(3,4), ["iMissionDamage"] = 0, ["location"] = Point(3,4), ["last_location"] = Point(3,5), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(3,4), ["undoReady"] = false, ["iKillCount"] = 2, ["iOwner"] = 0, ["piTarget"] = Point(4,4), ["piOrigin"] = Point(3,4), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,4), },


["pawn3"] = {["type"] = "TankMech", ["name"] = "", ["id"] = 1, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Brute_Tankmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Detritus", ["name"] = "Isla Zhang", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 3, ["exp"] = 1, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 1, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 3, ["max_health"] = 3, },
["undo_ready"] = true, ["undo_point"] = Point(4,3), ["iMissionDamage"] = 0, ["location"] = Point(4,3), ["last_location"] = Point(3,3), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(4,3), ["undoReady"] = true, ["iKillCount"] = 1, ["iOwner"] = 1, ["piTarget"] = Point(4,4), ["piOrigin"] = Point(4,3), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,4), },


["pawn4"] = {["type"] = "ArtiMech", ["name"] = "", ["id"] = 2, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Ranged_Artillerymech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Rust", ["name"] = "Urbana Smith", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 2, ["exp"] = 7, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 3, ["is_corpse"] = true, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 2, ["max_health"] = 2, },
["undo_ready"] = false, ["undo_point"] = Point(2,5), ["iMissionDamage"] = 0, ["location"] = Point(2,5), ["last_location"] = Point(3,5), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(2,5), ["undoReady"] = false, ["iKillCount"] = 7, ["iOwner"] = 2, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(2,5), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(2,3), },


["pawn5"] = {["type"] = "Scarab1", ["name"] = "", ["id"] = 458, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScarabAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,1), ["last_location"] = Point(4,2), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 2, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 458, ["piTarget"] = Point(4,3), ["piOrigin"] = Point(4,1), ["piQueuedShot"] = Point(4,3), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,3), },


["pawn6"] = {["type"] = "Firefly1", ["name"] = "", ["id"] = 480, ["mech"] = false, ["offset"] = 0, ["primary"] = "FireflyAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 1, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,6), ["last_location"] = Point(4,6), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 480, ["piTarget"] = Point(4,5), ["piOrigin"] = Point(4,6), ["piQueuedShot"] = Point(4,5), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,5), },


["pawn7"] = {["type"] = "Scarab1", ["name"] = "", ["id"] = 482, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScarabAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,4), ["last_location"] = Point(6,5), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 482, ["piTarget"] = Point(3,4), ["piOrigin"] = Point(6,4), ["piQueuedShot"] = Point(3,4), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,4), },


["pawn8"] = {["type"] = "Scarab1", ["name"] = "", ["id"] = 483, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScarabAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,6), ["last_location"] = Point(3,5), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 132570048, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 483, ["piTarget"] = Point(3,4), ["piOrigin"] = Point(3,6), ["piQueuedShot"] = Point(3,4), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,4), },
["pawn_count"] = 8, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Lightning Point", },

["region2"] = {["mission"] = "Mission2", ["state"] = 0, ["name"] = "R.S.T. Perimeter", },

["region3"] = {["mission"] = "Mission7", ["state"] = 0, ["name"] = "The Rift", },

["region4"] = {["mission"] = "Mission5", ["state"] = 0, ["name"] = "Storm Mill", },

["region5"] = {["mission"] = "Mission3", ["state"] = 0, ["name"] = "Strafe Zone Beta", },

["region6"] = {["mission"] = "Mission6", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission6", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Crack_Briefing_CEO_Sand_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 55243129, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "anyAE18", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 90, ["people2"] = 0, ["health_max"] = 1, ["shield"] = true, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 104, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 7, },
{["loc"] = Point( 1, 5 ), ["terrain"] = 7, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 76, ["people2"] = 0, ["health_max"] = 1, ["shield"] = true, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 7, },
{["loc"] = Point( 2, 4 ), ["terrain"] = 7, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 104, ["people2"] = 0, ["health_max"] = 1, ["shield"] = true, },
{["loc"] = Point( 3, 0 ), ["terrain"] = 7, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 215, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 3 ), ["terrain"] = 4, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 170, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 4 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 3 ), ["terrain"] = 7, },
{["loc"] = Point( 5, 5 ), ["terrain"] = 7, },
{["loc"] = Point( 5, 6 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_recycle1", ["people1"] = 77, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 164, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 6, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 5 ), ["terrain"] = 7, },
{["loc"] = Point( 6, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 2 ), ["terrain"] = 7, },
{["loc"] = Point( 7, 3 ), ["terrain"] = 7, },
{["loc"] = Point( 7, 4 ), ["terrain"] = 7, },
{["loc"] = Point( 7, 5 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 4, },
},
["spawns"] = {"Firefly1", "Firefly1", "Scarab1", },
["spawn_ids"] = {451, 452, 453, },
["spawn_points"] = {Point(5,2), Point(6,5), Point(6,2), },
["zones"] = {},
["tags"] = {"generic", "any_sector", "mountain", },
["pawn_count"] = 0, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Fox Plateau", },

["region7"] = {["mission"] = "Mission1", ["state"] = 0, ["name"] = "Detonation Bay", },
["iBattleRegion"] = 1, }
 

GAME = { 
["WeaponDeck"] = { 
[31] = "Ranged_ScatterShot", 
[2] = "Prime_Lasermech", 
[8] = "Prime_Flamethrower", 
[32] = "Ranged_BackShot", 
[33] = "Ranged_Ice", 
[34] = "Ranged_SmokeBlast", 
[35] = "Ranged_Fireball", 
[9] = "Prime_Areablast", 
[36] = "Ranged_RainingVolley", 
[37] = "Ranged_Wide", 
[38] = "Ranged_Dual", 
[39] = "Science_Pullmech", 
[10] = "Prime_Spear", 
[40] = "Science_Gravwell", 
[41] = "Science_Swap", 
[42] = "Science_Repulse", 
[43] = "Science_Confuse", 
[11] = "Prime_Leap", 
[44] = "Science_SmokeDefense", 
[45] = "Science_Shield", 
[46] = "Science_FireBeam", 
[3] = "Prime_ShieldBash", 
[12] = "Prime_SpinFist", 
[48] = "Science_LocalShield", 
[49] = "Science_PushBeam", 
[50] = "Support_Boosters", 
[51] = "Support_Smoke", 
[13] = "Prime_Sword", 
[52] = "Support_Refrigerate", 
[53] = "Support_Destruct", 
[54] = "DeploySkill_Tank", 
[55] = "DeploySkill_AcidTank", 
[14] = "Prime_Smash", 
[56] = "DeploySkill_PullTank", 
[57] = "Support_Force", 
[58] = "Support_SmokeDrop", 
[59] = "Support_Repair", 
[15] = "Brute_Jetmech", 
[60] = "Support_Missiles", 
[61] = "Support_Wind", 
[62] = "Support_Blizzard", 
[1] = "Prime_Lightning", 
[4] = "Prime_Rockmech", 
[16] = "Brute_Mirrorshot", 
[64] = "Passive_Electric", 
[65] = "Passive_Leech", 
[66] = "Passive_MassRepair", 
[17] = "Brute_PhaseShot", 
[68] = "Passive_Burrows", 
[69] = "Passive_AutoShields", 
[70] = "Passive_Psions", 
[18] = "Brute_Shrapnel", 
[72] = "Passive_Medical", 
[73] = "Passive_FriendlyFire", 
[74] = "Passive_ForceAmp", 
[19] = "Brute_Sniper", 
[5] = "Prime_RightHook", 
[20] = "Brute_Shockblast", 
[21] = "Brute_Beetle", 
[22] = "Brute_Unstable", 
[23] = "Brute_Heavyrocket", 
[6] = "Prime_RocketPunch", 
[24] = "Brute_Splitshot", 
[25] = "Brute_Bombrun", 
[26] = "Brute_Sonic", 
[27] = "Ranged_Rockthrow", 
[7] = "Prime_Shift", 
[28] = "Ranged_Defensestrike", 
[29] = "Ranged_Rocket", 
[75] = "Passive_CritDefense", 
[71] = "Passive_Boosters", 
[67] = "Passive_Defenses", 
[30] = "Ranged_Ignite", 
[63] = "Passive_FlameImmune", 
[47] = "Science_FreezeBeam" 
}, 
["PodWeaponDeck"] = { 
[27] = "Support_Destruct", 
[2] = "Prime_Spear", 
[38] = "Passive_Electric", 
[3] = "Prime_Leap", 
[4] = "Prime_SpinFist", 
[5] = "Prime_Sword", 
[6] = "Prime_Smash", 
[7] = "Brute_Sniper", 
[8] = "Brute_Shockblast", 
[10] = "Brute_Heavyrocket", 
[12] = "Brute_Sonic", 
[14] = "Ranged_SmokeBlast", 
[16] = "Ranged_RainingVolley", 
[20] = "Science_FireBeam", 
[24] = "Support_Boosters", 
[28] = "DeploySkill_Tank", 
[32] = "Support_SmokeDrop", 
[40] = "Passive_MassRepair", 
[48] = "Passive_ForceAmp", 
[33] = "Support_Repair", 
[41] = "Passive_Defenses", 
[49] = "Passive_CritDefense", 
[17] = "Ranged_Dual", 
[21] = "Science_FreezeBeam", 
[25] = "Support_Smoke", 
[29] = "DeploySkill_AcidTank", 
[34] = "Support_Missiles", 
[42] = "Passive_Burrows", 
[9] = "Brute_Beetle", 
[11] = "Brute_Bombrun", 
[13] = "Ranged_Ice", 
[15] = "Ranged_Fireball", 
[18] = "Science_SmokeDefense", 
[22] = "Science_LocalShield", 
[26] = "Support_Refrigerate", 
[30] = "DeploySkill_PullTank", 
[36] = "Support_Blizzard", 
[44] = "Passive_Psions", 
[47] = "Passive_FriendlyFire", 
[46] = "Passive_Medical", 
[39] = "Passive_Leech", 
[43] = "Passive_AutoShields", 
[37] = "Passive_FlameImmune", 
[45] = "Passive_Boosters", 
[35] = "Support_Wind", 
[1] = "Prime_Areablast", 
[19] = "Science_Shield", 
[23] = "Science_PushBeam", 
[31] = "Support_Force" 
}, 
["PilotDeck"] = { 
[7] = "Pilot_Genius", 
[1] = "Pilot_Original", 
[2] = "Pilot_Soldier", 
[4] = "Pilot_Warrior", 
[8] = "Pilot_Miner", 
[9] = "Pilot_Recycler", 
[5] = "Pilot_Aquatic", 
[10] = "Pilot_Assassin", 
[3] = "Pilot_Youth", 
[6] = "Pilot_Medic", 
[11] = "Pilot_Leader" 
}, 
["SeenPilots"] = { 
[2] = "Pilot_Detritus", 
[3] = "Pilot_Rust", 
[1] = "Pilot_Pinnacle", 
[4] = "Pilot_Hotshot", 
[5] = "Pilot_Repairman" 
}, 
["PodDeck"] = { 
[7] = { 
["cores"] = 1, 
["weapon"] = "random" 
}, 
[1] = { 
["cores"] = 1 
}, 
[2] = { 
["cores"] = 1 
}, 
[4] = { 
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
}, 
[5] = { 
["cores"] = 1, 
["weapon"] = "random" 
}, 
[3] = { 
["cores"] = 1 
}, 
[6] = { 
["cores"] = 1, 
["weapon"] = "random" 
} 
}, 
["Bosses"] = { 
[1] = "Mission_BlobBoss", 
[2] = "Mission_SpiderBoss", 
[4] = "Mission_ScorpionBoss", 
[3] = "Mission_JellyBoss" 
}, 
["Enemies"] = { 
[1] = { 
[6] = "Beetle", 
[2] = "Hornet", 
[3] = "Scarab", 
[1] = "Scorpion", 
[4] = "Jelly_Explode", 
[5] = "Spider", 
["island"] = 1 
}, 
[2] = { 
[6] = "Burrower", 
[2] = "Firefly", 
[3] = "Scarab", 
[1] = "Leaper", 
[4] = "Jelly_Armor", 
[5] = "Blobber", 
["island"] = 2 
}, 
[4] = { 
[6] = "Digger", 
[2] = "Firefly", 
[3] = "Hornet", 
[1] = "Leaper", 
[4] = "Jelly_Regen", 
[5] = "Crab", 
["island"] = 4 
}, 
[3] = { 
[6] = "Digger", 
[2] = "Hornet", 
[3] = "Firefly", 
[1] = "Scorpion", 
[4] = "Jelly_Health", 
[5] = "Centipede", 
["island"] = 3 
} 
}, 
["Missions"] = { 
[6] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["pawn_counts"] = { 
["Firefly"] = 2, 
["Scarab"] = 1 
}, 
["curr_weakRatio"] = { 
[1] = 2, 
[2] = 2 
}, 
["num_bosses"] = 0, 
["curr_upgradeRatio"] = { 
[1] = 0, 
[2] = 2 
}, 
["num_spawns"] = 3, 
["upgrade_streak"] = 0 
}, 
["AssetId"] = "Str_Nimbus", 
["BonusObjs"] = { 
[1] = 1 
}, 
["AssetLoc"] = Point( 5, 6 ), 
["ID"] = "Mission_Crack", 
["VoiceEvents"] = { 
}, 
["DiffMod"] = 1, 
["LiveEnvironment"] = { 
["Path"] = { 
[7] = Point( 3, 3 ), 
[1] = Point( 7, 5 ), 
[2] = Point( 7, 4 ), 
[4] = Point( 6, 3 ), 
[8] = Point( 2, 3 ), 
[9] = Point( 1, 3 ), 
[5] = Point( 5, 3 ), 
[10] = Point( 0, 3 ), 
[3] = Point( 6, 4 ), 
[6] = Point( 4, 3 ) 
}, 
["Locations"] = { 
}, 
["Planned"] = { 
} 
} 
}, 
[2] = { 
["Spawner"] = { 
}, 
["AssetId"] = "Str_Power", 
["ID"] = "Mission_Force", 
["LiveEnvironment"] = { 
}, 
["DiffMod"] = 2, 
["BonusObjs"] = { 
[1] = 6, 
[2] = 1 
} 
}, 
[8] = { 
["Spawner"] = { 
}, 
["AssetId"] = "Str_Tower", 
["ID"] = "Mission_SpiderBoss", 
["LiveEnvironment"] = { 
}, 
["BonusObjs"] = { 
[1] = 1 
} 
}, 
[3] = { 
["Spawner"] = { 
}, 
["AssetId"] = "Str_Power", 
["ID"] = "Mission_Volatile", 
["LiveEnvironment"] = { 
}, 
["BonusObjs"] = { 
[1] = 1 
} 
}, 
[1] = { 
["ID"] = "Mission_Bomb", 
["BonusObjs"] = { 
}, 
["LiveEnvironment"] = { 
}, 
["Spawner"] = { 
} 
}, 
[4] = { 
["Filler"] = 454, 
["LiveEnvironment"] = { 
}, 
["Spawner"] = { 
["used_bosses"] = 0, 
["pawn_counts"] = { 
["Firefly"] = 3, 
["Scarab"] = 3, 
["Leaper"] = 2, 
["Jelly_Armor"] = 1 
}, 
["curr_weakRatio"] = { 
[1] = 0, 
[2] = 1 
}, 
["num_bosses"] = 0, 
["curr_upgradeRatio"] = { 
[1] = 0, 
[2] = 1 
}, 
["num_spawns"] = 9, 
["upgrade_streak"] = 0 
}, 
["BonusObjs"] = { 
[1] = 5 
}, 
["ID"] = "Mission_Filler", 
["VoiceEvents"] = { 
}, 
["BlockedSpawns"] = 0, 
["PowerStart"] = 5 
}, 
[5] = { 
["Spawner"] = { 
}, 
["AssetId"] = "Str_Battery", 
["ID"] = "Mission_Terraform", 
["LiveEnvironment"] = { 
}, 
["DiffMod"] = 2, 
["BonusObjs"] = { 
[1] = 1 
} 
}, 
[7] = { 
["ID"] = "Mission_Solar", 
["BonusObjs"] = { 
}, 
["LiveEnvironment"] = { 
}, 
["Spawner"] = { 
} 
} 
}, 
["Island"] = 2 
}

 

SquadData = {
["money"] = 0, ["cores"] = 0, ["bIsFavor"] = false, ["repairs"] = 0, ["CorpReward"] = {CreateEffect({weapon = "DeploySkill_ShieldTank",}), CreateEffect({skill1 = "Health",skill2 = "Move",pilot = "Pilot_Hotshot",}), CreateEffect({power = 2,}), },
["RewardClaimed"] = false, 
["skip_pawns"] = true, 

["storage_size"] = 3, ["CorpStore"] = {CreateEffect({weapon = "Brute_Grapple",money = -2,}), CreateEffect({weapon = "Science_AcidShot",money = -2,}), CreateEffect({stock = 0,}), CreateEffect({stock = 0,}), CreateEffect({money = -3,stock = -1,cores = 1,}), CreateEffect({money = -1,power = 1,stock = -1,}), },
["island_store_count"] = 0, ["store_undo_size"] = 0, }
 

