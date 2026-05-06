GameData = {["save_version"] = 1, ["language"] = 1, ["network"] = 7, ["networkMax"] = 7, ["overflow"] = 10, ["seed"] = 547498648, ["new_enemies"] = 1, ["new_missions"] = 1, ["new_equip"] = 1, ["difficulty"] = 0, ["new_abilities"] = 1, ["ach_info"] = {["squad"] = "Rust_A", ["trackers"] = {["Detritus_B_2"] = 0, ["Global_Challenge_Power"] = 0, ["Archive_A_1"] = 0, ["Archive_B_2"] = 0, ["Rust_A_2"] = 2, ["Rust_A_3"] = 2, ["Pinnacle_A_3"] = 0, ["Archive_B_1"] = 0, ["Pinnacle_B_3"] = 0, ["Detritus_B_1"] = 0, ["Pinnacle_B_1"] = 0, ["Global_Island_Mechs"] = 2, ["Global_Island_Building"] = 0, ["Squad_Mist_1"] = 0, ["Squad_Bomber_2"] = 0, ["Squad_Spiders_1"] = 0, ["Squad_Mist_2"] = 0, ["Squad_Heat_1"] = 0, ["Squad_Cataclysm_1"] = 0, ["Squad_Cataclysm_2"] = 0, ["Squad_Cataclysm_3"] = 0, },
},


["current"] = {["score"] = 2500, ["time"] = 10548035.000000, ["kills"] = 34, ["damage"] = 0, ["failures"] = 2, ["difficulty"] = 0, ["victory"] = false, ["islands"] = 1, ["squad"] = 1, 
["mechs"] = {"JetMech", "RocketMech", "PulseMech", },
["colors"] = {1, 1, 1, },
["weapons"] = {"Brute_Jetmech", "", "Ranged_Rocket", "Passive_Electric", "Science_Repulse", "", },
["pilot0"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 0, ["exp"] = 50, ["level"] = 2, ["travel"] = 3, ["final"] = 2, ["starting"] = true, ["last_end"] = 2, },
["pilot1"] = {["id"] = "Pilot_Detritus", ["name"] = "Zoe Koleda", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 7, ["skill2"] = 8, ["exp"] = 25, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot2"] = {["id"] = "Pilot_Artificial", ["name"] = "A.I. Unit", ["name_id"] = "Pilot_Artificial_Name", ["renamed"] = false, ["skill1"] = 4, ["skill2"] = 10, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = false, },
},
["current_squad"] = 1, }
 

RegionData = {
["sector"] = 1, ["island"] = 0, ["secret"] = false, 
["island0"] = {["corporation"] = "Corp_Grass", ["id"] = 0, ["secured"] = false, },
["island1"] = {["corporation"] = "Corp_Desert", ["id"] = 1, ["secured"] = true, },
["island2"] = {["corporation"] = "Corp_Snow", ["id"] = 2, ["secured"] = false, },
["island3"] = {["corporation"] = "Corp_Factory", ["id"] = 3, ["secured"] = false, },

["turn"] = 0, ["iTower"] = 7, ["quest_tracker"] = 0, ["quest_id"] = 0, ["podRewards"] = {CreateEffect({pilot = "random",cores = 1,}), },


["region0"] = {["mission"] = "Mission3", ["state"] = 0, ["name"] = "Archivist Hall", },

["region1"] = {["mission"] = "Mission7", ["state"] = 0, ["name"] = "Preserved Farms", },

["region2"] = {["mission"] = "Mission2", ["state"] = 0, ["name"] = "Old Town", },

["region3"] = {["mission"] = "Mission5", ["state"] = 0, ["name"] = "OhmTown", },

["region4"] = {["mission"] = "Mission6", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission6", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Repair_Briefing_CEO_Grass_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 1103182704, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "any21", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 14, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 4, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 17, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 20, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 6, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 0, ["item"] = "Item_Repair_Mine", },
{["loc"] = Point( 2, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 37, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 42, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 4 ), ["terrain"] = 0, ["item"] = "Item_Repair_Mine", },
{["loc"] = Point( 2, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 54, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 87, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 6, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 0, ["item"] = "Item_Repair_Mine", },
{["loc"] = Point( 4, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 52, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 51, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 64, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 58, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 7 ), ["terrain"] = 6, },
{["loc"] = Point( 5, 1 ), ["terrain"] = 0, ["item"] = "Item_Repair_Mine", },
{["loc"] = Point( 5, 2 ), ["terrain"] = 0, ["item"] = "Item_Repair_Mine", },
{["loc"] = Point( 5, 6 ), ["terrain"] = 0, ["item"] = "Item_Repair_Mine", },
{["loc"] = Point( 5, 7 ), ["terrain"] = 6, },
{["loc"] = Point( 6, 0 ), ["terrain"] = 6, },
{["loc"] = Point( 6, 4 ), ["terrain"] = 0, ["item"] = "Item_Repair_Mine", },
{["loc"] = Point( 6, 5 ), ["terrain"] = 0, ["item"] = "Item_Repair_Mine", },
},
["rain"] = 3, ["rain_type"] = 0, ["spawns"] = {"Leaper1", "Mosquito1", },
["spawn_ids"] = {229, 230, },
["spawn_points"] = {Point(7,2), Point(5,4), },
["zones"] = {},
["tags"] = {"generic", "any_sector", },
["pawn_count"] = 0, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Storage Vaults", },

["region5"] = {["mission"] = "Mission1", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 3, ["iTeamTurn"] = 1, ["iState"] = 0, ["sMission"] = "Mission1", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Armored_Train_Briefing_CEO_Grass_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 3, ["aiDelay"] = 0.000000, ["aiSeed"] = 1530344591, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "train0", ["enemy_kills"] = 5, 
["map"] = {{["loc"] = Point( 0, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 26, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_research1", ["people1"] = 40, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 6, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 0, ["smoke"] = 1, ["smoke"] = 1, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 26, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 38, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 140, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 2, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 2, 5 ), ["terrain"] = 0, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 94, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 2, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 3, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 3, 3 ), ["terrain"] = 0, ["smoke"] = 1, ["smoke"] = 1, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 3, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 0 ), ["terrain"] = 0, ["custom"] = "ground_rail.png", },
{["loc"] = Point( 4, 1 ), ["terrain"] = 0, ["custom"] = "ground_rail.png", },
{["loc"] = Point( 4, 2 ), ["terrain"] = 0, ["custom"] = "ground_rail.png", },
{["loc"] = Point( 4, 3 ), ["terrain"] = 0, ["custom"] = "ground_rail.png", },
{["loc"] = Point( 4, 4 ), ["terrain"] = 0, ["custom"] = "ground_rail.png", },
{["loc"] = Point( 4, 5 ), ["terrain"] = 0, ["smoke"] = 1, ["smoke"] = 1, ["custom"] = "ground_rail.png", },
{["loc"] = Point( 4, 6 ), ["terrain"] = 0, ["smoke"] = 1, ["smoke"] = 1, ["custom"] = "ground_rail.png", },
{["loc"] = Point( 4, 7 ), ["terrain"] = 0, ["custom"] = "ground_rail.png", },
{["loc"] = Point( 5, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 136, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 5, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 2 ), ["terrain"] = 6, },
{["loc"] = Point( 6, 3 ), ["terrain"] = 0, ["smoke"] = 1, ["smoke"] = 1, },
{["loc"] = Point( 6, 4 ), ["terrain"] = 0, ["smoke"] = 1, ["smoke"] = 1, },
{["loc"] = Point( 6, 5 ), ["terrain"] = 0, },
{["loc"] = Point( 6, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 4, },
},
["pod"] = Point(5,4), ["spawns"] = {},
["spawn_ids"] = {},
["spawn_points"] = {},
["zones"] = {},
["tags"] = {"train", "any_sector", },


["pawn1"] = {["type"] = "JetMech", ["name"] = "", ["id"] = 0, ["mech"] = true, ["offset"] = 1, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Brute_Jetmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 0, ["exp"] = 50, ["level"] = 2, ["travel"] = 3, ["final"] = 2, ["starting"] = true, ["last_end"] = 2, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 1, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 4, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,4), ["last_location"] = Point(3,2), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 3, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 6, ["iOwner"] = 0, ["piTarget"] = Point(3,4), ["piOrigin"] = Point(3,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,4), },


["pawn2"] = {["type"] = "RocketMech", ["name"] = "", ["id"] = 1, ["mech"] = true, ["offset"] = 1, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 1, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {1, },
["primary"] = "Ranged_Rocket", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["secondary"] = "Passive_Electric", ["secondary_power"] = {},
["secondary_power_class"] = false, ["secondary_mod1"] = {0, 0, 0, },
["secondary_mod2"] = {0, },
["secondary_damaged"] = false, ["secondary_starting"] = true, ["secondary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Detritus", ["name"] = "Zoe Koleda", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 7, ["skill2"] = 8, ["exp"] = 25, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 1, ["is_corpse"] = true, ["health"] = 5, ["max_health"] = 5, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(2,4), ["last_location"] = Point(2,5), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 3, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 6, ["iOwner"] = 1, ["piTarget"] = Point(5,4), ["piOrigin"] = Point(2,4), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,4), },


["pawn3"] = {["type"] = "PulseMech", ["name"] = "", ["id"] = 2, ["mech"] = true, ["offset"] = 1, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Science_Repulse", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 1, ["is_corpse"] = true, ["health"] = 2, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,4), ["last_location"] = Point(6,3), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 3, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 2, ["piTarget"] = Point(4,2), ["piOrigin"] = Point(4,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,2), },


["pawn4"] = {["type"] = "Crab1", ["name"] = "", ["id"] = 237, ["mech"] = false, ["offset"] = 0, ["primary"] = "CrabAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(2,5), ["last_location"] = Point(3,5), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 1698980969, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 237, ["piTarget"] = Point(2,3), ["piOrigin"] = Point(2,5), ["piQueuedShot"] = Point(2,3), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(2,3), },


["pawn5"] = {["type"] = "Mosquito1", ["name"] = "", ["id"] = 238, ["mech"] = false, ["offset"] = 0, ["primary"] = "MosquitoAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,5), ["last_location"] = Point(6,4), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 1698980969, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 238, ["piTarget"] = Point(6,4), ["piOrigin"] = Point(6,5), ["piQueuedShot"] = Point(6,4), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(6,4), },


["pawn6"] = {["type"] = "Train_Armored", ["name"] = "", ["id"] = 231, ["mech"] = false, ["offset"] = 0, ["primary"] = "Armored_Train_Move", ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Archive", ["name"] = "Stefan Volkov", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 5, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = false, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 1, ["max_health"] = 1, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,2), ["last_location"] = Point(4,2), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 3, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 231, ["piTarget"] = Point(4,1), ["piOrigin"] = Point(4,2), ["piQueuedShot"] = Point(4,1), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,1), },
["pawn_count"] = 6, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Antiquity Row", },

["region6"] = {["mission"] = "Mission4", ["state"] = 0, ["name"] = "Exhibits Archive", },

["region7"] = {["mission"] = "", ["state"] = 2, ["name"] = "Corporate HQ", ["objectives"] = {},
},
["iBattleRegion"] = 5, }
 

GAME = { 
["WeaponDeck"] = { 
[1] = "Prime_Punchmech", 
[2] = "Prime_Lightning", 
[3] = "Prime_Lasermech", 
[4] = "Prime_Rockmech", 
[5] = "Prime_RightHook", 
[6] = "Prime_RocketPunch", 
[7] = "Prime_Shift", 
[8] = "Prime_Flamethrower", 
[9] = "Prime_Areablast", 
[10] = "Prime_Leap", 
[11] = "Prime_SpinFist", 
[12] = "Prime_Sword", 
[13] = "Prime_Smash", 
[14] = "Brute_Tankmech", 
[15] = "Brute_Mirrorshot", 
[16] = "Brute_PhaseShot", 
[17] = "Brute_Grapple", 
[18] = "Brute_Shrapnel", 
[19] = "Brute_Sniper", 
[20] = "Brute_Shockblast", 
[21] = "Brute_Beetle", 
[22] = "Brute_Unstable", 
[23] = "Brute_Heavyrocket", 
[24] = "Brute_Splitshot", 
[25] = "Brute_Bombrun", 
[26] = "Brute_Sonic", 
[27] = "Ranged_Artillerymech", 
[28] = "Ranged_Rockthrow", 
[29] = "Ranged_Defensestrike", 
[30] = "Ranged_Ignite", 
[31] = "Ranged_ScatterShot", 
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
[43] = "Science_SmokeDefense", 
[44] = "Science_Shield", 
[45] = "Science_FreezeBeam", 
[46] = "Science_LocalShield", 
[47] = "Science_PushBeam", 
[48] = "Support_Boosters", 
[49] = "Support_Smoke", 
[50] = "Support_Refrigerate", 
[51] = "Support_Destruct", 
[52] = "DeploySkill_ShieldTank", 
[53] = "DeploySkill_Tank", 
[54] = "DeploySkill_AcidTank", 
[55] = "DeploySkill_PullTank", 
[56] = "Support_Force", 
[57] = "Support_SmokeDrop", 
[58] = "Support_Repair", 
[59] = "Support_Missiles", 
[60] = "Support_Wind", 
[61] = "Support_Blizzard", 
[62] = "Passive_Leech", 
[63] = "Passive_MassRepair", 
[64] = "Passive_Defenses", 
[65] = "Passive_Burrows", 
[66] = "Passive_AutoShields", 
[67] = "Passive_Psions", 
[68] = "Passive_Boosters", 
[69] = "Passive_Medical", 
[70] = "Passive_FriendlyFire", 
[71] = "Passive_ForceAmp", 
[72] = "Passive_CritDefense", 
[73] = "Prime_Flamespreader", 
[74] = "Prime_WayTooBig", 
[75] = "Prime_PrismLaser", 
[76] = "Prime_TC_Punt", 
[77] = "Prime_TC_BendBeam", 
[78] = "Prime_TC_Feint", 
[79] = "Prime_KO_Crack", 
[80] = "Brute_KickBack", 
[81] = "Brute_PierceShot", 
[82] = "Brute_TC_GuidedMissile", 
[83] = "Brute_TC_Ricochet", 
[84] = "Brute_TC_DoubleShot", 
[85] = "Brute_KO_Combo", 
[86] = "Ranged_Crack", 
[87] = "Ranged_DeployBomb", 
[88] = "Ranged_Arachnoid", 
[89] = "Ranged_SmokeFire", 
[90] = "Ranged_TC_BounceShot", 
[91] = "Ranged_TC_DoubleArt", 
[92] = "Ranged_KO_Combo", 
[93] = "Science_RainingFire", 
[94] = "Science_MassShift", 
[95] = "Science_TelePush", 
[96] = "Science_TC_Control", 
[97] = "Science_TC_Enrage", 
[98] = "Science_TC_SwapOther", 
[99] = "Science_KO_Crack", 
[100] = "Support_Confuse", 
[101] = "Support_GridDefense", 
[102] = "Support_Waterdrill", 
[103] = "Support_TC_GridAtk", 
[104] = "Support_TC_Bombline", 
[105] = "Support_KO_GridCharger", 
[106] = "Passive_HealingSmoke", 
[107] = "Passive_FireBoost", 
[108] = "Passive_PlayerTurnShield", 
[109] = "Passive_VoidShock" 
}, 
["PodWeaponDeck"] = { 
[1] = "Prime_Areablast", 
[2] = "Prime_Leap", 
[3] = "Prime_SpinFist", 
[4] = "Prime_Sword", 
[5] = "Prime_Smash", 
[6] = "Brute_Grapple", 
[7] = "Brute_Sniper", 
[8] = "Brute_Shockblast", 
[9] = "Brute_Beetle", 
[10] = "Brute_Heavyrocket", 
[11] = "Brute_Bombrun", 
[12] = "Brute_Sonic", 
[13] = "Ranged_Ice", 
[14] = "Ranged_SmokeBlast", 
[15] = "Ranged_Fireball", 
[16] = "Ranged_RainingVolley", 
[17] = "Science_SmokeDefense", 
[18] = "Science_Shield", 
[19] = "Science_FreezeBeam", 
[20] = "Science_LocalShield", 
[21] = "Science_PushBeam", 
[22] = "Support_Boosters", 
[23] = "Support_Smoke", 
[24] = "Support_Refrigerate", 
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
[36] = "Passive_Leech", 
[37] = "Passive_MassRepair", 
[38] = "Passive_Defenses", 
[39] = "Passive_Burrows", 
[40] = "Passive_AutoShields", 
[41] = "Passive_Psions", 
[42] = "Passive_Boosters", 
[43] = "Passive_Medical", 
[44] = "Passive_FriendlyFire", 
[45] = "Passive_ForceAmp", 
[46] = "Passive_CritDefense", 
[47] = "Prime_WayTooBig", 
[48] = "Prime_PrismLaser", 
[49] = "Prime_TC_BendBeam", 
[50] = "Prime_TC_Feint", 
[51] = "Brute_TC_GuidedMissile", 
[52] = "Brute_KO_Combo", 
[53] = "Ranged_TC_BounceShot", 
[54] = "Ranged_TC_DoubleArt", 
[55] = "Ranged_KO_Combo", 
[56] = "Science_TelePush", 
[57] = "Science_TC_Enrage", 
[58] = "Support_Confuse", 
[59] = "Support_GridDefense", 
[60] = "Support_Waterdrill", 
[61] = "Support_TC_GridAtk", 
[62] = "Support_TC_Bombline", 
[63] = "Support_KO_GridCharger", 
[64] = "Passive_HealingSmoke", 
[65] = "Passive_FireBoost", 
[66] = "Passive_PlayerTurnShield", 
[67] = "Passive_VoidShock" 
}, 
["PilotDeck"] = { 
[1] = "Pilot_Soldier", 
[2] = "Pilot_Youth", 
[3] = "Pilot_Warrior", 
[4] = "Pilot_Aquatic", 
[5] = "Pilot_Medic", 
[6] = "Pilot_Genius", 
[7] = "Pilot_Miner", 
[8] = "Pilot_Recycler", 
[9] = "Pilot_Assassin", 
[10] = "Pilot_Leader", 
[11] = "Pilot_Arrogant", 
[12] = "Pilot_Caretaker", 
[13] = "Pilot_Chemical", 
[14] = "Pilot_Delusional" 
}, 
["SeenPilots"] = { 
[1] = "Pilot_Original", 
[2] = "Pilot_Detritus", 
[3] = "Pilot_Rust", 
[4] = "Pilot_Hotshot", 
[5] = "Pilot_Repairman" 
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
[1] = "Mission_HornetBoss", 
[2] = "Mission_BouncerBoss", 
[3] = "Mission_BurnbugBoss", 
[4] = "Mission_ScorpionBoss" 
}, 
["Island"] = 1, 
["Missions"] = { 
[1] = { 
["BonusObjs"] = { 
[1] = 1 
}, 
["TrainLoc"] = Point( 4, 2 ), 
["AssetId"] = "Str_Research", 
["Train"] = 231, 
["LiveEnvironment"] = { 
}, 
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
["Jelly_Armor"] = 1, 
["Firefly"] = 1, 
["Mosquito"] = 2, 
["Leaper"] = 2, 
["Crab"] = 1 
} 
}, 
["AssetLoc"] = Point( 0, 2 ), 
["ID"] = "Mission_Armored_Train", 
["VoiceEvents"] = { 
}, 
["DiffMod"] = 2, 
["PowerStart"] = 7 
}, 
[2] = { 
["ID"] = "Mission_Survive", 
["BonusObjs"] = { 
[1] = 6, 
[2] = 1 
}, 
["AssetId"] = "Str_Nimbus" 
}, 
[3] = { 
["ID"] = "Mission_Tanks", 
["BonusObjs"] = { 
} 
}, 
[4] = { 
["ID"] = "Mission_Satellite", 
["BonusObjs"] = { 
[1] = 1 
}, 
["DiffMod"] = 2, 
["AssetId"] = "Str_Power" 
}, 
[5] = { 
["ID"] = "Mission_Tides", 
["BonusObjs"] = { 
[1] = 1 
}, 
["DiffMod"] = 1, 
["AssetId"] = "Str_Power" 
}, 
[6] = { 
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
["Leaper"] = 1, 
["Mosquito"] = 1 
} 
}, 
["LiveEnvironment"] = { 
}, 
["MineCount"] = 8, 
["ID"] = "Mission_Repair", 
["VoiceEvents"] = { 
}, 
["BonusObjs"] = { 
[1] = 3 
}, 
["MineLocations"] = { 
[1] = Point( 6, 4 ), 
[2] = Point( 5, 6 ), 
[3] = Point( 5, 1 ), 
[4] = Point( 1, 4 ), 
[5] = Point( 6, 5 ), 
[6] = Point( 3, 4 ), 
[7] = Point( 5, 2 ), 
[8] = Point( 2, 4 ) 
} 
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
["ID"] = "Mission_HornetBoss", 
["BonusObjs"] = { 
[1] = 1 
}, 
["AssetId"] = "Str_Tower" 
} 
}, 
["Enemies"] = { 
[1] = { 
[1] = "Leaper", 
[2] = "Mosquito", 
[3] = "Firefly", 
[4] = "Jelly_Armor", 
[5] = "Crab", 
[6] = "Shaman", 
["island"] = 1 
}, 
[2] = { 
[1] = "Scorpion", 
[2] = "Hornet", 
[3] = "Scarab", 
[4] = "Jelly_Health", 
[5] = "Dung", 
[6] = "Beetle", 
["island"] = 2 
}, 
[3] = { 
[1] = "Burnbug", 
[2] = "Moth", 
[3] = "Bouncer", 
[4] = "Jelly_Regen", 
[5] = "Digger", 
[6] = "Blobber", 
["island"] = 3 
}, 
[4] = { 
[1] = "Leaper", 
[2] = "Bouncer", 
[3] = "Firefly", 
[4] = "Jelly_Fire", 
[5] = "Centipede", 
[6] = "Spider", 
["island"] = 4 
} 
} 
}

 

SquadData = {
["money"] = 0, ["cores"] = 0, ["bIsFavor"] = false, ["repairs"] = 0, ["CorpReward"] = {CreateEffect({weapon = "Prime_Spear",}), CreateEffect({skill1 = "Invulnerable",skill2 = "Skilled",pilot = "Pilot_Repairman",}), CreateEffect({power = 2,}), },
["RewardClaimed"] = false, 
["skip_pawns"] = true, 

["storage_size"] = 3, ["CorpStore"] = {CreateEffect({weapon = "Passive_FlameImmune",money = -2,}), CreateEffect({weapon = "Prime_ShieldBash",money = -2,}), CreateEffect({weapon = "Brute_Fracture",money = -2,}), CreateEffect({stock = 0,}), CreateEffect({money = -3,stock = -1,cores = 1,}), CreateEffect({money = -1,power = 1,stock = -1,}), },
["island_store_count"] = 1, ["store_undo_size"] = 0, }
 

