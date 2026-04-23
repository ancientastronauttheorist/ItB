GameData = {["save_version"] = 1, ["language"] = 1, ["network"] = 2, ["networkMax"] = 7, ["overflow"] = 0, ["seed"] = 2129015049, ["new_enemies"] = 0, ["new_missions"] = 0, ["new_equip"] = 0, ["difficulty"] = 2, ["new_abilities"] = 0, ["ach_info"] = {["squad"] = "Random", ["trackers"] = {["Detritus_B_2"] = 0, ["Global_Challenge_Power"] = 2, ["Archive_A_1"] = 0, ["Archive_B_2"] = 0, ["Rust_A_2"] = 0, ["Rust_A_3"] = 0, ["Pinnacle_A_3"] = 0, ["Archive_B_1"] = 0, ["Pinnacle_B_3"] = 0, ["Detritus_B_1"] = 0, ["Pinnacle_B_1"] = 0, ["Global_Island_Mechs"] = 2, ["Global_Island_Building"] = 0, ["Squad_Mist_1"] = 0, ["Squad_Bomber_2"] = 0, ["Squad_Spiders_1"] = 0, ["Squad_Mist_2"] = 0, ["Squad_Heat_1"] = 0, ["Squad_Cataclysm_1"] = 0, ["Squad_Cataclysm_2"] = 0, ["Squad_Cataclysm_3"] = 0, },
},


["current"] = {["score"] = 0, ["time"] = 286333.187500, ["kills"] = 0, ["damage"] = 0, ["failures"] = 0, ["difficulty"] = 2, ["victory"] = false, ["squad"] = 8, 
["mechs"] = {"JetMech", "IceMech", "PulseMech", },
["colors"] = {1, 6, 1, },
["weapons"] = {"Brute_Jetmech", "", "Ranged_Ice", "", "Science_Repulse", "", },
["pilot0"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 1, ["exp"] = 41, ["level"] = 1, ["travel"] = 4, ["final"] = 0, ["starting"] = true, ["last_end"] = 2, },
["pilot1"] = {["id"] = "Pilot_Detritus", ["name"] = "Maxim Prieto", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 1, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot2"] = {["id"] = "Pilot_Rust", ["name"] = "Nick Chavez", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 2, ["skill2"] = 1, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
},
["current_squad"] = 8, ["undosave"] = true, }
 

RegionData = {
["sector"] = 0, ["island"] = 1, ["secret"] = false, 
["island0"] = {["corporation"] = "Corp_Grass", ["id"] = 0, ["secured"] = false, },
["island1"] = {["corporation"] = "Corp_Desert", ["id"] = 1, ["secured"] = false, },
["island2"] = {["corporation"] = "Corp_Snow", ["id"] = 2, ["secured"] = false, },
["island3"] = {["corporation"] = "Corp_Factory", ["id"] = 3, ["secured"] = false, },

["turn"] = 0, ["iTower"] = 1, ["quest_tracker"] = 0, ["quest_id"] = 0, ["podRewards"] = {},


["region0"] = {["mission"] = "Mission6", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 4, ["iTeamTurn"] = 1, ["iState"] = 0, ["sMission"] = "Mission6", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Terraform_Briefing_CEO_Sand_2", ["podReward"] = CreateEffect({skill1 = "Health",skill2 = "Move",pilot = "Pilot_Warrior",cores = 1,}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 3, ["aiDelay"] = 0.000000, ["aiSeed"] = 248761074, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "terraformer2", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 7, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 7, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 7, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 127, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 160, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 3 ), ["terrain"] = 0, ["custom"] = "snow.png", },
{["loc"] = Point( 1, 5 ), ["terrain"] = 7, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 7, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 7, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 7, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 7, ["custom"] = "snow.png", ["frozen"] = true, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 0, },
{["loc"] = Point( 2, 4 ), ["terrain"] = 0, ["custom"] = "snow.png", ["grappled"] = 1, },
{["loc"] = Point( 2, 5 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_power1", ["people1"] = 160, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 167, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 7 ), ["terrain"] = 7, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 3, 3 ), ["terrain"] = 0, ["smoke"] = 1, ["smoke"] = 1, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 3, 4 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", ["grapple_targets"] = {3, },
},
{["loc"] = Point( 3, 5 ), ["terrain"] = 2, ["health_max"] = 2, ["health_min"] = 0, ["rubble_type"] = 0, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 269, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 4, 3 ), ["terrain"] = 0, ["fire"] = 2, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 4, 4 ), ["terrain"] = 6, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 4, 5 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 4, 6 ), ["terrain"] = 0, ["pod"] = 1, },
{["loc"] = Point( 4, 7 ), ["terrain"] = 7, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 1 ), ["terrain"] = 4, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 5, 2 ), ["terrain"] = 6, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 5, 3 ), ["terrain"] = 0, ["custom"] = "snow.png", ["grappled"] = 2, },
{["loc"] = Point( 5, 4 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", ["grapple_targets"] = {0, },
},
{["loc"] = Point( 5, 5 ), ["terrain"] = 0, ["smoke"] = 1, ["smoke"] = 1, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 5, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 157, ["people2"] = 0, ["health_max"] = 2, ["health_min"] = 1, },
{["loc"] = Point( 6, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 1 ), ["terrain"] = 7, },
{["loc"] = Point( 6, 2 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 6, 3 ), ["terrain"] = 6, ["custom"] = "ground_grass.png", ["grapple_targets"] = {3, },
},
{["loc"] = Point( 6, 4 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 6, 5 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 6, 7 ), ["terrain"] = 7, },
{["loc"] = Point( 7, 2 ), ["terrain"] = 4, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 7, 3 ), ["terrain"] = 4, ["custom"] = "ground_grass.png", },
},
["pod"] = Point(4,6), ["spawns"] = {},
["spawn_ids"] = {},
["spawn_points"] = {},
["zones"] = {["grass"] = {Point( 4, 5 ), Point( 4, 4 ), Point( 3, 4 ), Point( 3, 3 ), Point( 4, 3 ), Point( 4, 1 ), Point( 5, 2 ), Point( 6, 2 ), Point( 6, 3 ), Point( 6, 4 ), Point( 5, 4 ), Point( 5, 5 ), Point( 6, 5 ), Point( 3, 2 ), Point( 7, 2 ), Point( 7, 3 ), },
["terraformer"] = {Point( 5, 3 ), },
["enemy"] = {Point( 5, 5 ), Point( 6, 6 ), Point( 6, 4 ), Point( 6, 3 ), Point( 5, 2 ), Point( 6, 2 ), Point( 6, 1 ), Point( 6, 5 ), Point( 5, 4 ), },
},
["tags"] = {"sand", "terraformer", },


["pawn1"] = {["type"] = "Terraformer", ["name"] = "", ["id"] = 417, ["mech"] = false, ["offset"] = 0, ["primary"] = "Terraformer_Attack", ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Rust", ["name"] = "Maria Koleda", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 0, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = false, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 1, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,3), ["last_location"] = Point(-1,-1), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 417, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn2"] = {["type"] = "JetMech", ["name"] = "", ["id"] = 0, ["mech"] = true, ["offset"] = 1, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Brute_Jetmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 1, ["exp"] = 41, ["level"] = 1, ["travel"] = 4, ["final"] = 0, ["starting"] = true, ["last_end"] = 2, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 4, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(2,3), ["last_location"] = Point(4,3), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 0, ["piTarget"] = Point(2,3), ["piOrigin"] = Point(4,3), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(2,3), },


["pawn3"] = {["type"] = "IceMech", ["name"] = "", ["id"] = 1, ["mech"] = true, ["offset"] = 6, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 1, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Ranged_Ice", ["primary_power"] = {1, },
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Detritus", ["name"] = "Maxim Prieto", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 0, ["skill2"] = 1, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 1, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(2,4), ["last_location"] = Point(1,4), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 1, ["piTarget"] = Point(2,2), ["piOrigin"] = Point(2,4), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(2,2), },


["pawn4"] = {["type"] = "PulseMech", ["name"] = "", ["id"] = 2, ["mech"] = true, ["offset"] = 1, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Science_Repulse", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Rust", ["name"] = "Nick Chavez", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 2, ["skill2"] = 1, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(2,1), ["last_location"] = Point(3,1), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 1, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 2, ["piTarget"] = Point(255,255), ["piOrigin"] = Point(2,1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,1), },


["pawn5"] = {["type"] = "Scorpion2", ["name"] = "", ["id"] = 418, ["mech"] = false, ["offset"] = 1, ["primary"] = "ScorpionAtk2", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 4, ["max_health"] = 5, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,4), ["last_location"] = Point(3,3), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 4, ["iOwner"] = 418, ["piTarget"] = Point(2,4), ["piOrigin"] = Point(3,4), ["piQueuedShot"] = Point(2,4), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(2,4), },


["pawn6"] = {["type"] = "Hornet1", ["name"] = "", ["id"] = 419, ["mech"] = false, ["offset"] = 0, ["primary"] = "HornetAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(1,3), ["last_location"] = Point(1,4), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 4, ["iOwner"] = 419, ["piTarget"] = Point(2,3), ["piOrigin"] = Point(1,3), ["piQueuedShot"] = Point(2,3), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(2,3), },


["pawn7"] = {["type"] = "Scarab1", ["name"] = "", ["id"] = 420, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScarabAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["bFrozen"] = true, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(2,2), ["last_location"] = Point(2,3), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 4, ["iOwner"] = 420, ["piTarget"] = Point(2,5), ["piOrigin"] = Point(2,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(2,5), },


["pawn8"] = {["type"] = "Scorpion1", ["name"] = "", ["id"] = 421, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScorpionAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,4), ["last_location"] = Point(4,4), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 4, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 4, ["iOwner"] = 421, ["piTarget"] = Point(5,3), ["piOrigin"] = Point(5,4), ["piQueuedShot"] = Point(5,3), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,3), },


["pawn9"] = {["type"] = "Scarab1", ["name"] = "", ["id"] = 428, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScarabAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,4), ["last_location"] = Point(3,4), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 2, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 4, ["iOwner"] = 428, ["piTarget"] = Point(2,4), ["piOrigin"] = Point(4,4), ["piQueuedShot"] = Point(2,4), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(2,4), },


["pawn10"] = {["type"] = "Jelly_Regen1", ["name"] = "", ["id"] = 429, ["mech"] = false, ["offset"] = 3, ["not_attacking"] = true, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,2), ["last_location"] = Point(5,3), ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 2, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 4, ["iOwner"] = 429, ["piTarget"] = Point(-2147483647,-2147483647), ["piOrigin"] = Point(6,3), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn11"] = {["type"] = "Scorpion1", ["name"] = "", ["id"] = 430, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScorpionAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,3), ["last_location"] = Point(6,2), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 0, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 4, ["iOwner"] = 430, ["piTarget"] = Point(5,3), ["piOrigin"] = Point(6,3), ["piQueuedShot"] = Point(5,3), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,3), },
["pawn_count"] = 11, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Tesla Fields", },

["region1"] = {["mission"] = "", ["state"] = 2, ["name"] = "Corporate HQ", ["objectives"] = {},
},

["region2"] = {["mission"] = "Mission4", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission4", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Lightning_Briefing_CEO_Sand_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 1088121233, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "anyAE22", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 1 ), ["terrain"] = 7, },
{["loc"] = Point( 0, 3 ), ["terrain"] = 7, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 149, ["people2"] = 0, ["health_max"] = 1, ["shield"] = true, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 114, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 101, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 0 ), ["terrain"] = 7, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 7, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 7, },
{["loc"] = Point( 3, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 108, ["people2"] = 0, ["health_max"] = 1, ["shield"] = true, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 250, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 250, ["people2"] = 0, ["health_max"] = 2, ["shield"] = true, },
{["loc"] = Point( 4, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 250, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 278, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 2 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 3 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 4 ), ["terrain"] = 7, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 2 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 3 ), ["terrain"] = 7, },
},
["spawns"] = {"Hornet2", "Hornet1", "Scorpion1", },
["spawn_ids"] = {422, 423, 424, },
["spawn_points"] = {Point(5,4), Point(7,3), Point(6,5), },
["zones"] = {},
["tags"] = {"generic", "any_sector", "mountain", },
["pawn_count"] = 0, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Test Site Echo", },

["region3"] = {["mission"] = "Mission7", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission7", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Solar_Briefing_CEO_Sand_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 1943849917, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "anyAE16", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 156, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 185, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 146, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 7, },
{["loc"] = Point( 2, 4 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_solar1", ["people1"] = 166, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 5 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_solar1", ["people1"] = 147, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 3, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 376, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 324, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 3 ), ["terrain"] = 7, },
{["loc"] = Point( 4, 5 ), ["terrain"] = 0, ["cracked"] = true, },
{["loc"] = Point( 4, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 4, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 2 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 2 ), ["terrain"] = 7, },
{["loc"] = Point( 6, 3 ), ["terrain"] = 7, },
{["loc"] = Point( 6, 5 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 7, },
{["loc"] = Point( 7, 4 ), ["terrain"] = 7, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 7, },
},
["spawns"] = {"Hornet1", "Scorpion2", "Scarab1", },
["spawn_ids"] = {425, 426, 427, },
["spawn_points"] = {Point(7,4), Point(6,4), Point(5,3), },
["zones"] = {},
["tags"] = {"generic", "any_sector", "mountain", },
["pawn_count"] = 0, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Rust Beach", },

["region4"] = {["mission"] = "Mission3", ["state"] = 0, ["name"] = "Hardened Shale", },

["region5"] = {["mission"] = "Mission1", ["state"] = 0, ["name"] = "Black Rock", },

["region6"] = {["mission"] = "Mission5", ["state"] = 0, ["name"] = "Tectonic Site 3.1", },

["region7"] = {["mission"] = "Mission2", ["state"] = 0, ["name"] = "Scorched Earth", },
["iBattleRegion"] = 0, }
 

GAME = { 
["WeaponDeck"] = { 
[1] = "Prime_Punchmech", 
[2] = "Prime_Lightning", 
[3] = "Prime_Lasermech", 
[4] = "Prime_ShieldBash", 
[5] = "Prime_Rockmech", 
[6] = "Prime_RightHook", 
[7] = "Prime_RocketPunch", 
[8] = "Prime_Shift", 
[9] = "Prime_Flamethrower", 
[10] = "Prime_Areablast", 
[11] = "Prime_Spear", 
[12] = "Prime_Leap", 
[13] = "Prime_SpinFist", 
[14] = "Prime_Sword", 
[15] = "Prime_Smash", 
[16] = "Brute_Tankmech", 
[17] = "Brute_Mirrorshot", 
[18] = "Brute_PhaseShot", 
[19] = "Brute_Grapple", 
[20] = "Brute_Shrapnel", 
[21] = "Brute_Sniper", 
[22] = "Brute_Shockblast", 
[23] = "Brute_Beetle", 
[24] = "Brute_Unstable", 
[25] = "Brute_Heavyrocket", 
[26] = "Brute_Splitshot", 
[27] = "Brute_Bombrun", 
[28] = "Brute_Sonic", 
[29] = "Ranged_Artillerymech", 
[30] = "Ranged_Rockthrow", 
[31] = "Ranged_Defensestrike", 
[32] = "Ranged_Rocket", 
[33] = "Ranged_Ignite", 
[34] = "Ranged_BackShot", 
[35] = "Ranged_SmokeBlast", 
[36] = "Ranged_Fireball", 
[37] = "Ranged_RainingVolley", 
[38] = "Ranged_Wide", 
[39] = "Ranged_Dual", 
[40] = "Science_Pullmech", 
[41] = "Science_Gravwell", 
[42] = "Science_Swap", 
[43] = "Science_AcidShot", 
[44] = "Science_Confuse", 
[45] = "Science_SmokeDefense", 
[46] = "Science_Shield", 
[47] = "Science_FireBeam", 
[48] = "Science_FreezeBeam", 
[49] = "Science_LocalShield", 
[50] = "Science_PushBeam", 
[51] = "Support_Boosters", 
[52] = "Support_Smoke", 
[53] = "Support_Refrigerate", 
[54] = "Support_Destruct", 
[55] = "DeploySkill_Tank", 
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
[14] = "Ranged_SmokeBlast", 
[15] = "Ranged_Fireball", 
[16] = "Ranged_RainingVolley", 
[17] = "Ranged_Dual", 
[18] = "Science_SmokeDefense", 
[19] = "Science_Shield", 
[20] = "Science_FireBeam", 
[21] = "Science_FreezeBeam", 
[22] = "Science_LocalShield", 
[23] = "Science_PushBeam", 
[24] = "Support_Boosters", 
[25] = "Support_Smoke", 
[26] = "Support_Refrigerate", 
[27] = "Support_Destruct", 
[28] = "DeploySkill_Tank", 
[29] = "DeploySkill_PullTank", 
[30] = "Support_Force", 
[31] = "Support_SmokeDrop", 
[32] = "Support_Repair", 
[33] = "Support_Missiles", 
[34] = "Support_Wind", 
[35] = "Support_Blizzard", 
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
[3] = "Pilot_Medic", 
[4] = "Pilot_Hotshot", 
[5] = "Pilot_Genius", 
[6] = "Pilot_Miner", 
[7] = "Pilot_Recycler", 
[8] = "Pilot_Assassin", 
[9] = "Pilot_Leader", 
[10] = "Pilot_Repairman" 
}, 
["SeenPilots"] = { 
[1] = "Pilot_Original", 
[2] = "Pilot_Detritus", 
[3] = "Pilot_Rust", 
[4] = "Pilot_Aquatic", 
[5] = "Pilot_Warrior" 
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
[1] = "Mission_BeetleBoss", 
[2] = "Mission_FireflyBoss", 
[3] = "Mission_BlobBoss", 
[4] = "Mission_JellyBoss" 
}, 
["Island"] = 2, 
["Missions"] = { 
[1] = { 
["ID"] = "Mission_Cataclysm", 
["BonusObjs"] = { 
[1] = 6, 
[2] = 1 
}, 
["AssetId"] = "Str_Power" 
}, 
[2] = { 
["ID"] = "Mission_Bomb", 
["BonusObjs"] = { 
[1] = 1 
}, 
["DiffMod"] = 2, 
["AssetId"] = "Str_Battery" 
}, 
[3] = { 
["ID"] = "Mission_Train", 
["BonusObjs"] = { 
} 
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
["Scorpion"] = 1, 
["Hornet"] = 2 
} 
}, 
["BonusObjs"] = { 
[1] = 4 
}, 
["ID"] = "Mission_Lightning", 
["VoiceEvents"] = { 
}, 
["DiffMod"] = 1, 
["LiveEnvironment"] = { 
["Locations"] = { 
}, 
["Planned"] = { 
} 
} 
}, 
[5] = { 
["ID"] = "Mission_Filler", 
["BonusObjs"] = { 
[1] = 5 
} 
}, 
[6] = { 
["BonusObjs"] = { 
[1] = 1 
}, 
["AssetId"] = "Str_Power", 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 6, 
["curr_weakRatio"] = { 
[1] = 3, 
[2] = 4 
}, 
["curr_upgradeRatio"] = { 
[1] = 1, 
[2] = 4 
}, 
["upgrade_streak"] = 0, 
["num_bosses"] = 0, 
["pawn_counts"] = { 
["Jelly_Regen"] = 1, 
["Scorpion"] = 3, 
["Scarab"] = 2, 
["Hornet"] = 1 
} 
}, 
["LiveEnvironment"] = { 
}, 
["TerraformerId"] = 417, 
["AssetLoc"] = Point( 2, 5 ), 
["ID"] = "Mission_Terraform", 
["VoiceEvents"] = { 
}, 
["DiffMod"] = 2, 
["PowerStart"] = 5 
}, 
[7] = { 
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
["Hornet"] = 1, 
["Scarab"] = 1, 
["Scorpion"] = 1 
} 
}, 
["LiveEnvironment"] = { 
}, 
["Criticals"] = { 
[1] = Point( 2, 4 ), 
[2] = Point( 2, 5 ) 
}, 
["ID"] = "Mission_Solar", 
["VoiceEvents"] = { 
}, 
["BonusObjs"] = { 
} 
}, 
[8] = { 
["ID"] = "Mission_FireflyBoss", 
["BonusObjs"] = { 
[1] = 1 
}, 
["AssetId"] = "Str_Tower" 
} 
}, 
["Enemies"] = { 
[1] = { 
[1] = "Leaper", 
[2] = "Firefly", 
[3] = "Hornet", 
[4] = "Jelly_Health", 
[5] = "Centipede", 
[6] = "Spider", 
["island"] = 1 
}, 
[2] = { 
[1] = "Scorpion", 
[2] = "Scarab", 
[3] = "Hornet", 
[4] = "Jelly_Regen", 
[5] = "Beetle", 
[6] = "Digger", 
["island"] = 2 
}, 
[3] = { 
[1] = "Leaper", 
[2] = "Firefly", 
[3] = "Scarab", 
[4] = "Jelly_Armor", 
[5] = "Blobber", 
[6] = "Burrower", 
["island"] = 3 
}, 
[4] = { 
[1] = "Scorpion", 
[2] = "Hornet", 
[3] = "Firefly", 
[4] = "Jelly_Explode", 
[5] = "Crab", 
[6] = "Blobber", 
["island"] = 4 
} 
} 
}

 

SquadData = {
["money"] = 0, ["cores"] = 0, ["bIsFavor"] = false, ["repairs"] = 0, ["CorpReward"] = {CreateEffect({weapon = "DeploySkill_AcidTank",}), CreateEffect({skill1 = "Move",skill2 = "Health",pilot = "Pilot_Aquatic",}), CreateEffect({power = 2,}), },
["RewardClaimed"] = false, 
["skip_pawns"] = true, 

["storage_size"] = 3, ["CorpStore"] = {CreateEffect({weapon = "DeploySkill_ShieldTank",money = -2,}), CreateEffect({weapon = "Ranged_ScatterShot",money = -2,}), CreateEffect({stock = 0,}), CreateEffect({stock = 0,}), CreateEffect({money = -3,stock = -1,cores = 1,}), CreateEffect({money = -1,power = 1,stock = -1,}), },
["island_store_count"] = 0, ["store_undo_size"] = 0, }
 

