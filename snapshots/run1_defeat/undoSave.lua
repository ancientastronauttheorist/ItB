GameData = {["save_version"] = 1, ["language"] = 1, ["network"] = 2, ["networkMax"] = 7, ["overflow"] = 0, ["seed"] = 711522456, ["new_enemies"] = 0, ["new_missions"] = 0, ["new_equip"] = 0, ["difficulty"] = 1, ["new_abilities"] = 0, ["ach_info"] = {["squad"] = "Archive_A", ["trackers"] = {["Detritus_B_2"] = 0, ["Global_Challenge_Power"] = 2, ["Archive_A_1"] = 0, ["Archive_B_2"] = 0, ["Rust_A_2"] = 0, ["Rust_A_3"] = 0, ["Pinnacle_A_3"] = 0, ["Archive_B_1"] = 0, ["Pinnacle_B_3"] = 0, ["Detritus_B_1"] = 0, ["Pinnacle_B_1"] = 0, ["Global_Island_Mechs"] = 3, ["Global_Island_Building"] = 3, ["Squad_Mist_1"] = 0, ["Squad_Bomber_2"] = 0, ["Squad_Spiders_1"] = 0, ["Squad_Mist_2"] = 0, ["Squad_Heat_1"] = 0, ["Squad_Cataclysm_1"] = 0, ["Squad_Cataclysm_2"] = 0, ["Squad_Cataclysm_3"] = 0, },
},


["current"] = {["score"] = 0, ["time"] = 6043021.500000, ["kills"] = 1, ["damage"] = 0, ["failures"] = 0, ["difficulty"] = 1, ["victory"] = false, ["squad"] = 0, 
["mechs"] = {"PunchMech", "TankMech", "ArtiMech", },
["colors"] = {0, 0, 0, },
["weapons"] = {"Prime_Punchmech", "", "Brute_Tankmech", "", "Ranged_Artillerymech", "", },
["pilot0"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 2, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot1"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Genos", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 2, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot2"] = {["id"] = "Pilot_Archive", ["name"] = "Liam Kirby", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 3, ["exp"] = 4, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
},
["current_squad"] = 0, ["undosave"] = true, }
 

RegionData = {
["sector"] = 0, ["island"] = 0, ["secret"] = false, 
["island0"] = {["corporation"] = "Corp_Grass", ["id"] = 0, ["secured"] = false, },
["island1"] = {["corporation"] = "Corp_Desert", ["id"] = 1, ["secured"] = false, },
["island2"] = {["corporation"] = "Corp_Snow", ["id"] = 2, ["secured"] = false, },
["island3"] = {["corporation"] = "Corp_Factory", ["id"] = 3, ["secured"] = false, },

["turn"] = 0, ["iTower"] = 1, ["quest_tracker"] = 0, ["quest_id"] = 0, ["podRewards"] = {CreateEffect({weapon = "random",cores = 1,}), },


["region0"] = {["mission"] = "Mission3", ["state"] = 0, ["name"] = "Exhibits Archive", },

["region1"] = {["mission"] = "", ["state"] = 2, ["name"] = "Corporate HQ", ["objectives"] = {},
},

["region2"] = {["mission"] = "Mission2", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 3, ["iTeamTurn"] = 1, ["iState"] = 0, ["sMission"] = "Mission2", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Volatile_Briefing_CEO_Grass_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 3, ["aiDelay"] = 0.000000, ["aiSeed"] = 189190896, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "grass2", ["enemy_kills"] = 1, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 6, },
{["loc"] = Point( 0, 1 ), ["terrain"] = 6, },
{["loc"] = Point( 0, 3 ), ["terrain"] = 6, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 91, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 5 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 2, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 131, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 5 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_power1", ["people1"] = 127, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 3, 0 ), ["terrain"] = 6, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 6, ["grappled"] = 1, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 0, },
{["loc"] = Point( 3, 3 ), ["terrain"] = 6, ["grappled"] = 1, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 1, ["populated"] = 1, ["grappled"] = 1, ["people1"] = 128, ["people2"] = 0, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 3, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 104, ["people2"] = 0, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 94, ["people2"] = 0, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 3, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 0, ["grapple_targets"] = {3, },
},
{["loc"] = Point( 4, 3 ), ["terrain"] = 0, ["grapple_targets"] = {3, },
},
{["loc"] = Point( 4, 4 ), ["terrain"] = 0, ["grapple_targets"] = {3, },
},
{["loc"] = Point( 4, 5 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 6 ), ["terrain"] = 6, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 4 ), ["terrain"] = 6, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 6, },
{["loc"] = Point( 6, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 6 ), ["terrain"] = 6, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 2 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 3 ), ["terrain"] = 6, },
{["loc"] = Point( 7, 4 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 5 ), ["terrain"] = 6, },
},
["pod"] = Point(4,5), ["spawns"] = {"Firefly1", },
["spawn_ids"] = {101, },
["spawn_points"] = {Point(6,2), },
["zones"] = {},
["tags"] = {"generic", "grass", },


["pawn1"] = {["type"] = "PunchMech", ["name"] = "", ["id"] = 0, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Prime_Punchmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 2, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 3, ["max_health"] = 3, },
["undo_ready"] = true, ["undo_point"] = Point(3,1), ["iMissionDamage"] = 0, ["location"] = Point(3,1), ["last_location"] = Point(3,1), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 3, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(3,1), ["undoReady"] = true, ["iKillCount"] = 0, ["iOwner"] = 0, ["piTarget"] = Point(4,1), ["piOrigin"] = Point(3,1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,1), },


["pawn2"] = {["type"] = "TankMech", ["name"] = "", ["id"] = 1, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Brute_Tankmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Genos", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 2, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,3), ["last_location"] = Point(3,3), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 3, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 1, ["piTarget"] = Point(4,3), ["piOrigin"] = Point(3,3), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,3), },


["pawn3"] = {["type"] = "ArtiMech", ["name"] = "", ["id"] = 2, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Ranged_Artillerymech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Archive", ["name"] = "Liam Kirby", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 3, ["exp"] = 4, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 1, ["is_corpse"] = true, ["health"] = 0, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,2), ["last_location"] = Point(3,2), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 3, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 4, ["iOwner"] = 2, ["piTarget"] = Point(5,2), ["piOrigin"] = Point(3,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,2), },


["pawn4"] = {["type"] = "Scorpion1", ["name"] = "", ["id"] = 93, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScorpionAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,3), ["last_location"] = Point(4,4), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 3, ["iTurnsRemaining"] = 3, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 93, ["piTarget"] = Point(3,3), ["piOrigin"] = Point(4,3), ["piQueuedShot"] = Point(3,3), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,3), },


["pawn5"] = {["type"] = "Scorpion1", ["name"] = "", ["id"] = 94, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScorpionAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,4), ["last_location"] = Point(4,5), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 3, ["iTurnsRemaining"] = 3, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 94, ["piTarget"] = Point(3,4), ["piOrigin"] = Point(4,4), ["piQueuedShot"] = Point(3,4), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,4), },


["pawn6"] = {["type"] = "Scorpion1", ["name"] = "", ["id"] = 98, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScorpionAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,1), ["last_location"] = Point(4,2), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 3, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 98, ["piTarget"] = Point(3,1), ["piOrigin"] = Point(4,1), ["piQueuedShot"] = Point(3,1), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,1), },


["pawn7"] = {["type"] = "Firefly1", ["name"] = "", ["id"] = 99, ["mech"] = false, ["offset"] = 0, ["primary"] = "FireflyAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,6), ["last_location"] = Point(5,6), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 3, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 99, ["piTarget"] = Point(3,6), ["piOrigin"] = Point(4,6), ["piQueuedShot"] = Point(3,6), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,6), },


["pawn8"] = {["type"] = "Hornet1", ["name"] = "", ["id"] = 100, ["mech"] = false, ["offset"] = 0, ["primary"] = "HornetAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,5), ["last_location"] = Point(5,5), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 2065710368, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 100, ["piTarget"] = Point(3,5), ["piOrigin"] = Point(4,5), ["piQueuedShot"] = Point(3,5), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,5), },
["pawn_count"] = 8, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Historic County", },

["region3"] = {["mission"] = "Mission4", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission4", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_MechHealth_Briefing_CEO_Grass_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 2003865420, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "anyAE14", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 113, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 87, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 3 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 1, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 85, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 115, ["people2"] = 0, ["health_max"] = 1, ["shield"] = true, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 6, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 210, ["people2"] = 0, ["health_max"] = 2, ["shield"] = true, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 2, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 3, 0 ), ["terrain"] = 6, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 6, },
{["loc"] = Point( 3, 5 ), ["terrain"] = 6, },
{["loc"] = Point( 3, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 4, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 155, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 235, ["people2"] = 0, ["health_max"] = 2, ["shield"] = true, },
{["loc"] = Point( 4, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 6, },
{["loc"] = Point( 5, 2 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 3 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 5 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 3, },
},
["spawns"] = {"Scorpion1", "Firefly1", "Scorpion1", },
["spawn_ids"] = {95, 96, 97, },
["spawn_points"] = {Point(7,2), Point(7,3), Point(7,5), },
["zones"] = {},
["tags"] = {"generic", "any_sector", },
["pawn_count"] = 0, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Colonial Park", },

["region4"] = {["mission"] = "Mission5", ["state"] = 0, ["name"] = "Central Museums", },

["region5"] = {["mission"] = "Mission1", ["state"] = 0, ["name"] = "Martial District", },

["region6"] = {["mission"] = "Mission7", ["state"] = 0, ["name"] = "Old Town", },

["region7"] = {["mission"] = "Mission6", ["state"] = 0, ["name"] = "Old Earth Park", },
["iBattleRegion"] = 2, }
 

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
[26] = "Brute_Sonic", 
[27] = "Ranged_Rockthrow", 
[28] = "Ranged_Defensestrike", 
[29] = "Ranged_Rocket", 
[30] = "Ranged_Ignite", 
[31] = "Ranged_ScatterShot", 
[32] = "Ranged_BackShot", 
[33] = "Ranged_Ice", 
[34] = "Ranged_SmokeBlast", 
[35] = "Ranged_Fireball", 
[36] = "Ranged_RainingVolley", 
[37] = "Ranged_Wide", 
[38] = "Ranged_Dual", 
[39] = "Science_Pullmech", 
[40] = "Science_Gravwell", 
[41] = "Science_Swap", 
[42] = "Science_Repulse", 
[43] = "Science_AcidShot", 
[44] = "Science_Confuse", 
[45] = "Science_SmokeDefense", 
[46] = "Science_Shield", 
[47] = "Science_FireBeam", 
[48] = "Science_FreezeBeam", 
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
[12] = "Brute_Sonic", 
[13] = "Ranged_Ice", 
[14] = "Ranged_SmokeBlast", 
[15] = "Ranged_Fireball", 
[16] = "Ranged_RainingVolley", 
[17] = "Ranged_Dual", 
[18] = "Science_SmokeDefense", 
[19] = "Science_Shield", 
[20] = "Science_FireBeam", 
[21] = "Science_FreezeBeam", 
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
[36] = "Support_Blizzard", 
[37] = "Passive_FlameImmune", 
[38] = "Passive_Electric", 
[39] = "Passive_Leech", 
[40] = "Passive_MassRepair", 
[41] = "Passive_Defenses", 
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
[9] = "Pilot_Assassin", 
[10] = "Pilot_Leader", 
[11] = "Pilot_Repairman" 
}, 
["SeenPilots"] = { 
[1] = "Pilot_Original", 
[2] = "Pilot_Pinnacle", 
[3] = "Pilot_Archive", 
[4] = "Pilot_Recycler" 
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
[4] = "Mission_JellyBoss" 
}, 
["Island"] = 1, 
["Missions"] = { 
[1] = { 
["ID"] = "Mission_Artillery", 
["BonusObjs"] = { 
[1] = 1 
}, 
["AssetId"] = "Str_Power" 
}, 
[2] = { 
["BonusObjs"] = { 
[1] = 1 
}, 
["TargetDied"] = true, 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 6, 
["curr_weakRatio"] = { 
[1] = 3, 
[2] = 4 
}, 
["curr_upgradeRatio"] = { 
[1] = 0, 
[2] = 4 
}, 
["upgrade_streak"] = 0, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Firefly"] = 2, 
["Scorpion"] = 3, 
["Hornet"] = 1 
} 
}, 
["LiveEnvironment"] = { 
}, 
["Target"] = 92, 
["AssetLoc"] = Point( 2, 5 ), 
["ID"] = "Mission_Volatile", 
["VoiceEvents"] = { 
}, 
["AssetId"] = "Str_Power", 
["PowerStart"] = 5 
}, 
[3] = { 
["ID"] = "Mission_Airstrike", 
["BonusObjs"] = { 
[1] = 6, 
[2] = 1 
}, 
["AssetId"] = "Str_Nimbus" 
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
["upgrade_streak"] = 0, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Firefly"] = 1, 
["Scorpion"] = 2 
} 
}, 
["BonusObjs"] = { 
[1] = 4 
}, 
["ID"] = "Mission_Survive", 
["VoiceEvents"] = { 
}, 
["DiffMod"] = 1, 
["LiveEnvironment"] = { 
} 
}, 
[5] = { 
["ID"] = "Mission_Train", 
["BonusObjs"] = { 
} 
}, 
[6] = { 
["ID"] = "Mission_Tanks", 
["BonusObjs"] = { 
} 
}, 
[7] = { 
["ID"] = "Mission_Tides", 
["BonusObjs"] = { 
[1] = 3, 
[2] = 1 
}, 
["AssetId"] = "Str_Battery" 
}, 
[8] = { 
["ID"] = "Mission_HornetBoss", 
["BonusObjs"] = { 
[1] = 1 
}, 
["AssetId"] = "Str_Tower" 
} 
}, 
["Enemies"] = { 
[1] = { 
[1] = "Hornet", 
[2] = "Scorpion", 
[3] = "Firefly", 
[4] = "Jelly_Health", 
[5] = "Beetle", 
[6] = "Crab", 
["island"] = 1 
}, 
[2] = { 
[1] = "Scarab", 
[2] = "Leaper", 
[3] = "Firefly", 
[4] = "Jelly_Regen", 
[5] = "Centipede", 
[6] = "Blobber", 
["island"] = 2 
}, 
[3] = { 
[1] = "Hornet", 
[2] = "Leaper", 
[3] = "Scarab", 
[4] = "Jelly_Armor", 
[5] = "Digger", 
[6] = "Spider", 
["island"] = 3 
}, 
[4] = { 
[1] = "Scorpion", 
[2] = "Hornet", 
[3] = "Scarab", 
[4] = "Jelly_Explode", 
[5] = "Digger", 
[6] = "Beetle", 
["island"] = 4 
} 
} 
}

 

SquadData = {
["money"] = 0, ["cores"] = 0, ["bIsFavor"] = false, ["repairs"] = 0, ["CorpReward"] = {CreateEffect({weapon = "Brute_Bombrun",}), CreateEffect({skill1 = "Grid",skill2 = "Health",pilot = "Pilot_Recycler",}), CreateEffect({power = 2,}), },
["RewardClaimed"] = false, 
["skip_pawns"] = true, 

["storage_size"] = 3, ["CorpStore"] = {CreateEffect({weapon = "Passive_Burrows",money = -2,}), CreateEffect({weapon = "Science_LocalShield",money = -2,}), CreateEffect({stock = 0,}), CreateEffect({stock = 0,}), CreateEffect({money = -3,stock = -1,cores = 1,}), CreateEffect({money = -1,power = 1,stock = -1,}), },
["island_store_count"] = 0, ["store_undo_size"] = 0, }
 

