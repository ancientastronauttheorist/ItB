GameData = {["save_version"] = 1, ["language"] = 1, ["network"] = 6, ["networkMax"] = 7, ["overflow"] = 13, ["seed"] = 1927933998, ["new_enemies"] = 0, ["new_missions"] = 0, ["new_equip"] = 0, ["difficulty"] = 0, ["new_abilities"] = 0, ["ach_info"] = {["squad"] = "Rust_B", ["trackers"] = {["Detritus_B_2"] = 0, ["Global_Challenge_Power"] = 0, ["Archive_A_1"] = 0, ["Archive_B_2"] = 0, ["Rust_A_2"] = 0, ["Rust_A_3"] = 0, ["Pinnacle_A_3"] = 0, ["Archive_B_1"] = 0, ["Pinnacle_B_3"] = 0, ["Detritus_B_1"] = 0, ["Pinnacle_B_1"] = 0, ["Global_Island_Mechs"] = 12, ["Global_Island_Building"] = 0, ["Squad_Mist_1"] = 0, ["Squad_Bomber_2"] = 0, ["Squad_Spiders_1"] = 0, ["Squad_Mist_2"] = 0, ["Squad_Heat_1"] = 0, ["Squad_Cataclysm_1"] = 0, ["Squad_Cataclysm_2"] = 0, ["Squad_Cataclysm_3"] = 0, },
},


["current"] = {["score"] = 5636, ["time"] = 20044326.000000, ["kills"] = 53, ["damage"] = 0, ["failures"] = 6, ["difficulty"] = 0, ["victory"] = false, ["islands"] = 2, ["squad"] = 5, 
["mechs"] = {"FlameMech", "IgniteMech", "TeleMech", },
["colors"] = {5, 5, 5, },
["weapons"] = {"Prime_Flamethrower", "Passive_FlameImmune", "Ranged_Ignite", "Support_Wind_A", "Science_Swap", "", },
["pilot0"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 0, ["exp"] = 50, ["level"] = 2, ["travel"] = 1, ["final"] = 1, ["starting"] = true, ["last_end"] = 2, },
["pilot1"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Fenrir", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 1, ["exp"] = 40, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot2"] = {["id"] = "Pilot_Aquatic", ["name"] = "Archimedes", ["name_id"] = "Pilot_Aquatic_Name", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 2, ["exp"] = 17, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = false, ["power"] = {0, },
},
},
["current_squad"] = 5, ["undosave"] = true, }
 

RegionData = {
["sector"] = 2, ["island"] = 3, ["secret"] = false, 
["island0"] = {["corporation"] = "Corp_Grass", ["id"] = 0, ["secured"] = true, },
["island1"] = {["corporation"] = "Corp_Desert", ["id"] = 1, ["secured"] = true, },
["island2"] = {["corporation"] = "Corp_Snow", ["id"] = 2, ["secured"] = false, },
["island3"] = {["corporation"] = "Corp_Factory", ["id"] = 3, ["secured"] = false, },

["turn"] = 2, ["iTower"] = 4, ["quest_tracker"] = 1, ["quest_id"] = 0, ["podRewards"] = {},


["region0"] = {["mission"] = "", ["state"] = 2, ["name"] = "Chemical Field A", ["objectives"] = {["0"] = {["text"] = "Bonus_Simple_Vek", ["param1"] = "", ["param2"] = "", ["value"] = 0, ["potential"] = 1, ["category"] = 0, },
["1"] = {["text"] = "Bonus_Simple_Asset", ["param1"] = "Str_Power_Name", ["param2"] = "", ["value"] = 1, ["potential"] = 1, ["category"] = 1, },
},
},

["region1"] = {["mission"] = "", ["state"] = 2, ["name"] = "Disposal Vault", ["objectives"] = {["0"] = {["text"] = "Bonus_Simple_Mechs", ["param1"] = "", ["param2"] = "", ["value"] = 1, ["potential"] = 1, ["category"] = 0, },
["1"] = {["text"] = "Bonus_Simple_Asset", ["param1"] = "Str_Power_Name", ["param2"] = "", ["value"] = 1, ["potential"] = 1, ["category"] = 1, },
["2"] = {["text"] = "Pod_Objective", ["param1"] = "", ["param2"] = "", ["value"] = 1, ["potential"] = 1, ["category"] = 3, },
},
},

["region2"] = {["mission"] = "Mission4", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 4, ["iTeamTurn"] = 1, ["iState"] = 0, ["sMission"] = "Mission4", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Disposal_Briefing_CEO_Acid_2", ["podReward"] = CreateEffect({weapon = "Brute_Shockblast",cores = 1,}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 3, ["aiDelay"] = 0.000000, ["aiSeed"] = 291805202, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "disposal13", ["enemy_kills"] = 2, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 0, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 36, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 64, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 3 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 0, },
{["loc"] = Point( 1, 5 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 29, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 72, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 2, 5 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 0, ["fire"] = 1, },
{["loc"] = Point( 3, 5 ), ["terrain"] = 0, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 0, ["fire"] = 1, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 65, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 135, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 3 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 5 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 6 ), ["terrain"] = 0, ["grapple_targets"] = {1, },
},
{["loc"] = Point( 5, 1 ), ["terrain"] = 0, ["pod"] = 1, },
{["loc"] = Point( 5, 2 ), ["terrain"] = 0, ["fire"] = 1, },
{["loc"] = Point( 5, 3 ), ["terrain"] = 0, },
{["loc"] = Point( 5, 4 ), ["terrain"] = 0, ["fire"] = 1, },
{["loc"] = Point( 5, 5 ), ["terrain"] = 0, },
{["loc"] = Point( 5, 6 ), ["terrain"] = 1, ["populated"] = 1, ["grappled"] = 1, ["people1"] = 99, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 6, 4 ), ["terrain"] = 4, ["fire"] = 1, },
{["loc"] = Point( 6, 5 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 0, },
{["loc"] = Point( 7, 2 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 7, 3 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 4 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 5 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 0, },
},
["pod"] = Point(5,1), ["spawns"] = {},
["spawn_ids"] = {},
["spawn_points"] = {},
["zones"] = {["disposal"] = {Point( 2, 4 ), },
},
["tags"] = {"generic", "acid", "disposal", },


["pawn1"] = {["type"] = "Disposal_Unit", ["name"] = "", ["id"] = 492, ["mech"] = false, ["offset"] = 0, ["primary"] = "Disposal_Attack", ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Detritus", ["name"] = "Elijah Patel", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 2, ["skill2"] = 1, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = false, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(2,4), ["last_location"] = Point(2,4), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 492, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(2,4), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn2"] = {["type"] = "FlameMech", ["name"] = "", ["id"] = 0, ["mech"] = true, ["offset"] = 5, 
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
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 1, ["max_health"] = 5, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,5), ["last_location"] = Point(4,5), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 1, ["iOwner"] = 0, ["piTarget"] = Point(3,6), ["piOrigin"] = Point(3,5), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,6), },


["pawn3"] = {["type"] = "IgniteMech", ["name"] = "", ["id"] = 1, ["mech"] = true, ["offset"] = 5, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 2, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {1, },
["healthPower"] = {0, },
["primary"] = "Ranged_Ignite", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["secondary"] = "Support_Wind", ["secondary_power"] = {},
["secondary_power_class"] = false, ["secondary_mod1"] = {1, },
["secondary_mod2"] = {0, },
["secondary_damaged"] = false, ["secondary_starting"] = true, ["secondary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Fenrir", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 1, ["exp"] = 40, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 1, ["is_corpse"] = true, ["health"] = 2, ["max_health"] = 5, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,5), ["last_location"] = Point(5,4), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 4, ["iOwner"] = 1, ["piTarget"] = Point(5,2), ["piOrigin"] = Point(5,5), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,2), },


["pawn4"] = {["type"] = "TeleMech", ["name"] = "", ["id"] = 2, ["mech"] = true, ["offset"] = 5, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 1, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {1, },
["healthPower"] = {0, },
["primary"] = "Science_Swap", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Aquatic", ["name"] = "Archimedes", ["name_id"] = "Pilot_Aquatic_Name", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 2, ["exp"] = 17, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = false, ["power"] = {0, },
},
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 0, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,3), ["last_location"] = Point(4,4), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 1, ["iOwner"] = 2, ["piTarget"] = Point(4,3), ["piOrigin"] = Point(4,4), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,3), },


["pawn5"] = {["type"] = "Scorpion2", ["name"] = "", ["id"] = 493, ["mech"] = false, ["offset"] = 1, ["primary"] = "ScorpionAtk2", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["bOnFire"] = true, ["health"] = 1, ["max_health"] = 6, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,6), ["last_location"] = Point(4,5), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 1, ["iOwner"] = 493, ["piTarget"] = Point(5,6), ["piOrigin"] = Point(4,6), ["piQueuedShot"] = Point(5,6), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,6), },


["pawn6"] = {["type"] = "Jelly_Health1", ["name"] = "", ["id"] = 494, ["mech"] = false, ["offset"] = 4, ["not_attacking"] = true, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["bOnFire"] = true, ["health"] = 1, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,3), ["last_location"] = Point(5,2), ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 1, ["iOwner"] = 494, ["piTarget"] = Point(-2147483647,-2147483647), ["piOrigin"] = Point(5,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn7"] = {["type"] = "Scarab1", ["name"] = "", ["id"] = 496, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScarabAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["bOnFire"] = true, ["bAcid"] = true, ["health"] = 1, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,5), ["last_location"] = Point(4,6), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 1, ["iOwner"] = 496, ["piTarget"] = Point(4,1), ["piOrigin"] = Point(4,5), ["piQueuedShot"] = Point(4,1), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,1), },


["pawn8"] = {["type"] = "Firefly1", ["name"] = "", ["id"] = 502, ["mech"] = false, ["offset"] = 0, ["primary"] = "FireflyAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["bOnFire"] = true, ["health"] = 2, ["max_health"] = 4, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,4), ["last_location"] = Point(5,4), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 1, ["iOwner"] = 502, ["piTarget"] = Point(3,4), ["piOrigin"] = Point(4,4), ["piQueuedShot"] = Point(3,4), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,4), },
["pawn_count"] = 8, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Venting Center", },

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
["iBattleRegion"] = 2, }
 

GAME = { 
["WeaponDeck"] = { 
[31] = "Ranged_Fireball", 
[2] = "Prime_Lightning", 
[8] = "Prime_Shift", 
[32] = "Ranged_RainingVolley", 
[33] = "Ranged_Wide", 
[34] = "Ranged_Dual", 
[35] = "Science_Gravwell", 
[9] = "Prime_Areablast", 
[36] = "Science_Repulse", 
[37] = "Science_AcidShot", 
[38] = "Science_Confuse", 
[39] = "Science_SmokeDefense", 
[10] = "Prime_Spear", 
[40] = "Science_Shield", 
[41] = "Science_FireBeam", 
[42] = "Science_FreezeBeam", 
[43] = "Science_LocalShield", 
[11] = "Prime_Leap", 
[44] = "Science_PushBeam", 
[45] = "Support_Boosters", 
[46] = "Support_Smoke", 
[3] = "Prime_Lasermech", 
[12] = "Prime_SpinFist", 
[48] = "Support_Destruct", 
[49] = "DeploySkill_ShieldTank", 
[50] = "DeploySkill_PullTank", 
[51] = "Support_Force", 
[13] = "Prime_Sword", 
[52] = "Support_SmokeDrop", 
[53] = "Support_Repair", 
[54] = "Support_Missiles", 
[55] = "Support_Blizzard", 
[14] = "Brute_Tankmech", 
[56] = "Passive_Leech", 
[57] = "Passive_MassRepair", 
[58] = "Passive_Defenses", 
[59] = "Passive_AutoShields", 
[15] = "Brute_Jetmech", 
[60] = "Passive_Boosters", 
[61] = "Passive_Medical", 
[62] = "Passive_FriendlyFire", 
[1] = "Prime_Punchmech", 
[4] = "Prime_ShieldBash", 
[16] = "Brute_Mirrorshot", 
[64] = "Passive_CritDefense", 
[17] = "Brute_PhaseShot", 
[18] = "Brute_Grapple", 
[19] = "Brute_Shrapnel", 
[5] = "Prime_Rockmech", 
[20] = "Brute_Sniper", 
[21] = "Brute_Beetle", 
[22] = "Brute_Unstable", 
[23] = "Brute_Splitshot", 
[6] = "Prime_RightHook", 
[24] = "Brute_Bombrun", 
[25] = "Ranged_Artillerymech", 
[26] = "Ranged_Rockthrow", 
[27] = "Ranged_Defensestrike", 
[7] = "Prime_RocketPunch", 
[28] = "Ranged_Rocket", 
[29] = "Ranged_ScatterShot", 
[30] = "Ranged_Ice", 
[47] = "Support_Refrigerate", 
[63] = "Passive_ForceAmp" 
}, 
["PodWeaponDeck"] = { 
[27] = "Support_SmokeDrop", 
[2] = "Prime_Spear", 
[38] = "Passive_ForceAmp", 
[3] = "Prime_Leap", 
[4] = "Prime_SpinFist", 
[5] = "Prime_Sword", 
[6] = "Brute_Grapple", 
[7] = "Brute_Sniper", 
[8] = "Brute_Beetle", 
[10] = "Ranged_Ice", 
[12] = "Ranged_RainingVolley", 
[14] = "Science_SmokeDefense", 
[16] = "Science_FireBeam", 
[20] = "Support_Boosters", 
[24] = "DeploySkill_ShieldTank", 
[28] = "Support_Repair", 
[32] = "Passive_MassRepair", 
[33] = "Passive_Defenses", 
[17] = "Science_FreezeBeam", 
[21] = "Support_Smoke", 
[25] = "DeploySkill_PullTank", 
[29] = "Support_Missiles", 
[34] = "Passive_AutoShields", 
[9] = "Brute_Bombrun", 
[11] = "Ranged_Fireball", 
[13] = "Ranged_Dual", 
[15] = "Science_Shield", 
[18] = "Science_LocalShield", 
[22] = "Support_Refrigerate", 
[26] = "Support_Force", 
[30] = "Support_Blizzard", 
[36] = "Passive_Medical", 
[37] = "Passive_FriendlyFire", 
[31] = "Passive_Leech", 
[35] = "Passive_Boosters", 
[1] = "Prime_Areablast", 
[19] = "Science_PushBeam", 
[23] = "Support_Destruct", 
[39] = "Passive_CritDefense" 
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
["Island"] = 4, 
["Missions"] = { 
[6] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["pawn_counts"] = { 
["Firefly"] = 1, 
["Scorpion"] = 2 
}, 
["curr_weakRatio"] = { 
[1] = 1, 
[2] = 2 
}, 
["num_bosses"] = 0, 
["curr_upgradeRatio"] = { 
[1] = 0, 
[2] = 2 
}, 
["num_spawns"] = 3, 
["upgrade_streak"] = 0 
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
[2] = { 
["Spawner"] = { 
}, 
["AssetId"] = "Str_Battery", 
["ID"] = "Mission_Train", 
["LiveEnvironment"] = { 
}, 
["DiffMod"] = 2, 
["BonusObjs"] = { 
[1] = 1 
} 
}, 
[8] = { 
["Spawner"] = { 
}, 
["AssetId"] = "Str_Tower", 
["ID"] = "Mission_JellyBoss", 
["LiveEnvironment"] = { 
}, 
["BonusObjs"] = { 
[1] = 1 
} 
}, 
[3] = { 
["BonusObjs"] = { 
[1] = 5, 
[2] = 1 
}, 
["BlockedSpawns"] = 2, 
["Spawner"] = { 
["used_bosses"] = 0, 
["pawn_counts"] = { 
["Centipede"] = 1, 
["Scarab"] = 2, 
["Firefly"] = 2, 
["Digger"] = 1, 
["Jelly_Health"] = 1, 
["Scorpion"] = 1 
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
["LiveEnvironment"] = { 
}, 
["AssetLoc"] = Point( 3, 6 ), 
["ID"] = "Mission_Survive", 
["VoiceEvents"] = { 
}, 
["AssetId"] = "Str_Power", 
["PowerStart"] = 5 
}, 
[1] = { 
["Spawner"] = { 
}, 
["AssetId"] = "Str_Research", 
["ID"] = "Mission_AcidTank", 
["LiveEnvironment"] = { 
}, 
["DiffMod"] = 2, 
["BonusObjs"] = { 
[1] = 1 
} 
}, 
[4] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["pawn_counts"] = { 
["Centipede"] = 1, 
["Scarab"] = 2, 
["Jelly_Health"] = 1, 
["Digger"] = 1, 
["Firefly"] = 1, 
["Scorpion"] = 1 
}, 
["curr_weakRatio"] = { 
[1] = 3, 
[2] = 3 
}, 
["num_bosses"] = 0, 
["curr_upgradeRatio"] = { 
[1] = 1, 
[2] = 3 
}, 
["num_spawns"] = 7, 
["upgrade_streak"] = 0 
}, 
["LiveEnvironment"] = { 
}, 
["DisposalId"] = 492, 
["ID"] = "Mission_Disposal", 
["VoiceEvents"] = { 
}, 
["BonusObjs"] = { 
}, 
["PowerStart"] = 6 
}, 
[5] = { 
["ID"] = "Mission_Power", 
["BonusObjs"] = { 
}, 
["LiveEnvironment"] = { 
}, 
["Spawner"] = { 
} 
}, 
[7] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["pawn_counts"] = { 
["Centipede"] = 1, 
["Scarab"] = 2, 
["Firefly"] = 2, 
["Digger"] = 1, 
["Scorpion"] = 1 
}, 
["curr_weakRatio"] = { 
[1] = 3, 
[2] = 3 
}, 
["num_bosses"] = 0, 
["curr_upgradeRatio"] = { 
[1] = 1, 
[2] = 3 
}, 
["num_spawns"] = 7, 
["upgrade_streak"] = 0 
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
[7] = Point( 5, 3 ), 
[1] = Point( 1, 1 ), 
[2] = Point( 2, 1 ), 
[4] = Point( 2, 3 ), 
[8] = Point( 6, 3 ), 
[9] = Point( 6, 4 ), 
[5] = Point( 3, 3 ), 
[10] = Point( 7, 4 ), 
[3] = Point( 2, 2 ), 
[6] = Point( 4, 3 ) 
}, 
["BeltsDir"] = { 
[7] = 3, 
[1] = 3, 
[2] = 3, 
[4] = 0, 
[8] = 3, 
[9] = 0, 
[5] = 3, 
[10] = 3, 
[3] = 0, 
[6] = 3 
} 
}, 
["PowerStart"] = 7 
} 
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
} 
}

 

SquadData = {
["money"] = 1, ["cores"] = 0, ["bIsFavor"] = false, ["repairs"] = 0, ["CorpReward"] = {CreateEffect({weapon = "Brute_Sonic",}), CreateEffect({skill1 = "Move",skill2 = "Grid",pilot = "Pilot_Warrior",}), CreateEffect({power = 2,}), },
["RewardClaimed"] = false, 
["skip_pawns"] = true, 

["storage_size"] = 3, ["CorpStore"] = {CreateEffect({weapon = "DeploySkill_AcidTank",money = -2,}), CreateEffect({weapon = "Prime_Smash",money = -2,}), CreateEffect({weapon = "Science_Pullmech",money = -2,}), CreateEffect({weapon = "Passive_Psions",money = -2,}), CreateEffect({money = -3,stock = -1,cores = 1,}), CreateEffect({money = -1,power = 1,stock = -1,}), },
["island_store_count"] = 2, ["store_undo_size"] = 0, }
 

