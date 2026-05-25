GameData = {["save_version"] = 1, ["language"] = 1, ["network"] = 7, ["networkMax"] = 7, ["overflow"] = 21, ["seed"] = 1034678130, ["new_enemies"] = 1, ["new_missions"] = 1, ["new_equip"] = 1, ["difficulty"] = 0, ["new_abilities"] = 1, ["ach_info"] = {["squad"] = "Rust_A", ["trackers"] = {["Detritus_B_2"] = 0, ["Global_Challenge_Power"] = 0, ["Archive_A_1"] = 0, ["Archive_B_2"] = 0, ["Rust_A_2"] = 1, ["Rust_A_3"] = 2, ["Pinnacle_A_3"] = 0, ["Archive_B_1"] = 0, ["Pinnacle_B_3"] = 0, ["Detritus_B_1"] = 0, ["Pinnacle_B_1"] = 0, ["Global_Island_Mechs"] = 3, ["Global_Island_Building"] = 0, ["Squad_Mist_1"] = 0, ["Squad_Bomber_2"] = 0, ["Squad_Spiders_1"] = 0, ["Squad_Mist_2"] = 0, ["Squad_Heat_1"] = 0, ["Squad_Cataclysm_1"] = 0, ["Squad_Cataclysm_2"] = 0, ["Squad_Cataclysm_3"] = 0, },
},


["current"] = {["score"] = 7867, ["time"] = 33959732.000000, ["kills"] = 108, ["damage"] = 0, ["failures"] = 3, ["difficulty"] = 0, ["victory"] = false, ["islands"] = 3, ["squad"] = 1, 
["mechs"] = {"JetMech", "RocketMech", "PulseMech", },
["colors"] = {1, 1, 1, },
["weapons"] = {"Brute_Jetmech", "Passive_FlameImmune", "Ranged_Rocket", "Passive_Electric", "Science_Repulse_A", "", },
["pilot0"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 0, ["exp"] = 50, ["level"] = 2, ["travel"] = 3, ["final"] = 2, ["starting"] = true, ["last_end"] = 2, },
["pilot1"] = {["id"] = "Pilot_Detritus", ["name"] = "Zoe Koleda", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 7, ["skill2"] = 8, ["exp"] = 50, ["level"] = 2, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot2"] = {["id"] = "Pilot_Repairman", ["name"] = "Harold Schmidt", ["name_id"] = "Pilot_Repairman_Name", ["renamed"] = false, ["skill1"] = 9, ["skill2"] = 8, ["exp"] = 29, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = false, },
},
["current_squad"] = 1, ["undosave"] = true, }
 

RegionData = {
["sector"] = 3, ["island"] = 3, ["secret"] = true, 
["island0"] = {["corporation"] = "Corp_Grass", ["id"] = 0, ["secured"] = true, },
["island1"] = {["corporation"] = "Corp_Desert", ["id"] = 1, ["secured"] = true, },
["island2"] = {["corporation"] = "Corp_Snow", ["id"] = 2, ["secured"] = true, },
["island3"] = {["corporation"] = "Corp_Factory", ["id"] = 3, ["secured"] = false, },

["turn"] = 1, ["iTower"] = 7, ["quest_tracker"] = 1, ["quest_id"] = 0, ["podRewards"] = {CreateEffect({cores = 1,}), },


["region0"] = {["mission"] = "Mission2", ["state"] = 0, ["name"] = "The Heap", },

["region1"] = {["mission"] = "Mission6", ["state"] = 0, ["name"] = "Containment Zone D", },

["region2"] = {["mission"] = "Mission1", ["state"] = 0, ["name"] = "Reprocessing", },

["region3"] = {["mission"] = "Mission7", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 4, ["iTeamTurn"] = 1, ["iState"] = 0, ["sMission"] = "Mission7", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Generic_Briefing_CEO_Acid_2", ["podReward"] = CreateEffect({skill1 = "Popular",skill2 = "Pain",pilot = "Pilot_Assassin",cores = 1,}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 3, ["aiDelay"] = 0.000000, ["aiSeed"] = 1698508219, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "acid4", ["enemy_kills"] = 5, 
["map"] = {{["loc"] = Point( 0, 1 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 0, ["custom"] = "conveyor2.png", },
{["loc"] = Point( 1, 1 ), ["terrain"] = 0, ["custom"] = "conveyor2.png", },
{["loc"] = Point( 1, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 76, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 3 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 0, ["grapple_targets"] = {2, },
},
{["loc"] = Point( 1, 5 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_recycle1", ["grappled"] = 1, ["people1"] = 79, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 2, 0 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 44, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 2, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 91, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 2, 7 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 3, 3 ), ["terrain"] = 0, ["custom"] = "conveyor0.png", },
{["loc"] = Point( 3, 4 ), ["terrain"] = 0, ["custom"] = "conveyor0.png", },
{["loc"] = Point( 3, 5 ), ["terrain"] = 0, ["fire"] = 1, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 0 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 4, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 5 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 6 ), ["terrain"] = 0, ["pod"] = 1, },
{["loc"] = Point( 4, 7 ), ["terrain"] = 0, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 5, 1 ), ["terrain"] = 0, ["grapple_targets"] = {2, },
},
{["loc"] = Point( 5, 2 ), ["terrain"] = 1, ["populated"] = 1, ["grappled"] = 1, ["people1"] = 105, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 5, 3 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 5, 4 ), ["terrain"] = 0, ["smoke"] = 1, ["smoke"] = 1, },
{["loc"] = Point( 5, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 105, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 5, 6 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 6, 0 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 6, 1 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 6, 2 ), ["terrain"] = 0, ["custom"] = "conveyor1.png", },
{["loc"] = Point( 6, 3 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 6, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 6, 5 ), ["terrain"] = 0, ["custom"] = "conveyor1.png", },
{["loc"] = Point( 6, 6 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 0, ["smoke"] = 1, ["smoke"] = 1, },
{["loc"] = Point( 7, 5 ), ["terrain"] = 0, ["custom"] = "conveyor2.png", },
{["loc"] = Point( 7, 6 ), ["terrain"] = 0, ["custom"] = "conveyor2.png", },
},
["pod"] = Point(4,6), ["spawns"] = {},
["spawn_ids"] = {},
["spawn_points"] = {},
["zones"] = {["pistons"] = {Point( 3, 2 ), Point( 3, 3 ), Point( 4, 3 ), Point( 4, 2 ), Point( 3, 0 ), Point( 4, 0 ), Point( 3, 5 ), Point( 3, 6 ), Point( 4, 6 ), Point( 4, 5 ), },
},
["tags"] = {"generic", "acid", "pistons", },


["pawn1"] = {["type"] = "JetMech", ["name"] = "", ["id"] = 0, ["mech"] = true, ["offset"] = 1, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 1, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {1, },
["primary"] = "Brute_Jetmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["secondary"] = "Passive_FlameImmune", ["secondary_power"] = {},
["secondary_power_class"] = false, ["secondary_mod1"] = {0, },
["secondary_mod2"] = {0, },
["secondary_damaged"] = false, ["secondary_starting"] = true, ["secondary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 0, ["exp"] = 50, ["level"] = 2, ["travel"] = 3, ["final"] = 2, ["starting"] = true, ["last_end"] = 2, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 1, ["is_corpse"] = true, ["health"] = 6, ["max_health"] = 6, ["undo_state"] = {["health"] = 6, ["max_health"] = 6, },
["undo_ready"] = true, ["undo_point"] = Point(2,4), ["iMissionDamage"] = 0, ["location"] = Point(3,6), ["last_location"] = Point(3,4), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(2,4), ["undoReady"] = true, ["iKillCount"] = 5, ["iOwner"] = 0, ["piTarget"] = Point(3,6), ["piOrigin"] = Point(3,4), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,6), },


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
["secondary_damaged"] = false, ["secondary_starting"] = true, ["secondary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Detritus", ["name"] = "Zoe Koleda", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 7, ["skill2"] = 8, ["exp"] = 50, ["level"] = 2, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 2, ["is_corpse"] = true, ["health"] = 7, ["max_health"] = 7, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,7), ["last_location"] = Point(5,7), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 4, ["iOwner"] = 1, ["piTarget"] = Point(4,4), ["piOrigin"] = Point(4,7), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,4), },


["pawn3"] = {["type"] = "PulseMech", ["name"] = "", ["id"] = 2, ["mech"] = true, ["offset"] = 1, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 3, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {1, },
["healthPower"] = {1, },
["primary"] = "Science_Repulse", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {1, },
["primary_mod2"] = {0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Repairman", ["name"] = "Harold Schmidt", ["name_id"] = "Pilot_Repairman_Name", ["renamed"] = false, ["skill1"] = 9, ["skill2"] = 8, ["exp"] = 29, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = false, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 1, ["is_corpse"] = true, ["bAcid"] = true, ["health"] = 3, ["max_health"] = 5, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,5), ["last_location"] = Point(4,4), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 1, ["iOwner"] = 2, ["piTarget"] = Point(3,2), ["piOrigin"] = Point(3,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,2), },


["pawn4"] = {["type"] = "Jelly_Fire1", ["name"] = "", ["id"] = 575, ["mech"] = false, ["offset"] = 8, ["not_attacking"] = true, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,2), ["last_location"] = Point(7,2), ["iCurrentWeapon"] = 0, ["iTurnCount"] = 2, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 10, ["iOwner"] = 575, ["piTarget"] = Point(-2147483647,-2147483647), ["piOrigin"] = Point(7,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn5"] = {["type"] = "Spider2", ["name"] = "", ["id"] = 576, ["mech"] = false, ["offset"] = 1, ["not_attacking"] = true, ["primary"] = "SpiderAtk2", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 4, ["max_health"] = 4, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,4), ["last_location"] = Point(6,4), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 2, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 10, ["iOwner"] = 576, ["piTarget"] = Point(1,4), ["piOrigin"] = Point(6,4), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(1,4), },


["pawn6"] = {["type"] = "Bouncer1", ["name"] = "", ["id"] = 584, ["mech"] = false, ["offset"] = 0, ["primary"] = "BouncerAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,4), ["last_location"] = Point(5,4), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 0, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 10, ["iOwner"] = 584, ["piTarget"] = Point(4,5), ["piOrigin"] = Point(4,4), ["piQueuedShot"] = Point(4,5), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,5), },


["pawn7"] = {["type"] = "Leaper2", ["name"] = "", ["id"] = 598, ["mech"] = false, ["offset"] = 1, ["primary"] = "LeaperAtk2", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,1), ["last_location"] = Point(7,3), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 975335528, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 10, ["iOwner"] = 598, ["piTarget"] = Point(5,2), ["piOrigin"] = Point(5,1), ["piQueuedShot"] = Point(5,2), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,2), },


["pawn8"] = {["type"] = "Firefly1", ["name"] = "", ["id"] = 599, ["mech"] = false, ["offset"] = 0, ["primary"] = "FireflyAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,5), ["last_location"] = Point(6,4), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 975335528, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 10, ["iOwner"] = 599, ["piTarget"] = Point(5,5), ["piOrigin"] = Point(6,5), ["piQueuedShot"] = Point(5,5), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,5), },


["pawn9"] = {["type"] = "WebbEgg1", ["name"] = "", ["id"] = 619, ["mech"] = false, ["offset"] = 0, ["owner"] = 576, ["primary"] = "WebeggHatch1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 1, ["max_health"] = 1, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(1,4), ["last_location"] = Point(1,4), ["bMinor"] = true, ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 1768837983, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 619, ["piTarget"] = Point(1,4), ["piOrigin"] = Point(1,4), ["piQueuedShot"] = Point(1,4), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(1,4), },
["pawn_count"] = 9, ["blocked_points"] = {Point(1,0), Point(1,1), Point(3,3), Point(3,4), Point(6,2), Point(6,5), Point(7,5), Point(7,6), },
["blocked_type"] = {2, 2, 2, 2, 2, 2, 2, 2, },
},


},
["state"] = 1, ["name"] = "Disposal Vault", },

["region4"] = {["mission"] = "Mission3", ["state"] = 0, ["name"] = "Waste Chambers", },

["region5"] = {["mission"] = "Mission5", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission5", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Teleporter_Briefing_CEO_Acid_3", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 1530121355, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "acid15", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 66, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 69, ["people2"] = 0, ["health_max"] = 1, ["shield"] = true, },
{["loc"] = Point( 1, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 64, ["people2"] = 0, ["health_max"] = 1, ["shield"] = true, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 31, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 74, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 2, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 135, ["people2"] = 0, ["health_max"] = 2, ["shield"] = true, },
{["loc"] = Point( 2, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 61, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 5, 1 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 5, 5 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 6, 1 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 6, 2 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 6, 4 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 6, 5 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 4, },
},
["teleports"] = {Point( 1, 4 ), Point( 2, 1 ), Point( 4, 4 ), Point( 5, 3 ), },
["tele_history"] = {-1, -1, -1, -1, },
["spawns"] = {"Leaper1", "Jelly_Fire1", "Centipede2", },
["spawn_ids"] = {572, 573, 574, },
["spawn_points"] = {Point(7,4), Point(6,3), Point(7,2), },
["zones"] = {["pistons"] = {Point( 3, 7 ), Point( 4, 7 ), Point( 5, 7 ), Point( 6, 7 ), Point( 4, 4 ), Point( 4, 2 ), Point( 2, 2 ), },
},
["tags"] = {"generic", "acid", "pistons", },
["pawn_count"] = 0, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Pumping Station", },

["region6"] = {["mission"] = "", ["state"] = 2, ["name"] = "The Landfill", ["objectives"] = {["0"] = {["text"] = "Mission_AcidStorm_Obj", ["param1"] = "", ["param2"] = "", ["value"] = 0, ["potential"] = 1, ["category"] = 0, },
["1"] = {["text"] = "Bonus_Simple_Grid", ["param1"] = "", ["param2"] = "", ["value"] = 1, ["potential"] = 1, ["category"] = 0, },
},
},

["region7"] = {["mission"] = "", ["state"] = 2, ["name"] = "Corporate HQ", ["objectives"] = {},
},
["iBattleRegion"] = 3, }
 

GAME = { 
["WeaponDeck"] = { 
[1] = "Prime_Punchmech", 
[2] = "Prime_Lightning", 
[3] = "Prime_Lasermech", 
[4] = "Prime_Rockmech", 
[5] = "Prime_RightHook", 
[6] = "Prime_Shift", 
[7] = "Prime_Flamethrower", 
[8] = "Prime_Areablast", 
[9] = "Prime_Leap", 
[10] = "Prime_Sword", 
[11] = "Prime_Smash", 
[12] = "Brute_Tankmech", 
[13] = "Brute_PhaseShot", 
[14] = "Brute_Grapple", 
[15] = "Brute_Shrapnel", 
[16] = "Brute_Sniper", 
[17] = "Brute_Shockblast", 
[18] = "Brute_Beetle", 
[19] = "Brute_Heavyrocket", 
[20] = "Brute_Splitshot", 
[21] = "Brute_Bombrun", 
[22] = "Brute_Sonic", 
[23] = "Ranged_Artillerymech", 
[24] = "Ranged_Rockthrow", 
[25] = "Ranged_Defensestrike", 
[26] = "Ranged_Ignite", 
[27] = "Ranged_ScatterShot", 
[28] = "Ranged_BackShot", 
[29] = "Ranged_Ice", 
[30] = "Ranged_SmokeBlast", 
[31] = "Ranged_Fireball", 
[32] = "Ranged_RainingVolley", 
[33] = "Ranged_Wide", 
[34] = "Science_Pullmech", 
[35] = "Science_Gravwell", 
[36] = "Science_Swap", 
[37] = "Science_AcidShot", 
[38] = "Science_Confuse", 
[39] = "Science_SmokeDefense", 
[40] = "Science_Shield", 
[41] = "Science_FreezeBeam", 
[42] = "Science_LocalShield", 
[43] = "Science_PushBeam", 
[44] = "Support_Boosters", 
[45] = "Support_Refrigerate", 
[46] = "Support_Destruct", 
[47] = "DeploySkill_ShieldTank", 
[48] = "DeploySkill_Tank", 
[49] = "DeploySkill_PullTank", 
[50] = "Support_Force", 
[51] = "Support_SmokeDrop", 
[52] = "Support_Repair", 
[53] = "Support_Missiles", 
[54] = "Support_Wind", 
[55] = "Support_Blizzard", 
[56] = "Passive_Leech", 
[57] = "Passive_MassRepair", 
[58] = "Passive_Defenses", 
[59] = "Passive_Burrows", 
[60] = "Passive_AutoShields", 
[61] = "Passive_Boosters", 
[62] = "Passive_Medical", 
[63] = "Passive_FriendlyFire", 
[64] = "Passive_CritDefense", 
[65] = "Prime_Flamespreader", 
[66] = "Prime_WayTooBig", 
[67] = "Prime_PrismLaser", 
[68] = "Prime_TC_Feint", 
[69] = "Prime_KO_Crack", 
[70] = "Brute_KickBack", 
[71] = "Brute_PierceShot", 
[72] = "Brute_TC_GuidedMissile", 
[73] = "Brute_TC_Ricochet", 
[74] = "Brute_TC_DoubleShot", 
[75] = "Brute_KO_Combo", 
[76] = "Ranged_Crack", 
[77] = "Ranged_DeployBomb", 
[78] = "Ranged_Arachnoid", 
[79] = "Ranged_SmokeFire", 
[80] = "Ranged_TC_BounceShot", 
[81] = "Ranged_TC_DoubleArt", 
[82] = "Ranged_KO_Combo", 
[83] = "Science_RainingFire", 
[84] = "Science_MassShift", 
[85] = "Science_TelePush", 
[86] = "Science_TC_Control", 
[87] = "Science_TC_SwapOther", 
[88] = "Science_KO_Crack", 
[89] = "Support_Confuse", 
[90] = "Support_GridDefense", 
[91] = "Support_Waterdrill", 
[92] = "Support_TC_GridAtk", 
[93] = "Support_TC_Bombline", 
[94] = "Support_KO_GridCharger", 
[95] = "Passive_HealingSmoke", 
[96] = "Passive_FireBoost", 
[97] = "Passive_PlayerTurnShield", 
[98] = "Passive_VoidShock" 
}, 
["PodWeaponDeck"] = { 
[1] = "Prime_Areablast", 
[2] = "Prime_Leap", 
[3] = "Prime_Sword", 
[4] = "Prime_Smash", 
[5] = "Brute_Grapple", 
[6] = "Brute_Sniper", 
[7] = "Brute_Shockblast", 
[8] = "Brute_Beetle", 
[9] = "Brute_Heavyrocket", 
[10] = "Brute_Bombrun", 
[11] = "Brute_Sonic", 
[12] = "Ranged_Ice", 
[13] = "Ranged_SmokeBlast", 
[14] = "Ranged_Fireball", 
[15] = "Ranged_RainingVolley", 
[16] = "Science_SmokeDefense", 
[17] = "Science_Shield", 
[18] = "Science_FreezeBeam", 
[19] = "Science_LocalShield", 
[20] = "Science_PushBeam", 
[21] = "Support_Boosters", 
[22] = "Support_Refrigerate", 
[23] = "Support_Destruct", 
[24] = "DeploySkill_ShieldTank", 
[25] = "DeploySkill_Tank", 
[26] = "DeploySkill_PullTank", 
[27] = "Support_Force", 
[28] = "Support_SmokeDrop", 
[29] = "Support_Repair", 
[30] = "Support_Missiles", 
[31] = "Support_Wind", 
[32] = "Support_Blizzard", 
[33] = "Passive_Leech", 
[34] = "Passive_MassRepair", 
[35] = "Passive_Defenses", 
[36] = "Passive_Burrows", 
[37] = "Passive_AutoShields", 
[38] = "Passive_Boosters", 
[39] = "Passive_Medical", 
[40] = "Passive_FriendlyFire", 
[41] = "Passive_CritDefense", 
[42] = "Prime_WayTooBig", 
[43] = "Prime_PrismLaser", 
[44] = "Prime_TC_Feint", 
[45] = "Brute_TC_GuidedMissile", 
[46] = "Brute_KO_Combo", 
[47] = "Ranged_TC_BounceShot", 
[48] = "Ranged_TC_DoubleArt", 
[49] = "Ranged_KO_Combo", 
[50] = "Science_TelePush", 
[51] = "Support_Confuse", 
[52] = "Support_GridDefense", 
[53] = "Support_Waterdrill", 
[54] = "Support_TC_GridAtk", 
[55] = "Support_TC_Bombline", 
[56] = "Support_KO_GridCharger", 
[57] = "Passive_HealingSmoke", 
[58] = "Passive_FireBoost", 
[59] = "Passive_PlayerTurnShield", 
[60] = "Passive_VoidShock" 
}, 
["PilotDeck"] = { 
[1] = "Pilot_Soldier", 
[2] = "Pilot_Youth", 
[3] = "Pilot_Warrior", 
[4] = "Pilot_Aquatic", 
[5] = "Pilot_Medic", 
[6] = "Pilot_Miner", 
[7] = "Pilot_Leader", 
[8] = "Pilot_Caretaker", 
[9] = "Pilot_Chemical", 
[10] = "Pilot_Delusional" 
}, 
["SeenPilots"] = { 
[1] = "Pilot_Original", 
[2] = "Pilot_Detritus", 
[3] = "Pilot_Rust", 
[4] = "Pilot_Hotshot", 
[5] = "Pilot_Repairman", 
[6] = "Pilot_Recycler", 
[7] = "Pilot_Arrogant", 
[8] = "Pilot_Genius", 
[9] = "Pilot_Assassin" 
}, 
["PodDeck"] = { 
[1] = { 
["cores"] = 1 
}, 
[2] = { 
["cores"] = 1, 
["weapon"] = "random" 
}, 
[3] = { 
["cores"] = 1, 
["weapon"] = "random" 
}, 
[4] = { 
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
["Island"] = 4, 
["Missions"] = { 
[1] = { 
["ID"] = "Mission_Missiles", 
["BonusObjs"] = { 
[1] = 1 
}, 
["DiffMod"] = 2, 
["AssetId"] = "Str_Robotics" 
}, 
[2] = { 
["ID"] = "Mission_Power", 
["BonusObjs"] = { 
[1] = 8 
}, 
["DiffMod"] = 2 
}, 
[3] = { 
["ID"] = "Mission_Acid", 
["BonusObjs"] = { 
[1] = 7, 
[2] = 1 
}, 
["AssetId"] = "Str_Power" 
}, 
[4] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 8, 
["curr_weakRatio"] = { 
[1] = 1, 
[2] = 2 
}, 
["curr_upgradeRatio"] = { 
[1] = 1, 
[2] = 2 
}, 
["upgrade_streak"] = 0, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Spider"] = 1, 
["Jelly_Fire"] = 1, 
["Firefly"] = 3, 
["Bouncer"] = 1, 
["Leaper"] = 2 
} 
}, 
["LiveEnvironment"] = { 
}, 
["BonusObjs"] = { 
[1] = 3 
}, 
["ID"] = "Mission_AcidStorm", 
["VoiceEvents"] = { 
}, 
["StormID"] = 419, 
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
[1] = 1, 
[2] = 2 
}, 
["upgrade_streak"] = 1, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Centipede"] = 1, 
["Leaper"] = 1, 
["Jelly_Fire"] = 1 
} 
}, 
["BonusObjs"] = { 
[1] = 9 
}, 
["ID"] = "Mission_Teleporter", 
["VoiceEvents"] = { 
}, 
["DiffMod"] = 1, 
["LiveEnvironment"] = { 
} 
}, 
[6] = { 
["ID"] = "Mission_Barrels", 
["BonusObjs"] = { 
} 
}, 
[7] = { 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 8, 
["curr_weakRatio"] = { 
[1] = 1, 
[2] = 2 
}, 
["curr_upgradeRatio"] = { 
[1] = 1, 
[2] = 2 
}, 
["upgrade_streak"] = 0, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Spider"] = 1, 
["Jelly_Fire"] = 1, 
["Firefly"] = 1, 
["Bouncer"] = 3, 
["Leaper"] = 2 
} 
}, 
["AssetId"] = "Str_Nimbus", 
["BonusObjs"] = { 
[1] = 4, 
[2] = 1 
}, 
["AssetLoc"] = Point( 1, 5 ), 
["ID"] = "Mission_BeltRandom", 
["VoiceEvents"] = { 
}, 
["LiveEnvironment"] = { 
["Belts"] = { 
[1] = Point( 1, 1 ), 
[2] = Point( 1, 0 ), 
[3] = Point( 3, 3 ), 
[4] = Point( 3, 4 ), 
[5] = Point( 6, 2 ), 
[6] = Point( 7, 6 ), 
[7] = Point( 7, 5 ), 
[8] = Point( 6, 5 ) 
}, 
["BeltsDir"] = { 
[1] = 2, 
[2] = 2, 
[3] = 0, 
[4] = 0, 
[5] = 1, 
[6] = 2, 
[7] = 2, 
[8] = 1 
} 
}, 
["PowerStart"] = 7 
}, 
[8] = { 
["ID"] = "Mission_ScorpionBoss", 
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
["money"] = 1, ["cores"] = 2, ["bIsFavor"] = false, ["repairs"] = 0, ["CorpReward"] = {CreateEffect({weapon = "Science_TC_Enrage",}), CreateEffect({skill1 = "Invulnerable",skill2 = "Closer",pilot = "Pilot_Genius",}), CreateEffect({power = 2,}), },
["RewardClaimed"] = false, 
["skip_pawns"] = true, 

["storage_size"] = 5, ["storage_3"] = {["pilot"] = true, ["id"] = "Pilot_Recycler", ["name"] = "Prospero", ["name_id"] = "Pilot_Recycler_Name", ["renamed"] = false, ["skill1"] = 8, ["skill2"] = 1, ["exp"] = 3, ["level"] = 1, ["travel"] = 0, ["final"] = 0, ["starting"] = false, ["power"] = {0, },
},
["storage_4"] = {["weapon"] = "Prime_TC_BendBeam", },
["CorpStore"] = {CreateEffect({weapon = "Brute_Unstable",money = -2,}), CreateEffect({weapon = "Brute_Mirrorshot",money = -2,}), CreateEffect({weapon = "Prime_TC_Punt",money = -2,}), CreateEffect({weapon = "Support_Smoke",money = -2,}), CreateEffect({money = -3,stock = -1,cores = 1,}), CreateEffect({money = -1,power = 1,stock = -1,}), },
["island_store_count"] = 3, ["store_undo_size"] = 0, }
 

