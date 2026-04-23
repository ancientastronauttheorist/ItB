GameData = {["save_version"] = 1, ["language"] = 1, ["network"] = 5, ["networkMax"] = 7, ["overflow"] = 0, ["seed"] = 369890607, ["new_enemies"] = 0, ["new_missions"] = 0, ["new_equip"] = 0, ["difficulty"] = 2, ["new_abilities"] = 0, ["ach_info"] = {["squad"] = "Random", ["trackers"] = {["Detritus_B_2"] = 0, ["Global_Challenge_Power"] = 0, ["Archive_A_1"] = 0, ["Archive_B_2"] = 0, ["Rust_A_2"] = 0, ["Rust_A_3"] = 0, ["Pinnacle_A_3"] = 0, ["Archive_B_1"] = 0, ["Pinnacle_B_3"] = 0, ["Detritus_B_1"] = 0, ["Pinnacle_B_1"] = 0, ["Global_Island_Mechs"] = 0, ["Global_Island_Building"] = 0, ["Squad_Mist_1"] = 0, ["Squad_Bomber_2"] = 0, ["Squad_Spiders_1"] = 0, ["Squad_Mist_2"] = 0, ["Squad_Heat_1"] = 0, ["Squad_Cataclysm_1"] = 0, ["Squad_Cataclysm_2"] = 0, ["Squad_Cataclysm_3"] = 0, },
},


["current"] = {["score"] = 0, ["time"] = 29770.521484, ["kills"] = 0, ["damage"] = 0, ["failures"] = 0, ["difficulty"] = 2, ["victory"] = false, ["squad"] = 8, 
["mechs"] = {"GuardMech", "ChargeMech", "ScienceMech", },
["colors"] = {6, 2, 2, },
["weapons"] = {"Prime_ShieldBash", "", "Brute_Beetle", "", "Science_Pullmech", "Science_Shield", },
["pilot0"] = {["id"] = "Pilot_Detritus", ["name"] = "Isla Romano", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 2, ["exp"] = 25, ["level"] = 1, ["travel"] = 6, ["final"] = 0, ["starting"] = true, ["last_end"] = 2, },
["pilot1"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Zera", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 0, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot2"] = {["id"] = "Pilot_Archive", ["name"] = "Lauren Huang", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 3, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
},
["current_squad"] = 8, }
 

RegionData = {
["sector"] = 0, ["island"] = 3, ["secret"] = false, 
["island0"] = {["corporation"] = "Corp_Grass", ["id"] = 0, ["secured"] = false, },
["island1"] = {["corporation"] = "Corp_Desert", ["id"] = 1, ["secured"] = false, },
["island2"] = {["corporation"] = "Corp_Snow", ["id"] = 2, ["secured"] = false, },
["island3"] = {["corporation"] = "Corp_Factory", ["id"] = 3, ["secured"] = false, },

["turn"] = 0, ["iTower"] = 6, ["quest_tracker"] = 0, ["quest_id"] = 0, ["podRewards"] = {CreateEffect({pilot = "random",cores = 1,}), },


["region0"] = {["mission"] = "Mission2", ["state"] = 0, ["name"] = "Pumping Station", },

["region1"] = {["mission"] = "Mission5", ["state"] = 0, ["name"] = "Chemical Field A", },

["region2"] = {["mission"] = "Mission6", ["state"] = 0, ["name"] = "Containment Zone J", },

["region3"] = {["mission"] = "Mission7", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission7", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Teleporter_Briefing_CEO_Acid_2", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 923244471, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "acid10", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 1 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 0, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 111, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 136, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 141, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_recycle1", ["people1"] = 109, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 3, 0 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 250, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 284, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 223, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 246, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 6, 6 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 7, 1 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 7, 2 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 7, 4 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 7, 6 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 1, },
},
["teleports"] = {Point( 6, 3 ), Point( 1, 2 ), Point( 3, 4 ), Point( 5, 6 ), },
["tele_history"] = {-1, -1, -1, -1, },
["spawns"] = {"Hornet1", "Leaper1", "Hornet1", },
["spawn_ids"] = {1638, 1639, 1640, },
["spawn_points"] = {Point(7,3), Point(5,3), Point(7,5), },
["zones"] = {["pistons"] = {Point( 4, 0 ), Point( 6, 0 ), Point( 5, 6 ), Point( 4, 6 ), Point( 3, 6 ), Point( 2, 6 ), Point( 5, 7 ), Point( 1, 6 ), Point( 5, 0 ), },
},
["tags"] = {"generic", "acid", "acid_pool", "pistons", },
["pawn_count"] = 0, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Venting Center", },

["region4"] = {["mission"] = "Mission1", ["state"] = 0, ["name"] = "Reclamation Zone", },

["region5"] = {["mission"] = "Mission4", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission4", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Disposal_Briefing_CEO_Acid_2", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 1696348862, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "disposal", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 5 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 0, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 146, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 148, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 5 ), ["terrain"] = 0, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 0, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 3, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 4, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 135, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 3, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 112, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 4, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 2 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 276, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 219, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 217, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 247, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
},
["spawns"] = {"Jelly_Health1", "Leaper2", "Scarab1", "Hornet1", },
["spawn_ids"] = {1634, 1635, 1636, 1637, },
["spawn_points"] = {Point(7,2), Point(6,4), Point(5,2), Point(6,5), },
["zones"] = {["disposal"] = {Point( 1, 5 ), },
},
["tags"] = {"generic", "acid", "disposal", },


["pawn1"] = {["type"] = "Disposal_Unit", ["name"] = "", ["id"] = 1633, ["mech"] = false, ["offset"] = 0, ["primary"] = "Disposal_Attack", ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Detritus", ["name"] = "Alexis Tigani", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 2, ["skill2"] = 3, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = false, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(1,5), ["last_location"] = Point(-1,-1), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 3, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 1633, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },
["pawn_count"] = 1, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Downtown", },

["region6"] = {["mission"] = "", ["state"] = 2, ["name"] = "Corporate HQ", ["objectives"] = {},
},

["region7"] = {["mission"] = "Mission3", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission3", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Barrels_Briefing_CEO_Acid_2", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 708688516, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "any29", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 3 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 172, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 137, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 160, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 130, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 2, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 300, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 2, 5 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 0, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 0 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 0, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 291, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 310, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 7 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 0, },
{["loc"] = Point( 5, 2 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 5, 3 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 4 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 2 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 4, },
},
["spawns"] = {"Scarab1", "Jelly_Health1", "Leaper1", },
["spawn_ids"] = {1643, 1644, 1645, },
["spawn_points"] = {Point(6,4), Point(5,5), Point(6,5), },
["zones"] = {["satellite"] = {Point( 3, 6 ), Point( 4, 6 ), Point( 4, 1 ), Point( 6, 1 ), Point( 5, 1 ), },
},
["tags"] = {"generic", "any_sector", "mountain", "satellite", },


["pawn1"] = {["type"] = "AcidVat", ["name"] = "", ["id"] = 1641, ["mech"] = false, ["offset"] = 0, ["death_seed"] = 614509884, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,6), ["last_location"] = Point(-1,-1), ["bMinor"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 1641, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn2"] = {["type"] = "AcidVat", ["name"] = "", ["id"] = 1642, ["mech"] = false, ["offset"] = 0, ["death_seed"] = 783538439, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,1), ["last_location"] = Point(-1,-1), ["bMinor"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 0, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 1642, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },
["pawn_count"] = 2, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Disposal Site C", },
}
 

GAME = { 
["WeaponDeck"] = { 
[1] = "Prime_Lightning", 
[2] = "Prime_Lasermech", 
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
[14] = "Brute_Tankmech", 
[15] = "Brute_Jetmech", 
[16] = "Brute_Mirrorshot", 
[17] = "Brute_PhaseShot", 
[18] = "Brute_Grapple", 
[19] = "Brute_Shrapnel", 
[20] = "Brute_Sniper", 
[21] = "Brute_Shockblast", 
[22] = "Brute_Unstable", 
[23] = "Brute_Heavyrocket", 
[24] = "Brute_Splitshot", 
[25] = "Brute_Bombrun", 
[26] = "Brute_Sonic", 
[27] = "Ranged_Artillerymech", 
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
[40] = "Science_Swap", 
[41] = "Science_Repulse", 
[42] = "Science_AcidShot", 
[43] = "Science_Confuse", 
[44] = "Science_SmokeDefense", 
[45] = "Science_FireBeam", 
[46] = "Science_FreezeBeam", 
[47] = "Science_LocalShield", 
[48] = "Science_PushBeam", 
[49] = "Support_Boosters", 
[50] = "Support_Smoke", 
[51] = "Support_Refrigerate", 
[52] = "Support_Destruct", 
[53] = "DeploySkill_ShieldTank", 
[54] = "DeploySkill_Tank", 
[55] = "DeploySkill_AcidTank", 
[56] = "DeploySkill_PullTank", 
[57] = "Support_Force", 
[58] = "Support_SmokeDrop", 
[59] = "Support_Repair", 
[60] = "Support_Missiles", 
[61] = "Support_Wind", 
[62] = "Support_Blizzard", 
[63] = "Passive_FlameImmune", 
[64] = "Passive_Electric", 
[65] = "Passive_Leech", 
[66] = "Passive_MassRepair", 
[67] = "Passive_Defenses", 
[68] = "Passive_Burrows", 
[69] = "Passive_AutoShields", 
[70] = "Passive_Psions", 
[71] = "Passive_Medical", 
[72] = "Passive_FriendlyFire", 
[73] = "Passive_ForceAmp", 
[74] = "Passive_CritDefense" 
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
[10] = "Brute_Heavyrocket", 
[11] = "Brute_Bombrun", 
[12] = "Brute_Sonic", 
[13] = "Ranged_Ice", 
[14] = "Ranged_SmokeBlast", 
[15] = "Ranged_Fireball", 
[16] = "Ranged_RainingVolley", 
[17] = "Ranged_Dual", 
[18] = "Science_SmokeDefense", 
[19] = "Science_FireBeam", 
[20] = "Science_FreezeBeam", 
[21] = "Science_LocalShield", 
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
[42] = "Passive_Burrows", 
[43] = "Passive_AutoShields", 
[44] = "Passive_Psions", 
[45] = "Passive_Medical", 
[46] = "Passive_FriendlyFire", 
[47] = "Passive_ForceAmp", 
[48] = "Passive_CritDefense" 
}, 
["PilotDeck"] = { 
[1] = "Pilot_Original", 
[2] = "Pilot_Soldier", 
[3] = "Pilot_Youth", 
[4] = "Pilot_Warrior", 
[5] = "Pilot_Aquatic", 
[6] = "Pilot_Medic", 
[7] = "Pilot_Hotshot", 
[8] = "Pilot_Genius", 
[9] = "Pilot_Recycler", 
[10] = "Pilot_Assassin", 
[11] = "Pilot_Leader", 
[12] = "Pilot_Repairman" 
}, 
["SeenPilots"] = { 
[1] = "Pilot_Detritus", 
[2] = "Pilot_Pinnacle", 
[3] = "Pilot_Archive", 
[4] = "Pilot_Miner" 
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
["weapon"] = "random" 
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
[1] = "Mission_ScorpionBoss", 
[2] = "Mission_JellyBoss", 
[3] = "Mission_BeetleBoss", 
[4] = "Mission_BlobBoss" 
}, 
["Island"] = 4, 
["Missions"] = { 
[1] = { 
["ID"] = "Mission_Survive", 
["BonusObjs"] = { 
[1] = 6, 
[2] = 1 
}, 
["AssetId"] = "Str_Power" 
}, 
[2] = { 
["ID"] = "Mission_Belt", 
["BonusObjs"] = { 
[1] = 4, 
[2] = 1 
}, 
["AssetId"] = "Str_Power" 
}, 
[3] = { 
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
["upgrade_streak"] = 0, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Jelly_Health"] = 1, 
["Scarab"] = 1, 
["Leaper"] = 1 
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
[4] = { 
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
["Jelly_Health"] = 1, 
["Scarab"] = 1, 
["Leaper"] = 1, 
["Hornet"] = 1 
} 
}, 
["LiveEnvironment"] = { 
}, 
["ID"] = "Mission_Disposal", 
["VoiceEvents"] = { 
}, 
["DisposalId"] = 1633, 
["BonusObjs"] = { 
} 
}, 
[5] = { 
["ID"] = "Mission_Acid", 
["BonusObjs"] = { 
[1] = 1 
}, 
["DiffMod"] = 1, 
["AssetId"] = "Str_Battery" 
}, 
[6] = { 
["ID"] = "Mission_BeltRandom", 
["BonusObjs"] = { 
[1] = 6, 
[2] = 1 
}, 
["AssetId"] = "Str_Bar" 
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
["upgrade_streak"] = 0, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Leaper"] = 1, 
["Hornet"] = 2 
} 
}, 
["AssetId"] = "Str_Nimbus", 
["AssetLoc"] = Point( 1, 4 ), 
["ID"] = "Mission_Teleporter", 
["VoiceEvents"] = { 
}, 
["LiveEnvironment"] = { 
}, 
["BonusObjs"] = { 
[1] = 5, 
[2] = 1 
} 
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
[1] = "Hornet", 
[2] = "Leaper", 
[3] = "Firefly", 
[4] = "Jelly_Regen", 
[5] = "Burrower", 
[6] = "Crab", 
["island"] = 1 
}, 
[2] = { 
[1] = "Scorpion", 
[2] = "Scarab", 
[3] = "Firefly", 
[4] = "Jelly_Explode", 
[5] = "Blobber", 
[6] = "Centipede", 
["island"] = 2 
}, 
[3] = { 
[1] = "Hornet", 
[2] = "Scorpion", 
[3] = "Scarab", 
[4] = "Jelly_Armor", 
[5] = "Digger", 
[6] = "Spider", 
["island"] = 3 
}, 
[4] = { 
[1] = "Leaper", 
[2] = "Scarab", 
[3] = "Hornet", 
[4] = "Jelly_Health", 
[5] = "Beetle", 
[6] = "Spider", 
["island"] = 4 
} 
} 
}

 

SquadData = {
["money"] = 0, ["cores"] = 0, ["bIsFavor"] = false, ["repairs"] = 0, ["CorpReward"] = {CreateEffect({weapon = "Passive_Boosters",}), CreateEffect({skill1 = "Move",skill2 = "Grid",pilot = "Pilot_Miner",}), CreateEffect({power = 2,}), },
["RewardClaimed"] = false, 


["pawn0"] = {["type"] = "GuardMech", ["name"] = "", ["id"] = 0, ["mech"] = true, ["offset"] = 6, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Prime_ShieldBash", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Detritus", ["name"] = "Isla Romano", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 2, ["exp"] = 25, ["level"] = 1, ["travel"] = 6, ["final"] = 0, ["starting"] = true, ["last_end"] = 2, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 5, ["max_health"] = 5, ["iOwner"] = 0, },


["pawn1"] = {["type"] = "ChargeMech", ["name"] = "", ["id"] = 1, ["mech"] = true, ["offset"] = 2, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Brute_Beetle", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Zera", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 0, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 3, ["iOwner"] = 1, },


["pawn2"] = {["type"] = "ScienceMech", ["name"] = "", ["id"] = 2, ["mech"] = true, ["offset"] = 2, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Science_Pullmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["secondary"] = "Science_Shield", ["secondary_power"] = {},
["secondary_power_class"] = false, ["secondary_mod1"] = {0, 0, },
["secondary_mod2"] = {0, 0, },
["secondary_damaged"] = false, ["secondary_starting"] = true, ["secondary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Archive", ["name"] = "Lauren Huang", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 3, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 2, ["max_health"] = 2, ["iOwner"] = 2, },


["storage_size"] = 3, ["CorpStore"] = {CreateEffect({weapon = "Prime_Punchmech",money = -2,}), CreateEffect({weapon = "Science_Gravwell",money = -2,}), CreateEffect({stock = 0,}), CreateEffect({stock = 0,}), CreateEffect({money = -3,stock = -1,cores = 1,}), CreateEffect({money = -1,power = 1,stock = -1,}), },
["island_store_count"] = 0, ["store_undo_size"] = 0, }
 

