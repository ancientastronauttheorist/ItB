-- Generated data-only ITB Observatory RNG trial capsule.
return {
  ["arm_packet_sha256"] = "6599c1d4e16efa80d433ec37b60d3f1e70ab44364af7181690e33397705f303b",
  ["capture_track"] = "owner_local_modified",
  ["expected_save"] = {
    ["ai_seed"] = 21843,
    ["master_seed"] = 664577925,
    ["mission_id"] = "Mission_Power",
    ["mission_slot"] = "Mission2",
    ["region_id"] = "region1",
    ["turn"] = 1
  },
  ["kind"] = "observatory_rng_trial_capsule",
  ["packet"] = {
    ["arm_packet_schema_version"] = 1,
    ["build_identity"] = {
      ["architecture"] = "x86",
      ["build_evidence"] = "local_appmanifest",
      ["build_id"] = "13725832",
      ["depot_manifest"] = "8335438558621014449",
      ["executable_sha256"] = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9",
      ["maps_revision_sha256"] = "a16ed060190402ab83d5968c000917c9979944dd11beb154329ba002cfcb28d4",
      ["platform"] = "windows",
      ["scripts_revision_sha256"] = "591315057e493d11b029ed669bc7eb1d02ae49d14cdca4bcdc640acfa5421155"
    },
    ["hook_plan"] = {
      {
        ["event_kind"] = "enemy_action_selected",
        ["hook_id"] = "rng_trial.enemy_action_selected",
        ["source_sha256"] = "a7c5bf375245ba058d59d3c92b73557b3620be4bf4bfae586acd36b59da3f2b3",
        ["status"] = "disabled",
        ["target"] = "catalog.native.enemy_action_selected",
        ["target_kind"] = "native_boundary"
      },
      {
        ["event_kind"] = "enemy_candidate",
        ["hook_id"] = "rng_trial.enemy_candidate",
        ["source_sha256"] = "a7c5bf375245ba058d59d3c92b73557b3620be4bf4bfae586acd36b59da3f2b3",
        ["status"] = "disabled",
        ["target"] = "catalog.native.enemy_candidate",
        ["target_kind"] = "native_boundary"
      },
      {
        ["event_kind"] = "enemy_target_score",
        ["hook_id"] = "rng_trial.enemy_target_score",
        ["source_sha256"] = "4b52b7ec48702ffafe90ac2db22c644fe270941fae0b211f0548411cc02077fb",
        ["status"] = "disabled",
        ["target"] = "catalog.callback.enemy_target_score",
        ["target_kind"] = "lua_method"
      },
      {
        ["event_kind"] = "get_skill_effect",
        ["hook_id"] = "rng_trial.get_skill_effect",
        ["source_sha256"] = "4b52b7ec48702ffafe90ac2db22c644fe270941fae0b211f0548411cc02077fb",
        ["status"] = "disabled",
        ["target"] = "catalog.callback.get_skill_effect",
        ["target_kind"] = "lua_method"
      },
      {
        ["event_kind"] = "get_target_area",
        ["hook_id"] = "rng_trial.get_target_area",
        ["source_sha256"] = "4b52b7ec48702ffafe90ac2db22c644fe270941fae0b211f0548411cc02077fb",
        ["status"] = "disabled",
        ["target"] = "catalog.callback.get_target_area",
        ["target_kind"] = "lua_method"
      },
      {
        ["event_kind"] = "random_bool",
        ["hook_id"] = "rng_trial.random_bool",
        ["source_sha256"] = "36a123e309bae6a3460ab9397d03bb7db7731c3cc0a00c23821dcdf4f5d316ea",
        ["status"] = "installed",
        ["target"] = "_G.random_bool",
        ["target_kind"] = "lua_global"
      },
      {
        ["event_kind"] = "random_int",
        ["hook_id"] = "rng_trial.random_int",
        ["source_sha256"] = "76e4d6f1289067724a2b6a8348ef91cb772a9bb12f6debf07b66efc11a6dd70e",
        ["status"] = "disabled",
        ["target"] = "_G.random_int",
        ["target_kind"] = "lua_global"
      },
      {
        ["event_kind"] = "score_positioning",
        ["hook_id"] = "rng_trial.score_positioning",
        ["source_sha256"] = "4b52b7ec48702ffafe90ac2db22c644fe270941fae0b211f0548411cc02077fb",
        ["status"] = "disabled",
        ["target"] = "catalog.callback.score_positioning",
        ["target_kind"] = "lua_method"
      }
    },
    ["manifest"] = {
      ["activated_epoch"] = 1787361949,
      ["ai_seed_fingerprint"] = "5d1d0ff2a35142705684bc04b87a7e3d2ef1e74900764ecbf633cf3b462257e3",
      ["allowed_kinds"] = {
        "random_bool"
      },
      ["arm_nonce"] = "09af57f25a660b766eac047946da15bd",
      ["build_identity_sha256"] = "e3e93229f5e216a397088f11051aa6c8e3763b0aa70cd05552c4717e8696dd11",
      ["capture_id"] = "owner-rng-bool-pair-012",
      ["checkpoint_seq"] = 0,
      ["config_sha256"] = "bc404fb4829c6aed31623b4500f85693c7befa4b497e2ce54f2d534966e88e98",
      ["controller_sha256"] = "938ad7e4f1e6bc965a2227de172b07f76a90d7245fe0430848ecbd39609e801e",
      ["controller_version"] = "observatory-controller/1",
      ["expected_mission_id"] = "Mission_Power",
      ["expected_phase"] = "combat_enemy",
      ["expected_turn"] = 1,
      ["expires_epoch"] = 1787362849,
      ["hook_coverage_sha256"] = "071e43410cf2aba9f18f8e28f69d9028d6852079dc5dc01a8cce4a0727f05556",
      ["installed_modloader_sha256"] = "42aa51721abd911630e9ae966d195dbcee399f9e889a0a9ff1eef94df7e33a82",
      ["master_seed"] = 664577925,
      ["max_attempts"] = 8,
      ["max_bundle_bytes"] = 3145728,
      ["max_event_bytes"] = 4096,
      ["max_events"] = 8,
      ["max_events_per_turn"] = 8,
      ["max_total_event_bytes"] = 65536,
      ["region_id"] = "region1",
      ["schema_version"] = 1,
      ["timeline_fingerprint"] = "ca305830ca471c3d5f1501bb8750a7d076283752bde39a66f637717e7f04eae5"
    },
    ["policy"] = {
      ["allowed_kinds"] = {
        "random_bool"
      },
      ["expected_phase"] = "combat_enemy",
      ["max_attempts"] = 8,
      ["max_bundle_bytes"] = 3145728,
      ["max_event_bytes"] = 4096,
      ["max_events"] = 8,
      ["max_events_per_turn"] = 8,
      ["max_total_event_bytes"] = 65536
    },
    ["trusted"] = {
      ["build_identity_sha256"] = "e3e93229f5e216a397088f11051aa6c8e3763b0aa70cd05552c4717e8696dd11",
      ["config_sha256"] = "bc404fb4829c6aed31623b4500f85693c7befa4b497e2ce54f2d534966e88e98",
      ["controller_sha256"] = "938ad7e4f1e6bc965a2227de172b07f76a90d7245fe0430848ecbd39609e801e",
      ["hook_coverage_sha256"] = "071e43410cf2aba9f18f8e28f69d9028d6852079dc5dc01a8cce4a0727f05556",
      ["installed_modloader_sha256"] = "42aa51721abd911630e9ae966d195dbcee399f9e889a0a9ff1eef94df7e33a82"
    }
  },
  ["probe"] = {
    ["argument"] = 2,
    ["kind"] = "random_bool"
  },
  ["rng_control"] = {
    ["architecture"] = "x86",
    ["build_id"] = "13725832",
    ["executable_sha256"] = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9",
    ["expected_result"] = true,
    ["helper_sha256"] = "bd6501c701b8c5f21dbaec309573ab654c7cf01a5705423e2c0ee554dd0e2787",
    ["helper_version"] = "observatory-rng-seed-helper/1",
    ["kind"] = "build_keyed_seed",
    ["rng_seed_region_sha256"] = "67b19fe39627674ef04d07bd86e989a39ce744be2e93f9265c16e2aeb928cf9d",
    ["rng_seed_rva"] = "0x00387f37",
    ["seed"] = 324508639
  },
  ["schema_version"] = 2
}
