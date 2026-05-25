GameData = {["save_version"] = 1, ["language"] = 1, ["network"] = 6, ["networkMax"] = 7, ["overflow"] = 4, ["seed"] = 1279794679, ["new_enemies"] = 1, ["new_missions"] = 1, ["new_equip"] = 1, ["difficulty"] = 0, ["new_abilities"] = 1, ["ach_info"] = {["squad"] = "Pinnacle_A", ["trackers"] = {["Detritus_B_2"] = 0, ["Global_Challenge_Power"] = 0, ["Archive_A_1"] = 0, ["Archive_B_2"] = 0, ["Rust_A_2"] = 0, ["Rust_A_3"] = 0, ["Pinnacle_A_3"] = 0, ["Archive_B_1"] = 0, ["Pinnacle_B_3"] = 0, ["Detritus_B_1"] = 0, ["Pinnacle_B_1"] = 0, ["Global_Island_Mechs"] = 0, ["Global_Island_Building"] = 0, ["Squad_Mist_1"] = 0, ["Squad_Bomber_2"] = 0, ["Squad_Spiders_1"] = 0, ["Squad_Mist_2"] = 0, ["Squad_Heat_1"] = 0, ["Squad_Cataclysm_1"] = 0, ["Squad_Cataclysm_2"] = 0, ["Squad_Cataclysm_3"] = 0, },
},


["current"] = {["score"] = 4671, ["time"] = 34749004.000000, ["kills"] = 57, ["damage"] = 0, ["failures"] = 5, ["difficulty"] = 0, ["victory"] = false, ["islands"] = 2, ["squad"] = 2, 
["mechs"] = {"LaserMech", "ChargeMech", "ScienceMech", },
["colors"] = {2, 2, 2, },
["weapons"] = {"Prime_Lasermech_A", "", "Brute_Beetle_A", "", "Science_Pullmech", "Science_Shield_A", },
["pilot0"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Leda", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 5, ["skill2"] = 0, ["exp"] = 50, ["level"] = 2, ["travel"] = 1, ["final"] = 1, ["starting"] = true, ["last_end"] = 1, },
["pilot1"] = {["id"] = "Pilot_Rust", ["name"] = "Amelia Montes", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 0, ["exp"] = 20, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot2"] = {["id"] = "Pilot_Recycler", ["name"] = "Prospero", ["name_id"] = "Pilot_Recycler_Name", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 9, ["exp"] = 5, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = false, ["power"] = {0, },
},
},
["current_squad"] = 2, ["undosave"] = true, }
 

RegionData = {
["sector"] = 2, ["island"] = 3, ["secret"] = false, 
["island0"] = {["corporation"] = "Corp_Grass", ["id"] = 0, ["secured"] = false, },
["island1"] = {["corporation"] = "Corp_Desert", ["id"] = 1, ["secured"] = true, },
["island2"] = {["corporation"] = "Corp_Snow", ["id"] = 2, ["secured"] = true, },
["island3"] = {["corporation"] = "Corp_Factory", ["id"] = 3, ["secured"] = false, },

["turn"] = 0, ["iTower"] = 0, ["quest_tracker"] = 0, ["quest_id"] = 0, ["podRewards"] = {CreateEffect({weapon = "random",cores = 1,}), },


["region0"] = {["mission"] = "", ["state"] = 2, ["name"] = "Corporate HQ", ["objectives"] = {},
},

["region1"] = {["mission"] = "Mission6", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 1, ["iTeamTurn"] = 1, ["iState"] = 0, ["sMission"] = "Mission6", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Power_Briefing_CEO_Acid_1", ["podReward"] = CreateEffect({cores = 1,}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 3, ["aiDelay"] = 0.000000, ["aiSeed"] = 2146790512, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "any4", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 80, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 43, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_power1", ["people1"] = 72, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 2, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_power1", ["people1"] = 81, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 82, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 0, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 0, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 142, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 2 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 3 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 5 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 1 ), ["terrain"] = 0, ["pod"] = 1, },
{["loc"] = Point( 5, 2 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 5, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 5, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 1 ), ["terrain"] = 0, },
{["loc"] = Point( 6, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 3 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 7, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 3, },
},
["pod"] = Point(5,1), ["spawns"] = {"Leaper1", "Mosquito1", },
["spawn_ids"] = {264, 265, },
["spawn_points"] = {Point(6,4), Point(6,2), },
["zones"] = {["satellite"] = {Point( 3, 4 ), Point( 4, 4 ), Point( 4, 2 ), Point( 4, 1 ), Point( 5, 1 ), Point( 5, 2 ), Point( 5, 4 ), },
},
["tags"] = {"generic", "any_sector", "satellite", },


["pawn1"] = {["type"] = "LaserMech", ["name"] = "", ["id"] = 0, ["mech"] = true, ["offset"] = 2, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 1, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Prime_Lasermech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {1, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Leda", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 5, ["skill2"] = 0, ["exp"] = 50, ["level"] = 2, ["travel"] = 1, ["final"] = 1, ["starting"] = true, ["last_end"] = 1, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 5, ["max_health"] = 5, ["undo_state"] = {["bBoosted"] = true, ["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(2,3), ["last_location"] = Point(6,3), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 0, ["piTarget"] = Point(5,3), ["piOrigin"] = Point(5,4), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,3), },


["pawn2"] = {["type"] = "ChargeMech", ["name"] = "", ["id"] = 1, ["mech"] = true, ["offset"] = 2, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 1, ["iBonusPower"] = 0, ["iUsedBonus"] = 1, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {2, },
["healthPower"] = {0, },
["primary"] = "Brute_Beetle", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {1, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Rust", ["name"] = "Amelia Montes", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 0, ["exp"] = 20, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,2), ["last_location"] = Point(6,3), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 1, ["piTarget"] = Point(4,3), ["piOrigin"] = Point(4,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,3), },


["pawn3"] = {["type"] = "ScienceMech", ["name"] = "", ["id"] = 2, ["mech"] = true, ["offset"] = 2, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 2, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Science_Pullmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["secondary"] = "Science_Shield", ["secondary_power"] = {},
["secondary_power_class"] = false, ["secondary_mod1"] = {1, 1, },
["secondary_mod2"] = {0, 0, },
["secondary_damaged"] = false, ["secondary_starting"] = true, ["secondary_uses"] = 3, ["pilot"] = {["id"] = "Pilot_Recycler", ["name"] = "Prospero", ["name_id"] = "Pilot_Recycler_Name", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 9, ["exp"] = 5, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = false, ["power"] = {0, },
},
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,4), ["last_location"] = Point(6,3), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 2, ["piTarget"] = Point(2,2), ["piOrigin"] = Point(2,3), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(2,2), },


["pawn4"] = {["type"] = "Digger1", ["name"] = "", ["id"] = 254, ["mech"] = false, ["offset"] = 0, ["primary"] = "DiggerAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,4), ["last_location"] = Point(5,4), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 5, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 11, ["iOwner"] = 254, ["piTarget"] = Point(4,4), ["piOrigin"] = Point(4,4), ["piQueuedShot"] = Point(4,4), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,4), },


["pawn5"] = {["type"] = "Jelly_Boost1", ["name"] = "", ["id"] = 255, ["mech"] = false, ["offset"] = 7, ["not_attacking"] = true, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,2), ["last_location"] = Point(4,3), ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 5, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 11, ["iOwner"] = 255, ["piTarget"] = Point(-2147483647,-2147483647), ["piOrigin"] = Point(5,3), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn6"] = {["type"] = "Burnbug2", ["name"] = "", ["id"] = 256, ["mech"] = false, ["offset"] = 1, ["primary"] = "BurnbugAtk2", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 4, ["max_health"] = 4, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,1), ["last_location"] = Point(6,2), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 5, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 11, ["iOwner"] = 256, ["piTarget"] = Point(5,1), ["piOrigin"] = Point(6,1), ["piQueuedShot"] = Point(5,1), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,1), },


["pawn7"] = {["type"] = "Wall", ["name"] = "", ["id"] = 261, ["mech"] = false, ["offset"] = 0, ["owner"] = 254, ["iTeamId"] = 2, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 1, ["max_health"] = 1, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,3), ["last_location"] = Point(-1,-1), ["iCurrentWeapon"] = 0, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 0, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 261, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn8"] = {["type"] = "Wall", ["name"] = "", ["id"] = 262, ["mech"] = false, ["offset"] = 0, ["owner"] = 254, ["iTeamId"] = 2, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["bAcid"] = true, ["health"] = 1, ["max_health"] = 1, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,4), ["last_location"] = Point(-1,-1), ["iCurrentWeapon"] = 0, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 0, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 262, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn9"] = {["type"] = "Wall", ["name"] = "", ["id"] = 263, ["mech"] = false, ["offset"] = 0, ["owner"] = 254, ["iTeamId"] = 2, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 1, ["max_health"] = 1, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,5), ["last_location"] = Point(-1,-1), ["iCurrentWeapon"] = 0, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 0, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 263, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },
["pawn_count"] = 9, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "The Heap", },

["region2"] = {["mission"] = "Mission3", ["state"] = 0, ["name"] = "Venting Center", },

["region3"] = {["mission"] = "Mission1", ["state"] = 0, ["name"] = "Chemical Field A", },

["region4"] = {["mission"] = "Mission4", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission4", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_AcidTank_Briefing_CEO_Acid_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 1378978260, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "anyAE10", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 30, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 67, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 33, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 3 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 68, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 2, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 62, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 3, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 138, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 3, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 2 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 4, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 5, 1 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 5, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 102, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 5, 5 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 5, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 5 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 3, },
},
["spawns"] = {"Burnbug1", "Spider1", "Burnbug2", },
["spawn_ids"] = {258, 259, 260, },
["spawn_points"] = {Point(7,5), Point(6,3), Point(6,2), },
["zones"] = {},
["tags"] = {"generic", "any_sector", },


["pawn1"] = {["type"] = "Acid_Tank", ["name"] = "", ["id"] = 257, ["mech"] = false, ["offset"] = 0, ["primary"] = "Acid_Tank_Attack", ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Detritus", ["name"] = "Liam Huang", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 9, ["skill2"] = 7, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = false, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 1, ["max_health"] = 1, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(2,4), ["last_location"] = Point(-1,-1), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 0, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 257, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },
["pawn_count"] = 1, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "The Landfill", },

["region5"] = {["mission"] = "Mission2", ["state"] = 0, ["name"] = "Containment Zone D", },

["region6"] = {["mission"] = "Mission5", ["state"] = 0, ["name"] = "Downtown", },

["region7"] = {["mission"] = "Mission7", ["state"] = 0, ["name"] = "Disposal Vault", },
["iBattleRegion"] = 1, }
 

GAME = { 
["WeaponDeck"] = { 
[31] = "Ranged_BackShot", 
[2] = "Prime_Lightning", 
[8] = "Prime_Flamethrower", 
[32] = "Ranged_SmokeBlast", 
[33] = "Ranged_Fireball", 
[34] = "Ranged_RainingVolley", 
[35] = "Ranged_Wide", 
[9] = "Prime_Areablast", 
[36] = "Ranged_Dual", 
[37] = "Science_Gravwell", 
[38] = "Science_Swap", 
[39] = "Science_Repulse", 
[10] = "Prime_Spear", 
[40] = "Science_AcidShot", 
[41] = "Science_Confuse", 
[42] = "Science_SmokeDefense", 
[43] = "Science_FireBeam", 
[11] = "Prime_Leap", 
[44] = "Science_FreezeBeam", 
[45] = "Science_LocalShield", 
[46] = "Science_PushBeam", 
[3] = "Prime_ShieldBash", 
[12] = "Prime_SpinFist", 
[48] = "Support_Smoke", 
[47] = "Support_Boosters", 
[49] = "Support_Refrigerate", 
[63] = "Passive_Burrows", 
[50] = "Support_Destruct", 
[22] = "Brute_Splitshot", 
[51] = "DeploySkill_AcidTank", 
[13] = "Prime_Smash", 
[52] = "Support_Force", 
[67] = "Passive_Medical", 
[53] = "Support_SmokeDrop", 
[71] = "Prime_Flamespreader", 
[54] = "Support_Repair", 
[75] = "Prime_TC_BendBeam", 
[55] = "Support_Missiles", 
[14] = "Brute_Tankmech", 
[56] = "Support_Wind", 
[25] = "Ranged_Artillerymech", 
[57] = "Support_Blizzard", 
[78] = "Brute_KickBack", 
[58] = "Passive_FlameImmune", 
[27] = "Ranged_Defensestrike", 
[59] = "Passive_Electric", 
[15] = "Brute_Jetmech", 
[60] = "Passive_Leech", 
[7] = "Prime_Shift", 
[61] = "Passive_MassRepair", 
[28] = "Ranged_Rocket", 
[62] = "Passive_Defenses", 
[1] = "Prime_Punchmech", 
[4] = "Prime_Rockmech", 
[16] = "Brute_Mirrorshot", 
[64] = "Passive_AutoShields", 
[65] = "Passive_Psions", 
[66] = "Passive_Boosters", 
[17] = "Brute_PhaseShot", 
[68] = "Passive_FriendlyFire", 
[69] = "Passive_ForceAmp", 
[70] = "Passive_CritDefense", 
[18] = "Brute_Grapple", 
[72] = "Prime_WayTooBig", 
[73] = "Prime_PrismLaser", 
[74] = "Prime_TC_Punt", 
[19] = "Brute_Shrapnel", 
[76] = "Prime_TC_Feint", 
[77] = "Prime_KO_Crack", 
[5] = "Prime_RightHook", 
[79] = "Brute_Fracture", 
[80] = "Brute_PierceShot", 
[81] = "Brute_TC_GuidedMissile", 
[82] = "Brute_TC_Ricochet", 
[83] = "Brute_TC_DoubleShot", 
[84] = "Brute_KO_Combo", 
[85] = "Ranged_DeployBomb", 
[86] = "Ranged_Arachnoid", 
[87] = "Ranged_SmokeFire", 
[88] = "Ranged_KO_Combo", 
[89] = "Science_RainingFire", 
[90] = "Science_MassShift", 
[91] = "Science_TelePush", 
[92] = "Science_Placer", 
[93] = "Science_TC_Control", 
[94] = "Science_TC_SwapOther", 
[95] = "Science_KO_Crack", 
[96] = "Support_Confuse", 
[97] = "Support_GridDefense", 
[98] = "Support_TC_GridAtk", 
[99] = "Support_TC_Bombline", 
[100] = "Support_KO_GridCharger", 
[101] = "Passive_HealingSmoke", 
[102] = "Passive_FireBoost", 
[103] = "Passive_PlayerTurnShield", 
[104] = "Passive_VoidShock", 
[26] = "Ranged_Rockthrow", 
[29] = "Ranged_Ignite", 
[24] = "Brute_Sonic", 
[6] = "Prime_RocketPunch", 
[23] = "Brute_Bombrun", 
[30] = "Ranged_ScatterShot", 
[21] = "Brute_Heavyrocket", 
[20] = "Brute_Shockblast" 
}, 
["PodWeaponDeck"] = { 
[31] = "Passive_FlameImmune", 
[2] = "Prime_Spear", 
[8] = "Brute_Heavyrocket", 
[32] = "Passive_Electric", 
[33] = "Passive_Leech", 
[34] = "Passive_MassRepair", 
[35] = "Passive_Defenses", 
[9] = "Brute_Bombrun", 
[36] = "Passive_Burrows", 
[37] = "Passive_AutoShields", 
[38] = "Passive_Psions", 
[39] = "Passive_Boosters", 
[10] = "Brute_Sonic", 
[40] = "Passive_Medical", 
[41] = "Passive_FriendlyFire", 
[42] = "Passive_ForceAmp", 
[43] = "Passive_CritDefense", 
[11] = "Ranged_SmokeBlast", 
[44] = "Prime_WayTooBig", 
[45] = "Prime_PrismLaser", 
[46] = "Prime_TC_BendBeam", 
[3] = "Prime_Leap", 
[12] = "Ranged_Fireball", 
[48] = "Brute_Fracture", 
[49] = "Brute_TC_GuidedMissile", 
[50] = "Brute_KO_Combo", 
[51] = "Ranged_KO_Combo", 
[13] = "Ranged_RainingVolley", 
[52] = "Science_TelePush", 
[53] = "Science_Placer", 
[54] = "Support_Confuse", 
[55] = "Support_GridDefense", 
[14] = "Ranged_Dual", 
[56] = "Support_TC_GridAtk", 
[57] = "Support_TC_Bombline", 
[58] = "Support_KO_GridCharger", 
[59] = "Passive_HealingSmoke", 
[15] = "Science_SmokeDefense", 
[60] = "Passive_FireBoost", 
[61] = "Passive_PlayerTurnShield", 
[62] = "Passive_VoidShock", 
[1] = "Prime_Areablast", 
[4] = "Prime_SpinFist", 
[16] = "Science_FireBeam", 
[17] = "Science_FreezeBeam", 
[18] = "Science_LocalShield", 
[19] = "Science_PushBeam", 
[5] = "Prime_Smash", 
[20] = "Support_Boosters", 
[21] = "Support_Smoke", 
[22] = "Support_Refrigerate", 
[23] = "Support_Destruct", 
[6] = "Brute_Grapple", 
[24] = "DeploySkill_AcidTank", 
[25] = "Support_Force", 
[26] = "Support_SmokeDrop", 
[27] = "Support_Repair", 
[7] = "Brute_Shockblast", 
[28] = "Support_Missiles", 
[29] = "Support_Wind", 
[47] = "Prime_TC_Feint", 
[30] = "Support_Blizzard" 
}, 
["PilotDeck"] = { 
[11] = "Pilot_Repairman", 
[13] = "Pilot_Chemical", 
[7] = "Pilot_Hotshot", 
[1] = "Pilot_Original", 
[2] = "Pilot_Soldier", 
[8] = "Pilot_Genius", 
[9] = "Pilot_Miner", 
[5] = "Pilot_Aquatic", 
[10] = "Pilot_Leader", 
[3] = "Pilot_Youth", 
[6] = "Pilot_Medic", 
[12] = "Pilot_Caretaker", 
[4] = "Pilot_Warrior" 
}, 
["SeenPilots"] = { 
[1] = "Pilot_Pinnacle", 
[2] = "Pilot_Rust", 
[3] = "Pilot_Archive", 
[4] = "Pilot_Assassin", 
[5] = "Pilot_Arrogant", 
[6] = "Pilot_Recycler", 
[7] = "Pilot_Delusional" 
}, 
["PodDeck"] = { 
[1] = { 
["cores"] = 1 
}, 
[2] = { 
["cores"] = 1, 
["weapon"] = "random" 
}, 
[4] = { 
["cores"] = 1, 
["weapon"] = "random" 
}, 
[5] = { 
["cores"] = 1, 
["pilot"] = "random" 
}, 
[3] = { 
["cores"] = 1, 
["weapon"] = "random" 
}, 
[6] = { 
["cores"] = 1, 
["pilot"] = "random" 
} 
}, 
["Bosses"] = { 
[1] = "Mission_DungBoss", 
[2] = "Mission_BurnbugBoss", 
[4] = "Mission_BlobBoss", 
[3] = "Mission_BouncerBoss" 
}, 
["Island"] = 4, 
["Missions"] = { 
[1] = { 
["ID"] = "Mission_Missiles", 
["BonusObjs"] = { 
[1] = 1 
}, 
["DiffMod"] = 2, 
["AssetId"] = "Str_Power" 
}, 
[2] = { 
["ID"] = "Mission_AcidStorm", 
["BonusObjs"] = { 
[1] = 3, 
[2] = 1 
}, 
["DiffMod"] = 2, 
["AssetId"] = "Str_Power" 
}, 
[3] = { 
["ID"] = "Mission_Belt", 
["BonusObjs"] = { 
[1] = 6 
}, 
["DiffMod"] = 1 
}, 
[4] = { 
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
["upgrade_streak"] = 1, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Burnbug"] = 2, 
["Spider"] = 1 
} 
}, 
["BonusObjs"] = { 
}, 
["ID"] = "Mission_AcidTank", 
["VoiceEvents"] = { 
}, 
["LiveEnvironment"] = { 
} 
}, 
[5] = { 
["ID"] = "Mission_Civilians", 
["BonusObjs"] = { 
} 
}, 
[6] = { 
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
["Jelly_Boost"] = 1, 
["Burnbug"] = 1, 
["Digger"] = 1, 
["Leaper"] = 1, 
["Mosquito"] = 1 
} 
}, 
["LiveEnvironment"] = { 
}, 
["Criticals"] = { 
[1] = Point( 1, 4 ), 
[2] = Point( 2, 1 ) 
}, 
["ID"] = "Mission_Power", 
["VoiceEvents"] = { 
}, 
["BonusObjs"] = { 
}, 
["PowerStart"] = 6 
}, 
[7] = { 
["ID"] = "Mission_Teleporter", 
["BonusObjs"] = { 
[1] = 7, 
[2] = 1 
}, 
["AssetId"] = "Str_Nimbus" 
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
[6] = "Blobber", 
[2] = "Bouncer", 
[3] = "Scorpion", 
[1] = "Mosquito", 
[4] = "Jelly_Armor", 
[5] = "Dung", 
["island"] = 1 
}, 
[2] = { 
[6] = "Starfish", 
[2] = "Scarab", 
[3] = "Firefly", 
[1] = "Leaper", 
[4] = "Jelly_Fire", 
[5] = "Burrower", 
["island"] = 2 
}, 
[4] = { 
[6] = "Digger", 
[2] = "Leaper", 
[3] = "Burnbug", 
[1] = "Mosquito", 
[4] = "Jelly_Boost", 
[5] = "Spider", 
["island"] = 4 
}, 
[3] = { 
[6] = "Beetle", 
[2] = "Burnbug", 
[3] = "Bouncer", 
[1] = "Hornet", 
[4] = "Jelly_Spider", 
[5] = "Crab", 
["island"] = 3 
} 
} 
}

 

SquadData = {
["money"] = 0, ["cores"] = 0, ["bIsFavor"] = false, ["repairs"] = 0, ["CorpReward"] = {CreateEffect({weapon = "Ranged_TC_DoubleArt",}), CreateEffect({skill1 = "Reactor",skill2 = "Invulnerable",pilot = "Pilot_Delusional",}), CreateEffect({power = 2,}), },
["RewardClaimed"] = false, 
["skip_pawns"] = true, 

["storage_size"] = 4, ["storage_3"] = {["weapon"] = "Ranged_Ice", },
["CorpStore"] = {CreateEffect({weapon = "Ranged_Crack",money = -2,}), CreateEffect({weapon = "Prime_Sword",money = -2,}), CreateEffect({weapon = "Science_TC_Enrage",money = -2,}), CreateEffect({weapon = "DeploySkill_ShieldTank",money = -2,}), CreateEffect({money = -3,stock = -1,cores = 1,}), CreateEffect({money = -1,power = 1,stock = -1,}), },
["island_store_count"] = 2, ["store_undo_size"] = 0, }
 

