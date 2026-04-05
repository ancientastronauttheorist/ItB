GameData = {["save_version"] = 1, ["language"] = 1, ["network"] = 3, ["networkMax"] = 7, ["overflow"] = 0, ["seed"] = 1294279092, ["new_enemies"] = 0, ["new_missions"] = 0, ["new_equip"] = 0, ["difficulty"] = 1, ["new_abilities"] = 0, ["ach_info"] = {["squad"] = "Archive_A", ["trackers"] = {["Detritus_B_2"] = 0, ["Global_Challenge_Power"] = 1, ["Archive_A_1"] = 0, ["Archive_B_2"] = 0, ["Rust_A_2"] = 0, ["Rust_A_3"] = 0, ["Pinnacle_A_3"] = 0, ["Archive_B_1"] = 0, ["Pinnacle_B_3"] = 0, ["Detritus_B_1"] = 0, ["Pinnacle_B_1"] = 0, ["Global_Island_Mechs"] = 2, ["Global_Island_Building"] = 2, ["Squad_Mist_1"] = 0, ["Squad_Bomber_2"] = 0, ["Squad_Spiders_1"] = 0, ["Squad_Mist_2"] = 0, ["Squad_Heat_1"] = 0, ["Squad_Cataclysm_1"] = 0, ["Squad_Cataclysm_2"] = 0, ["Squad_Cataclysm_3"] = 0, },
},


["current"] = {["score"] = 0, ["time"] = 3031785.500000, ["kills"] = 1, ["damage"] = 0, ["failures"] = 0, ["difficulty"] = 1, ["victory"] = false, ["squad"] = 0, 
["mechs"] = {"PunchMech", "TankMech", "ArtiMech", },
["colors"] = {0, 0, 0, },
["weapons"] = {"Prime_Punchmech", "", "Brute_Tankmech", "", "Ranged_Artillerymech", "", },
["pilot0"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 2, ["skill2"] = 3, ["exp"] = 4, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot1"] = {["id"] = "Pilot_Archive", ["name"] = "Peter Patel", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 0, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot2"] = {["id"] = "Pilot_Rust", ["name"] = "Elizabeth Chavez", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 3, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
},
["current_squad"] = 0, ["undosave"] = true, }
 

RegionData = {
["sector"] = 0, ["island"] = 3, ["secret"] = false, 
["island0"] = {["corporation"] = "Corp_Grass", ["id"] = 0, ["secured"] = false, },
["island1"] = {["corporation"] = "Corp_Desert", ["id"] = 1, ["secured"] = false, },
["island2"] = {["corporation"] = "Corp_Snow", ["id"] = 2, ["secured"] = false, },
["island3"] = {["corporation"] = "Corp_Factory", ["id"] = 3, ["secured"] = false, },

["turn"] = 0, ["iTower"] = 4, ["quest_tracker"] = 0, ["quest_id"] = 0, ["podRewards"] = {CreateEffect({weapon = "random",cores = 1,}), },


["region0"] = {["mission"] = "Mission3", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 3, ["iTeamTurn"] = 1, ["iState"] = 0, ["sMission"] = "Mission3", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Train_Briefing_CEO_Acid_3", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 3, ["aiDelay"] = 0.000000, ["aiSeed"] = 297333330, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "train14", ["enemy_kills"] = 1, 
["map"] = {{["loc"] = Point( 0, 1 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 3 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 1, 2 ), ["terrain"] = 2, ["health_max"] = 1, ["health_min"] = 0, ["rubble_type"] = 0, },
{["loc"] = Point( 1, 3 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 1, ["populated"] = 1, ["grappled"] = 1, ["people1"] = 158, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 118, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 2, 4 ), ["terrain"] = 0, ["grapple_targets"] = {3, },
},
{["loc"] = Point( 2, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 302, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 0, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 148, ["people2"] = 0, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 3, 5 ), ["terrain"] = 0, ["grappled"] = 1, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 0, },
{["loc"] = Point( 4, 0 ), ["terrain"] = 0, ["custom"] = "ground_rail.png", },
{["loc"] = Point( 4, 1 ), ["terrain"] = 0, ["custom"] = "ground_rail.png", },
{["loc"] = Point( 4, 2 ), ["terrain"] = 0, ["custom"] = "ground_rail.png", },
{["loc"] = Point( 4, 3 ), ["terrain"] = 0, ["custom"] = "ground_rail.png", },
{["loc"] = Point( 4, 4 ), ["terrain"] = 0, ["custom"] = "ground_rail.png", ["undo_state"] = {["active"] = true, ["neighbor1"] = {["health"] = 3, ["max_health"] = 3, },
["neighbor2"] = {["health"] = 2, ["max_health"] = 2, },
["neighbor3"] = {["health"] = 3, ["max_health"] = 3, },
},
},
{["loc"] = Point( 4, 5 ), ["terrain"] = 0, ["custom"] = "ground_rail.png", ["grapple_targets"] = {3, },
},
{["loc"] = Point( 4, 6 ), ["terrain"] = 0, ["custom"] = "ground_rail.png", },
{["loc"] = Point( 4, 7 ), ["terrain"] = 0, ["custom"] = "ground_rail.png", },
{["loc"] = Point( 5, 0 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 5, 1 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 5, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 5, 5 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 5, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 1 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 6, 3 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 6, 4 ), ["terrain"] = 0, },
{["loc"] = Point( 6, 6 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 0, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 3 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 7, 4 ), ["terrain"] = 0, ["poison"] = 1, ["acid_pool"] = 3, },
{["loc"] = Point( 7, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 4, },
},
["pod"] = Point(5,3), ["rain"] = 3, ["rain_type"] = 1, ["spawns"] = {},
["spawn_ids"] = {},
["spawn_points"] = {},
["zones"] = {},
["tags"] = {"train", "acid", },


["pawn1"] = {["type"] = "PunchMech", ["name"] = "", ["id"] = 0, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Prime_Punchmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 2, ["skill2"] = 3, ["exp"] = 4, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 1, ["is_corpse"] = true, ["health"] = 1, ["max_health"] = 3, ["undo_state"] = {["health"] = 3, ["max_health"] = 3, },
["undo_ready"] = false, ["undo_point"] = Point(4,4), ["iMissionDamage"] = 0, ["location"] = Point(4,4), ["last_location"] = Point(3,4), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 3, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(4,4), ["undoReady"] = false, ["iKillCount"] = 4, ["iOwner"] = 0, ["piTarget"] = Point(4,3), ["piOrigin"] = Point(4,4), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,3), },


["pawn2"] = {["type"] = "TankMech", ["name"] = "", ["id"] = 1, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Brute_Tankmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Archive", ["name"] = "Peter Patel", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 0, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,4), ["last_location"] = Point(3,4), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 3, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 1, ["piTarget"] = Point(1,1), ["piOrigin"] = Point(3,4), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,4), },


["pawn3"] = {["type"] = "ArtiMech", ["name"] = "", ["id"] = 2, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Ranged_Artillerymech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Rust", ["name"] = "Elizabeth Chavez", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 3, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,5), ["last_location"] = Point(4,5), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 3, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 2, ["piTarget"] = Point(1,2), ["piOrigin"] = Point(3,5), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn4"] = {["type"] = "Scorpion1", ["name"] = "", ["id"] = 193, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScorpionAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["bAcid"] = true, ["health"] = 1, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(2,4), ["last_location"] = Point(2,3), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 3, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 5, ["iOwner"] = 193, ["piTarget"] = Point(1,4), ["piOrigin"] = Point(2,4), ["piQueuedShot"] = Point(1,4), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(1,4), },


["pawn5"] = {["type"] = "Jelly_Armor1", ["name"] = "", ["id"] = 194, ["mech"] = false, ["offset"] = 2, ["not_attacking"] = true, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 1, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,1), ["last_location"] = Point(3,2), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 3, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 5, ["iOwner"] = 194, ["piTarget"] = Point(-2147483647,-2147483647), ["piOrigin"] = Point(4,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn6"] = {["type"] = "Hornet1", ["name"] = "", ["id"] = 202, ["mech"] = false, ["offset"] = 0, ["primary"] = "HornetAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,6), ["last_location"] = Point(2,6), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 5, ["iOwner"] = 202, ["piTarget"] = Point(2,6), ["piOrigin"] = Point(3,6), ["piQueuedShot"] = Point(2,6), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(2,6), },


["pawn7"] = {["type"] = "Scarab1", ["name"] = "", ["id"] = 203, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScarabAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,4), ["last_location"] = Point(5,3), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 5, ["iOwner"] = 203, ["piTarget"] = Point(3,4), ["piOrigin"] = Point(5,4), ["piQueuedShot"] = Point(3,4), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,4), },


["pawn8"] = {["type"] = "Scorpion1", ["name"] = "", ["id"] = 205, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScorpionAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,5), ["last_location"] = Point(5,5), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = -15921385, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 5, ["iOwner"] = 205, ["piTarget"] = Point(3,5), ["piOrigin"] = Point(4,5), ["piQueuedShot"] = Point(3,5), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(3,5), },


["pawn9"] = {["type"] = "Scarab1", ["name"] = "", ["id"] = 206, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScarabAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,4), ["last_location"] = Point(6,4), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 1869435743, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 5, ["iOwner"] = 206, ["piTarget"] = Point(4,4), ["piOrigin"] = Point(6,4), ["piQueuedShot"] = Point(4,4), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,4), },


["pawn10"] = {["type"] = "Train_Damaged", ["name"] = "", ["id"] = 204, ["mech"] = false, ["offset"] = 0, ["pilot"] = {["id"] = "Pilot_Detritus", ["name"] = "Aidan Lee", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 0, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = false, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 1, ["max_health"] = 1, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,6), ["last_location"] = Point(-1,-1), ["iCurrentWeapon"] = 0, ["iTurnCount"] = 2, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 204, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },
["pawn_count"] = 10, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Venting Fields", },

["region1"] = {["mission"] = "Mission1", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission1", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Belt_Briefing_CEO_Acid_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 503792468, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "disposal9", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 3 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 0, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 87, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 122, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 3 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 1, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 123, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_battery1", ["people1"] = 85, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 3, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 225, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 3 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 4, 3 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 4, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 167, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 191, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 5, 3 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 5, 5 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 6, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 2 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 3 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 6, 6 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
{["loc"] = Point( 7, 3 ), ["terrain"] = 0, ["custom"] = "conveyor3.png", },
{["loc"] = Point( 7, 6 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 1, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 3, ["poison"] = 1, ["acid_pool"] = 2, },
},
["spawns"] = {"Scorpion1", "Hornet1", "Scarab1", },
["spawn_ids"] = {196, 197, 198, },
["spawn_points"] = {Point(7,5), Point(6,4), Point(7,4), },
["zones"] = {["disposal"] = {Point( 1, 3 ), },
},
["tags"] = {"generic", "acid", "disposal", },
["pawn_count"] = 0, ["blocked_points"] = {Point(1,3), Point(2,3), Point(3,3), Point(4,3), Point(5,3), Point(6,3), Point(7,3), },
["blocked_type"] = {2, 2, 2, 2, 2, 2, 2, },
},


},
["state"] = 1, ["name"] = "Chemical Field A", },

["region2"] = {["mission"] = "Mission4", ["state"] = 0, ["name"] = "Pumping Station", },

["region3"] = {["mission"] = "Mission7", ["state"] = 0, ["name"] = "Venting Center", },

["region4"] = {["mission"] = "", ["state"] = 2, ["name"] = "Corporate HQ", ["objectives"] = {},
},

["region5"] = {["mission"] = "Mission2", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission2", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_KillAll_Briefing_CEO_Acid_2", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 1018319989, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "any40", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 119, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_recycle1", ["people1"] = 112, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 89, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 7 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 122, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 159, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 4 ), ["terrain"] = 3, },
{["loc"] = Point( 3, 7 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 200, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 199, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 4 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 3, },
},
["spawns"] = {"Scorpion1", "Scorpion1", "Hornet1", },
["spawn_ids"] = {199, 200, 201, },
["spawn_points"] = {Point(7,5), Point(6,4), Point(6,3), },
["zones"] = {["satellite"] = {Point( 3, 5 ), Point( 4, 5 ), Point( 3, 3 ), Point( 4, 3 ), Point( 6, 6 ), Point( 6, 5 ), Point( 6, 4 ), Point( 6, 3 ), Point( 2, 5 ), },
},
["tags"] = {"generic", "any_sector", "mountain", "water", "satellite", },
["pawn_count"] = 0, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Containment Zone D", },

["region6"] = {["mission"] = "Mission6", ["state"] = 0, ["name"] = "The Heap", },

["region7"] = {["mission"] = "Mission5", ["state"] = 0, ["name"] = "Waste Chambers", },
["iBattleRegion"] = 0, }
 

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
[22] = "Brute_Unstable", 
[23] = "Brute_Heavyrocket", 
[24] = "Brute_Splitshot", 
[25] = "Brute_Bombrun", 
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
[49] = "Science_LocalShield", 
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
[63] = "Passive_FlameImmune", 
[64] = "Passive_Electric", 
[65] = "Passive_Leech", 
[66] = "Passive_MassRepair", 
[67] = "Passive_Defenses", 
[68] = "Passive_Burrows", 
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
[17] = "Ranged_Dual", 
[18] = "Science_SmokeDefense", 
[19] = "Science_Shield", 
[20] = "Science_FireBeam", 
[21] = "Science_FreezeBeam", 
[22] = "Science_LocalShield", 
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
[36] = "Passive_FlameImmune", 
[37] = "Passive_Electric", 
[38] = "Passive_Leech", 
[39] = "Passive_MassRepair", 
[40] = "Passive_Defenses", 
[41] = "Passive_Burrows", 
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
[2] = "Pilot_Archive", 
[3] = "Pilot_Rust", 
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
[1] = "Mission_BlobBoss", 
[2] = "Mission_FireflyBoss", 
[3] = "Mission_JellyBoss", 
[4] = "Mission_BeetleBoss" 
}, 
["Island"] = 4, 
["Missions"] = { 
[1] = { 
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
["Scorpion"] = 1, 
["Scarab"] = 1, 
["Hornet"] = 1 
} 
}, 
["AssetId"] = "Str_Battery", 
["AssetLoc"] = Point( 1, 6 ), 
["ID"] = "Mission_Belt", 
["VoiceEvents"] = { 
}, 
["LiveEnvironment"] = { 
["Belts"] = { 
[1] = Point( 1, 3 ), 
[2] = Point( 2, 3 ), 
[3] = Point( 3, 3 ), 
[4] = Point( 4, 3 ), 
[5] = Point( 5, 3 ), 
[6] = Point( 6, 3 ), 
[7] = Point( 7, 3 ) 
}, 
["BeltsDir"] = { 
[1] = 3, 
[2] = 3, 
[3] = 3, 
[4] = 3, 
[5] = 3, 
[6] = 3, 
[7] = 3 
} 
}, 
["BonusObjs"] = { 
[1] = 4, 
[2] = 1 
} 
}, 
[2] = { 
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
["Hornet"] = 1, 
["Scorpion"] = 2 
} 
}, 
["AssetId"] = "Str_Nimbus", 
["AssetLoc"] = Point( 1, 1 ), 
["ID"] = "Mission_Survive", 
["VoiceEvents"] = { 
}, 
["LiveEnvironment"] = { 
}, 
["BonusObjs"] = { 
[1] = 6, 
[2] = 1 
} 
}, 
[3] = { 
["BonusObjs"] = { 
}, 
["TrainLoc"] = Point( 4, 6 ), 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 7, 
["curr_weakRatio"] = { 
[1] = 3, 
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
["Scorpion"] = 2, 
["Scarab"] = 2, 
["Hornet"] = 2 
} 
}, 
["LiveEnvironment"] = { 
}, 
["TrainStopped"] = true, 
["ID"] = "Mission_Train", 
["VoiceEvents"] = { 
}, 
["Train"] = 204, 
["PowerStart"] = 5 
}, 
[4] = { 
["ID"] = "Mission_Acid", 
["BonusObjs"] = { 
[1] = 3, 
[2] = 1 
}, 
["AssetId"] = "Str_Power" 
}, 
[5] = { 
["ID"] = "Mission_Teleporter", 
["BonusObjs"] = { 
[1] = 5 
}, 
["DiffMod"] = 1 
}, 
[6] = { 
["ID"] = "Mission_BeltRandom", 
["BonusObjs"] = { 
[1] = 4, 
[2] = 1 
}, 
["AssetId"] = "Str_Bar" 
}, 
[7] = { 
["ID"] = "Mission_Barrels", 
["BonusObjs"] = { 
} 
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
[1] = "Hornet", 
[2] = "Leaper", 
[3] = "Firefly", 
[4] = "Jelly_Health", 
[5] = "Crab", 
[6] = "Digger", 
["island"] = 1 
}, 
[2] = { 
[1] = "Scarab", 
[2] = "Scorpion", 
[3] = "Firefly", 
[4] = "Jelly_Explode", 
[5] = "Centipede", 
[6] = "Blobber", 
["island"] = 2 
}, 
[3] = { 
[1] = "Leaper", 
[2] = "Hornet", 
[3] = "Scarab", 
[4] = "Jelly_Regen", 
[5] = "Spider", 
[6] = "Burrower", 
["island"] = 3 
}, 
[4] = { 
[1] = "Scorpion", 
[2] = "Scarab", 
[3] = "Hornet", 
[4] = "Jelly_Armor", 
[5] = "Beetle", 
[6] = "Centipede", 
["island"] = 4 
} 
} 
}

 

SquadData = {
["money"] = 0, ["cores"] = 0, ["bIsFavor"] = false, ["repairs"] = 0, ["CorpReward"] = {CreateEffect({weapon = "Science_PushBeam",}), CreateEffect({skill1 = "Health",skill2 = "Move",pilot = "Pilot_Recycler",}), CreateEffect({power = 2,}), },
["RewardClaimed"] = false, 
["skip_pawns"] = true, 

["storage_size"] = 3, ["CorpStore"] = {CreateEffect({weapon = "Prime_Spear",money = -2,}), CreateEffect({weapon = "Support_Blizzard",money = -2,}), CreateEffect({stock = 0,}), CreateEffect({stock = 0,}), CreateEffect({money = -3,stock = -1,cores = 1,}), CreateEffect({money = -1,power = 1,stock = -1,}), },
["island_store_count"] = 0, ["store_undo_size"] = 0, }
 

