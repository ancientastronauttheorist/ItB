GameData = {["save_version"] = 1, ["language"] = 1, ["network"] = 7, ["networkMax"] = 7, ["overflow"] = 13, ["seed"] = 814530270, ["new_enemies"] = 0, ["new_missions"] = 0, ["new_equip"] = 0, ["difficulty"] = 0, ["new_abilities"] = 0, ["ach_info"] = {["squad"] = "Rust_B", ["trackers"] = {["Detritus_B_2"] = 0, ["Global_Challenge_Power"] = 0, ["Archive_A_1"] = 0, ["Archive_B_2"] = 0, ["Rust_A_2"] = 0, ["Rust_A_3"] = 0, ["Pinnacle_A_3"] = 0, ["Archive_B_1"] = 0, ["Pinnacle_B_3"] = 0, ["Detritus_B_1"] = 0, ["Pinnacle_B_1"] = 0, ["Global_Island_Mechs"] = 0, ["Global_Island_Building"] = 0, ["Squad_Mist_1"] = 0, ["Squad_Bomber_2"] = 0, ["Squad_Spiders_1"] = 0, ["Squad_Mist_2"] = 0, ["Squad_Heat_1"] = 0, ["Squad_Cataclysm_1"] = 0, ["Squad_Cataclysm_2"] = 0, ["Squad_Cataclysm_3"] = 0, },
},


["current"] = {["score"] = 4848, ["time"] = 14785081.000000, ["kills"] = 39, ["damage"] = 0, ["failures"] = 5, ["difficulty"] = 0, ["victory"] = false, ["islands"] = 2, ["squad"] = 5, 
["mechs"] = {"FlameMech", "IgniteMech", "TeleMech", },
["colors"] = {5, 5, 5, },
["weapons"] = {"Prime_Flamethrower", "Passive_FlameImmune", "Ranged_Ignite", "Support_Wind_A", "Science_Swap", "", },
["pilot0"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 0, ["exp"] = 50, ["level"] = 2, ["travel"] = 1, ["final"] = 1, ["starting"] = true, ["last_end"] = 2, },
["pilot1"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Fenrir", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 1, ["exp"] = 14, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot2"] = {["id"] = "Pilot_Assassin", ["name"] = "Abe Isamu", ["name_id"] = "Pilot_Assassin_Name", ["renamed"] = false, ["skill1"] = 2, ["skill2"] = 0, ["exp"] = 15, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = false, },
},
["current_squad"] = 5, }
 

RegionData = {
["sector"] = 2, ["island"] = 3, ["secret"] = false, 
["island0"] = {["corporation"] = "Corp_Grass", ["id"] = 0, ["secured"] = true, },
["island1"] = {["corporation"] = "Corp_Desert", ["id"] = 1, ["secured"] = true, },
["island2"] = {["corporation"] = "Corp_Snow", ["id"] = 2, ["secured"] = false, },
["island3"] = {["corporation"] = "Corp_Factory", ["id"] = 3, ["secured"] = false, },

["turn"] = 0, ["iTower"] = 4, ["quest_tracker"] = 0, ["quest_id"] = 0, ["podRewards"] = {CreateEffect({weapon = "random",cores = 1,}), },


["region0"] = {["mission"] = "Mission3", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission3", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Block_Briefing_CEO_Acid_2", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 481867871, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "acid10", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 1 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 0, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 45, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 61, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 62, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 69, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 3, 0 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 84, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 60, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_power1", ["people1"] = 27, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 4, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 92, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 6, 6 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 0, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 7, 1 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 7, 2 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 7, 4 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 7, 6 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 0, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
},
["spawns"] = {"Scarab2", "Scarab1", "Firefly1", },
["spawn_ids"] = {475, 476, 477, },
["spawn_points"] = {Point(7,3), Point(6,4), Point(5,3), },
["zones"] = {["pistons"] = {Point( 4, 0 ), Point( 6, 0 ), Point( 5, 6 ), Point( 4, 6 ), Point( 3, 6 ), Point( 2, 6 ), Point( 5, 7 ), Point( 1, 6 ), Point( 5, 0 ), },
},
["tags"] = {"generic", "acid", "acid_pool", "pistons", },
["pawn_count"] = 0, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Chemical Field A", },

["region1"] = {["mission"] = "Mission7", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 1, ["iTeamTurn"] = 1, ["iState"] = 0, ["sMission"] = "Mission7", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Belt_Briefing_CEO_Acid_1", ["podReward"] = CreateEffect({cores = 1,}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 3, ["aiDelay"] = 0.000000, ["aiSeed"] = 1843583910, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "any22", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 1 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 1, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 67, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 43, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 2, 2 ), ["terrain"] = 0, ["custom"] = "conveyor0.png", },
{["loc"] = Point( 2, 3 ), ["terrain"] = 0, ["custom"] = "conveyor0.png", },
{["loc"] = Point( 2, 5 ), ["terrain"] = 0, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 32, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 78, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 3, 3 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 3, 5 ), ["terrain"] = 0, },
{["loc"] = Point( 3, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 0 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 2 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 3 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 4, 4 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_power1", ["people1"] = 41, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 4, 5 ), ["terrain"] = 3, },
{["loc"] = Point( 4, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 4, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 134, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 5, 3 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 5, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 105, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 5, 5 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 6 ), ["terrain"] = 0, ["pod"] = 1, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 1 ), ["terrain"] = 0, },
{["loc"] = Point( 6, 3 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 6, 4 ), ["terrain"] = 0, ["custom"] = "conveyor0.png", },
{["loc"] = Point( 6, 5 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 4 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 7, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 4, },
},
["pod"] = Point(5,6), ["spawns"] = {"Scorpion1", "Firefly2", },
["spawn_ids"] = {486, 487, },
["spawn_points"] = {Point(6,0), Point(7,0), },
["zones"] = {["enemy"] = {Point( 5, 3 ), Point( 5, 2 ), Point( 6, 3 ), Point( 6, 2 ), Point( 7, 2 ), Point( 7, 1 ), Point( 6, 1 ), Point( 7, 3 ), Point( 7, 0 ), Point( 6, 0 ), Point( 5, 0 ), },
},
["tags"] = {"generic", "any_sector", },


["pawn1"] = {["type"] = "FlameMech", ["name"] = "", ["id"] = 0, ["mech"] = true, ["offset"] = 5, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Prime_Flamethrower", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["secondary"] = "Passive_FlameImmune", ["secondary_power"] = {},
["secondary_power_class"] = false, ["secondary_mod1"] = {0, },
["secondary_mod2"] = {0, },
["secondary_damaged"] = false, ["secondary_starting"] = true, ["secondary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 0, ["exp"] = 50, ["level"] = 2, ["travel"] = 1, ["final"] = 1, ["starting"] = true, ["last_end"] = 2, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 5, ["max_health"] = 5, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,5), ["last_location"] = Point(3,5), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 0, ["piTarget"] = Point(5,5), ["piOrigin"] = Point(6,5), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,5), },


["pawn2"] = {["type"] = "IgniteMech", ["name"] = "", ["id"] = 1, ["mech"] = true, ["offset"] = 5, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 2, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {1, },
["healthPower"] = {0, },
["primary"] = "Ranged_Ignite", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["secondary"] = "Support_Wind", ["secondary_power"] = {},
["secondary_power_class"] = false, ["secondary_mod1"] = {1, },
["secondary_mod2"] = {0, },
["secondary_damaged"] = false, ["secondary_starting"] = true, ["secondary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Fenrir", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 1, ["exp"] = 14, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 5, ["max_health"] = 5, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(1,4), ["last_location"] = Point(1,4), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 1, ["piTarget"] = Point(4,5), ["piOrigin"] = Point(2,5), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,5), },


["pawn3"] = {["type"] = "TeleMech", ["name"] = "", ["id"] = 2, ["mech"] = true, ["offset"] = 5, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Science_Swap", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Assassin", ["name"] = "Abe Isamu", ["name_id"] = "Pilot_Assassin_Name", ["renamed"] = false, ["skill1"] = 2, ["skill2"] = 0, ["exp"] = 15, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = false, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(2,5), ["last_location"] = Point(2,5), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 2, ["piTarget"] = Point(3,5), ["piOrigin"] = Point(4,5), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,5), },


["pawn4"] = {["type"] = "Scarab1", ["name"] = "", ["id"] = 478, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScarabAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,3), ["last_location"] = Point(6,2), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 5, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 478, ["piTarget"] = Point(1,3), ["piOrigin"] = Point(6,3), ["piQueuedShot"] = Point(1,3), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(1,3), },


["pawn5"] = {["type"] = "Firefly1", ["name"] = "", ["id"] = 479, ["mech"] = false, ["offset"] = 0, ["primary"] = "FireflyAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,1), ["last_location"] = Point(6,0), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 5, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 479, ["piTarget"] = Point(5,1), ["piOrigin"] = Point(6,1), ["piQueuedShot"] = Point(5,1), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,1), },


["pawn6"] = {["type"] = "Digger1", ["name"] = "", ["id"] = 480, ["mech"] = false, ["offset"] = 0, ["primary"] = "DiggerAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,1), ["last_location"] = Point(4,2), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 5, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 480, ["piTarget"] = Point(4,1), ["piOrigin"] = Point(4,1), ["piQueuedShot"] = Point(4,1), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,1), },


["pawn7"] = {["type"] = "Wall", ["name"] = "", ["id"] = 484, ["mech"] = false, ["offset"] = 0, ["owner"] = 480, ["iTeamId"] = 2, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 1, ["max_health"] = 1, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,0), ["last_location"] = Point(-1,-1), ["iCurrentWeapon"] = 0, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 0, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 484, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn8"] = {["type"] = "Wall", ["name"] = "", ["id"] = 485, ["mech"] = false, ["offset"] = 0, ["owner"] = 480, ["iTeamId"] = 2, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 1, ["max_health"] = 1, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,2), ["last_location"] = Point(-1,-1), ["iCurrentWeapon"] = 0, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 0, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 485, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },
["pawn_count"] = 8, ["blocked_points"] = {Point(1,1), Point(2,1), Point(2,2), Point(2,3), Point(3,3), Point(4,3), Point(5,3), Point(6,3), Point(6,4), Point(7,4), },
["blocked_type"] = {2, 2, 2, 2, 2, 2, 2, 2, 2, 2, },
},


},
["state"] = 1, ["name"] = "Disposal Vault", },

["region2"] = {["mission"] = "Mission4", ["state"] = 0, ["name"] = "Venting Center", },

["region3"] = {["mission"] = "Mission1", ["state"] = 0, ["name"] = "The Heap", },

["region4"] = {["mission"] = "", ["state"] = 2, ["name"] = "Corporate HQ", ["objectives"] = {},
},

["region5"] = {["mission"] = "Mission6", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission6", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Teleporter_Briefing_CEO_Acid_2", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 69098031, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "anyAE29", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 27, ["people2"] = 0, ["health_max"] = 1, ["shield"] = true, },
{["loc"] = Point( 0, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 31, ["people2"] = 0, ["health_max"] = 1, ["shield"] = true, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 65, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 51, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 2 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 3, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 128, ["people2"] = 0, ["health_max"] = 2, ["shield"] = true, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 69, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 3, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 5 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 0, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 82, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 5, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 47, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 6, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 3 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 2 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 7, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 4, },
},
["teleports"] = {Point( 5, 3 ), Point( 2, 5 ), Point( 3, 2 ), Point( 6, 4 ), },
["tele_history"] = {-1, -1, -1, -1, },
["spawns"] = {"Scorpion2", "Scorpion1", "Firefly1", },
["spawn_ids"] = {481, 482, 483, },
["spawn_points"] = {Point(6,5), Point(7,4), Point(7,3), },
["zones"] = {},
["tags"] = {"generic", "any_sector", },
["pawn_count"] = 0, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Nanite Farms", },

["region6"] = {["mission"] = "Mission2", ["state"] = 0, ["name"] = "Nano Silos", },

["region7"] = {["mission"] = "Mission5", ["state"] = 0, ["name"] = "The Landfill", },
["iBattleRegion"] = 1, }
 

GAME = { 
["WeaponDeck"] = { 
[31] = "Ranged_Ice", 
[2] = "Prime_Lightning", 
[8] = "Prime_Shift", 
[32] = "Ranged_Fireball", 
[33] = "Ranged_RainingVolley", 
[34] = "Ranged_Wide", 
[35] = "Ranged_Dual", 
[9] = "Prime_Areablast", 
[36] = "Science_Gravwell", 
[37] = "Science_Repulse", 
[38] = "Science_AcidShot", 
[39] = "Science_Confuse", 
[10] = "Prime_Spear", 
[40] = "Science_SmokeDefense", 
[41] = "Science_Shield", 
[42] = "Science_FireBeam", 
[43] = "Science_FreezeBeam", 
[11] = "Prime_Leap", 
[44] = "Science_LocalShield", 
[45] = "Science_PushBeam", 
[46] = "Support_Boosters", 
[3] = "Prime_Lasermech", 
[12] = "Prime_SpinFist", 
[48] = "Support_Refrigerate", 
[49] = "Support_Destruct", 
[50] = "DeploySkill_ShieldTank", 
[51] = "DeploySkill_PullTank", 
[13] = "Prime_Sword", 
[52] = "Support_Force", 
[53] = "Support_SmokeDrop", 
[54] = "Support_Repair", 
[55] = "Support_Missiles", 
[14] = "Brute_Tankmech", 
[56] = "Support_Blizzard", 
[57] = "Passive_Leech", 
[58] = "Passive_MassRepair", 
[59] = "Passive_Defenses", 
[15] = "Brute_Jetmech", 
[60] = "Passive_AutoShields", 
[61] = "Passive_Boosters", 
[62] = "Passive_Medical", 
[1] = "Prime_Punchmech", 
[4] = "Prime_ShieldBash", 
[16] = "Brute_Mirrorshot", 
[64] = "Passive_ForceAmp", 
[65] = "Passive_CritDefense", 
[17] = "Brute_PhaseShot", 
[18] = "Brute_Grapple", 
[19] = "Brute_Shrapnel", 
[5] = "Prime_Rockmech", 
[20] = "Brute_Sniper", 
[21] = "Brute_Shockblast", 
[22] = "Brute_Beetle", 
[23] = "Brute_Unstable", 
[6] = "Prime_RightHook", 
[24] = "Brute_Splitshot", 
[25] = "Brute_Bombrun", 
[26] = "Ranged_Artillerymech", 
[27] = "Ranged_Rockthrow", 
[7] = "Prime_RocketPunch", 
[28] = "Ranged_Defensestrike", 
[29] = "Ranged_Rocket", 
[30] = "Ranged_ScatterShot", 
[63] = "Passive_FriendlyFire", 
[47] = "Support_Smoke" 
}, 
["PodWeaponDeck"] = { 
[27] = "Support_Force", 
[2] = "Prime_Spear", 
[38] = "Passive_FriendlyFire", 
[3] = "Prime_Leap", 
[4] = "Prime_SpinFist", 
[5] = "Prime_Sword", 
[6] = "Brute_Grapple", 
[7] = "Brute_Sniper", 
[8] = "Brute_Shockblast", 
[10] = "Brute_Bombrun", 
[12] = "Ranged_Fireball", 
[14] = "Ranged_Dual", 
[16] = "Science_Shield", 
[20] = "Science_PushBeam", 
[24] = "Support_Destruct", 
[28] = "Support_SmokeDrop", 
[32] = "Passive_Leech", 
[40] = "Passive_CritDefense", 
[33] = "Passive_MassRepair", 
[17] = "Science_FireBeam", 
[21] = "Support_Boosters", 
[25] = "DeploySkill_ShieldTank", 
[29] = "Support_Repair", 
[34] = "Passive_Defenses", 
[9] = "Brute_Beetle", 
[11] = "Ranged_Ice", 
[13] = "Ranged_RainingVolley", 
[15] = "Science_SmokeDefense", 
[18] = "Science_FreezeBeam", 
[22] = "Support_Smoke", 
[26] = "DeploySkill_PullTank", 
[30] = "Support_Missiles", 
[36] = "Passive_Boosters", 
[37] = "Passive_Medical", 
[39] = "Passive_ForceAmp", 
[35] = "Passive_AutoShields", 
[1] = "Prime_Areablast", 
[19] = "Science_LocalShield", 
[23] = "Support_Refrigerate", 
[31] = "Support_Blizzard" 
}, 
["PilotDeck"] = { 
[6] = "Pilot_Leader", 
[2] = "Pilot_Youth", 
[3] = "Pilot_Medic", 
[1] = "Pilot_Soldier", 
[4] = "Pilot_Hotshot", 
[5] = "Pilot_Recycler", 
[7] = "Pilot_Repairman" 
}, 
["SeenPilots"] = { 
[6] = "Pilot_Miner", 
[2] = "Pilot_Pinnacle", 
[8] = "Pilot_Warrior", 
[3] = "Pilot_Archive", 
[1] = "Pilot_Original", 
[4] = "Pilot_Aquatic", 
[5] = "Pilot_Assassin", 
[7] = "Pilot_Genius" 
}, 
["PodDeck"] = { 
[6] = { 
["cores"] = 1, 
["pilot"] = "random" 
}, 
[2] = { 
["cores"] = 1 
}, 
[3] = { 
["cores"] = 1, 
["weapon"] = "random" 
}, 
[1] = { 
["cores"] = 1 
}, 
[4] = { 
["cores"] = 1, 
["weapon"] = "random" 
}, 
[5] = { 
["cores"] = 1, 
["weapon"] = "random" 
} 
}, 
["Bosses"] = { 
[1] = "Mission_BeetleBoss", 
[2] = "Mission_HornetBoss", 
[4] = "Mission_JellyBoss", 
[3] = "Mission_ScorpionBoss" 
}, 
["Enemies"] = { 
[1] = { 
[6] = "Blobber", 
[2] = "Firefly", 
[3] = "Scarab", 
[1] = "Hornet", 
[4] = "Jelly_Armor", 
[5] = "Digger", 
["island"] = 1 
}, 
[2] = { 
[6] = "Centipede", 
[2] = "Firefly", 
[3] = "Hornet", 
[1] = "Leaper", 
[4] = "Jelly_Regen", 
[5] = "Beetle", 
["island"] = 2 
}, 
[4] = { 
[6] = "Centipede", 
[2] = "Scarab", 
[3] = "Firefly", 
[1] = "Scorpion", 
[4] = "Jelly_Health", 
[5] = "Digger", 
["island"] = 4 
}, 
[3] = { 
[6] = "Beetle", 
[2] = "Scarab", 
[3] = "Hornet", 
[1] = "Leaper", 
[4] = "Jelly_Explode", 
[5] = "Spider", 
["island"] = 3 
} 
}, 
["Missions"] = { 
[1] = { 
["ID"] = "Mission_AcidTank", 
["BonusObjs"] = { 
[1] = 1 
}, 
["DiffMod"] = 2, 
["AssetId"] = "Str_Research" 
}, 
[2] = { 
["ID"] = "Mission_Train", 
["BonusObjs"] = { 
[1] = 1 
}, 
["DiffMod"] = 2, 
["AssetId"] = "Str_Battery" 
}, 
[3] = { 
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
["Scarab"] = 2 
} 
}, 
["AssetId"] = "Str_Power", 
["AssetLoc"] = Point( 3, 6 ), 
["ID"] = "Mission_Survive", 
["VoiceEvents"] = { 
}, 
["LiveEnvironment"] = { 
}, 
["BonusObjs"] = { 
[1] = 5, 
[2] = 1 
} 
}, 
[4] = { 
["ID"] = "Mission_Disposal", 
["BonusObjs"] = { 
} 
}, 
[5] = { 
["ID"] = "Mission_Power", 
["BonusObjs"] = { 
} 
}, 
[6] = { 
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
["Scorpion"] = 2 
} 
}, 
["BonusObjs"] = { 
[1] = 3 
}, 
["ID"] = "Mission_Teleporter", 
["VoiceEvents"] = { 
}, 
["DiffMod"] = 1, 
["LiveEnvironment"] = { 
} 
}, 
[7] = { 
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
["upgrade_streak"] = 1, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Firefly"] = 2, 
["Scarab"] = 1, 
["Scorpion"] = 1, 
["Digger"] = 1 
} 
}, 
["AssetId"] = "Str_Power", 
["BonusObjs"] = { 
[1] = 4, 
[2] = 1 
}, 
["AssetLoc"] = Point( 4, 4 ), 
["ID"] = "Mission_Belt", 
["VoiceEvents"] = { 
}, 
["LiveEnvironment"] = { 
["Belts"] = { 
[1] = Point( 1, 1 ), 
[2] = Point( 2, 1 ), 
[3] = Point( 2, 2 ), 
[4] = Point( 2, 3 ), 
[5] = Point( 3, 3 ), 
[6] = Point( 4, 3 ), 
[7] = Point( 5, 3 ), 
[8] = Point( 6, 3 ), 
[9] = Point( 6, 4 ), 
[10] = Point( 7, 4 ) 
}, 
["BeltsDir"] = { 
[1] = 3, 
[2] = 3, 
[3] = 0, 
[4] = 0, 
[5] = 3, 
[6] = 3, 
[7] = 3, 
[8] = 3, 
[9] = 0, 
[10] = 3 
} 
}, 
["PowerStart"] = 7 
}, 
[8] = { 
["ID"] = "Mission_JellyBoss", 
["BonusObjs"] = { 
[1] = 1 
}, 
["AssetId"] = "Str_Tower" 
} 
}, 
["Island"] = 4 
}

 

SquadData = {
["money"] = 0, ["cores"] = 0, ["bIsFavor"] = false, ["repairs"] = 0, ["CorpReward"] = {CreateEffect({weapon = "Brute_Sonic",}), CreateEffect({skill1 = "Move",skill2 = "Grid",pilot = "Pilot_Warrior",}), CreateEffect({power = 2,}), },
["RewardClaimed"] = false, 
["skip_pawns"] = true, 

["storage_size"] = 4, ["storage_3"] = {["pilot"] = true, ["id"] = "Pilot_Aquatic", ["name"] = "Archimedes", ["name_id"] = "Pilot_Aquatic_Name", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 2, ["exp"] = 15, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = false, ["power"] = {0, },
},
["CorpStore"] = {CreateEffect({weapon = "DeploySkill_AcidTank",money = -2,}), CreateEffect({weapon = "Prime_Smash",money = -2,}), CreateEffect({weapon = "Science_Pullmech",money = -2,}), CreateEffect({weapon = "Passive_Psions",money = -2,}), CreateEffect({money = -3,stock = -1,cores = 1,}), CreateEffect({money = -1,power = 1,stock = -1,}), },
["island_store_count"] = 2, ["store_undo_size"] = 0, }
 

