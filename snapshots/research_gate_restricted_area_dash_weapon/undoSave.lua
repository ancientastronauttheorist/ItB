GameData = {["save_version"] = 1, ["language"] = 1, ["network"] = 7, ["networkMax"] = 7, ["overflow"] = 8, ["seed"] = 637591263, ["new_enemies"] = 1, ["new_missions"] = 1, ["new_equip"] = 1, ["difficulty"] = 0, ["new_abilities"] = 1, ["ach_info"] = {["squad"] = "Archive_A", ["trackers"] = {["Detritus_B_2"] = 0, ["Global_Challenge_Power"] = 0, ["Archive_A_1"] = 0, ["Archive_B_2"] = 0, ["Rust_A_2"] = 0, ["Rust_A_3"] = 0, ["Pinnacle_A_3"] = 0, ["Archive_B_1"] = 0, ["Pinnacle_B_3"] = 0, ["Detritus_B_1"] = 0, ["Pinnacle_B_1"] = 0, ["Global_Island_Mechs"] = 5, ["Global_Island_Building"] = 0, ["Squad_Mist_1"] = 0, ["Squad_Bomber_2"] = 0, ["Squad_Spiders_1"] = 0, ["Squad_Mist_2"] = 0, ["Squad_Heat_1"] = 0, ["Squad_Cataclysm_1"] = 0, ["Squad_Cataclysm_2"] = 0, ["Squad_Cataclysm_3"] = 0, },
},


["current"] = {["score"] = 3000, ["time"] = 9166583.000000, ["kills"] = 37, ["damage"] = 0, ["failures"] = 3, ["difficulty"] = 0, ["victory"] = false, ["islands"] = 1, ["squad"] = 0, 
["mechs"] = {"PunchMech", "TankMech", "ArtiMech", },
["colors"] = {0, 0, 0, },
["weapons"] = {"Prime_Punchmech_A", "", "Brute_Tankmech", "", "Ranged_Artillerymech", "", },
["pilot0"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 5, ["skill2"] = 3, ["exp"] = 0, ["level"] = 2, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot1"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Fenrir", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 5, ["skill2"] = 1, ["exp"] = 5, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot2"] = {["id"] = "Pilot_Artificial", ["name"] = "A.I. Unit", ["name_id"] = "Pilot_Artificial_Name", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 13, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = false, },
},
["current_squad"] = 0, ["undosave"] = true, }
 

RegionData = {
["sector"] = 1, ["island"] = 1, ["secret"] = false, 
["island0"] = {["corporation"] = "Corp_Grass", ["id"] = 0, ["secured"] = false, },
["island1"] = {["corporation"] = "Corp_Desert", ["id"] = 1, ["secured"] = false, },
["island2"] = {["corporation"] = "Corp_Snow", ["id"] = 2, ["secured"] = false, },
["island3"] = {["corporation"] = "Corp_Factory", ["id"] = 3, ["secured"] = true, },

["turn"] = 1, ["iTower"] = 0, ["quest_tracker"] = 1, ["quest_id"] = 0, ["podRewards"] = {CreateEffect({pilot = "random",cores = 1,}), },


["region0"] = {["mission"] = "", ["state"] = 2, ["name"] = "Corporate HQ", ["objectives"] = {},
},

["region1"] = {["mission"] = "Mission7", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission7", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Terratide_Briefing_CEO_Sand_2", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 1650091409, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "any10", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 3 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 4, ["smoke"] = 1, ["smoke"] = 1, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 60, ["people2"] = 0, ["health_max"] = 1, ["shield"] = true, },
{["loc"] = Point( 1, 2 ), ["terrain"] = 7, },
{["loc"] = Point( 1, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 53, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 29, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 1, ["populated"] = 1, ["smoke"] = 1, ["smoke"] = 1, ["people1"] = 54, ["people2"] = 0, ["health_max"] = 1, ["shield"] = true, },
{["loc"] = Point( 2, 0 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 48, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 0, },
{["loc"] = Point( 2, 7 ), ["terrain"] = 1, ["populated"] = 1, ["smoke"] = 1, ["smoke"] = 1, ["people1"] = 82, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 7, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 7, },
{["loc"] = Point( 3, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 84, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 90, ["people2"] = 0, ["health_max"] = 2, ["shield"] = true, },
{["loc"] = Point( 3, 7 ), ["terrain"] = 4, ["smoke"] = 1, ["smoke"] = 1, },
{["loc"] = Point( 4, 2 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 7 ), ["terrain"] = 0, ["smoke"] = 1, ["smoke"] = 1, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 7, ["smoke"] = 1, ["smoke"] = 1, },
{["loc"] = Point( 6, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 3 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 4 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 4, ["smoke"] = 1, ["smoke"] = 1, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 2 ), ["terrain"] = 7, },
{["loc"] = Point( 7, 3 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 4 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 4, ["smoke"] = 1, ["smoke"] = 1, },
},
["spawns"] = {"Centipede1", "Hornet1", },
["spawn_ids"] = {674, 675, },
["spawn_points"] = {Point(7,5), Point(6,2), },
["zones"] = {["flooding"] = {Point( 0, 1 ), Point( 1, 1 ), Point( 2, 2 ), Point( 1, 2 ), Point( 3, 5 ), Point( 2, 5 ), Point( 4, 6 ), Point( 3, 6 ), Point( 5, 7 ), Point( 4, 7 ), Point( 2, 6 ), Point( 0, 2 ), Point( 1, 5 ), Point( 0, 5 ), },
["satellite"] = {Point( 3, 6 ), Point( 5, 4 ), Point( 5, 3 ), Point( 3, 1 ), Point( 5, 6 ), Point( 5, 1 ), },
},
["tags"] = {"generic", "any_sector", "mountain", "flooding", "satellite", },


["pawn1"] = {["type"] = "BonusDebris", ["name"] = "", ["id"] = 672, ["mech"] = false, ["offset"] = 0, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 1, ["max_health"] = 1, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,2), ["last_location"] = Point(-1,-1), ["bMinor"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 672, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn2"] = {["type"] = "BonusDebris", ["name"] = "", ["id"] = 673, ["mech"] = false, ["offset"] = 0, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 1, ["max_health"] = 1, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(2,2), ["last_location"] = Point(-1,-1), ["bMinor"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 0, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 673, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },
["pawn_count"] = 2, ["blocked_points"] = {Point(0,1), Point(1,1), Point(2,1), Point(3,1), Point(4,1), Point(5,1), Point(6,1), Point(7,1), },
["blocked_type"] = {2, 2, 2, 2, 2, 2, 2, 2, },
},


},
["state"] = 1, ["name"] = "D-CM Test Site", },

["region2"] = {["mission"] = "Mission4", ["state"] = 0, ["name"] = "Test Site Delta", },

["region3"] = {["mission"] = "Mission5", ["state"] = 0, ["name"] = "Hardened Shale", },

["region4"] = {["mission"] = "Mission3", ["state"] = 0, ["name"] = "Countdown Ridge", },

["region5"] = {["mission"] = "Mission1", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 1, ["iTeamTurn"] = 1, ["iState"] = 0, ["sMission"] = "Mission1", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Crack_Briefing_CEO_Sand_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 3, ["aiDelay"] = 0.000000, ["aiSeed"] = 1129244237, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "any21", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 39, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 16, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 41, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 17, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 5 ), ["terrain"] = 7, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 17, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 29, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 0, },
{["loc"] = Point( 2, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 46, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 51, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 7, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 0, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 90, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 65, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 70, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 6 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_battery1", ["people1"] = 19, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 7, },
{["loc"] = Point( 5, 2 ), ["terrain"] = 0, },
{["loc"] = Point( 5, 3 ), ["terrain"] = 7, },
{["loc"] = Point( 5, 4 ), ["terrain"] = 7, },
{["loc"] = Point( 6, 3 ), ["terrain"] = 0, },
},
["pod"] = Point(5,6), ["spawns"] = {"Burnbug1", "Scorpion1", },
["spawn_ids"] = {687, 688, },
["spawn_points"] = {Point(7,3), Point(5,3), },
["zones"] = {},
["tags"] = {"generic", "any_sector", },


["pawn1"] = {["type"] = "PunchMech", ["name"] = "", ["id"] = 0, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 1, ["iBonusPower"] = 0, ["iUsedBonus"] = 1, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Prime_Punchmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {1, 2, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 5, ["skill2"] = 3, ["exp"] = 0, ["level"] = 2, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,2), ["last_location"] = Point(4,3), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 0, ["piTarget"] = Point(5,3), ["piOrigin"] = Point(4,3), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,3), },


["pawn2"] = {["type"] = "TankMech", ["name"] = "", ["id"] = 1, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Brute_Tankmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Fenrir", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 5, ["skill2"] = 1, ["exp"] = 5, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(2,3), ["last_location"] = Point(6,6), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 1, ["piTarget"] = Point(5,2), ["piOrigin"] = Point(6,6), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(6,5), },


["pawn3"] = {["type"] = "ArtiMech", ["name"] = "", ["id"] = 2, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 1, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Ranged_Artillerymech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,4), ["last_location"] = Point(5,2), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 2, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(5,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,4), },


["pawn4"] = {["type"] = "Centipede1", ["name"] = "", ["id"] = 681, ["mech"] = false, ["offset"] = 0, ["primary"] = "CentipedeAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,3), ["last_location"] = Point(6,2), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 5, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 4, ["iOwner"] = 681, ["piTarget"] = Point(5,3), ["piOrigin"] = Point(6,3), ["piQueuedShot"] = Point(5,3), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,3), },


["pawn5"] = {["type"] = "Jelly_Regen1", ["name"] = "", ["id"] = 682, ["mech"] = false, ["offset"] = 3, ["not_attacking"] = true, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,2), ["last_location"] = Point(6,2), ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 5, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 4, ["iOwner"] = 682, ["piTarget"] = Point(-2147483647,-2147483647), ["piOrigin"] = Point(7,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },
["pawn_count"] = 5, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Restricted Area", },

["region6"] = {["mission"] = "", ["state"] = 2, ["name"] = "Thunderbolt Grid", ["objectives"] = {["0"] = {["text"] = "Mission_Force_Obj", ["param1"] = "", ["param2"] = "", ["value"] = 0, ["potential"] = 1, ["category"] = 0, },
["1"] = {["text"] = "Bonus_Simple_Kill_Five", ["param1"] = "5", ["param2"] = "", ["value"] = 1, ["potential"] = 1, ["category"] = 0, },
["2"] = {["text"] = "Bonus_Simple_Asset", ["param1"] = "Str_Power_Name", ["param2"] = "", ["value"] = 1, ["potential"] = 1, ["category"] = 1, },
},
},

["region7"] = {["mission"] = "Mission6", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission6", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Cataclysm_Briefing_CEO_Sand_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 686501620, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "sand5", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 7, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 44, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 7, },
{["loc"] = Point( 1, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 55, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 7, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 2, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 39, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 39, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 137, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 7, },
{["loc"] = Point( 2, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 3, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 110, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_recycle1", ["people1"] = 76, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 7, },
{["loc"] = Point( 3, 5 ), ["terrain"] = 7, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 7, },
{["loc"] = Point( 3, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 7, },
{["loc"] = Point( 4, 4 ), ["terrain"] = 7, },
{["loc"] = Point( 4, 5 ), ["terrain"] = 7, },
{["loc"] = Point( 4, 6 ), ["terrain"] = 7, },
{["loc"] = Point( 4, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 5 ), ["terrain"] = 7, },
{["loc"] = Point( 5, 6 ), ["terrain"] = 7, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 1 ), ["terrain"] = 7, },
{["loc"] = Point( 6, 4 ), ["terrain"] = 7, },
{["loc"] = Point( 6, 5 ), ["terrain"] = 7, },
{["loc"] = Point( 6, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 4 ), ["terrain"] = 7, },
{["loc"] = Point( 7, 5 ), ["terrain"] = 7, },
{["loc"] = Point( 7, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 3, },
},
["spawns"] = {"Centipede1", "Scorpion1", },
["spawn_ids"] = {683, 684, },
["spawn_points"] = {Point(6,2), Point(5,3), },
["zones"] = {},
["tags"] = {"generic", "sand", "cataclysm", },
["pawn_count"] = 0, ["blocked_points"] = {Point(7,0), Point(7,1), Point(7,2), Point(7,3), Point(7,4), Point(7,5), Point(7,6), Point(7,7), },
["blocked_type"] = {2, 2, 2, 2, 2, 2, 2, 2, },
},


},
["state"] = 1, ["name"] = "Mercury Ridge", },
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
[32] = "Ranged_BackShot", 
[33] = "Ranged_Ice", 
[34] = "Ranged_SmokeBlast", 
[35] = "Ranged_Fireball", 
[36] = "Ranged_RainingVolley", 
[37] = "Ranged_Wide", 
[38] = "Science_Pullmech", 
[39] = "Science_Gravwell", 
[40] = "Science_Swap", 
[41] = "Science_AcidShot", 
[42] = "Science_Confuse", 
[43] = "Science_Shield", 
[44] = "Science_FireBeam", 
[45] = "Science_FreezeBeam", 
[46] = "Science_LocalShield", 
[47] = "Science_PushBeam", 
[48] = "Support_Boosters", 
[49] = "Support_Smoke", 
[50] = "Support_Destruct", 
[51] = "DeploySkill_ShieldTank", 
[52] = "DeploySkill_Tank", 
[53] = "DeploySkill_AcidTank", 
[54] = "DeploySkill_PullTank", 
[55] = "Support_Force", 
[56] = "Support_SmokeDrop", 
[57] = "Support_Repair", 
[58] = "Support_Missiles", 
[59] = "Support_Wind", 
[60] = "Support_Blizzard", 
[61] = "Passive_FlameImmune", 
[62] = "Passive_Electric", 
[63] = "Passive_Leech", 
[64] = "Passive_MassRepair", 
[65] = "Passive_Defenses", 
[66] = "Passive_Burrows", 
[67] = "Passive_AutoShields", 
[68] = "Passive_Psions", 
[69] = "Passive_Boosters", 
[70] = "Passive_Medical", 
[71] = "Passive_FriendlyFire", 
[72] = "Passive_CritDefense", 
[73] = "Prime_Flamespreader", 
[74] = "Prime_WayTooBig", 
[75] = "Prime_PrismLaser", 
[76] = "Prime_TC_Punt", 
[77] = "Prime_TC_BendBeam", 
[78] = "Prime_TC_Feint", 
[79] = "Prime_KO_Crack", 
[80] = "Brute_KickBack", 
[81] = "Brute_Fracture", 
[82] = "Brute_PierceShot", 
[83] = "Brute_TC_GuidedMissile", 
[84] = "Brute_TC_Ricochet", 
[85] = "Brute_TC_DoubleShot", 
[86] = "Brute_KO_Combo", 
[87] = "Ranged_Crack", 
[88] = "Ranged_DeployBomb", 
[89] = "Ranged_Arachnoid", 
[90] = "Ranged_SmokeFire", 
[91] = "Ranged_TC_BounceShot", 
[92] = "Ranged_TC_DoubleArt", 
[93] = "Ranged_KO_Combo", 
[94] = "Science_RainingFire", 
[95] = "Science_MassShift", 
[96] = "Science_TelePush", 
[97] = "Science_TC_Control", 
[98] = "Science_TC_Enrage", 
[99] = "Science_TC_SwapOther", 
[100] = "Science_KO_Crack", 
[101] = "Support_Confuse", 
[102] = "Support_GridDefense", 
[103] = "Support_Waterdrill", 
[104] = "Support_TC_GridAtk", 
[105] = "Support_TC_Bombline", 
[106] = "Support_KO_GridCharger", 
[107] = "Passive_HealingSmoke", 
[108] = "Passive_FireBoost", 
[109] = "Passive_VoidShock" 
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
[18] = "Science_Shield", 
[19] = "Science_FireBeam", 
[20] = "Science_FreezeBeam", 
[21] = "Science_LocalShield", 
[22] = "Science_PushBeam", 
[23] = "Support_Boosters", 
[24] = "Support_Smoke", 
[25] = "Support_Destruct", 
[26] = "DeploySkill_ShieldTank", 
[27] = "DeploySkill_Tank", 
[28] = "DeploySkill_AcidTank", 
[29] = "DeploySkill_PullTank", 
[30] = "Support_Force", 
[31] = "Support_SmokeDrop", 
[32] = "Support_Repair", 
[33] = "Support_Missiles", 
[34] = "Support_Wind", 
[35] = "Support_Blizzard", 
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
[47] = "Passive_CritDefense", 
[48] = "Prime_WayTooBig", 
[49] = "Prime_PrismLaser", 
[50] = "Prime_TC_BendBeam", 
[51] = "Prime_TC_Feint", 
[52] = "Brute_Fracture", 
[53] = "Brute_TC_GuidedMissile", 
[54] = "Brute_KO_Combo", 
[55] = "Ranged_TC_BounceShot", 
[56] = "Ranged_TC_DoubleArt", 
[57] = "Ranged_KO_Combo", 
[58] = "Science_TelePush", 
[59] = "Science_TC_Enrage", 
[60] = "Support_Confuse", 
[61] = "Support_GridDefense", 
[62] = "Support_Waterdrill", 
[63] = "Support_TC_GridAtk", 
[64] = "Support_TC_Bombline", 
[65] = "Support_KO_GridCharger", 
[66] = "Passive_HealingSmoke", 
[67] = "Passive_FireBoost", 
[68] = "Passive_VoidShock" 
}, 
["PilotDeck"] = { 
[1] = "Pilot_Soldier", 
[2] = "Pilot_Youth", 
[3] = "Pilot_Warrior", 
[4] = "Pilot_Medic", 
[5] = "Pilot_Genius", 
[6] = "Pilot_Miner", 
[7] = "Pilot_Recycler", 
[8] = "Pilot_Assassin", 
[9] = "Pilot_Leader", 
[10] = "Pilot_Repairman", 
[11] = "Pilot_Arrogant", 
[12] = "Pilot_Caretaker", 
[13] = "Pilot_Chemical", 
[14] = "Pilot_Delusional" 
}, 
["SeenPilots"] = { 
[1] = "Pilot_Original", 
[2] = "Pilot_Pinnacle", 
[3] = "Pilot_Rust", 
[4] = "Pilot_Aquatic", 
[5] = "Pilot_Hotshot" 
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
} 
}, 
["Bosses"] = { 
[1] = "Mission_ScorpionBoss", 
[2] = "Mission_JellyBoss", 
[3] = "Mission_BotBoss", 
[4] = "Mission_StarfishBoss" 
}, 
["Island"] = 2, 
["Missions"] = { 
[1] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 4, 
["curr_weakRatio"] = { 
[1] = 1, 
[2] = 1 
}, 
["curr_upgradeRatio"] = { 
[1] = 0, 
[2] = 1 
}, 
["upgrade_streak"] = 0, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Jelly_Regen"] = 1, 
["Scorpion"] = 1, 
["Burnbug"] = 1, 
["Centipede"] = 1 
} 
}, 
["AssetId"] = "Str_Battery", 
["BonusObjs"] = { 
[1] = 4, 
[2] = 1 
}, 
["AssetLoc"] = Point( 4, 6 ), 
["ID"] = "Mission_Crack", 
["VoiceEvents"] = { 
}, 
["LiveEnvironment"] = { 
["Path"] = { 
[1] = Point( 4, 7 ), 
[2] = Point( 5, 7 ), 
[3] = Point( 5, 6 ), 
[4] = Point( 5, 5 ), 
[5] = Point( 5, 4 ), 
[6] = Point( 5, 3 ), 
[7] = Point( 5, 2 ), 
[8] = Point( 5, 1 ), 
[9] = Point( 5, 0 ) 
}, 
["Locations"] = { 
[1] = Point( 4, 7 ), 
[2] = Point( 5, 7 ), 
[3] = Point( 5, 6 ) 
}, 
["Planned"] = { 
[1] = Point( 4, 7 ), 
[2] = Point( 5, 7 ), 
[3] = Point( 5, 6 ) 
}, 
["Index"] = 4, 
["FirstTile"] = Point( 4, 7 ), 
["StartEffect"] = true, 
["EndEffect"] = true 
}, 
["PowerStart"] = 7 
}, 
[2] = { 
["BonusObjs"] = { 
[1] = 6, 
[2] = 1 
}, 
["Mountains"] = 0, 
["KilledVek"] = 6, 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 7, 
["curr_weakRatio"] = { 
[1] = 3, 
[2] = 3 
}, 
["curr_upgradeRatio"] = { 
[1] = 0, 
[2] = 3 
}, 
["upgrade_streak"] = 0, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Centipede"] = 2, 
["Scorpion"] = 2, 
["Jelly_Regen"] = 1, 
["Burnbug"] = 3 
} 
}, 
["LiveEnvironment"] = { 
}, 
["AssetId"] = "Str_Power", 
["AssetLoc"] = Point( 0, 1 ), 
["ID"] = "Mission_Force", 
["VoiceEvents"] = { 
}, 
["DiffMod"] = 2, 
["PowerStart"] = 7 
}, 
[3] = { 
["ID"] = "Mission_Volatile", 
["BonusObjs"] = { 
[1] = 1 
}, 
["AssetId"] = "Str_Power" 
}, 
[4] = { 
["ID"] = "Mission_Solar", 
["BonusObjs"] = { 
[1] = 8 
}, 
["DiffMod"] = 2 
}, 
[5] = { 
["ID"] = "Mission_Filler", 
["BonusObjs"] = { 
[1] = 1 
}, 
["AssetId"] = "Str_Robotics" 
}, 
[6] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 2, 
["curr_weakRatio"] = { 
[1] = 3, 
[2] = 3 
}, 
["curr_upgradeRatio"] = { 
[1] = 0, 
[2] = 3 
}, 
["upgrade_streak"] = 0, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Centipede"] = 1, 
["Scorpion"] = 1 
} 
}, 
["AssetId"] = "Str_Nimbus", 
["AssetLoc"] = Point( 3, 2 ), 
["ID"] = "Mission_Cataclysm", 
["VoiceEvents"] = { 
}, 
["LiveEnvironment"] = { 
}, 
["BonusObjs"] = { 
[1] = 3, 
[2] = 1 
} 
}, 
[7] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 2, 
["curr_weakRatio"] = { 
[1] = 3, 
[2] = 3 
}, 
["curr_upgradeRatio"] = { 
[1] = 0, 
[2] = 3 
}, 
["upgrade_streak"] = 0, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Centipede"] = 1, 
["Hornet"] = 1 
} 
}, 
["BonusObjs"] = { 
[1] = 7 
}, 
["DebrisId"] = { 
[1] = 672, 
[2] = 673 
}, 
["ID"] = "Mission_Terratide", 
["VoiceEvents"] = { 
}, 
["DiffMod"] = 1, 
["LiveEnvironment"] = { 
} 
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
[1] = "Scarab", 
[2] = "Bouncer", 
[3] = "Firefly", 
[4] = "Jelly_Spider", 
[5] = "Starfish", 
[6] = "Blobber", 
["island"] = 1 
}, 
[2] = { 
[1] = "Hornet", 
[2] = "Scorpion", 
[3] = "Burnbug", 
[4] = "Jelly_Regen", 
[5] = "Centipede", 
[6] = "Spider", 
["island"] = 2 
}, 
[3] = { 
[1] = "Mosquito", 
[2] = "Leaper", 
[3] = "Firefly", 
[4] = "Jelly_Boost", 
[5] = "Crab", 
[6] = "Beetle", 
["island"] = 3 
}, 
[4] = { 
[1] = "Mosquito", 
[2] = "Bouncer", 
[3] = "Leaper", 
[4] = "Jelly_Health", 
[5] = "Digger", 
[6] = "Shaman", 
["island"] = 4 
} 
} 
}

 

SquadData = {
["money"] = 1, ["cores"] = 0, ["bIsFavor"] = false, ["repairs"] = 0, ["CorpReward"] = {CreateEffect({weapon = "Science_SmokeDefense",}), CreateEffect({skill1 = "Invulnerable",skill2 = "Closer",pilot = "Pilot_Hotshot",}), CreateEffect({power = 2,}), },
["RewardClaimed"] = false, 
["skip_pawns"] = true, 

["storage_size"] = 4, ["storage_3"] = {["weapon"] = "Ranged_Dual", },
["CorpStore"] = {CreateEffect({weapon = "Support_Refrigerate",money = -2,}), CreateEffect({weapon = "Science_Repulse",money = -2,}), CreateEffect({weapon = "Ranged_ScatterShot",money = -2,}), CreateEffect({stock = 0,}), CreateEffect({money = -3,stock = -1,cores = 1,}), CreateEffect({money = -1,power = 1,stock = -1,}), },
["island_store_count"] = 1, ["store_undo_size"] = 0, }
 

