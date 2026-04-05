GameData = {["save_version"] = 1, ["language"] = 1, ["network"] = 3, ["networkMax"] = 7, ["overflow"] = 0, ["seed"] = 1863431517, ["new_enemies"] = 0, ["new_missions"] = 0, ["new_equip"] = 0, ["difficulty"] = 0, ["new_abilities"] = 0, ["ach_info"] = {["squad"] = "Archive_A", ["trackers"] = {["Detritus_B_2"] = 0, ["Global_Challenge_Power"] = 0, ["Archive_A_1"] = 0, ["Archive_B_2"] = 0, ["Rust_A_2"] = 0, ["Rust_A_3"] = 0, ["Pinnacle_A_3"] = 0, ["Archive_B_1"] = 0, ["Pinnacle_B_3"] = 0, ["Detritus_B_1"] = 0, ["Pinnacle_B_1"] = 0, ["Global_Island_Mechs"] = 4, ["Global_Island_Building"] = 0, ["Squad_Mist_1"] = 0, ["Squad_Bomber_2"] = 0, ["Squad_Spiders_1"] = 0, ["Squad_Mist_2"] = 0, ["Squad_Heat_1"] = 0, ["Squad_Cataclysm_1"] = 0, ["Squad_Cataclysm_2"] = 0, ["Squad_Cataclysm_3"] = 0, },
},


["current"] = {["score"] = 0, ["time"] = 621256.500000, ["kills"] = 0, ["damage"] = 0, ["failures"] = 0, ["difficulty"] = 0, ["victory"] = false, ["squad"] = 0, 
["mechs"] = {"PunchMech", "TankMech", "ArtiMech", },
["colors"] = {0, 0, 0, },
["weapons"] = {"Prime_Punchmech", "", "Brute_Tankmech", "", "Ranged_Artillerymech", "", },
["pilot0"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 2, ["exp"] = 0, ["level"] = 0, ["travel"] = 2, ["final"] = 0, ["starting"] = true, ["last_end"] = 2, },
["pilot1"] = {["id"] = "Pilot_Detritus", ["name"] = "Alison Kirk", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 2, ["skill2"] = 3, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot2"] = {["id"] = "Pilot_Rust", ["name"] = "Maria Patel", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 2, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
},
["current_squad"] = 0, }
 

RegionData = {
["sector"] = 0, ["island"] = 0, ["secret"] = false, 
["island0"] = {["corporation"] = "Corp_Grass", ["id"] = 0, ["secured"] = false, },
["island1"] = {["corporation"] = "Corp_Desert", ["id"] = 1, ["secured"] = false, },
["island2"] = {["corporation"] = "Corp_Snow", ["id"] = 2, ["secured"] = false, },
["island3"] = {["corporation"] = "Corp_Factory", ["id"] = 3, ["secured"] = false, },

["turn"] = 0, ["iTower"] = 0, ["quest_tracker"] = 0, ["quest_id"] = 0, ["podRewards"] = {CreateEffect({cores = 1,}), },


["region0"] = {["mission"] = "", ["state"] = 2, ["name"] = "Corporate HQ", ["objectives"] = {},
},

["region1"] = {["mission"] = "Mission1", ["state"] = 0, ["name"] = "Preserved Farms", },

["region2"] = {["mission"] = "Mission5", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission5", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Satellite_Briefing_CEO_Grass_4", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 1719949353, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "any44", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 0, ["custom"] = "square_missilesilo.png", },
{["loc"] = Point( 1, 3 ), ["terrain"] = 6, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 26, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 61, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 6, },
{["loc"] = Point( 2, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 66, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 39, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 144, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 102, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 62, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 1 ), ["terrain"] = 0, ["custom"] = "square_missilesilo.png", },
{["loc"] = Point( 6, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 4 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 2 ), ["terrain"] = 3, },
},
["rain"] = 3, ["rain_type"] = 0, ["spawns"] = {"Jelly_Armor1", "Firefly1", },
["spawn_ids"] = {314, 315, },
["spawn_points"] = {Point(7,4), Point(5,5), },
["zones"] = {["satellite"] = {Point( 5, 6 ), Point( 5, 5 ), Point( 5, 4 ), Point( 5, 3 ), Point( 5, 2 ), Point( 5, 1 ), Point( 1, 1 ), },
},
["tags"] = {"generic", "any_sector", "satellite", "water", },


["pawn1"] = {["type"] = "SatelliteRocket", ["name"] = "", ["id"] = 312, ["mech"] = false, ["offset"] = 0, ["primary"] = "Rocket_Launch", ["primary_uses"] = 1, ["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,1), ["last_location"] = Point(-1,-1), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 0, ["iTurnsRemaining"] = -15921385, ["bPowered"] = false, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 312, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn2"] = {["type"] = "SatelliteRocket", ["name"] = "", ["id"] = 313, ["mech"] = false, ["offset"] = 0, ["primary"] = "Rocket_Launch", ["primary_uses"] = 1, ["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(1,1), ["last_location"] = Point(-1,-1), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 0, ["bPowered"] = false, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 313, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },
["pawn_count"] = 2, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Excavation Site", },

["region3"] = {["mission"] = "Mission6", ["state"] = 0, ["name"] = "Archival Flats", },

["region4"] = {["mission"] = "Mission2", ["state"] = 0, ["name"] = "Colonial Park", },

["region5"] = {["mission"] = "Mission7", ["state"] = 0, ["name"] = "Accord Repository", },

["region6"] = {["mission"] = "Mission4", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 4, ["iTeamTurn"] = 1, ["iState"] = 0, ["sMission"] = "Mission4", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Volatile_Briefing_CEO_Grass_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 3, ["aiDelay"] = 0.000000, ["aiSeed"] = 1773917624, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "any1", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 49, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 36, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 1, ["unique"] = "str_recycle1", ["health_max"] = 1, ["health_min"] = 0, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 1, ["populated"] = 1, ["grappled"] = 1, ["people1"] = 55, ["people2"] = 0, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 6, },
{["loc"] = Point( 1, 3 ), ["terrain"] = 0, },
{["loc"] = Point( 1, 5 ), ["terrain"] = 6, ["grapple_targets"] = {3, },
},
{["loc"] = Point( 2, 2 ), ["terrain"] = 0, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 0, ["fire"] = 2, },
{["loc"] = Point( 2, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 135, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 96, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 4, 3 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 4 ), ["terrain"] = 0, ["grappled"] = 1, ["undo_state"] = {["active"] = true, },
},
{["loc"] = Point( 4, 5 ), ["terrain"] = 0, ["grapple_targets"] = {0, },
},
{["loc"] = Point( 4, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 4, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 2 ), ["terrain"] = 0, ["fire"] = 2, },
{["loc"] = Point( 5, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 4 ), ["terrain"] = 6, },
{["loc"] = Point( 6, 5 ), ["terrain"] = 6, },
{["loc"] = Point( 7, 2 ), ["terrain"] = 6, },
{["loc"] = Point( 7, 3 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 4 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 5 ), ["terrain"] = 6, },
},
["pod"] = Point(4,5), ["spawns"] = {},
["spawn_ids"] = {},
["spawn_points"] = {},
["zones"] = {["satellite"] = {Point( 2, 4 ), Point( 2, 3 ), Point( 3, 3 ), Point( 3, 4 ), Point( 4, 4 ), Point( 4, 3 ), Point( 5, 2 ), Point( 5, 3 ), Point( 5, 4 ), Point( 5, 5 ), },
},
["tags"] = {"generic", "any_sector", "satellite", },


["pawn1"] = {["type"] = "PunchMech", ["name"] = "", ["id"] = 0, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Prime_Punchmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 2, ["exp"] = 0, ["level"] = 0, ["travel"] = 2, ["final"] = 0, ["starting"] = true, ["last_end"] = 2, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 1, ["max_health"] = 3, ["undo_state"] = {["health"] = 3, ["max_health"] = 3, },
["undo_ready"] = false, ["undo_point"] = Point(4,4), ["iMissionDamage"] = 0, ["location"] = Point(4,4), ["last_location"] = Point(3,4), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(4,4), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 0, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(4,4), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,3), },


["pawn2"] = {["type"] = "TankMech", ["name"] = "", ["id"] = 1, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Brute_Tankmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Detritus", ["name"] = "Alison Kirk", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 2, ["skill2"] = 3, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 1, ["max_health"] = 3, ["undo_state"] = {["health"] = 1, ["max_health"] = 3, },
["undo_ready"] = true, ["undo_point"] = Point(2,4), ["iMissionDamage"] = 0, ["location"] = Point(2,4), ["last_location"] = Point(2,4), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(2,4), ["undoReady"] = true, ["iKillCount"] = 0, ["iOwner"] = 1, ["piTarget"] = Point(4,2), ["piOrigin"] = Point(2,4), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn3"] = {["type"] = "ArtiMech", ["name"] = "", ["id"] = 2, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Ranged_Artillerymech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Rust", ["name"] = "Maria Patel", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 2, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 2, ["max_health"] = 2, },
["undo_ready"] = true, ["undo_point"] = Point(2,2), ["iMissionDamage"] = 0, ["location"] = Point(2,2), ["last_location"] = Point(2,2), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(2,2), ["undoReady"] = true, ["iKillCount"] = 0, ["iOwner"] = 2, ["piTarget"] = Point(5,2), ["piOrigin"] = Point(2,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,2), },


["pawn4"] = {["type"] = "GlowingScorpion", ["name"] = "", ["id"] = 316, ["mech"] = false, ["offset"] = 3, ["primary"] = "ScorpionAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 4, ["max_health"] = 4, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(1,5), ["last_location"] = Point(2,5), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 5, ["iOwner"] = 316, ["piTarget"] = Point(0,5), ["piOrigin"] = Point(1,5), ["piQueuedShot"] = Point(0,5), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(0,5), },


["pawn5"] = {["type"] = "Scarab1", ["name"] = "", ["id"] = 317, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScarabAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,4), ["last_location"] = Point(3,3), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 5, ["iOwner"] = 317, ["piTarget"] = Point(3,6), ["piOrigin"] = Point(3,4), ["piQueuedShot"] = Point(3,6), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,6), },


["pawn6"] = {["type"] = "Jelly_Armor1", ["name"] = "", ["id"] = 318, ["mech"] = false, ["offset"] = 2, ["not_attacking"] = true, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(1,3), ["last_location"] = Point(1,3), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 2, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 5, ["iOwner"] = 318, ["piTarget"] = Point(-2147483647,-2147483647), ["piOrigin"] = Point(1,3), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn7"] = {["type"] = "Scorpion1", ["name"] = "", ["id"] = 319, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScorpionAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,5), ["last_location"] = Point(3,5), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 2, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 5, ["iOwner"] = 319, ["piTarget"] = Point(4,4), ["piOrigin"] = Point(4,5), ["piQueuedShot"] = Point(4,4), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,4), },


["pawn8"] = {["type"] = "Firefly1", ["name"] = "", ["id"] = 320, ["mech"] = false, ["offset"] = 0, ["primary"] = "FireflyAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,4), ["last_location"] = Point(5,4), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 5, ["iOwner"] = 320, ["piTarget"] = Point(5,4), ["piOrigin"] = Point(6,4), ["piQueuedShot"] = Point(5,4), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,4), },


["pawn9"] = {["type"] = "Firefly1", ["name"] = "", ["id"] = 321, ["mech"] = false, ["offset"] = 0, ["primary"] = "FireflyAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,3), ["last_location"] = Point(5,3), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 1819627615, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 5, ["iOwner"] = 321, ["piTarget"] = Point(4,4), ["piOrigin"] = Point(4,3), ["piQueuedShot"] = Point(4,4), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,4), },
["pawn_count"] = 9, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Forgotten Hills", },

["region7"] = {["mission"] = "Mission3", ["state"] = 0, ["name"] = "Martial District", },
["iBattleRegion"] = 6, }
 

GAME = { 
["WeaponDeck"] = { 
[1] = "Prime_Lasermech", 
[2] = "Prime_ShieldBash", 
[3] = "Prime_Rockmech", 
[4] = "Prime_RightHook", 
[5] = "Prime_RocketPunch", 
[6] = "Prime_Shift", 
[7] = "Prime_Flamethrower", 
[8] = "Prime_Areablast", 
[9] = "Prime_Spear", 
[10] = "Prime_Leap", 
[11] = "Prime_SpinFist", 
[12] = "Prime_Sword", 
[13] = "Prime_Smash", 
[14] = "Brute_Jetmech", 
[15] = "Brute_Mirrorshot", 
[16] = "Brute_PhaseShot", 
[17] = "Brute_Grapple", 
[18] = "Brute_Shrapnel", 
[19] = "Brute_Sniper", 
[20] = "Brute_Shockblast", 
[21] = "Brute_Beetle", 
[22] = "Brute_Heavyrocket", 
[23] = "Brute_Splitshot", 
[24] = "Brute_Bombrun", 
[25] = "Brute_Sonic", 
[26] = "Ranged_Rockthrow", 
[27] = "Ranged_Defensestrike", 
[28] = "Ranged_Rocket", 
[29] = "Ranged_Ignite", 
[30] = "Ranged_ScatterShot", 
[31] = "Ranged_BackShot", 
[32] = "Ranged_Ice", 
[33] = "Ranged_SmokeBlast", 
[34] = "Ranged_Fireball", 
[35] = "Ranged_RainingVolley", 
[36] = "Ranged_Wide", 
[37] = "Ranged_Dual", 
[38] = "Science_Pullmech", 
[39] = "Science_Gravwell", 
[40] = "Science_Swap", 
[41] = "Science_Repulse", 
[42] = "Science_AcidShot", 
[43] = "Science_Confuse", 
[44] = "Science_SmokeDefense", 
[45] = "Science_Shield", 
[46] = "Science_FireBeam", 
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
[63] = "Support_Blizzard", 
[64] = "Passive_FlameImmune", 
[65] = "Passive_Electric", 
[66] = "Passive_Leech", 
[67] = "Passive_MassRepair", 
[68] = "Passive_Defenses", 
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
[30] = "DeploySkill_Tank", 
[31] = "DeploySkill_AcidTank", 
[32] = "DeploySkill_PullTank", 
[33] = "Support_Force", 
[34] = "Support_SmokeDrop", 
[35] = "Support_Repair", 
[36] = "Support_Missiles", 
[37] = "Support_Wind", 
[38] = "Support_Blizzard", 
[39] = "Passive_FlameImmune", 
[40] = "Passive_Electric", 
[41] = "Passive_Leech", 
[42] = "Passive_MassRepair", 
[43] = "Passive_Defenses", 
[44] = "Passive_AutoShields", 
[45] = "Passive_Psions", 
[46] = "Passive_Boosters", 
[47] = "Passive_Medical", 
[48] = "Passive_FriendlyFire", 
[49] = "Passive_ForceAmp", 
[50] = "Passive_CritDefense" 
}, 
["PilotDeck"] = { 
[1] = "Pilot_Soldier", 
[2] = "Pilot_Warrior", 
[3] = "Pilot_Aquatic", 
[4] = "Pilot_Medic", 
[5] = "Pilot_Hotshot", 
[6] = "Pilot_Genius", 
[7] = "Pilot_Miner", 
[8] = "Pilot_Recycler", 
[9] = "Pilot_Assassin", 
[10] = "Pilot_Leader", 
[11] = "Pilot_Repairman" 
}, 
["SeenPilots"] = { 
[1] = "Pilot_Original", 
[2] = "Pilot_Detritus", 
[3] = "Pilot_Rust", 
[4] = "Pilot_Youth" 
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
}, 
[9] = { 
["cores"] = 1, 
["pilot"] = "random" 
} 
}, 
["Bosses"] = { 
[1] = "Mission_BeetleBoss", 
[2] = "Mission_ScorpionBoss", 
[3] = "Mission_BlobBoss", 
[4] = "Mission_FireflyBoss" 
}, 
["Island"] = 1, 
["Missions"] = { 
[1] = { 
["ID"] = "Mission_Dam", 
["BonusObjs"] = { 
[1] = 4 
} 
}, 
[2] = { 
["ID"] = "Mission_Tanks", 
["BonusObjs"] = { 
} 
}, 
[3] = { 
["ID"] = "Mission_Survive", 
["BonusObjs"] = { 
[1] = 3, 
[2] = 1 
}, 
["AssetId"] = "Str_Power" 
}, 
[4] = { 
["BonusObjs"] = { 
[1] = 1 
}, 
["TargetDied"] = false, 
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
["Scarab"] = 1, 
["Firefly"] = 2, 
["Scorpion"] = 1 
} 
}, 
["LiveEnvironment"] = { 
}, 
["Target"] = 316, 
["AssetLoc"] = Point( 0, 4 ), 
["ID"] = "Mission_Volatile", 
["VoiceEvents"] = { 
}, 
["AssetId"] = "Str_Nimbus", 
["PowerStart"] = 5 
}, 
[5] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 2, 
["curr_weakRatio"] = { 
[1] = 2, 
[2] = 3 
}, 
["curr_upgradeRatio"] = { 
[1] = 0, 
[2] = 3 
}, 
["upgrade_streak"] = 0, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Jelly_Armor"] = 1, 
["Firefly"] = 1 
} 
}, 
["LiveEnvironment"] = { 
}, 
["ID"] = "Mission_Satellite", 
["VoiceEvents"] = { 
}, 
["Satellites"] = { 
[1] = 312, 
[2] = 313 
}, 
["BonusObjs"] = { 
} 
}, 
[6] = { 
["ID"] = "Mission_Airstrike", 
["BonusObjs"] = { 
[1] = 1 
}, 
["DiffMod"] = 1, 
["AssetId"] = "Str_Power" 
}, 
[7] = { 
["ID"] = "Mission_Mines", 
["BonusObjs"] = { 
[1] = 5, 
[2] = 1 
}, 
["AssetId"] = "Str_Battery" 
}, 
[8] = { 
["ID"] = "Mission_BeetleBoss", 
["BonusObjs"] = { 
[1] = 1 
}, 
["AssetId"] = "Str_Tower" 
} 
}, 
["Enemies"] = { 
[1] = { 
[1] = "Firefly", 
[2] = "Scorpion", 
[3] = "Scarab", 
[4] = "Jelly_Armor", 
[5] = "Spider", 
[6] = "Digger", 
["island"] = 1 
}, 
[2] = { 
[1] = "Hornet", 
[2] = "Leaper", 
[3] = "Firefly", 
[4] = "Jelly_Regen", 
[5] = "Burrower", 
[6] = "Crab", 
["island"] = 2 
}, 
[3] = { 
[1] = "Hornet", 
[2] = "Leaper", 
[3] = "Scarab", 
[4] = "Jelly_Health", 
[5] = "Blobber", 
[6] = "Centipede", 
["island"] = 3 
}, 
[4] = { 
[1] = "Scorpion", 
[2] = "Scarab", 
[3] = "Firefly", 
[4] = "Jelly_Explode", 
[5] = "Beetle", 
[6] = "Centipede", 
["island"] = 4 
} 
} 
}

 

SquadData = {
["money"] = 0, ["cores"] = 0, ["bIsFavor"] = false, ["repairs"] = 0, ["CorpReward"] = {CreateEffect({weapon = "Passive_Burrows",}), CreateEffect({skill1 = "Health",skill2 = "Grid",pilot = "Pilot_Youth",}), CreateEffect({power = 2,}), },
["RewardClaimed"] = false, 
["skip_pawns"] = true, 

["storage_size"] = 3, ["CorpStore"] = {CreateEffect({weapon = "Brute_Unstable",money = -2,}), CreateEffect({weapon = "Prime_Lightning",money = -2,}), CreateEffect({stock = 0,}), CreateEffect({stock = 0,}), CreateEffect({money = -3,stock = -1,cores = 1,}), CreateEffect({money = -1,power = 1,stock = -1,}), },
["island_store_count"] = 0, ["store_undo_size"] = 0, }
 

