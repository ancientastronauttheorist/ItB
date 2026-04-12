GameData = {["save_version"] = 1, ["language"] = 1, ["network"] = 5, ["networkMax"] = 7, ["overflow"] = 0, ["seed"] = 239958375, ["new_enemies"] = 0, ["new_missions"] = 0, ["new_equip"] = 0, ["difficulty"] = 1, ["new_abilities"] = 0, ["ach_info"] = {["squad"] = "Archive_A", ["trackers"] = {["Detritus_B_2"] = 0, ["Global_Challenge_Power"] = 0, ["Archive_A_1"] = 0, ["Archive_B_2"] = 0, ["Rust_A_2"] = 0, ["Rust_A_3"] = 0, ["Pinnacle_A_3"] = 0, ["Archive_B_1"] = 0, ["Pinnacle_B_3"] = 0, ["Detritus_B_1"] = 0, ["Pinnacle_B_1"] = 0, ["Global_Island_Mechs"] = 0, ["Global_Island_Building"] = 0, ["Squad_Mist_1"] = 0, ["Squad_Bomber_2"] = 0, ["Squad_Spiders_1"] = 0, ["Squad_Mist_2"] = 0, ["Squad_Heat_1"] = 0, ["Squad_Cataclysm_1"] = 0, ["Squad_Cataclysm_2"] = 0, ["Squad_Cataclysm_3"] = 0, },
},


["current"] = {["score"] = 0, ["time"] = 645673.500000, ["kills"] = 0, ["damage"] = 0, ["failures"] = 0, ["difficulty"] = 1, ["victory"] = false, ["squad"] = 0, 
["mechs"] = {"PunchMech", "TankMech", "ArtiMech", },
["colors"] = {0, 0, 0, },
["weapons"] = {"Prime_Punchmech", "", "Brute_Tankmech", "", "Ranged_Artillerymech", "", },
["pilot0"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Celestine", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 2, ["skill2"] = 1, ["exp"] = 7, ["level"] = 0, ["travel"] = 2, ["final"] = 0, ["starting"] = true, ["last_end"] = 2, },
["pilot1"] = {["id"] = "Pilot_Detritus", ["name"] = "Sergei Chavez", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 3, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot2"] = {["id"] = "Pilot_Archive", ["name"] = "Tatiana Perez", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 2, ["skill2"] = 1, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
},
["current_squad"] = 0, }
 

RegionData = {
["sector"] = 0, ["island"] = 1, ["secret"] = false, 
["island0"] = {["corporation"] = "Corp_Grass", ["id"] = 0, ["secured"] = false, },
["island1"] = {["corporation"] = "Corp_Desert", ["id"] = 1, ["secured"] = false, },
["island2"] = {["corporation"] = "Corp_Snow", ["id"] = 2, ["secured"] = false, },
["island3"] = {["corporation"] = "Corp_Factory", ["id"] = 3, ["secured"] = false, },

["turn"] = 0, ["iTower"] = 0, ["quest_tracker"] = 0, ["quest_id"] = 0, ["podRewards"] = {CreateEffect({weapon = "random",cores = 1,}), },


["region0"] = {["mission"] = "", ["state"] = 2, ["name"] = "Corporate HQ", ["objectives"] = {},
},

["region1"] = {["mission"] = "Mission2", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission2", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Terraform_Briefing_CEO_Sand_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 2095348755, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "terraformerAE5", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 70, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 66, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 66, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 0 ), ["terrain"] = 7, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 7, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 77, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 195, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 166, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 2, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 193, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 3 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 3, 4 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 3, 6 ), ["terrain"] = 7, },
{["loc"] = Point( 4, 2 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 4, 3 ), ["terrain"] = 3, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 4, 4 ), ["terrain"] = 3, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 4, 5 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 5, 1 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 5, 2 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 5, 3 ), ["terrain"] = 0, },
{["loc"] = Point( 5, 4 ), ["terrain"] = 3, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 5, 5 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 5, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 167, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 6, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 1 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 6, 2 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 3 ), ["terrain"] = 3, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 6, 4 ), ["terrain"] = 3, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 6, 5 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 6, 7 ), ["terrain"] = 7, },
{["loc"] = Point( 7, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 7, 2 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 7, 3 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 7, 4 ), ["terrain"] = 0, ["custom"] = "ground_grass.png", },
{["loc"] = Point( 7, 6 ), ["terrain"] = 7, },
},
["spawns"] = {"Scorpion1", "Jelly_Regen1", "Scorpion1", },
["spawn_ids"] = {582, 583, 584, },
["spawn_points"] = {Point(5,5), Point(6,5), Point(5,1), },
["zones"] = {["grass"] = {Point( 4, 5 ), Point( 3, 4 ), Point( 3, 3 ), Point( 5, 5 ), Point( 6, 5 ), Point( 7, 2 ), Point( 7, 3 ), Point( 4, 2 ), Point( 5, 1 ), Point( 7, 4 ), },
["terraformer"] = {Point( 5, 3 ), },
["enemy"] = {Point( 5, 5 ), Point( 6, 6 ), Point( 5, 2 ), Point( 6, 1 ), Point( 6, 5 ), Point( 5, 1 ), },
},
["tags"] = {"sand", "terraformer", },


["pawn1"] = {["type"] = "Terraformer", ["name"] = "", ["id"] = 581, ["mech"] = false, ["offset"] = 0, ["primary"] = "Terraformer_Attack", ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Rust", ["name"] = "Omar Kim", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 3, ["skill2"] = 0, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = false, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,3), ["last_location"] = Point(-1,-1), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 0, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 581, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },
["pawn_count"] = 1, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "R.S.T. Perimeter", },

["region2"] = {["mission"] = "Mission6", ["state"] = 0, ["name"] = "Proving Grounds", },

["region3"] = {["mission"] = "Mission5", ["state"] = 0, ["name"] = "Gamma Trench", },

["region4"] = {["mission"] = "Mission3", ["state"] = 0, ["name"] = "Scorched Earth", },

["region5"] = {["mission"] = "Mission1", ["state"] = 0, ["name"] = "Lone Mesa", },

["region6"] = {["mission"] = "Mission7", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 1, ["iTeamTurn"] = 1, ["iState"] = 0, ["sMission"] = "Mission7", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Lightning_Briefing_CEO_Sand_2", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 3, ["aiDelay"] = 0.000000, ["aiSeed"] = 1002220897, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "any48", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 1 ), ["terrain"] = 7, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 108, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 4 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_power1", ["people1"] = 101, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 1 ), ["terrain"] = 7, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 0, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 0, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 7, },
{["loc"] = Point( 2, 7 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 60, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 3, 0 ), ["terrain"] = 7, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 7, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 62, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 3, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 125, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 7 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 166, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 179, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 3 ), ["terrain"] = 1, ["populated"] = 1, ["grappled"] = 1, ["people1"] = 199, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 4 ), ["terrain"] = 0, ["grapple_targets"] = {0, },
},
{["loc"] = Point( 4, 7 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 1 ), ["terrain"] = 0, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 2 ), ["terrain"] = 0, },
{["loc"] = Point( 6, 4 ), ["terrain"] = 7, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 3, },
},
["pod"] = Point(4,5), ["spawns"] = {"Scarab1", "Firefly1", },
["spawn_ids"] = {585, 586, },
["spawn_points"] = {Point(5,2), Point(6,5), },
["zones"] = {["satellite"] = {Point( 5, 6 ), Point( 6, 6 ), Point( 3, 5 ), Point( 4, 5 ), Point( 2, 5 ), Point( 5, 5 ), Point( 6, 5 ), Point( 6, 4 ), },
},
["tags"] = {"generic", "any_sector", "satellite", "water", "mountain", },


["pawn1"] = {["type"] = "PunchMech", ["name"] = "", ["id"] = 0, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Prime_Punchmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Pinnacle", ["name"] = "Celestine", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 2, ["skill2"] = 1, ["exp"] = 7, ["level"] = 0, ["travel"] = 2, ["final"] = 0, ["starting"] = true, ["last_end"] = 2, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(2,1), ["last_location"] = Point(2,1), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 0, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn2"] = {["type"] = "TankMech", ["name"] = "", ["id"] = 1, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Brute_Tankmech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, 0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Detritus", ["name"] = "Sergei Chavez", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 3, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,1), ["last_location"] = Point(3,1), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 1, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn3"] = {["type"] = "ArtiMech", ["name"] = "", ["id"] = 2, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Ranged_Artillerymech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Archive", ["name"] = "Tatiana Perez", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 2, ["skill2"] = 1, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(2,2), ["last_location"] = Point(2,2), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 2, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn4"] = {["type"] = "Scorpion1", ["name"] = "", ["id"] = 578, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScorpionAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(4,4), ["last_location"] = Point(5,4), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 5, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 4, ["iOwner"] = 578, ["piTarget"] = Point(4,3), ["piOrigin"] = Point(4,4), ["piQueuedShot"] = Point(4,3), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,3), },


["pawn5"] = {["type"] = "Jelly_Regen1", ["name"] = "", ["id"] = 579, ["mech"] = false, ["offset"] = 3, ["not_attacking"] = true, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,2), ["last_location"] = Point(7,2), ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 5, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 4, ["iOwner"] = 579, ["piTarget"] = Point(-2147483647,-2147483647), ["piOrigin"] = Point(7,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn6"] = {["type"] = "Firefly1", ["name"] = "", ["id"] = 580, ["mech"] = false, ["offset"] = 0, ["primary"] = "FireflyAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(5,1), ["last_location"] = Point(5,2), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 5, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iMutation"] = 4, ["iOwner"] = 580, ["piTarget"] = Point(4,1), ["piOrigin"] = Point(5,1), ["piQueuedShot"] = Point(4,1), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(4,1), },
["pawn_count"] = 6, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Geothermal Station", },

["region7"] = {["mission"] = "Mission4", ["state"] = 0, ["name"] = "Tesla Fields", },
["iBattleRegion"] = 6, }
 

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
[50] = "Science_PushBeam", 
[51] = "Support_Boosters", 
[52] = "Support_Smoke", 
[53] = "Support_Refrigerate", 
[54] = "Support_Destruct", 
[55] = "DeploySkill_ShieldTank", 
[56] = "DeploySkill_Tank", 
[57] = "DeploySkill_AcidTank", 
[58] = "DeploySkill_PullTank", 
[59] = "Support_Force", 
[60] = "Support_SmokeDrop", 
[61] = "Support_Missiles", 
[62] = "Support_Wind", 
[63] = "Support_Blizzard", 
[64] = "Passive_FlameImmune", 
[65] = "Passive_Electric", 
[66] = "Passive_Leech", 
[67] = "Passive_MassRepair", 
[68] = "Passive_Defenses", 
[69] = "Passive_Burrows", 
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
[23] = "Science_PushBeam", 
[24] = "Support_Boosters", 
[25] = "Support_Smoke", 
[26] = "Support_Refrigerate", 
[27] = "Support_Destruct", 
[28] = "DeploySkill_ShieldTank", 
[29] = "DeploySkill_Tank", 
[30] = "DeploySkill_AcidTank", 
[31] = "DeploySkill_PullTank", 
[32] = "Support_Force", 
[33] = "Support_SmokeDrop", 
[34] = "Support_Missiles", 
[35] = "Support_Wind", 
[36] = "Support_Blizzard", 
[37] = "Passive_FlameImmune", 
[38] = "Passive_Electric", 
[39] = "Passive_Leech", 
[40] = "Passive_MassRepair", 
[41] = "Passive_Defenses", 
[42] = "Passive_Burrows", 
[43] = "Passive_Psions", 
[44] = "Passive_Boosters", 
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
[1] = "Pilot_Pinnacle", 
[2] = "Pilot_Detritus", 
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
[2] = "Mission_HornetBoss", 
[3] = "Mission_JellyBoss", 
[4] = "Mission_FireflyBoss" 
}, 
["Island"] = 2, 
["Missions"] = { 
[1] = { 
["ID"] = "Mission_Survive", 
["BonusObjs"] = { 
[1] = 5, 
[2] = 1 
}, 
["AssetId"] = "Str_Power" 
}, 
[2] = { 
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
["Jelly_Regen"] = 1, 
["Scorpion"] = 2 
} 
}, 
["LiveEnvironment"] = { 
}, 
["TerraformerId"] = 581, 
["ID"] = "Mission_Terraform", 
["VoiceEvents"] = { 
}, 
["BonusObjs"] = { 
} 
}, 
[3] = { 
["ID"] = "Mission_Force", 
["BonusObjs"] = { 
[1] = 6, 
[2] = 1 
}, 
["DiffMod"] = 2, 
["AssetId"] = "Str_Battery" 
}, 
[4] = { 
["ID"] = "Mission_Train", 
["BonusObjs"] = { 
[1] = 1 
}, 
["DiffMod"] = 2, 
["AssetId"] = "Str_Nimbus" 
}, 
[5] = { 
["ID"] = "Mission_Bomb", 
["BonusObjs"] = { 
} 
}, 
[6] = { 
["ID"] = "Mission_Filler", 
["BonusObjs"] = { 
}, 
["DiffMod"] = 1 
}, 
[7] = { 
["BonusObjs"] = { 
[1] = 6, 
[2] = 1 
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
["Jelly_Regen"] = 1, 
["Scorpion"] = 1, 
["Scarab"] = 1, 
["Firefly"] = 2 
} 
}, 
["LiveEnvironment"] = { 
["StartEffect"] = true, 
["EndEffect"] = true, 
["Locations"] = { 
[1] = Point( 1, 1 ), 
[2] = Point( 3, 4 ), 
[3] = Point( 4, 1 ), 
[4] = Point( 6, 6 ) 
}, 
["Planned"] = { 
[1] = Point( 1, 1 ), 
[2] = Point( 3, 4 ), 
[3] = Point( 4, 1 ), 
[4] = Point( 6, 6 ) 
} 
}, 
["KilledVek"] = 0, 
["AssetLoc"] = Point( 0, 4 ), 
["ID"] = "Mission_Lightning", 
["VoiceEvents"] = { 
}, 
["AssetId"] = "Str_Power", 
["PowerStart"] = 5 
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
[2] = "Hornet", 
[3] = "Firefly", 
[4] = "Jelly_Armor", 
[5] = "Crab", 
[6] = "Burrower", 
["island"] = 1 
}, 
[2] = { 
[1] = "Scorpion", 
[2] = "Scarab", 
[3] = "Firefly", 
[4] = "Jelly_Regen", 
[5] = "Beetle", 
[6] = "Centipede", 
["island"] = 2 
}, 
[3] = { 
[1] = "Scorpion", 
[2] = "Scarab", 
[3] = "Hornet", 
[4] = "Jelly_Health", 
[5] = "Blobber", 
[6] = "Digger", 
["island"] = 3 
}, 
[4] = { 
[1] = "Leaper", 
[2] = "Scarab", 
[3] = "Hornet", 
[4] = "Jelly_Explode", 
[5] = "Spider", 
[6] = "Digger", 
["island"] = 4 
} 
} 
}

 

SquadData = {
["money"] = 0, ["cores"] = 0, ["bIsFavor"] = false, ["repairs"] = 0, ["CorpReward"] = {CreateEffect({weapon = "Prime_Leap",}), CreateEffect({skill1 = "Reactor",skill2 = "Grid",pilot = "Pilot_Miner",}), CreateEffect({power = 2,}), },
["RewardClaimed"] = false, 
["skip_pawns"] = true, 

["storage_size"] = 3, ["CorpStore"] = {CreateEffect({weapon = "Passive_AutoShields",money = -2,}), CreateEffect({weapon = "Support_Repair",money = -2,}), CreateEffect({stock = 0,}), CreateEffect({stock = 0,}), CreateEffect({money = -3,stock = -1,cores = 1,}), CreateEffect({money = -1,power = 1,stock = -1,}), },
["island_store_count"] = 0, ["store_undo_size"] = 0, }
 

