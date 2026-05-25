GameData = {["save_version"] = 1, ["language"] = 1, ["network"] = 6, ["networkMax"] = 7, ["overflow"] = 0, ["seed"] = 2111456759, ["new_enemies"] = 1, ["new_missions"] = 1, ["new_equip"] = 1, ["difficulty"] = 1, ["new_abilities"] = 1, ["ach_info"] = {["squad"] = "Random", ["trackers"] = {["Detritus_B_2"] = 0, ["Global_Challenge_Power"] = 8, ["Archive_A_1"] = 0, ["Archive_B_2"] = 0, ["Rust_A_2"] = 0, ["Rust_A_3"] = 0, ["Pinnacle_A_3"] = 0, ["Archive_B_1"] = 0, ["Pinnacle_B_3"] = 0, ["Detritus_B_1"] = 0, ["Pinnacle_B_1"] = 0, ["Global_Island_Mechs"] = 0, ["Global_Island_Building"] = 0, ["Squad_Mist_1"] = 0, ["Squad_Bomber_2"] = 0, ["Squad_Spiders_1"] = 0, ["Squad_Mist_2"] = 0, ["Squad_Heat_1"] = 0, ["Squad_Cataclysm_1"] = 0, ["Squad_Cataclysm_2"] = 0, ["Squad_Cataclysm_3"] = 0, },
},


["current"] = {["score"] = 4571, ["time"] = 10267819.000000, ["kills"] = 24, ["damage"] = 0, ["failures"] = 4, ["difficulty"] = 1, ["victory"] = false, ["islands"] = 1, ["squad"] = 8, 
["mechs"] = {"WallMech", "ArtiMech", "PulseMech", },
["colors"] = {3, 0, 1, },
["weapons"] = {"Brute_Grapple", "", "Ranged_Artillerymech", "", "Science_Repulse", "", },
["pilot0"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 0, ["exp"] = 50, ["level"] = 2, ["travel"] = 2, ["final"] = 2, ["starting"] = true, ["last_end"] = 1, },
["pilot1"] = {["id"] = "Pilot_Detritus", ["name"] = "Clara Torcasio", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 12, ["skill2"] = 8, ["exp"] = 22, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["pilot2"] = {["id"] = "Pilot_Rust", ["name"] = "Tatiana Kirby", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 8, ["skill2"] = 11, ["exp"] = 20, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
},
["current_squad"] = 8, ["undosave"] = true, }
 

RegionData = {
["sector"] = 1, ["island"] = 0, ["secret"] = false, 
["island0"] = {["corporation"] = "Corp_Grass", ["id"] = 0, ["secured"] = false, },
["island1"] = {["corporation"] = "Corp_Desert", ["id"] = 1, ["secured"] = false, },
["island2"] = {["corporation"] = "Corp_Snow", ["id"] = 2, ["secured"] = true, },
["island3"] = {["corporation"] = "Corp_Factory", ["id"] = 3, ["secured"] = false, },

["turn"] = 0, ["iTower"] = 1, ["quest_tracker"] = 0, ["quest_id"] = 0, ["podRewards"] = {CreateEffect({pilot = "random",cores = 1,}), },


["region0"] = {["mission"] = "Mission1", ["state"] = 0, ["name"] = "Chronology Hall", },

["region1"] = {["mission"] = "", ["state"] = 2, ["name"] = "Corporate HQ", ["objectives"] = {},
},

["region2"] = {["mission"] = "Mission7", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 1, ["iTeamTurn"] = 1, ["iState"] = 0, ["sMission"] = "Mission7", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Artillery_Briefing_CEO_Grass_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 3, ["aiDelay"] = 0.000000, ["aiSeed"] = 1891506297, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "grass8", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 89, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 3 ), ["terrain"] = 4, },
{["loc"] = Point( 1, 4 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 89, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 5 ), ["terrain"] = 0, },
{["loc"] = Point( 1, 6 ), ["terrain"] = 0, },
{["loc"] = Point( 2, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 6, },
{["loc"] = Point( 2, 2 ), ["terrain"] = 0, ["grappled"] = 1, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 88, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 4 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_battery1", ["people1"] = 111, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 201, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 3, 0 ), ["terrain"] = 4, },
{["loc"] = Point( 3, 2 ), ["terrain"] = 0, ["grapple_targets"] = {3, },
},
{["loc"] = Point( 3, 3 ), ["terrain"] = 6, },
{["loc"] = Point( 3, 5 ), ["terrain"] = 0, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 200, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 6 ), ["terrain"] = 6, },
{["loc"] = Point( 4, 7 ), ["terrain"] = 6, },
{["loc"] = Point( 5, 3 ), ["terrain"] = 6, },
{["loc"] = Point( 5, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 222, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 6, 2 ), ["terrain"] = 0, },
{["loc"] = Point( 6, 3 ), ["terrain"] = 4, },
{["loc"] = Point( 6, 5 ), ["terrain"] = 0, },
{["loc"] = Point( 6, 6 ), ["terrain"] = 0, },
{["loc"] = Point( 6, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 3 ), ["terrain"] = 6, },
{["loc"] = Point( 7, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 7, 7 ), ["terrain"] = 3, },
},
["pod"] = Point(5,1), ["spawns"] = {"Scorpion1", "Firefly1", },
["spawn_ids"] = {30, 31, },
["spawn_points"] = {Point(7,2), Point(5,4), },
["zones"] = {},
["tags"] = {"generic", "grass", },


["pawn1"] = {["type"] = "ArchiveArtillery", ["name"] = "", ["id"] = 8, ["mech"] = false, ["offset"] = 0, ["primary"] = "Archive_ArtShot", ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Archive", ["name"] = "Thuy Nguyen", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 13, ["skill2"] = 12, ["exp"] = 0, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = false, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(1,6), ["last_location"] = Point(-1,-1), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 8, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn2"] = {["type"] = "WallMech", ["name"] = "", ["id"] = 0, ["mech"] = true, ["offset"] = 3, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Brute_Grapple", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Original", ["name"] = "Ralph Karlsson", ["name_id"] = "Pilot_Original_Name", ["renamed"] = false, ["skill1"] = 1, ["skill2"] = 0, ["exp"] = 50, ["level"] = 2, ["travel"] = 2, ["final"] = 2, ["starting"] = true, ["last_end"] = 1, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 5, ["max_health"] = 5, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,5), ["last_location"] = Point(6,3), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 0, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn3"] = {["type"] = "ArtiMech", ["name"] = "", ["id"] = 1, ["mech"] = true, ["offset"] = 0, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Ranged_Artillerymech", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Detritus", ["name"] = "Clara Torcasio", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 12, ["skill2"] = 8, ["exp"] = 22, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 2, ["max_health"] = 2, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(2,2), ["last_location"] = Point(6,3), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 1, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn4"] = {["type"] = "PulseMech", ["name"] = "", ["id"] = 2, ["mech"] = true, ["offset"] = 1, 
["reactor"] = {["iNormalPower"] = 0, ["iUsedPower"] = 0, ["iBonusPower"] = 0, ["iUsedBonus"] = 0, ["iUndoPower"] = 0, ["iUsedUndo"] = 0, },
["movePower"] = {0, },
["healthPower"] = {0, },
["primary"] = "Science_Repulse", ["primary_power"] = {},
["primary_power_class"] = false, ["primary_mod1"] = {0, },
["primary_mod2"] = {0, 0, },
["primary_damaged"] = false, ["primary_starting"] = true, ["primary_uses"] = 1, ["pilot"] = {["id"] = "Pilot_Rust", ["name"] = "Tatiana Kirby", ["name_id"] = "", ["renamed"] = false, ["skill1"] = 8, ["skill2"] = 11, ["exp"] = 20, ["level"] = 0, ["travel"] = 0, ["final"] = 0, ["starting"] = true, },
["iTeamId"] = 1, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = true, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(1,5), ["last_location"] = Point(6,3), ["bActive"] = true, ["iCurrentWeapon"] = 0, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 4, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 2, ["piTarget"] = Point(-1,-1), ["piOrigin"] = Point(-1,-1), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(-1,-1), },


["pawn5"] = {["type"] = "Firefly2", ["name"] = "", ["id"] = 9, ["mech"] = false, ["offset"] = 1, ["primary"] = "FireflyAtk2", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 5, ["max_health"] = 5, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,5), ["last_location"] = Point(7,5), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 5, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 9, ["piTarget"] = Point(5,5), ["piOrigin"] = Point(6,5), ["piQueuedShot"] = Point(5,5), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,5), },


["pawn6"] = {["type"] = "Scorpion1", ["name"] = "", ["id"] = 10, ["mech"] = false, ["offset"] = 0, ["primary"] = "ScorpionAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(3,2), ["last_location"] = Point(4,2), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 5, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 10, ["piTarget"] = Point(2,2), ["piOrigin"] = Point(3,2), ["piQueuedShot"] = Point(2,2), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(2,2), },


["pawn7"] = {["type"] = "Shaman1", ["name"] = "", ["id"] = 11, ["mech"] = false, ["offset"] = 0, ["not_attacking"] = true, ["primary"] = "ShamanAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 3, ["max_health"] = 3, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,2), ["last_location"] = Point(7,2), ["iCurrentWeapon"] = 1, ["iTurnCount"] = 1, ["iTurnsRemaining"] = 5, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 11, ["piTarget"] = Point(6,6), ["piOrigin"] = Point(6,2), ["piQueuedShot"] = Point(-1,-1), ["iQueuedSkill"] = -1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(6,6), },


["pawn8"] = {["type"] = "Totem1", ["name"] = "", ["id"] = 29, ["mech"] = false, ["offset"] = 0, ["owner"] = 11, ["primary"] = "TotemAtk1", ["primary_uses"] = 1, ["iTeamId"] = 6, ["timebonus"] = false, ["iFaction"] = 0, ["iKills"] = 0, ["is_corpse"] = false, ["health"] = 1, ["max_health"] = 1, ["undo_state"] = {["health"] = 5, ["max_health"] = 5, },
["undo_ready"] = false, ["undo_point"] = Point(-1,-1), ["iMissionDamage"] = 0, ["location"] = Point(6,6), ["last_location"] = Point(6,6), ["bMinor"] = true, ["iCurrentWeapon"] = 1, ["iTurnCount"] = 0, ["iTurnsRemaining"] = 0, ["undoPosition"] = Point(-1,-1), ["undoReady"] = false, ["iKillCount"] = 0, ["iOwner"] = 29, ["piTarget"] = Point(5,6), ["piOrigin"] = Point(6,6), ["piQueuedShot"] = Point(5,6), ["iQueuedSkill"] = 1, ["priorityTarget"] = Point(-1,-1), ["targetHistory"] = Point(5,6), },
["pawn_count"] = 8, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Artifact Vaults", },

["region3"] = {["mission"] = "Mission2", ["player"] = {["battle_type"] = 0, ["iCurrentTurn"] = 0, ["iTeamTurn"] = 1, ["iState"] = 4, ["sMission"] = "Mission2", ["iMissionType"] = 0, ["sBriefingMessage"] = "Mission_Mines_Briefing_CEO_Grass_1", ["podReward"] = CreateEffect({}), ["secret"] = false, ["spawn_needed"] = false, ["env_time"] = 1000, ["actions"] = 0, ["iUndoTurn"] = 1, ["aiState"] = 0, ["aiDelay"] = 0.000000, ["aiSeed"] = 916705328, ["victory"] = 2, ["undo_pawns"] = {},


["map_data"] = {["version"] = 7, ["dimensions"] = Point( 8, 8 ), ["name"] = "anyAE36", ["enemy_kills"] = 0, 
["map"] = {{["loc"] = Point( 0, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 1 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 2 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 3 ), ["terrain"] = 4, },
{["loc"] = Point( 0, 5 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 6 ), ["terrain"] = 3, },
{["loc"] = Point( 0, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 1, 0 ), ["terrain"] = 3, },
{["loc"] = Point( 1, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 87, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 3 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 86, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 1, 5 ), ["terrain"] = 6, },
{["loc"] = Point( 1, 7 ), ["terrain"] = 3, },
{["loc"] = Point( 2, 1 ), ["terrain"] = 6, },
{["loc"] = Point( 2, 3 ), ["terrain"] = 0, ["item"] = "Item_Mine", },
{["loc"] = Point( 2, 5 ), ["terrain"] = 1, ["populated"] = 1, ["unique"] = "str_power1", ["people1"] = 113, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 2, 6 ), ["terrain"] = 4, },
{["loc"] = Point( 3, 1 ), ["terrain"] = 0, ["item"] = "Item_Mine", },
{["loc"] = Point( 3, 2 ), ["terrain"] = 0, ["item"] = "Item_Mine", },
{["loc"] = Point( 3, 3 ), ["terrain"] = 0, ["item"] = "Item_Mine", },
{["loc"] = Point( 3, 4 ), ["terrain"] = 6, },
{["loc"] = Point( 3, 5 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 82, ["people2"] = 0, ["health_max"] = 1, },
{["loc"] = Point( 3, 6 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 195, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 1 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 199, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 4, 2 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 1 ), ["terrain"] = 4, },
{["loc"] = Point( 5, 2 ), ["terrain"] = 1, ["populated"] = 1, ["people1"] = 238, ["people2"] = 0, ["health_max"] = 2, },
{["loc"] = Point( 5, 3 ), ["terrain"] = 0, ["item"] = "Item_Mine", },
{["loc"] = Point( 5, 4 ), ["terrain"] = 6, },
{["loc"] = Point( 5, 7 ), ["terrain"] = 6, },
{["loc"] = Point( 6, 1 ), ["terrain"] = 0, ["item"] = "Item_Mine", },
{["loc"] = Point( 6, 2 ), ["terrain"] = 0, ["item"] = "Item_Mine", },
{["loc"] = Point( 6, 3 ), ["terrain"] = 0, ["item"] = "Item_Mine", },
{["loc"] = Point( 7, 0 ), ["terrain"] = 6, },
},
["spawns"] = {"Firefly1", "Shaman1", "Scorpion1", "Firefly1", },
["spawn_ids"] = {12, 13, 14, 15, },
["spawn_points"] = {Point(5,5), Point(6,4), Point(7,5), Point(7,2), },
["zones"] = {},
["tags"] = {"generic", "any_sector", },
["pawn_count"] = 0, ["blocked_points"] = {},
["blocked_type"] = {},
},


},
["state"] = 1, ["name"] = "Colonial Park", },

["region4"] = {["mission"] = "Mission3", ["state"] = 0, ["name"] = "Safeguard Valley", },

["region5"] = {["mission"] = "Mission6", ["state"] = 0, ["name"] = "Old Earth Park", },

["region6"] = {["mission"] = "Mission4", ["state"] = 0, ["name"] = "Storage Vaults", },

["region7"] = {["mission"] = "Mission5", ["state"] = 0, ["name"] = "Martial District", },
["iBattleRegion"] = 2, }
 

GAME = { 
["WeaponDeck"] = { 
[31] = "Ranged_ScatterShot", 
[2] = "Prime_Lightning", 
[8] = "Prime_Shift", 
[32] = "Ranged_BackShot", 
[33] = "Ranged_Ice", 
[34] = "Ranged_SmokeBlast", 
[35] = "Ranged_Fireball", 
[9] = "Prime_Flamethrower", 
[36] = "Ranged_RainingVolley", 
[37] = "Ranged_Wide", 
[38] = "Ranged_Dual", 
[39] = "Science_Pullmech", 
[10] = "Prime_Areablast", 
[40] = "Science_Swap", 
[41] = "Science_AcidShot", 
[42] = "Science_Confuse", 
[43] = "Science_SmokeDefense", 
[11] = "Prime_Spear", 
[44] = "Science_Shield", 
[45] = "Science_FireBeam", 
[46] = "Science_FreezeBeam", 
[3] = "Prime_Lasermech", 
[12] = "Prime_Leap", 
[48] = "Science_PushBeam", 
[67] = "Passive_AutoShields", 
[49] = "Support_Boosters", 
[79] = "Prime_KO_Crack", 
[50] = "Support_Smoke", 
[71] = "Passive_FriendlyFire", 
[51] = "Support_Refrigerate", 
[13] = "Prime_SpinFist", 
[52] = "Support_Destruct", 
[22] = "Brute_Unstable", 
[53] = "DeploySkill_ShieldTank", 
[91] = "Ranged_TC_BounceShot", 
[54] = "DeploySkill_Tank", 
[94] = "Science_RainingFire", 
[55] = "DeploySkill_PullTank", 
[14] = "Prime_Sword", 
[56] = "Support_Force", 
[24] = "Brute_Splitshot", 
[57] = "Support_SmokeDrop", 
[103] = "Support_GridDefense", 
[58] = "Support_Repair", 
[107] = "Passive_HealingSmoke", 
[59] = "Support_Missiles", 
[15] = "Brute_Tankmech", 
[60] = "Support_Wind", 
[61] = "Passive_FlameImmune", 
[62] = "Passive_Electric", 
[1] = "Prime_Punchmech", 
[4] = "Prime_ShieldBash", 
[16] = "Brute_Jetmech", 
[64] = "Passive_MassRepair", 
[65] = "Passive_Defenses", 
[66] = "Passive_Burrows", 
[17] = "Brute_Mirrorshot", 
[68] = "Passive_Psions", 
[69] = "Passive_Boosters", 
[70] = "Passive_Medical", 
[18] = "Brute_PhaseShot", 
[72] = "Passive_CritDefense", 
[73] = "Prime_Flamespreader", 
[74] = "Prime_WayTooBig", 
[19] = "Brute_Shrapnel", 
[76] = "Prime_TC_Punt", 
[77] = "Prime_TC_BendBeam", 
[5] = "Prime_Rockmech", 
[20] = "Brute_Shockblast", 
[80] = "Brute_KickBack", 
[81] = "Brute_Fracture", 
[82] = "Brute_PierceShot", 
[83] = "Brute_TC_GuidedMissile", 
[84] = "Brute_TC_Ricochet", 
[85] = "Brute_TC_DoubleShot", 
[86] = "Brute_KO_Combo", 
[87] = "Ranged_Crack", 
[88] = "Ranged_DeployBomb", 
[89] = "Ranged_Arachnoid", 
[90] = "Ranged_SmokeFire", 
[23] = "Brute_Heavyrocket", 
[92] = "Ranged_TC_DoubleArt", 
[93] = "Ranged_KO_Combo", 
[6] = "Prime_RightHook", 
[95] = "Science_MassShift", 
[96] = "Science_TelePush", 
[97] = "Science_Placer", 
[98] = "Science_TC_Control", 
[99] = "Science_TC_Enrage", 
[100] = "Science_TC_SwapOther", 
[101] = "Science_KO_Crack", 
[102] = "Support_Confuse", 
[26] = "Brute_Sonic", 
[104] = "Support_Waterdrill", 
[105] = "Support_TC_GridAtk", 
[106] = "Support_TC_Bombline", 
[27] = "Ranged_Rockthrow", 
[108] = "Passive_FireBoost", 
[109] = "Passive_PlayerTurnShield", 
[7] = "Prime_RocketPunch", 
[28] = "Ranged_Defensestrike", 
[25] = "Brute_Bombrun", 
[29] = "Ranged_Rocket", 
[21] = "Brute_Beetle", 
[78] = "Prime_TC_Feint", 
[75] = "Prime_PrismLaser", 
[30] = "Ranged_Ignite", 
[63] = "Passive_Leech", 
[47] = "Science_LocalShield" 
}, 
["PodWeaponDeck"] = { 
[31] = "Support_Repair", 
[2] = "Prime_Spear", 
[8] = "Brute_Heavyrocket", 
[32] = "Support_Missiles", 
[33] = "Support_Wind", 
[34] = "Passive_FlameImmune", 
[35] = "Passive_Electric", 
[9] = "Brute_Bombrun", 
[36] = "Passive_Leech", 
[37] = "Passive_MassRepair", 
[38] = "Passive_Defenses", 
[39] = "Passive_Burrows", 
[10] = "Brute_Sonic", 
[40] = "Passive_AutoShields", 
[41] = "Passive_Psions", 
[42] = "Passive_Boosters", 
[43] = "Passive_Medical", 
[11] = "Ranged_Ice", 
[44] = "Passive_FriendlyFire", 
[45] = "Passive_CritDefense", 
[46] = "Prime_WayTooBig", 
[3] = "Prime_Leap", 
[12] = "Ranged_SmokeBlast", 
[48] = "Prime_TC_BendBeam", 
[49] = "Prime_TC_Feint", 
[50] = "Brute_Fracture", 
[51] = "Brute_TC_GuidedMissile", 
[13] = "Ranged_Fireball", 
[52] = "Brute_KO_Combo", 
[53] = "Ranged_TC_BounceShot", 
[54] = "Ranged_TC_DoubleArt", 
[55] = "Ranged_KO_Combo", 
[14] = "Ranged_RainingVolley", 
[56] = "Science_TelePush", 
[57] = "Science_Placer", 
[58] = "Science_TC_Enrage", 
[59] = "Support_Confuse", 
[15] = "Ranged_Dual", 
[60] = "Support_GridDefense", 
[61] = "Support_Waterdrill", 
[62] = "Support_TC_GridAtk", 
[1] = "Prime_Areablast", 
[4] = "Prime_SpinFist", 
[16] = "Science_SmokeDefense", 
[64] = "Passive_HealingSmoke", 
[65] = "Passive_FireBoost", 
[66] = "Passive_PlayerTurnShield", 
[17] = "Science_Shield", 
[18] = "Science_FireBeam", 
[19] = "Science_FreezeBeam", 
[5] = "Prime_Sword", 
[20] = "Science_LocalShield", 
[21] = "Science_PushBeam", 
[22] = "Support_Boosters", 
[23] = "Support_Smoke", 
[6] = "Brute_Shockblast", 
[24] = "Support_Refrigerate", 
[25] = "Support_Destruct", 
[26] = "DeploySkill_ShieldTank", 
[27] = "DeploySkill_Tank", 
[7] = "Brute_Beetle", 
[28] = "DeploySkill_PullTank", 
[29] = "Support_Force", 
[30] = "Support_SmokeDrop", 
[63] = "Support_TC_Bombline", 
[47] = "Prime_PrismLaser" 
}, 
["PilotDeck"] = { 
[13] = "Pilot_Arrogant", 
[7] = "Pilot_Genius", 
[1] = "Pilot_Soldier", 
[2] = "Pilot_Youth", 
[4] = "Pilot_Aquatic", 
[8] = "Pilot_Miner", 
[9] = "Pilot_Recycler", 
[5] = "Pilot_Medic", 
[10] = "Pilot_Assassin", 
[3] = "Pilot_Warrior", 
[11] = "Pilot_Leader", 
[6] = "Pilot_Hotshot", 
[12] = "Pilot_Repairman", 
[14] = "Pilot_Delusional" 
}, 
["SeenPilots"] = { 
[1] = "Pilot_Original", 
[2] = "Pilot_Detritus", 
[3] = "Pilot_Rust", 
[4] = "Pilot_Caretaker", 
[5] = "Pilot_Chemical" 
}, 
["PodDeck"] = { 
[7] = { 
["cores"] = 1, 
["pilot"] = "random" 
}, 
[1] = { 
["cores"] = 1 
}, 
[2] = { 
["cores"] = 1 
}, 
[4] = { 
["cores"] = 1, 
["weapon"] = "random" 
}, 
[8] = { 
["cores"] = 1, 
["pilot"] = "random" 
}, 
[5] = { 
["cores"] = 1, 
["weapon"] = "random" 
}, 
[3] = { 
["cores"] = 1 
}, 
[6] = { 
["cores"] = 1, 
["weapon"] = "random" 
} 
}, 
["Bosses"] = { 
[1] = "Mission_BouncerBoss", 
[2] = "Mission_BurnbugBoss", 
[4] = "Mission_MosquitoBoss", 
[3] = "Mission_CrabBoss" 
}, 
["Enemies"] = { 
[1] = { 
[6] = "Dung", 
[2] = "Firefly", 
[3] = "Scorpion", 
[1] = "Hornet", 
[4] = "Jelly_Armor", 
[5] = "Shaman", 
["island"] = 1 
}, 
[2] = { 
[6] = "Spider", 
[2] = "Burnbug", 
[3] = "Bouncer", 
[1] = "Scarab", 
[4] = "Jelly_Regen", 
[5] = "Burrower", 
["island"] = 2 
}, 
[4] = { 
[6] = "Blobber", 
[2] = "Scarab", 
[3] = "Scorpion", 
[1] = "Bouncer", 
[4] = "Jelly_Health", 
[5] = "Beetle", 
["island"] = 4 
}, 
[3] = { 
[6] = "Centipede", 
[2] = "Moth", 
[3] = "Burnbug", 
[1] = "Leaper", 
[4] = "Jelly_Boost", 
[5] = "Starfish", 
["island"] = 3 
} 
}, 
["Missions"] = { 
[1] = { 
["ID"] = "Mission_Tanks", 
["BonusObjs"] = { 
[1] = 1 
}, 
["DiffMod"] = 2, 
["AssetId"] = "Str_Robotics" 
}, 
[2] = { 
["BonusObjs"] = { 
[1] = 8, 
[2] = 1 
}, 
["MineLocations"] = { 
[1] = Point( 2, 3 ), 
[2] = Point( 5, 3 ), 
[3] = Point( 3, 1 ), 
[4] = Point( 6, 3 ), 
[5] = Point( 3, 3 ), 
[6] = Point( 3, 2 ), 
[7] = Point( 6, 2 ), 
[8] = Point( 6, 1 ) 
}, 
["Spawner"] = { 
["used_bosses"] = 0, 
["num_spawns"] = 4, 
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
["Shaman"] = 1, 
["Firefly"] = 2, 
["Scorpion"] = 1, 
["Dung"] = 5, 
["Jelly_Explode"] = 5 
} 
}, 
["LiveEnvironment"] = { 
}, 
["AssetLoc"] = Point( 2, 5 ), 
["ID"] = "Mission_Mines", 
["VoiceEvents"] = { 
}, 
["MineCount"] = 8, 
["AssetId"] = "Str_Power" 
}, 
[3] = { 
["ID"] = "Mission_Dam", 
["BonusObjs"] = { 
}, 
["DiffMod"] = 1 
}, 
[4] = { 
["ID"] = "Mission_Repair", 
["BonusObjs"] = { 
[1] = 9, 
[2] = 1 
}, 
["DiffMod"] = 2, 
["AssetId"] = "Str_Power" 
}, 
[5] = { 
["ID"] = "Mission_Survive", 
["BonusObjs"] = { 
[1] = 5, 
[2] = 1 
}, 
["AssetId"] = "Str_Nimbus" 
}, 
[6] = { 
["ID"] = "Mission_Train", 
["BonusObjs"] = { 
} 
}, 
[7] = { 
["BonusObjs"] = { 
[1] = 1 
}, 
["ArtilleryId"] = 8, 
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
["Firefly"] = 2, 
["Scorpion"] = 2, 
["Shaman"] = 1 
} 
}, 
["LiveEnvironment"] = { 
}, 
["AssetLoc"] = Point( 2, 4 ), 
["ID"] = "Mission_Artillery", 
["VoiceEvents"] = { 
}, 
["AssetId"] = "Str_Battery", 
["PowerStart"] = 6 
}, 
[8] = { 
["ID"] = "Mission_BouncerBoss", 
["BonusObjs"] = { 
[1] = 1 
}, 
["AssetId"] = "Str_Tower" 
} 
}, 
["Island"] = 1 
}

 

SquadData = {
["money"] = 0, ["cores"] = 1, ["bIsFavor"] = false, ["repairs"] = 0, ["CorpReward"] = {CreateEffect({weapon = "Support_KO_GridCharger",}), CreateEffect({skill1 = "Grid",skill2 = "Move",pilot = "Pilot_Chemical",}), CreateEffect({power = 2,}), },
["RewardClaimed"] = false, 
["skip_pawns"] = true, 

["storage_size"] = 4, ["storage_3"] = {["weapon"] = "Passive_VoidShock", },
["CorpStore"] = {CreateEffect({weapon = "DeploySkill_AcidTank",money = -2,}), CreateEffect({weapon = "Science_Gravwell",money = -2,}), CreateEffect({weapon = "Brute_Sniper",money = -2,}), CreateEffect({stock = 0,}), CreateEffect({money = -3,stock = -1,cores = 1,}), CreateEffect({money = -1,power = 1,stock = -1,}), },
["island_store_count"] = 1, ["store_undo_size"] = 0, }
 

