GameData = {["save_version"] = 1, ["language"] = 1, ["network"] = 1, ["networkMax"] = 7, ["overflow"] = 0, ["seed"] = 833461199, ["new_enemies"] = 0, ["new_missions"] = 0, ["new_equip"] = 0, ["difficulty"] = 1, ["new_abilities"] = 0, ["ach_info"] = {["squad"] = "Archive_A", ["trackers"] = {["Detritus_B_2"] = 0, ["Global_Challenge_Power"] = 3, ["Archive_A_1"] = 0, ["Archive_B_2"] = 0, ["Rust_A_2"] = 0, ["Rust_A_3"] = 0, ["Pinnacle_A_3"] = 0, ["Archive_B_1"] = 0, ["Pinnacle_B_3"] = 0, ["Detritus_B_1"] = 0, ["Pinnacle_B_1"] = 0, ["Global_Island_Mechs"] = 1, ["Global_Island_Building"] = 4, ["Squad_Mist_1"] = 0, ["Squad_Bomber_2"] = 0, ["Squad_Spiders_1"] = 0, ["Squad_Mist_2"] = 0, ["Squad_Heat_1"] = 0, ["Squad_Cataclysm_1"] = 0, ["Squad_Cataclysm_2"] = 0, ["Squad_Cataclysm_3"] = 0, },
},


["current"] = {["score"] = 0, ["time"] = 542456.312500, ["kills"] = 2, ["damage"] = 0, ["failures"] = 0, ["difficulty"] = 1, ["victory"] = false, ["squad"] = 0, 
["mechs"] = {"PunchMech", "TankMech", "ArtiMech", },
["colors"] = {0, 0, 0, },
["weapons"] = {"Prime_Punchmech", "", "Brute_Tankmech", "", "Ranged_Artillerymech", "", },
["pilot0"] = {["id"] = "Pilot_Detritus", ["name"] = "Isabel Nguyen", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 2, ["skill2"] = 3, ["exp"] = 11, ["level"] = 0, ["travel"] = 2, ["final"] = 0, ["starting"] = true, ["last_end"] = 2, },
["pilot1"] = {["id"] = "Pilot_Rust", ["name"] = "Maxim Huang", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 0, ["exp"] = 3, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot2"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Celestine", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 0, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
},
["current_squad"] = 0, }
 

RegionData = {
["sector"] = 0, ["island"] = 1, ["secret"] = false, 
["island0"] = {["corporation"] = "Corp_Grass", ["id"] = 0, ["secured"] = false, },
["island1"] = {["corporation"] = "Corp_Desert", ["id"] = 1, ["secured"] = false, },
["island2"] = {["corporation"] = "Corp_Snow", ["id"] = 2, ["secured"] = false, },
["island3"] = {["corporation"] = "Corp_Factory", ["id"] = 3, ["secured"] = false, },

["turn"] = 0, ["iTower"] = 7, ["quest_tracker"] = 0, ["quest_id"] = 0, ["podRewards"] = {CreateEffect({weapon = "random",cores = 1,}), },


["region0"] = {["mission"] = "Mission3", ["state"] = 0, ["name"] = "Thunderbolt Grid", },

["region1"] = {["mission"] = "Mission2", ["state"] = 0, ["name"] = "Restricted Area", },

["region2"] = {["mission"] = "Mission5", ["state"] = 0, ["name"] = "The Haze", },

["region3"] = {["mission"] = "Mission7", ["state"] = 0, ["name"] = "Tectonic Site 3.1", },

["region4"] = {["mission"] = "Mission6", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission6", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Solar_Briefing_CEO_Sand_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 1197368932, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "anyAE7", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 3 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 125, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 89, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 97, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 5 ), ["terrain"] = 7, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 7, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_solar1", ["people1"] = 97, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 5 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_solar1", ["people1"] = 111, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 7, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 3, },
{["loc"] = Point( 3, 5 ), ["terrain"] = 3, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 7, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 4, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 258, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 223, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 2 ), ["terrain"] = 0, },
{["loc"] = Point( 5, 5 ), ["terrain"] = 7, },
{["loc"] = Point( 5, 6 ), ["terrain"] = 7, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 4 ), ["terrain"] = 7, },
},
["spawns"] = {"Firefly1", "Scarab1", "Scarab1", },
["spawn_ids"] = {339, 340, 341, },
["spawn_points"] = {Point(7,3), Point(5,5), Point(6,2), },
["zones"] = {},
["tags"] = {"generic", "any_sector", },


["pawn1"] = {["type"] = "Scorpion2", ["name"] = "", ["id"] = 338, ["mech"] = false, ["offset"] = 1, ["primary"] = "ScorpionAtk2", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 5, ["max_health"] = 5, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,2), ["last_location"] = Point(-1,-1), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 741816866, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 338, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },
["pawn_count"] = 1, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Rust Beach", },

["region5"] = {["mission"] = "Mission4", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 3, ["iTeamTurn"] = 1, ["iState"] = 0, ["sMission"] = "Mission4", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Crack_Briefing_CEO_Sand_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 3, ["aiDelay"] = 0.000000, ["aiSeed"] = 316298321, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "anyAE39", ["enemy_kills"] = 2, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_battery1", ["people1"] = 68, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 71, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 100, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 106, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 1, 2 ), ["terrain"] = 0, ["smoke"] = 1, ["smoke"] = 1, ["undo_state"] = {["terrain"] = 7, ["active"] = true, },
},
{["loc"] = Point( 1, 4 ), ["terrain"] = 0, ["undo_state"] = {["active"] = true, ["neighbor1"] = {["health"] = 3, ["max_health"] = 3, },
},
},
{["loc"] = Point( 1, 5 ), ["terrain"] = 7, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 84, ["people2"] = 0, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 2, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 98, ["people2"] = 0, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 2, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 0, ["undo_state"] = {["active"] = true, ["neighbor1"] = {["health"] = 2, ["max_health"] = 2, },
["neighbor2"] = {["health"] = 3, ["max_health"] = 3, },
},
},
{["loc"] = Point( 3, 3 ), ["terrain"] = 9, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 9, },
{["loc"] = Point( 3, 5 ), ["terrain"] = 9, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 0, ["undo_state"] = {["active"] = true, },
},
{["loc"] = Point( 4, 2 ), ["terrain"] = 9, },
{["loc"] = Point( 4, 3 ), ["terrain"] = 1, ["populated"] = 1, ["grappled"] = 1, ["people1"] = 63, ["people2"] = 0, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 4, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 83, ["people2"] = 0, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 4, 5 ), ["terrain"] = 9, },
{["loc"] = Point( 4, 6 ), ["terrain"] = 9, },
{["loc"] = Point( 4, 7 ), ["terrain"] = 9, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 0, ["cracked"] = true, },
{["loc"] = Point( 5, 2 ), ["terrain"] = 0, },
{["loc"] = Point( 5, 3 ), ["terrain"] = 0, ["grapple_targets"] = {3, },
},
{["loc"] = Point( 5, 4 ), ["terrain"] = 0, ["smoke"] = 1, ["smoke"] = 1, },
{["loc"] = Point( 5, 6 ), ["terrain"] = 9, },
{["loc"] = Point( 6, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 3 ), ["terrain"] = 0, },
{["loc"] = Point( 6, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 6, 5 ), ["terrain"] = 0, },
{["loc"] = Point( 6, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 5 ), ["terrain"] = 7, },
{["loc"] = Point( 7, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 4, },
},
["pod"] = Point(5,1), ["spawns"] = {"Scarab1", },
["spawn_ids"] = {355, },
["spawn_points"] = {Point(7,5), },
["zones"] = {},
["tags"] = {"generic", "any_sector", },


["pawn1"] = {["type"] = "PunchMech", ["name"] = "", ["id"] = 0, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Prime_Punchmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Detritus", ["name"] = "Isabel Nguyen", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 2, ["skill2"] = 3, ["exp"] = 11, ["level"] = 0, ["travel"] = 2, ["final"] = 0, ["starting"] = true, ["last_end"] = 2, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 1, ["is_corpse"] = true, ["health"] = 2, ["max_health"] = 3, ["undo_state"] = {["health"] = 3, ["max_health"] = 3, },
["undo_ready"] = false, ["undo_point"] = Point(3,2), ["iMissionDamage"] = 0, ["location"] = Point(3,2), ["last_location"] = Point(3,3), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 3, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(3,2), ["undoReady"] = false, ["iKillCount"] = 2, ["iOwner"] = 0, ["piTarget"] = Point(1,2), ["piOrigin"] = Point(3,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,2), },


["pawn2"] = {["type"] = "TankMech", ["name"] = "", ["id"] = 1, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Brute_Tankmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Rust", ["name"] = "Maxim Huang", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 0, ["exp"] = 3, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 1, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 3, ["max_health"] = 3, },
["undo_ready"] = false, ["undo_point"] = Point(3,6), ["iMissionDamage"] = 0, ["location"] = Point(3,6), ["last_location"] = Point(3,5), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 3, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(3,6), ["undoReady"] = false, ["iKillCount"] = 3, ["iOwner"] = 1, ["piTarget"] = Point(4,6), ["piOrigin"] = Point(3,6), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,6), },


["pawn3"] = {["type"] = "ArtiMech", ["name"] = "", ["id"] = 2, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Ranged_Artillerymech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Celestine", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 0, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 2, ["max_health"] = 2, },
["undo_ready"] = false, ["undo_point"] = Point(1,4), ["iMissionDamage"] = 0, ["location"] = Point(1,4), ["last_location"] = Point(1,3), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 3, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(1,4), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 2, ["piTarget"] = Point(5,4), ["piOrigin"] = Point(1,4), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,4), },


["pawn4"] = {["type"] = "Scarab1", ["name"] = "", ["id"] = 337, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScarabAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,3), ["last_location"] = Point(6,4), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 3, ["iTurnsRemaining"] = 3, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 337, ["piTarget"] = Point(4,3), ["piOrigin"] = Point(6,3), ["piQueuedShot"] = Point(4,3), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,3), },


["pawn5"] = {["type"] = "Scorpion1", ["name"] = "", ["id"] = 342, ["mech"] = false, ["offset"] = 0, ["not_attacking"] = true, ["primary"] = "ScorpionAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,2), ["last_location"] = Point(5,3), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 3, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 342, ["piTarget"] = Point(6,5), ["piOrigin"] = Point(7,5), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,4), },


["pawn6"] = {["type"] = "Scarab1", ["name"] = "", ["id"] = 343, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScarabAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,5), ["last_location"] = Point(6,4), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 3, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 343, ["piTarget"] = Point(2,5), ["piOrigin"] = Point(6,5), ["piQueuedShot"] = Point(2,5), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(2,5), },


["pawn7"] = {["type"] = "Scorpion1", ["name"] = "", ["id"] = 352, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScorpionAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,3), ["last_location"] = Point(5,3), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 7, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 352, ["piTarget"] = Point(4,3), ["piOrigin"] = Point(5,3), ["piQueuedShot"] = Point(4,3), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,3), },


["pawn8"] = {["type"] = "Scorpion1", ["name"] = "", ["id"] = 353, ["mech"] = false, ["offset"] = 0, ["not_attacking"] = true, ["primary"] = "ScorpionAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,4), ["last_location"] = Point(6,3), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = -15921385, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 353, ["piTarget"] = Point(6,3), ["piOrigin"] = Point(7,3), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },
["pawn_count"] = 8, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Scrapyard", },

["region6"] = {["mission"] = "Mission1", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission1", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Force_Briefing_CEO_Sand_2", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 2115363241, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "hightide3", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 88, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 85, ["people2"] = 0, ["health_max"] = 1, ["shield"] = true, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 7, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 7, },
{["loc"] = Point( 1, 2 ), ["terrain"] = 7, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 85, ["people2"] = 0, ["health_max"] = 1, ["shield"] = true, },
{["loc"] = Point( 1, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 112, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 7, },
{["loc"] = Point( 2, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 3, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 7, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 228, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 235, ["people2"] = 0, ["health_max"] = 2, ["shield"] = true, },
{["loc"] = Point( 4, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 2 ), ["terrain"] = 7, },
{["loc"] = Point( 6, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 5 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 167, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 2 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 3 ), ["terrain"] = 4, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 7, 4 ), ["terrain"] = 4, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 7, 5 ), ["terrain"] = 4, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 7, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 4, },
},
["spawns"] = {"Firefly1", "Scorpion1", "Jelly_Health1", },
["spawn_ids"] = {332, 333, 334, },
["spawn_points"] = {Point(6,3), Point(6,4), Point(5,4), },
["zones"] = {},
["tags"] = {"mountain", "water", "tide", "any_sector", },
["pawn_count"] = 0, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Razor Bay", },

["region7"] = {["mission"] = "", ["state"] = 2, ["name"] = "Corporate HQ", ["objectives"] = {},
},
["iBattleRegion"] = 5, }
 

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
[47] = "Science_Shield", 
[48] = "Science_FireBeam", 
[49] = "Science_FreezeBeam", 
[50] = "Science_LocalShield", 
[51] = "Science_PushBeam", 
[52] = "Support_Boosters", 
[53] = "Support_Smoke", 
[54] = "Support_Refrigerate", 
[55] = "Support_Destruct", 
[56] = "DeploySkill_ShieldTank", 
[57] = "DeploySkill_AcidTank", 
[58] = "Support_Force", 
[59] = "Support_SmokeDrop", 
[60] = "Support_Repair", 
[61] = "Support_Missiles", 
[62] = "Support_Wind", 
[63] = "Support_Blizzard", 
[64] = "Passive_FlameImmune", 
[65] = "Passive_Electric", 
[66] = "Passive_Leech", 
[67] = "Passive_MassRepair", 
[68] = "Passive_Defenses", 
[69] = "Passive_Burrows", 
[70] = "Passive_AutoShields", 
[71] = "Passive_Psions", 
[72] = "Passive_Boosters", 
[73] = "Passive_Medical", 
[74] = "Passive_FriendlyFire", 
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
[20] = "Science_Shield", 
[21] = "Science_FireBeam", 
[22] = "Science_FreezeBeam", 
[23] = "Science_LocalShield", 
[24] = "Science_PushBeam", 
[25] = "Support_Boosters", 
[26] = "Support_Smoke", 
[27] = "Support_Refrigerate", 
[28] = "Support_Destruct", 
[29] = "DeploySkill_ShieldTank", 
[30] = "DeploySkill_AcidTank", 
[31] = "Support_Force", 
[32] = "Support_SmokeDrop", 
[33] = "Support_Repair", 
[34] = "Support_Missiles", 
[35] = "Support_Wind", 
[36] = "Support_Blizzard", 
[37] = "Passive_FlameImmune", 
[38] = "Passive_Electric", 
[39] = "Passive_Leech", 
[40] = "Passive_MassRepair", 
[41] = "Passive_Defenses", 
[42] = "Passive_Burrows", 
[43] = "Passive_AutoShields", 
[44] = "Passive_Psions", 
[45] = "Passive_Boosters", 
[46] = "Passive_Medical", 
[47] = "Passive_FriendlyFire", 
[48] = "Passive_CritDefense" 
}, 
["PilotDeck"] = { 
[1] = "Pilot_Original", 
[2] = "Pilot_Soldier", 
[3] = "Pilot_Youth", 
[4] = "Pilot_Warrior", 
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
[3] = "Pilot_Pinnacle", 
[4] = "Pilot_Aquatic" 
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
["pilot"] = "random" 
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
[1] = "Mission_HornetBoss", 
[2] = "Mission_BlobBoss", 
[3] = "Mission_ScorpionBoss", 
[4] = "Mission_SpiderBoss" 
}, 
["Island"] = 2, 
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
["Scorpion"] = 1, 
["Jelly_Health"] = 1 
} 
}, 
["BonusObjs"] = { 
}, 
["ID"] = "Mission_Force", 
["VoiceEvents"] = { 
}, 
["DiffMod"] = 1, 
["LiveEnvironment"] = { 
} 
}, 
[2] = { 
["ID"] = "Mission_Volatile", 
["BonusObjs"] = { 
[1] = 1 
}, 
["AssetId"] = "Str_Bar" 
}, 
[3] = { 
["ID"] = "Mission_Cataclysm", 
["BonusObjs"] = { 
[1] = 3, 
[2] = 1 
}, 
["AssetId"] = "Str_Nimbus" 
}, 
[4] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 8, 
["curr_weakRatio"] = { 
[1] = 2, 
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
["Scarab"] = 3, 
["Scorpion"] = 3, 
["Jelly_Health"] = 1 
} 
}, 
["AssetId"] = "Str_Battery", 
["BonusObjs"] = { 
[1] = 4, 
[2] = 1 
}, 
["AssetLoc"] = Point( 0, 2 ), 
["ID"] = "Mission_Crack", 
["VoiceEvents"] = { 
}, 
["LiveEnvironment"] = { 
["Path"] = { 
[1] = Point( 4, 7 ), 
[2] = Point( 4, 6 ), 
[3] = Point( 4, 5 ), 
[4] = Point( 3, 5 ), 
[5] = Point( 3, 4 ), 
[6] = Point( 3, 3 ), 
[7] = Point( 3, 2 ), 
[8] = Point( 3, 1 ), 
[9] = Point( 3, 0 ) 
}, 
["EndEffect"] = true, 
["Planned"] = { 
[1] = Point( 3, 2 ), 
[2] = Point( 3, 1 ), 
[3] = Point( 3, 0 ) 
}, 
["Locations"] = { 
[1] = Point( 3, 2 ), 
[2] = Point( 3, 1 ), 
[3] = Point( 3, 0 ) 
}, 
["Index"] = 10, 
["StartEffect"] = true, 
["FirstTile"] = Point( 3, 2 ) 
}, 
["PowerStart"] = 5 
}, 
[5] = { 
["ID"] = "Mission_Lightning", 
["BonusObjs"] = { 
[1] = 6, 
[2] = 1 
}, 
["AssetId"] = "Str_Power" 
}, 
[6] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 3, 
["curr_weakRatio"] = { 
[1] = 2, 
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
["Scorpion"] = 1, 
["Scarab"] = 2 
} 
}, 
["BonusObjs"] = { 
[1] = 5 
}, 
["Criticals"] = { 
[1] = Point( 2, 2 ), 
[2] = Point( 2, 5 ) 
}, 
["ID"] = "Mission_Solar", 
["VoiceEvents"] = { 
}, 
["DiffMod"] = 2, 
["LiveEnvironment"] = { 
} 
}, 
[7] = { 
["ID"] = "Mission_Train", 
["BonusObjs"] = { 
[1] = 1 
}, 
["DiffMod"] = 2, 
["AssetId"] = "Str_Power" 
}, 
[8] = { 
["ID"] = "Mission_BlobBoss", 
["BonusObjs"] = { 
[1] = 1 
}, 
["AssetId"] = "Str_Tower" 
} 
}, 
["Enemies"] = { 
[1] = { 
[1] = "Scarab", 
[2] = "Leaper", 
[3] = "Hornet", 
[4] = "Jelly_Armor", 
[5] = "Centipede", 
[6] = "Blobber", 
["island"] = 1 
}, 
[2] = { 
[1] = "Firefly", 
[2] = "Scorpion", 
[3] = "Scarab", 
[4] = "Jelly_Health", 
[5] = "Beetle", 
[6] = "Burrower", 
["island"] = 2 
}, 
[3] = { 
[1] = "Scorpion", 
[2] = "Hornet", 
[3] = "Firefly", 
[4] = "Jelly_Regen", 
[5] = "Spider", 
[6] = "Crab", 
["island"] = 3 
}, 
[4] = { 
[1] = "Leaper", 
[2] = "Hornet", 
[3] = "Scarab", 
[4] = "Jelly_Explode", 
[5] = "Digger", 
[6] = "Centipede", 
["island"] = 4 
} 
} 
}

 

SquadData = {
["money"] = 0, ["cores"] = 0, ["bIsFavor"] = false, ["repairs"] = 0, ["CorpReward"] = {CreateEffect({weapon = "Passive_ForceAmp",}), CreateEffect({skill1 = "Grid",skill2 = "Move",pilot = "Pilot_Aquatic",}), CreateEffect({power = 2,}), },
["RewardClaimed"] = false, 
["skip_pawns"] = true, 

["storage_size"] = 3, ["CorpStore"] = {CreateEffect({weapon = "DeploySkill_PullTank",money = -2,}), CreateEffect({weapon = "DeploySkill_Tank",money = -2,}), CreateEffect({stock = 0,}), CreateEffect({stock = 0,}), CreateEffect({money = -3,stock = -1,cores = 1,}), CreateEffect({money = -1,power = 1,stock = -1,}), },
["island_store_count"] = 0, ["store_undo_size"] = 0, }
 

