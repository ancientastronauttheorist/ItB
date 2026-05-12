GameData = {["save_version"] = 1, ["language"] = 1, ["network"] = 5, ["networkMax"] = 7, ["overflow"] = 0, ["seed"] = 1325065165, ["new_enemies"] = 1, ["new_missions"] = 1, ["new_equip"] = 1, ["difficulty"] = 2, ["new_abilities"] = 1, ["ach_info"] = {["squad"] = "Rust_A", ["trackers"] = {["Detritus_B_2"] = 0, ["Global_Challenge_Power"] = 0, ["Archive_A_1"] = 0, ["Archive_B_2"] = 0, ["Rust_A_2"] = 1, ["Rust_A_3"] = 1, ["Pinnacle_A_3"] = 0, ["Archive_B_1"] = 0, ["Pinnacle_B_3"] = 0, ["Detritus_B_1"] = 0, ["Pinnacle_B_1"] = 0, ["Global_Island_Mechs"] = 0, ["Global_Island_Building"] = 0, ["Squad_Mist_1"] = 0, ["Squad_Bomber_2"] = 0, ["Squad_Spiders_1"] = 0, ["Squad_Mist_2"] = 0, ["Squad_Heat_1"] = 0, ["Squad_Cataclysm_1"] = 0, ["Squad_Cataclysm_2"] = 0, ["Squad_Cataclysm_3"] = 0, },
},


["current"] = {["score"] = 7060, ["time"] = 18301724.000000, ["kills"] = 40, ["damage"] = 0, ["failures"] = 2, ["difficulty"] = 2, ["victory"] = false, ["islands"] = 1, ["squad"] = 1, 
["mechs"] = {"JetMech", "RocketMech", "PulseMech", },
["colors"] = {1, 1, 1, },
["weapons"] = {"Brute_Jetmech", "", "Ranged_Rocket", "Passive_Electric", "Science_Repulse", "", },
["pilot0"] = {["id"] = "Pilot_Arrogant", ["name"] = "Kai Miller", ["name_id"] = "Pilot_Arrogant_Name", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 2, ["exp"] = 7, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = false, },
["pilot1"] = {["id"] = "Pilot_Detritus", ["name"] = "Amelia Smith", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 8, ["skill2"] = 5, ["exp"] = 19, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot2"] = {["id"] = "Pilot_Archive", ["name"] = "Maria Torcasio", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 6, ["skill2"] = 3, ["exp"] = 3, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
},
["current_squad"] = 1, ["undosave"] = true, }
 

RegionData = {
["sector"] = 1, ["island"] = 3, ["secret"] = false, 
["island0"] = {["corporation"] = "Corp_Grass", ["id"] = 0, ["secured"] = false, },
["island1"] = {["corporation"] = "Corp_Desert", ["id"] = 1, ["secured"] = true, },
["island2"] = {["corporation"] = "Corp_Snow", ["id"] = 2, ["secured"] = false, },
["island3"] = {["corporation"] = "Corp_Factory", ["id"] = 3, ["secured"] = false, },

["turn"] = 0, ["iTower"] = 0, ["quest_tracker"] = 0, ["quest_id"] = 0, ["podRewards"] = {CreateEffect({cores = 1,}), },


["region0"] = {["mission"] = "", ["state"] = 2, ["name"] = "Corporate HQ", ["objectives"] = {},
},

["region1"] = {["mission"] = "Mission7", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission7", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Barrels_Briefing_CEO_Acid_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 490610290, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "any23", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 171, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 129, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 161, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 139, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 270, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 3 ), ["terrain"] = 4, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 338, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 3 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 4 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 292, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 6, 6 ), ["terrain"] = 0, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 4, },
},
["rain"] = 3, ["rain_type"] = 1, ["spawns"] = {"Jelly_Regen1", "Moth1", "Spider2", },
["spawn_ids"] = {87, 88, 89, },
["spawn_points"] = {Point(6,5), Point(6,3), Point(5,5), },
["zones"] = {["satellite"] = {Point( 5, 4 ), Point( 4, 1 ), Point( 5, 1 ), Point( 6, 6 ), },
},
["tags"] = {"generic", "any_sector", "mountain", "satellite", },


["pawn1"] = {["type"] = "AcidVat", ["name"] = "", ["id"] = 85, ["mech"] = false, ["offset"] = 0, ["death_seed"] = 1419914893, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,6), ["last_location"] = Point(-1,-1), ["bMinor"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 2074442310, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 85, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn2"] = {["type"] = "AcidVat", ["name"] = "", ["id"] = 86, ["mech"] = false, ["offset"] = 0, ["death_seed"] = 2135716250, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,1), ["last_location"] = Point(-1,-1), ["bMinor"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 0, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 86, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },
["pawn_count"] = 2, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Containment Zone J", },

["region2"] = {["mission"] = "Mission2", ["state"] = 0, ["name"] = "Chemical Field A", },

["region3"] = {["mission"] = "Mission3", ["state"] = 0, ["name"] = "Venting Center", },

["region4"] = {["mission"] = "Mission5", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 2, ["iTeamTurn"] = 1, ["iState"] = 0, ["sMission"] = "Mission5", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Belt_Briefing_CEO_Acid_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 3, ["aiDelay"] = 0.000000, ["aiSeed"] = 788809171, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "acid6", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 0, 1 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 0, 3 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 0, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_bar1", ["people1"] = 171, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 2 ), ["terrain"] = 1, ["populated"] = 1, ["grappled"] = 1, ["people1"] = 140, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 1, 5 ), ["terrain"] = 2, ["health_max"] = 1, ["health_min"] = 0, ["rubble_type"] = 0, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 0, ["grapple_targets"] = {1, 3, },
},
{["loc"] = Point( 2, 4 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 2, 5 ), ["terrain"] = 0, ["custom"] = "conveyor0.png", },
{["loc"] = Point( 2, 7 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 0, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 1, ["populated"] = 1, ["grappled"] = 1, ["people1"] = 174, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 3, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 263, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 5 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 3, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 331, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 0 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 0, ["smoke"] = 1, ["smoke"] = 1, },
{["loc"] = Point( 4, 2 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 5 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 4, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 292, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 5, 1 ), ["terrain"] = 0, },
{["loc"] = Point( 5, 2 ), ["terrain"] = 0, },
{["loc"] = Point( 5, 3 ), ["terrain"] = 0, },
{["loc"] = Point( 5, 5 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 6, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 1 ), ["terrain"] = 0, },
{["loc"] = Point( 6, 5 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 6, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 3 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 0, },
{["loc"] = Point( 7, 4 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 7, 5 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 7, 7 ), ["terrain"] = 3, },
},
["pod"] = Point(4,2), ["spawns"] = {"Scorpion1", },
["spawn_ids"] = {121, },
["spawn_points"] = {Point(7,2), },
["zones"] = {},
["tags"] = {"generic", "acid", "acid_pool", },


["pawn1"] = {["type"] = "JetMech", ["name"] = "", ["id"] = 0, ["mech"] = true, ["offset"] = 1, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 1, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {2, },
["healthPower"] = {0, },
["primary"] = "Brute_Jetmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Arrogant", ["name"] = "Kai Miller", ["name_id"] = "Pilot_Arrogant_Name", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 2, ["exp"] = 7, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = false, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["bAcid"] = true, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,1), ["last_location"] = Point(3,1), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 2, ["iTurnsRemaining"] = 3, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 0, ["piTarget"] = Point(5,1), ["piOrigin"] = Point(3,1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,1), },


["pawn2"] = {["type"] = "RocketMech", ["name"] = "", ["id"] = 1, ["mech"] = true, ["offset"] = 1, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Ranged_Rocket", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["secondary"] = "Passive_Electric", ["secondary_power"] = {},
["secondary_power_class"] = false, ["secondary_mod1"] = {0, 0, 0, },
["secondary_mod2"] = {0, },
["secondary_damaged"] = false, ["secondary_starting"] = true, ["secondary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Detritus", ["name"] = "Amelia Smith", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 8, ["skill2"] = 5, ["exp"] = 19, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 5, ["max_health"] = 5, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,0), ["last_location"] = Point(3,0), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 2, ["iTurnsRemaining"] = 3, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 1, ["piTarget"] = Point(4,2), ["piOrigin"] = Point(4,0), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,2), },


["pawn3"] = {["type"] = "PulseMech", ["name"] = "", ["id"] = 2, ["mech"] = true, ["offset"] = 1, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 1, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {1, },
["healthPower"] = {0, },
["primary"] = "Science_Repulse", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Archive", ["name"] = "Maria Torcasio", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 6, ["skill2"] = 3, ["exp"] = 3, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(2,5), ["last_location"] = Point(3,5), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 2, ["iTurnsRemaining"] = 3, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 2, ["piTarget"] = Point(3,5), ["piOrigin"] = Point(3,5), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,5), },


["pawn4"] = {["type"] = "Moth2", ["name"] = "", ["id"] = 90, ["mech"] = false, ["offset"] = 1, ["primary"] = "MothAtk2", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 5, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,1), ["last_location"] = Point(4,1), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 2, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 90, ["piTarget"] = Point(3,3), ["piOrigin"] = Point(3,1), ["piQueuedShot"] = Point(3,3), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,3), },


["pawn5"] = {["type"] = "Moth1", ["name"] = "", ["id"] = 91, ["mech"] = false, ["offset"] = 0, ["primary"] = "MothAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,2), ["last_location"] = Point(5,3), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 2, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 91, ["piTarget"] = Point(3,2), ["piOrigin"] = Point(5,2), ["piQueuedShot"] = Point(3,2), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,2), },


["pawn6"] = {["type"] = "Moth1", ["name"] = "", ["id"] = 92, ["mech"] = false, ["offset"] = 0, ["primary"] = "MothAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 1, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,1), ["last_location"] = Point(5,1), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 2, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 92, ["piTarget"] = Point(1,1), ["piOrigin"] = Point(6,1), ["piQueuedShot"] = Point(1,1), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(1,1), },


["pawn7"] = {["type"] = "Spider1", ["name"] = "", ["id"] = 93, ["mech"] = false, ["offset"] = 0, ["not_attacking"] = true, ["primary"] = "SpiderAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,2), ["last_location"] = Point(5,2), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 3, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 93, ["piTarget"] = Point(2,2), ["piOrigin"] = Point(4,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(2,2), },


["pawn8"] = {["type"] = "Bouncer2", ["name"] = "", ["id"] = 94, ["mech"] = false, ["offset"] = 1, ["not_attacking"] = true, ["primary"] = "BouncerAtk2", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 4, ["max_health"] = 4, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,3), ["last_location"] = Point(5,2), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 0, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 94, ["piTarget"] = Point(6,2), ["piOrigin"] = Point(7,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn9"] = {["type"] = "WebbEgg1", ["name"] = "", ["id"] = 120, ["mech"] = false, ["offset"] = 0, ["owner"] = 93, ["primary"] = "WebeggHatch1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 1, ["max_health"] = 1, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(2,2), ["last_location"] = Point(2,2), ["bMinor"] = true, ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 3, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 120, ["piTarget"] = Point(2,2), ["piOrigin"] = Point(2,2), ["piQueuedShot"] = Point(2,2), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(2,2), },
["pawn_count"] = 9, ["blocked_points"] = {Point(1,4), Point(2,4), Point(2,5), Point(3,5), Point(4,5), Point(5,5), Point(6,5), Point(7,5), },
["blocked_type"] = {2, 2, 2, 2, 2, 2, 2, 2, },
},


},
["state"] = 1, ["name"] = "Venting Fields", },

["region5"] = {["mission"] = "Mission6", ["state"] = 0, ["name"] = "Disposal Vault", },

["region6"] = {["mission"] = "Mission1", ["state"] = 0, ["name"] = "The Heap", },

["region7"] = {["mission"] = "Mission4", ["state"] = 0, ["name"] = "Waste Chambers", },
["iBattleRegion"] = 4, }
 

GAME = { 
["WeaponDeck"] = { 
[31] = "Ranged_Ignite", 
[2] = "Prime_Lightning", 
[8] = "Prime_Shift", 
[32] = "Ranged_ScatterShot", 
[33] = "Ranged_BackShot", 
[34] = "Ranged_SmokeBlast", 
[35] = "Ranged_Fireball", 
[9] = "Prime_Flamethrower", 
[36] = "Ranged_RainingVolley", 
[37] = "Ranged_Wide", 
[38] = "Ranged_Dual", 
[39] = "Science_Pullmech", 
[10] = "Prime_Areablast", 
[40] = "Science_Gravwell", 
[41] = "Science_Swap", 
[42] = "Science_AcidShot", 
[43] = "Science_Confuse", 
[11] = "Prime_Spear", 
[44] = "Science_SmokeDefense", 
[75] = "Prime_TC_Punt", 
[45] = "Science_Shield", 
[46] = "Science_FireBeam", 
[78] = "Prime_KO_Crack", 
[3] = "Prime_Lasermech", 
[12] = "Prime_Leap", 
[48] = "Science_LocalShield", 
[79] = "Brute_KickBack", 
[49] = "Science_PushBeam", 
[83] = "Brute_TC_DoubleShot", 
[50] = "Support_Boosters", 
[51] = "Support_Refrigerate", 
[13] = "Prime_SpinFist", 
[52] = "DeploySkill_ShieldTank", 
[53] = "DeploySkill_Tank", 
[87] = "Ranged_SmokeFire", 
[54] = "DeploySkill_AcidTank", 
[91] = "Science_RainingFire", 
[55] = "DeploySkill_PullTank", 
[14] = "Prime_Sword", 
[56] = "Support_Force", 
[107] = "Passive_VoidShock", 
[57] = "Support_SmokeDrop", 
[94] = "Science_Placer", 
[58] = "Support_Repair", 
[95] = "Science_TC_Control", 
[59] = "Support_Missiles", 
[15] = "Prime_Smash", 
[60] = "Support_Wind", 
[99] = "Support_Confuse", 
[61] = "Support_Blizzard", 
[103] = "Support_TC_Bombline", 
[62] = "Passive_FlameImmune", 
[1] = "Prime_Punchmech", 
[4] = "Prime_ShieldBash", 
[16] = "Brute_Tankmech", 
[64] = "Passive_MassRepair", 
[65] = "Passive_Defenses", 
[66] = "Passive_AutoShields", 
[17] = "Brute_Mirrorshot", 
[68] = "Passive_Medical", 
[69] = "Passive_FriendlyFire", 
[70] = "Passive_ForceAmp", 
[18] = "Brute_PhaseShot", 
[72] = "Prime_Flamespreader", 
[73] = "Prime_WayTooBig", 
[74] = "Prime_PrismLaser", 
[19] = "Brute_Grapple", 
[76] = "Prime_TC_BendBeam", 
[77] = "Prime_TC_Feint", 
[5] = "Prime_Rockmech", 
[20] = "Brute_Shrapnel", 
[80] = "Brute_Fracture", 
[81] = "Brute_PierceShot", 
[82] = "Brute_TC_Ricochet", 
[21] = "Brute_Sniper", 
[84] = "Brute_KO_Combo", 
[85] = "Ranged_DeployBomb", 
[86] = "Ranged_Arachnoid", 
[22] = "Brute_Shockblast", 
[88] = "Ranged_TC_BounceShot", 
[89] = "Ranged_TC_DoubleArt", 
[90] = "Ranged_KO_Combo", 
[23] = "Brute_Beetle", 
[92] = "Science_MassShift", 
[93] = "Science_TelePush", 
[6] = "Prime_RightHook", 
[24] = "Brute_Unstable", 
[96] = "Science_TC_Enrage", 
[97] = "Science_TC_SwapOther", 
[98] = "Science_KO_Crack", 
[25] = "Brute_Heavyrocket", 
[100] = "Support_GridDefense", 
[101] = "Support_Waterdrill", 
[102] = "Support_TC_GridAtk", 
[26] = "Brute_Splitshot", 
[104] = "Passive_HealingSmoke", 
[105] = "Passive_FireBoost", 
[106] = "Passive_PlayerTurnShield", 
[27] = "Brute_Bombrun", 
[7] = "Prime_RocketPunch", 
[28] = "Brute_Sonic", 
[29] = "Ranged_Rockthrow", 
[71] = "Passive_CritDefense", 
[67] = "Passive_Boosters", 
[30] = "Ranged_Defensestrike", 
[63] = "Passive_Leech", 
[47] = "Science_FreezeBeam" 
}, 
["PodWeaponDeck"] = { 
[31] = "Support_SmokeDrop", 
[2] = "Prime_Spear", 
[8] = "Brute_Sniper", 
[32] = "Support_Repair", 
[33] = "Support_Missiles", 
[34] = "Support_Wind", 
[35] = "Support_Blizzard", 
[9] = "Brute_Shockblast", 
[36] = "Passive_FlameImmune", 
[37] = "Passive_Leech", 
[38] = "Passive_MassRepair", 
[39] = "Passive_Defenses", 
[10] = "Brute_Beetle", 
[40] = "Passive_AutoShields", 
[41] = "Passive_Boosters", 
[42] = "Passive_Medical", 
[43] = "Passive_FriendlyFire", 
[11] = "Brute_Heavyrocket", 
[44] = "Passive_ForceAmp", 
[45] = "Passive_CritDefense", 
[46] = "Prime_WayTooBig", 
[3] = "Prime_Leap", 
[12] = "Brute_Bombrun", 
[48] = "Prime_TC_BendBeam", 
[49] = "Prime_TC_Feint", 
[50] = "Brute_Fracture", 
[51] = "Brute_KO_Combo", 
[13] = "Brute_Sonic", 
[52] = "Ranged_TC_BounceShot", 
[53] = "Ranged_TC_DoubleArt", 
[54] = "Ranged_KO_Combo", 
[55] = "Science_TelePush", 
[14] = "Ranged_SmokeBlast", 
[56] = "Science_Placer", 
[57] = "Science_TC_Enrage", 
[58] = "Support_Confuse", 
[59] = "Support_GridDefense", 
[15] = "Ranged_Fireball", 
[60] = "Support_Waterdrill", 
[61] = "Support_TC_GridAtk", 
[62] = "Support_TC_Bombline", 
[1] = "Prime_Areablast", 
[4] = "Prime_SpinFist", 
[16] = "Ranged_RainingVolley", 
[64] = "Passive_FireBoost", 
[65] = "Passive_PlayerTurnShield", 
[66] = "Passive_VoidShock", 
[17] = "Ranged_Dual", 
[18] = "Science_SmokeDefense", 
[19] = "Science_Shield", 
[5] = "Prime_Sword", 
[20] = "Science_FireBeam", 
[21] = "Science_FreezeBeam", 
[22] = "Science_LocalShield", 
[23] = "Science_PushBeam", 
[6] = "Prime_Smash", 
[24] = "Support_Boosters", 
[25] = "Support_Refrigerate", 
[26] = "DeploySkill_ShieldTank", 
[27] = "DeploySkill_Tank", 
[7] = "Brute_Grapple", 
[28] = "DeploySkill_AcidTank", 
[29] = "DeploySkill_PullTank", 
[30] = "Support_Force", 
[63] = "Passive_HealingSmoke", 
[47] = "Prime_PrismLaser" 
}, 
["PilotDeck"] = { 
[13] = "Pilot_Delusional", 
[7] = "Pilot_Hotshot", 
[1] = "Pilot_Original", 
[2] = "Pilot_Soldier", 
[4] = "Pilot_Warrior", 
[8] = "Pilot_Genius", 
[9] = "Pilot_Miner", 
[5] = "Pilot_Aquatic", 
[10] = "Pilot_Recycler", 
[3] = "Pilot_Youth", 
[6] = "Pilot_Medic", 
[12] = "Pilot_Repairman", 
[11] = "Pilot_Leader" 
}, 
["Enemies"] = { 
[1] = { 
[6] = "Shaman", 
[2] = "Mosquito", 
[3] = "Scarab", 
[1] = "Bouncer", 
[4] = "Jelly_Armor", 
[5] = "Centipede", 
["island"] = 1 
}, 
[2] = { 
[6] = "Starfish", 
[2] = "Hornet", 
[3] = "Burnbug", 
[1] = "Firefly", 
[4] = "Jelly_Spider", 
[5] = "Crab", 
["island"] = 2 
}, 
[4] = { 
[6] = "Beetle", 
[2] = "Moth", 
[3] = "Bouncer", 
[1] = "Scorpion", 
[4] = "Jelly_Regen", 
[5] = "Spider", 
["island"] = 4 
}, 
[3] = { 
[6] = "Digger", 
[2] = "Moth", 
[3] = "Burnbug", 
[1] = "Scorpion", 
[4] = "Jelly_Boost", 
[5] = "Blobber", 
["island"] = 3 
} 
}, 
["PodDeck"] = { 
[1] = { 
["cores"] = 1 
}, 
[2] = { 
["cores"] = 1 
}, 
[3] = { 
["cores"] = 1, 
["weapon"] = "random" 
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
[1] = "Mission_JellyBoss", 
[2] = "Mission_CrabBoss", 
[4] = "Mission_MosquitoBoss", 
[3] = "Mission_BurnbugBoss" 
}, 
["Island"] = 4, 
["Missions"] = { 
[1] = { 
["ID"] = "Mission_Teleporter", 
["BonusObjs"] = { 
[1] = 6, 
[2] = 1 
}, 
["AssetId"] = "Str_Power" 
}, 
[2] = { 
["ID"] = "Mission_Acid", 
["BonusObjs"] = { 
[1] = 7, 
[2] = 1 
}, 
["AssetId"] = "Str_Nimbus" 
}, 
[3] = { 
["ID"] = "Mission_Civilians", 
["BonusObjs"] = { 
[1] = 1 
}, 
["DiffMod"] = 2, 
["AssetId"] = "Str_Robotics" 
}, 
[4] = { 
["ID"] = "Mission_Survive", 
["BonusObjs"] = { 
[1] = 4, 
[2] = 1 
}, 
["AssetId"] = "Str_Power" 
}, 
[5] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 6, 
["curr_weakRatio"] = { 
[1] = 3, 
[2] = 4 
}, 
["curr_upgradeRatio"] = { 
[1] = 2, 
[2] = 4 
}, 
["upgrade_streak"] = 0, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Scorpion"] = 1, 
["Bouncer"] = 1, 
["Spider"] = 1, 
["Moth"] = 3 
} 
}, 
["AssetId"] = "Str_Bar", 
["BonusObjs"] = { 
[1] = 3, 
[2] = 1 
}, 
["AssetLoc"] = Point( 1, 1 ), 
["ID"] = "Mission_Belt", 
["VoiceEvents"] = { 
}, 
["LiveEnvironment"] = { 
["Belts"] = { 
[1] = Point( 1, 4 ), 
[2] = Point( 2, 4 ), 
[3] = Point( 2, 5 ), 
[4] = Point( 3, 5 ), 
[5] = Point( 4, 5 ), 
[6] = Point( 5, 5 ), 
[7] = Point( 6, 5 ), 
[8] = Point( 7, 5 ) 
}, 
["BeltsDir"] = { 
[1] = 3, 
[2] = 3, 
[3] = 0, 
[4] = 3, 
[5] = 3, 
[6] = 3, 
[7] = 3, 
[8] = 3 
} 
}, 
["PowerStart"] = 6 
}, 
[6] = { 
["ID"] = "Mission_BeltRandom", 
["BonusObjs"] = { 
[1] = 9 
}, 
["DiffMod"] = 1 
}, 
[7] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 3, 
["curr_weakRatio"] = { 
[1] = 2, 
[2] = 2 
}, 
["curr_upgradeRatio"] = { 
[1] = 1, 
[2] = 2 
}, 
["upgrade_streak"] = 1, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Jelly_Regen"] = 1, 
["Spider"] = 1, 
["Moth"] = 1 
} 
}, 
["LiveEnvironment"] = { 
}, 
["ID"] = "Mission_Barrels", 
["VoiceEvents"] = { 
}, 
["BonusObjs"] = { 
} 
}, 
[8] = { 
["ID"] = "Mission_MosquitoBoss", 
["BonusObjs"] = { 
[1] = 1 
}, 
["AssetId"] = "Str_Tower" 
} 
}, 
["SeenPilots"] = { 
[1] = "Pilot_Chemical", 
[2] = "Pilot_Detritus", 
[3] = "Pilot_Archive", 
[4] = "Pilot_Caretaker", 
[5] = "Pilot_Arrogant", 
[6] = "Pilot_Assassin" 
} 
}

 

SquadData = {
["money"] = 0, ["cores"] = 1, ["bIsFavor"] = false, ["repairs"] = 0, ["CorpReward"] = {CreateEffect({weapon = "Support_Destruct",}), CreateEffect({skill1 = "Invulnerable",skill2 = "Pain",pilot = "Pilot_Assassin",}), CreateEffect({power = 2,}), },
["RewardClaimed"] = false, 
["skip_pawns"] = true, 

["storage_size"] = 3, ["CorpStore"] = {CreateEffect({weapon = "Brute_TC_GuidedMissile",money = -2,}), CreateEffect({weapon = "Support_Smoke",money = -2,}), CreateEffect({weapon = "Ranged_Artillerymech",money = -2,}), CreateEffect({stock = 0,}), CreateEffect({money = -3,stock = -1,cores = 1,}), CreateEffect({money = -1,power = 1,stock = -1,}), },
["island_store_count"] = 1, ["store_undo_size"] = 0, }
 

