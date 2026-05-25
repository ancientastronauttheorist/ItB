GameData = {["save_version"] = 1, ["language"] = 1, ["network"] = 5, ["networkMax"] = 7, ["overflow"] = 13, ["seed"] = 460474742, ["new_enemies"] = 0, ["new_missions"] = 0, ["new_equip"] = 0, ["difficulty"] = 0, ["new_abilities"] = 0, ["ach_info"] = {["squad"] = "Rust_B", ["trackers"] = {["Detritus_B_2"] = 0, ["Global_Challenge_Power"] = 0, ["Archive_A_1"] = 0, ["Archive_B_2"] = 0, ["Rust_A_2"] = 0, ["Rust_A_3"] = 0, ["Pinnacle_A_3"] = 0, ["Archive_B_1"] = 0, ["Pinnacle_B_3"] = 0, ["Detritus_B_1"] = 0, ["Pinnacle_B_1"] = 0, ["Global_Island_Mechs"] = 20, ["Global_Island_Building"] = 0, ["Squad_Mist_1"] = 0, ["Squad_Bomber_2"] = 0, ["Squad_Spiders_1"] = 0, ["Squad_Mist_2"] = 0, ["Squad_Heat_1"] = 0, ["Squad_Cataclysm_1"] = 0, ["Squad_Cataclysm_2"] = 0, ["Squad_Cataclysm_3"] = 0, },
},


["current"] = {["score"] = 8707, ["time"] = 39837120.000000, ["kills"] = 93, ["damage"] = 0, ["failures"] = 12, ["difficulty"] = 0, ["victory"] = false, ["islands"] = 3, ["squad"] = 5, 
["mechs"] = {"FlameMech", "IgniteMech", "TeleMech", },
["colors"] = {5, 5, 5, },
["weapons"] = {"Prime_Flamethrower_A", "Passive_FlameImmune", "Ranged_Ignite_A", "Support_Wind_A", "Science_Swap_A", "", },
["pilot0"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 0, ["exp"] = 50, ["level"] = 2, ["travel"] = 1, ["final"] = 1, ["starting"] = true, ["last_end"] = 2, },
["pilot1"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Fenrir", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 1, ["exp"] = 22, ["level"] = 2, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot2"] = {["id"] = "Pilot_Artificial", ["name"] = "A.I. Unit", ["name_id"] = "Pilot_Artificial_Name", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 0, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = false, },
},
["current_squad"] = 5, ["undosave"] = true, }
 

RegionData = {
["sector"] = 3, ["island"] = 2, ["secret"] = false, 
["island0"] = {["corporation"] = "Corp_Grass", ["id"] = 0, ["secured"] = true, },
["island1"] = {["corporation"] = "Corp_Desert", ["id"] = 1, ["secured"] = true, },
["island2"] = {["corporation"] = "Corp_Snow", ["id"] = 2, ["secured"] = false, },
["island3"] = {["corporation"] = "Corp_Factory", ["id"] = 3, ["secured"] = true, },

["turn"] = 4, ["iTower"] = 2, ["quest_tracker"] = 1, ["quest_id"] = 0, ["podRewards"] = {},


["region0"] = {["mission"] = "", ["state"] = 3, ["name"] = "Sub-Zero Range", ["objectives"] = {["0"] = {["text"] = "Bonus_Simple_Vek", ["param1"] = "", ["param2"] = "", ["value"] = 0, ["potential"] = 1, ["category"] = 0, },
},
},

["region1"] = {["mission"] = "", ["state"] = 2, ["name"] = "Lifeless Basin", ["objectives"] = {["0"] = {["text"] = "Bonus_Simple_Kill_Five", ["param1"] = "5", ["param2"] = "", ["value"] = 0, ["potential"] = 1, ["category"] = 0, },
["1"] = {["text"] = "Bonus_Simple_Asset", ["param1"] = "Str_Power_Name", ["param2"] = "", ["value"] = 1, ["potential"] = 1, ["category"] = 1, },
["2"] = {["text"] = "Pod_Objective", ["param1"] = "", ["param2"] = "", ["value"] = 1, ["potential"] = 1, ["category"] = 3, },
},
},

["region2"] = {["mission"] = "Mission8", ["player"] = {["battle_type"] = 1, ["iCurrentTurn"] = 4, ["iTeamTurn"] = 1, ["iState"] = 0, ["sMission"] = "Mission8", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_BossGeneric_Briefing_CEO_Snow_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 3, ["aiDelay"] = 0.000000, ["aiSeed"] = 1238239213, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "snow21", ["enemy_kills"] = 3, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 6, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 6, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 66, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 5 ), ["terrain"] = 6, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 74, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 0 ), ["terrain"] = 5, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_tower1", ["people1"] = 27, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 34, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 137, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 0 ), ["terrain"] = 5, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 0, ["fire"] = 1, },
{["loc"] = Point( 3, 3 ), ["terrain"] = 4, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 88, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 0 ), ["terrain"] = 4, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 3, ["health_max"] = 2, ["health_min"] = 0, },
{["loc"] = Point( 4, 2 ), ["terrain"] = 0, ["fire"] = 1, },
{["loc"] = Point( 4, 3 ), ["terrain"] = 0, ["grapple_targets"] = {2, },
},
{["loc"] = Point( 4, 4 ), ["terrain"] = 0, ["grappled"] = 1, },
{["loc"] = Point( 4, 5 ), ["terrain"] = 0, ["fire"] = 1, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 2, ["health_max"] = 2, ["health_min"] = 0, ["rubble_type"] = 1, },
{["loc"] = Point( 5, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 5, 2 ), ["terrain"] = 0, ["grappled"] = 1, },
{["loc"] = Point( 5, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 74, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 6, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 1 ), ["terrain"] = 5, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 6, 2 ), ["terrain"] = 5, ["grapple_targets"] = {3, },
},
{["loc"] = Point( 6, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 6, 5 ), ["terrain"] = 0, ["fire"] = 2, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 6, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 2 ), ["terrain"] = 5, },
},
["pod"] = Point(4,2), ["spawns"] = {},
["spawn_ids"] = {},
["spawn_points"] = {},
["zones"] = {},
["tags"] = {"generic", "snow", },


["pawn1"] = {["type"] = "FlameMech", ["name"] = "", ["id"] = 0, ["mech"] = true, ["offset"] = 5, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 2, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {1, },
["healthPower"] = {0, },
["primary"] = "Prime_Flamethrower", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {1, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["secondary"] = "Passive_FlameImmune", ["secondary_power"] = {},
["secondary_power_class"] = false, ["secondary_mod1"] = {0, },
["secondary_mod2"] = {0, },
["secondary_damaged"] = false, ["secondary_starting"] = true, ["secondary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 0, ["exp"] = 50, ["level"] = 2, ["travel"] = 1, ["final"] = 1, ["starting"] = true, ["last_end"] = 2, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 1, ["is_corpse"] = true, ["health"] = 4, ["max_health"] = 5, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,2), ["last_location"] = Point(4,2), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 9, ["iOwner"] = 0, ["piTarget"] = Point(5,1), ["piOrigin"] = Point(5,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,1), },


["pawn2"] = {["type"] = "IgniteMech", ["name"] = "", ["id"] = 1, ["mech"] = true, ["offset"] = 5, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 3, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {1, },
["healthPower"] = {0, },
["primary"] = "Ranged_Ignite", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {1, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["secondary"] = "Support_Wind", ["secondary_power"] = {},
["secondary_power_class"] = false, ["secondary_mod1"] = {1, },
["secondary_mod2"] = {0, },
["secondary_damaged"] = false, ["secondary_starting"] = true, ["secondary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Fenrir", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 1, ["exp"] = 22, ["level"] = 2, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 5, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,5), ["last_location"] = Point(4,4), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 2, ["iOwner"] = 1, ["piTarget"] = Point(4,2), ["piOrigin"] = Point(4,4), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,2), },


["pawn3"] = {["type"] = "TeleMech", ["name"] = "", ["id"] = 2, ["mech"] = true, ["offset"] = 5, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 3, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {1, },
["healthPower"] = {1, },
["primary"] = "Science_Swap", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {1, },
["primary_mod2"] = {0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 1, ["max_health"] = 4, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,4), ["last_location"] = Point(5,4), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 2, ["piTarget"] = Point(5,4), ["piOrigin"] = Point(6,4), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,4), },


["pawn4"] = {["type"] = "ScorpionBoss", ["name"] = "", ["id"] = 751, ["mech"] = false, ["offset"] = 2, ["primary"] = "ScorpionAtkB", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["bOnFire"] = true, ["health"] = 1, ["max_health"] = 7, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,2), ["last_location"] = Point(6,3), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 751, ["piTarget"] = Point(6,2), ["piOrigin"] = Point(6,2), ["piQueuedShot"] = Point(6,2), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(6,2), },


["pawn5"] = {["type"] = "Beetle1", ["name"] = "", ["id"] = 755, ["mech"] = false, ["offset"] = 0, ["primary"] = "BeetleAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 4, ["max_health"] = 4, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,4), ["last_location"] = Point(6,5), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 809116260, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 755, ["piTarget"] = Point(5,4), ["piOrigin"] = Point(6,4), ["piQueuedShot"] = Point(5,4), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,4), },


["pawn6"] = {["type"] = "Leaper1", ["name"] = "", ["id"] = 756, ["mech"] = false, ["offset"] = 0, ["primary"] = "LeaperAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 1, ["max_health"] = 1, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,3), ["last_location"] = Point(5,3), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 809116260, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 756, ["piTarget"] = Point(4,4), ["piOrigin"] = Point(4,3), ["piQueuedShot"] = Point(4,4), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,4), },
["pawn_count"] = 6, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Corporate HQ", },

["region3"] = {["mission"] = "", ["state"] = 2, ["name"] = "Robotics Repair", ["objectives"] = {["0"] = {["text"] = "Bonus_Simple_Vek", ["param1"] = "", ["param2"] = "", ["value"] = 0, ["potential"] = 1, ["category"] = 0, },
["1"] = {["text"] = "Bonus_Simple_Asset", ["param1"] = "Str_Power_Name", ["param2"] = "", ["value"] = 1, ["potential"] = 1, ["category"] = 1, },
["2"] = {["text"] = "Pod_Objective", ["param1"] = "", ["param2"] = "", ["value"] = 1, ["potential"] = 1, ["category"] = 3, },
},
},

["region4"] = {["mission"] = "", ["state"] = 3, ["name"] = "Cryogenic Labs", ["objectives"] = {["0"] = {["text"] = "Mission_BotDefense_Obj", ["param1"] = "", ["param2"] = "", ["value"] = 2, ["potential"] = 2, ["category"] = 0, },
},
},

["region5"] = {["mission"] = "", ["state"] = 2, ["name"] = "Thermal Dampeners", ["objectives"] = {["0"] = {["text"] = "Mission_Factory_Objective", ["param1"] = "", ["param2"] = "", ["value"] = 1, ["potential"] = 2, ["category"] = 0, },
["1"] = {["text"] = "Bonus_Simple_Asset", ["param1"] = "Str_Research_Name", ["param2"] = "", ["value"] = 1, ["potential"] = 1, ["category"] = 2, },
},
},

["region6"] = {["mission"] = "", ["state"] = 2, ["name"] = "Frozen Plains", ["objectives"] = {["0"] = {["text"] = "Bonus_Simple_Grid", ["param1"] = "", ["param2"] = "", ["value"] = 1, ["potential"] = 1, ["category"] = 0, },
["1"] = {["text"] = "Bonus_Simple_Asset", ["param1"] = "Str_Nimbus_Name", ["param2"] = "", ["value"] = 1, ["potential"] = 1, ["category"] = 1, },
},
},

["region7"] = {["mission"] = "", ["state"] = 3, ["name"] = "District Z-1001", ["objectives"] = {},
},
["iBattleRegion"] = 2, }
 

GAME = { 
["WeaponDeck"] = { 
[27] = "Ranged_Fireball", 
[31] = "Science_Gravwell", 
[38] = "Science_PushBeam", 
[46] = "Support_SmokeDrop", 
[54] = "Passive_Boosters", 
[4] = "Prime_ShieldBash", 
[5] = "Prime_Rockmech", 
[6] = "Prime_RightHook", 
[7] = "Prime_RocketPunch", 
[8] = "Prime_Areablast", 
[39] = "Support_Boosters", 
[12] = "Prime_Sword", 
[55] = "Passive_Medical", 
[16] = "Brute_PhaseShot", 
[20] = "Brute_Splitshot", 
[24] = "Ranged_Rocket", 
[28] = "Ranged_RainingVolley", 
[32] = "Science_Repulse", 
[40] = "Support_Smoke", 
[48] = "Support_Missiles", 
[56] = "Passive_FriendlyFire", 
[33] = "Science_AcidShot", 
[41] = "Support_Refrigerate", 
[49] = "Support_Blizzard", 
[57] = "Passive_ForceAmp", 
[17] = "Brute_Grapple", 
[21] = "Ranged_Artillerymech", 
[25] = "Ranged_ScatterShot", 
[29] = "Ranged_Wide", 
[34] = "Science_Confuse", 
[42] = "Support_Destruct", 
[50] = "Passive_Leech", 
[58] = "Passive_CritDefense", 
[47] = "Support_Repair", 
[10] = "Prime_Leap", 
[9] = "Prime_Spear", 
[43] = "DeploySkill_ShieldTank", 
[51] = "Passive_MassRepair", 
[15] = "Brute_Mirrorshot", 
[18] = "Brute_Shrapnel", 
[22] = "Ranged_Rockthrow", 
[26] = "Ranged_Ice", 
[30] = "Ranged_Dual", 
[36] = "Science_Shield", 
[44] = "DeploySkill_PullTank", 
[52] = "Passive_Defenses", 
[35] = "Science_SmokeDefense", 
[11] = "Prime_SpinFist", 
[14] = "Brute_Jetmech", 
[3] = "Prime_Lasermech", 
[13] = "Brute_Tankmech", 
[37] = "Science_FireBeam", 
[45] = "Support_Force", 
[53] = "Passive_AutoShields", 
[1] = "Prime_Punchmech", 
[19] = "Brute_Unstable", 
[23] = "Ranged_Defensestrike", 
[2] = "Prime_Lightning" 
}, 
["PodWeaponDeck"] = { 
[27] = "Passive_MassRepair", 
[2] = "Prime_Spear", 
[3] = "Prime_Leap", 
[4] = "Prime_SpinFist", 
[5] = "Prime_Sword", 
[6] = "Brute_Grapple", 
[7] = "Ranged_Ice", 
[8] = "Ranged_Fireball", 
[10] = "Ranged_Dual", 
[12] = "Science_Shield", 
[14] = "Science_PushBeam", 
[16] = "Support_Smoke", 
[20] = "DeploySkill_PullTank", 
[24] = "Support_Missiles", 
[28] = "Passive_Defenses", 
[32] = "Passive_FriendlyFire", 
[33] = "Passive_ForceAmp", 
[17] = "Support_Refrigerate", 
[21] = "Support_Force", 
[25] = "Support_Blizzard", 
[29] = "Passive_AutoShields", 
[34] = "Passive_CritDefense", 
[9] = "Ranged_RainingVolley", 
[11] = "Science_SmokeDefense", 
[13] = "Science_FireBeam", 
[15] = "Support_Boosters", 
[18] = "Support_Destruct", 
[22] = "Support_SmokeDrop", 
[26] = "Passive_Leech", 
[30] = "Passive_Boosters", 
[1] = "Prime_Areablast", 
[19] = "DeploySkill_ShieldTank", 
[23] = "Support_Repair", 
[31] = "Passive_Medical" 
}, 
["PilotDeck"] = { 
[2] = "Pilot_Youth", 
[3] = "Pilot_Medic", 
[1] = "Pilot_Soldier", 
[4] = "Pilot_Recycler", 
[5] = "Pilot_Repairman" 
}, 
["SeenPilots"] = { 
[7] = "Pilot_Genius", 
[1] = "Pilot_Original", 
[2] = "Pilot_Pinnacle", 
[4] = "Pilot_Aquatic", 
[8] = "Pilot_Warrior", 
[9] = "Pilot_Leader", 
[5] = "Pilot_Assassin", 
[10] = "Pilot_Hotshot", 
[3] = "Pilot_Archive", 
[6] = "Pilot_Miner" 
}, 
["PodDeck"] = { 
[3] = { 
["cores"] = 1, 
["weapon"] = "random" 
}, 
[2] = { 
["cores"] = 1 
}, 
[4] = { 
["cores"] = 1, 
["weapon"] = "random" 
}, 
[1] = { 
["cores"] = 1 
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
[6] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 9, 
["curr_weakRatio"] = { 
[1] = 1, 
[2] = 1 
}, 
["curr_upgradeRatio"] = { 
[1] = 1, 
[2] = 1 
}, 
["upgrade_streak"] = 0, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Scarab"] = 2, 
["Beetle"] = 2, 
["Hornet"] = 3, 
["Leaper"] = 1, 
["Jelly_Explode"] = 1 
} 
}, 
["AssetId"] = "Str_Nimbus", 
["BonusObjs"] = { 
[1] = 3, 
[2] = 1 
}, 
["AssetLoc"] = Point( 2, 3 ), 
["ID"] = "Mission_SnowStorm", 
["VoiceEvents"] = { 
}, 
["LiveEnvironment"] = { 
["Options"] = { 
}, 
["Planned"] = { 
[1] = Point( 5, 3 ), 
[2] = Point( 5, 2 ), 
[3] = Point( 6, 2 ), 
[4] = Point( 6, 3 ), 
[5] = Point( 6, 4 ), 
[6] = Point( 5, 4 ), 
[7] = Point( 4, 4 ), 
[8] = Point( 4, 3 ), 
[9] = Point( 4, 2 ) 
}, 
["EndEffect"] = true, 
["Locations"] = { 
}, 
["StartEffect"] = true, 
["LastLoc"] = Point( 5, 3 ) 
}, 
["PowerStart"] = 4 
}, 
[2] = { 
["BonusObjs"] = { 
[1] = 5, 
[2] = 1 
}, 
["BlockedSpawns"] = 0, 
["Spawner"] = { 
["used_bosses"] = 0, 
["pawn_counts"] = { 
["Snowlaser"] = 1, 
["Scarab"] = 2, 
["Snowtank"] = 1, 
["Snowart"] = 1, 
["Beetle"] = 1, 
["Hornet"] = 1, 
["Leaper"] = 1, 
["Jelly_Explode"] = 1 
}, 
["curr_weakRatio"] = { 
[1] = 1, 
[2] = 1 
}, 
["num_bosses"] = 0, 
["curr_upgradeRatio"] = { 
[1] = 1, 
[2] = 1 
}, 
["num_spawns"] = 9, 
["upgrade_streak"] = 0 
}, 
["LiveEnvironment"] = { 
}, 
["AssetLoc"] = Point( 0, 6 ), 
["ID"] = "Mission_SnowBattle", 
["VoiceEvents"] = { 
}, 
["AssetId"] = "Str_Power", 
["PowerStart"] = 7 
}, 
[8] = { 
["BonusObjs"] = { 
[1] = 1 
}, 
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
["Scarab"] = 1, 
["Beetle"] = 1, 
["Scorpion"] = 1, 
["Leaper"] = 2, 
["Jelly_Explode"] = 1 
} 
}, 
["LiveEnvironment"] = { 
}, 
["BossID"] = 751, 
["AssetLoc"] = Point( 2, 1 ), 
["ID"] = "Mission_ScorpionBoss", 
["VoiceEvents"] = { 
}, 
["AssetId"] = "Str_Tower", 
["PowerStart"] = 5 
}, 
[3] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["upgrade_streak"] = 0, 
["curr_weakRatio"] = { 
[1] = 2, 
[2] = 2 
}, 
["num_spawns"] = 3, 
["curr_upgradeRatio"] = { 
[1] = 1, 
[2] = 2 
}, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Scarab"] = 1, 
["Spider"] = 1, 
["Hornet"] = 1 
} 
}, 
["LiveEnvironment"] = { 
}, 
["ID"] = "Mission_BotDefense", 
["VoiceEvents"] = { 
}, 
["Bots"] = { 
[1] = 562, 
[2] = 563 
}, 
["BonusObjs"] = { 
} 
}, 
[1] = { 
["BonusObjs"] = { 
[1] = 6, 
[2] = 1 
}, 
["LiveEnvironment"] = { 
}, 
["MineLocations"] = { 
[6] = Point( 5, 1 ), 
[2] = Point( 2, 2 ), 
[8] = Point( 5, 2 ), 
[3] = Point( 5, 4 ), 
[1] = Point( 6, 2 ), 
[4] = Point( 6, 4 ), 
[5] = Point( 6, 3 ), 
[7] = Point( 3, 1 ) 
}, 
["Spawner"] = { 
["used_bosses"] = 0, 
["pawn_counts"] = { 
["Scarab"] = 2, 
["Spider"] = 1, 
["Beetle"] = 1, 
["Hornet"] = 3, 
["Jelly_Explode"] = 1 
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
["num_spawns"] = 8, 
["upgrade_streak"] = 1 
}, 
["KilledVek"] = 1, 
["MineCount"] = 8, 
["AssetLoc"] = Point( 2, 6 ), 
["ID"] = "Mission_FreezeMines", 
["VoiceEvents"] = { 
}, 
["AssetId"] = "Str_Power", 
["PowerStart"] = 6 
}, 
[4] = { 
["BonusObjs"] = { 
[1] = 1 
}, 
["Criticals"] = { 
[1] = Point( 2, 5 ), 
[2] = Point( 0, 4 ) 
}, 
["NewPawns"] = { 
}, 
["NewPoints"] = { 
}, 
["Spawner"] = { 
["used_bosses"] = 0, 
["upgrade_streak"] = 0, 
["curr_weakRatio"] = { 
[1] = 2, 
[2] = 2 
}, 
["num_spawns"] = 8, 
["curr_upgradeRatio"] = { 
[1] = 1, 
[2] = 2 
}, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Scarab"] = 2, 
["Spider"] = 1, 
["Snowtank"] = 2, 
["Snowart"] = 1, 
["Hornet"] = 1, 
["Leaper"] = 1, 
["Jelly_Explode"] = 1 
} 
}, 
["LiveEnvironment"] = { 
}, 
["AssetId"] = "Str_Research", 
["AssetLoc"] = Point( 0, 6 ), 
["ID"] = "Mission_Factory", 
["VoiceEvents"] = { 
}, 
["DiffMod"] = 2, 
["PowerStart"] = 7 
}, 
[5] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 3, 
["curr_weakRatio"] = { 
[1] = 2, 
[2] = 2 
}, 
["curr_upgradeRatio"] = { 
[1] = 2, 
[2] = 2 
}, 
["upgrade_streak"] = 0, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Hornet"] = 1, 
["Spider"] = 1, 
["Jelly_Explode"] = 1 
} 
}, 
["LiveEnvironment"] = { 
}, 
["Buildings"] = { 
[1] = Point( 0, 1 ), 
[2] = Point( 1, 6 ), 
[3] = Point( 2, 2 ), 
[4] = Point( 2, 3 ), 
[5] = Point( 2, 6 ), 
[6] = Point( 5, 2 ), 
[7] = Point( 5, 3 ) 
}, 
["ID"] = "Mission_FreezeBldg", 
["VoiceEvents"] = { 
}, 
["BonusObjs"] = { 
[1] = 4 
} 
}, 
[7] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["pawn_counts"] = { 
["Beetle"] = 1, 
["Leaper"] = 1, 
["Jelly_Explode"] = 1 
}, 
["curr_weakRatio"] = { 
[1] = 2, 
[2] = 2 
}, 
["num_bosses"] = 0, 
["curr_upgradeRatio"] = { 
[1] = 1, 
[2] = 2 
}, 
["num_spawns"] = 3, 
["upgrade_streak"] = 1 
}, 
["BonusObjs"] = { 
[1] = 5 
}, 
["ID"] = "Mission_Survive", 
["VoiceEvents"] = { 
}, 
["DiffMod"] = 1, 
["LiveEnvironment"] = { 
} 
} 
}, 
["Island"] = 3 
}

 

SquadData = {
["money"] = 2, ["cores"] = 0, ["bIsFavor"] = false, ["repairs"] = 0, ["CorpReward"] = {CreateEffect({weapon = "Science_LocalShield",}), CreateEffect({skill1 = "Move",skill2 = "Health",pilot = "Pilot_Leader",}), CreateEffect({power = 2,}), },
["RewardClaimed"] = false, 
["skip_pawns"] = true, 

["storage_size"] = 5, ["storage_3"] = {["weapon"] = "Brute_Shockblast", },
["storage_4"] = {["weapon"] = "Brute_Beetle", },
["CorpStore"] = {CreateEffect({weapon = "Brute_Bombrun",money = -2,}), CreateEffect({weapon = "Brute_Sniper",money = -2,}), CreateEffect({weapon = "Prime_Shift",money = -2,}), CreateEffect({weapon = "Science_FreezeBeam",money = -2,}), CreateEffect({money = -3,stock = -1,cores = 1,}), CreateEffect({money = -1,power = 1,stock = -1,}), },
["island_store_count"] = 3, ["store_undo_size"] = 0, }
 

